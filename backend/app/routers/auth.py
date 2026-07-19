"""Authentication endpoints and the shared authenticated-user dependency."""
from __future__ import annotations

import datetime
import hashlib
import hmac
import os
import re
import secrets
import sqlite3
from typing import Optional
from uuid import uuid4

import jwt
from fastapi import APIRouter, Depends, Header, HTTPException, Request, Response, status
from pydantic import BaseModel, ConfigDict, Field, field_validator

from ..config import settings
from ..db import get_db_connection
from ..security import rate_limit, require_csrf


router = APIRouter(prefix="/api/auth", tags=["auth"])
ALGORITHM = "HS256"
PBKDF2_ITERATIONS = 600_000
LEGACY_PBKDF2_ITERATIONS = 100_000
USERNAME_RE = re.compile(r"^[A-Za-z0-9_.-]+$")
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _jwt_secret() -> str:
    secret = settings.jwt_secret_key.strip()
    if len(secret) < 32:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Authentication is temporarily unavailable because the server secret is not configured.",
        )
    return secret


class UserRegister(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    username: str = Field(..., min_length=3, max_length=20)
    email: str = Field(..., min_length=5, max_length=254)
    password: str = Field(..., min_length=8, max_length=128)

    @field_validator("username")
    @classmethod
    def valid_username(cls, value: str) -> str:
        if not USERNAME_RE.fullmatch(value):
            raise ValueError("Username may contain only letters, numbers, dots, underscores and hyphens")
        return value

class UserLogin(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    username_or_email: str = Field(..., min_length=3, max_length=254)
    password: str = Field(..., min_length=1, max_length=128)


class ForgotPasswordRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    username_or_email: str = Field(..., min_length=3, max_length=254)


class ResetPasswordRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    username_or_email: str = Field(..., min_length=3, max_length=254)
    recovery_code: str = Field(..., min_length=20, max_length=80)
    new_password: str = Field(..., min_length=8, max_length=128)


def hash_password(password: str) -> str:
    """Create a versioned PBKDF2-HMAC-SHA256 hash with a unique salt."""
    salt = os.urandom(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, PBKDF2_ITERATIONS)
    return f"pbkdf2_sha256${PBKDF2_ITERATIONS}${salt.hex()}${digest.hex()}"


def _hash_parts(hashed: str) -> tuple[int, bytes, str]:
    if hashed.startswith("pbkdf2_sha256$"):
        algorithm, iterations, salt_hex, digest_hex = hashed.split("$", 3)
        if algorithm != "pbkdf2_sha256":
            raise ValueError("Unsupported password hash")
        return int(iterations), bytes.fromhex(salt_hex), digest_hex
    # Backward-compatible verification for accounts created by older WCAI builds.
    salt_hex, digest_hex = hashed.split(":", 1)
    return LEGACY_PBKDF2_ITERATIONS, bytes.fromhex(salt_hex), digest_hex


def verify_password(password: str, hashed: str) -> bool:
    try:
        iterations, salt, expected = _hash_parts(hashed)
        if iterations < 50_000 or iterations > 2_000_000:
            return False
        digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
        return hmac.compare_digest(digest.hex(), expected)
    except (TypeError, ValueError):
        return False


def password_needs_rehash(hashed: str) -> bool:
    try:
        iterations, _, _ = _hash_parts(hashed)
        return not hashed.startswith("pbkdf2_sha256$") or iterations < PBKDF2_ITERATIONS
    except (TypeError, ValueError):
        return True


_DUMMY_PASSWORD_HASH = hash_password("WCAI-Dummy-Password-Only-1")


def validate_password_strength(password: str) -> bool:
    return bool(
        len(password) >= 8
        and len(password) <= 128
        and re.search(r"[A-Z]", password)
        and re.search(r"[a-z]", password)
        and re.search(r"[0-9]", password)
    )


def validate_email_format(email: str) -> bool:
    return len(email) <= 254 and bool(EMAIL_RE.fullmatch(email))


def create_token(user_id: int, username: str, token_version: int = 0) -> str:
    now = datetime.datetime.now(datetime.timezone.utc)
    expires = now + datetime.timedelta(minutes=max(15, min(settings.jwt_expire_minutes, 1440)))
    payload = {
        "sub": str(user_id),
        "user_id": user_id,
        "username": username,
        "ver": token_version,
        "iss": settings.jwt_issuer,
        "aud": settings.jwt_audience,
        "iat": now,
        "nbf": now,
        "exp": expires,
        "jti": uuid4().hex,
    }
    return jwt.encode(payload, _jwt_secret(), algorithm=ALGORITHM)


def decode_token(token: str) -> dict:
    try:
        if token.startswith("Bearer "):
            token = token.removeprefix("Bearer ").strip()
        if not token or len(token) > 4096:
            raise jwt.InvalidTokenError("Invalid token length")
        return jwt.decode(
            token,
            _jwt_secret(),
            algorithms=[ALGORITHM],
            issuer=settings.jwt_issuer,
            audience=settings.jwt_audience,
            options={"require": ["sub", "exp", "iat", "nbf", "iss", "aud", "jti", "ver"]},
        )
    except jwt.ExpiredSignatureError as error:
        raise HTTPException(status_code=401, detail="Session has expired. Please log in again.") from error
    except jwt.InvalidTokenError as error:
        raise HTTPException(status_code=401, detail="Invalid authentication token.") from error


def get_current_user_id(
    request: Request,
    authorization: Optional[str] = Header(None),
) -> int:
    """Authenticate a bearer client or an HttpOnly-cookie browser session."""
    token: Optional[str] = None
    cookie_authenticated = False
    if authorization:
        if not authorization.startswith("Bearer "):
            raise HTTPException(status_code=401, detail="Invalid authorization scheme.")
        token = authorization.removeprefix("Bearer ").strip()
    else:
        token = request.cookies.get(settings.auth_cookie_name)
        cookie_authenticated = bool(token)
    if not token:
        raise HTTPException(status_code=401, detail="Authentication is required.")
    if cookie_authenticated:
        require_csrf(request, settings.csrf_cookie_name)

    payload = decode_token(token)
    try:
        user_id = int(payload["sub"])
    except (KeyError, TypeError, ValueError) as error:
        raise HTTPException(status_code=401, detail="Invalid authentication token.") from error

    conn = get_db_connection()
    try:
        row = conn.execute(
            "SELECT id, username, token_version FROM users WHERE id = ?",
            (user_id,),
        ).fetchone()
    finally:
        conn.close()
    if not row or int(payload.get("ver", -1)) != int(row["token_version"]):
        raise HTTPException(status_code=401, detail="Session is no longer valid. Please log in again.")
    return user_id


def _set_auth_cookies(response: Response, token: str) -> str:
    same_site = settings.auth_cookie_samesite.strip().lower()
    if same_site not in {"lax", "strict", "none"}:
        same_site = "lax"
    max_age = max(15, min(settings.jwt_expire_minutes, 1440)) * 60
    response.set_cookie(
        settings.auth_cookie_name,
        token,
        max_age=max_age,
        httponly=True,
        secure=settings.auth_cookie_secure,
        samesite=same_site,
        path="/",
    )
    csrf_token = os.urandom(24).hex()
    response.set_cookie(
        settings.csrf_cookie_name,
        csrf_token,
        max_age=max_age,
        httponly=False,
        secure=settings.auth_cookie_secure,
        samesite=same_site,
        path="/",
    )
    return csrf_token


@router.post("/register")
async def register(user: UserRegister, request: Request):
    rate_limit(request, "auth-register", limit=6, window_seconds=600)
    username = user.username.strip()
    email = user.email.strip().lower()
    if not validate_email_format(email):
        raise HTTPException(status_code=400, detail="Enter a valid email address.")
    if not validate_password_strength(user.password):
        raise HTTPException(
            status_code=400,
            detail="Use at least 8 characters with an uppercase letter, a lowercase letter and a number.",
        )

    recovery_code = f"WCAI-{secrets.token_urlsafe(24)}"
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO users
                (username, email, password_hash, security_question, security_answer_hash, recovery_code_hash)
            VALUES (?, ?, ?, 'disabled', 'disabled', ?)
            """,
            (username, email, hash_password(user.password), hash_password(recovery_code)),
        )
        conn.commit()
    except sqlite3.IntegrityError as error:
        conn.rollback()
        raise HTTPException(status_code=409, detail="That username or email address is already registered.") from error
    finally:
        conn.close()
    return {
        "success": True,
        "message": "Manager registration completed successfully. Save the one-time recovery code now.",
        "recoveryCode": recovery_code,
    }


@router.post("/login")
async def login(user: UserLogin, request: Request, response: Response):
    identifier = user.username_or_email.strip().lower()
    rate_limit(request, "auth-login-ip", limit=50, window_seconds=300)
    rate_limit(request, "auth-login", subject=identifier, limit=10, window_seconds=300)
    conn = get_db_connection()
    try:
        row = conn.execute(
            """
            SELECT id, username, password_hash, token_version
            FROM users WHERE LOWER(username) = ? OR LOWER(email) = ?
            """,
            (identifier, identifier),
        ).fetchone()
        valid = verify_password(user.password, row["password_hash"] if row else _DUMMY_PASSWORD_HASH)
        if not row or not valid:
            raise HTTPException(status_code=401, detail="Invalid username/email or password.")
        if password_needs_rehash(row["password_hash"]):
            conn.execute("UPDATE users SET password_hash = ? WHERE id = ?", (hash_password(user.password), row["id"]))
            conn.commit()
        token = create_token(row["id"], row["username"], int(row["token_version"]))
    finally:
        conn.close()
    csrf_token = _set_auth_cookies(response, token)
    # The token remains in the API response for CLI/test clients. The WCAI web
    # client deliberately ignores it and relies on the HttpOnly cookie.
    return {"success": True, "token": token, "csrfToken": csrf_token, "username": row["username"]}


@router.post("/forgot-password-question")
async def forgot_password_question(body: ForgotPasswordRequest, request: Request):
    identifier = body.username_or_email.strip().lower()
    rate_limit(request, "auth-recovery-question-ip", limit=20, window_seconds=900)
    rate_limit(request, "auth-recovery-question", subject=identifier, limit=5, window_seconds=900)
    conn = get_db_connection()
    try:
        row = conn.execute(
            "SELECT 1 FROM users WHERE LOWER(username) = ? OR LOWER(email) = ?",
            (identifier, identifier),
        ).fetchone()
    finally:
        conn.close()
    # Always return the same response so this endpoint is not an account oracle.
    return {
        "success": True,
        "recovery_prompt": "Enter the one-time recovery code that was shown when this account was created.",
    }


@router.post("/reset-password")
async def reset_password(body: ResetPasswordRequest, request: Request):
    identifier = body.username_or_email.strip().lower()
    rate_limit(request, "auth-recovery-reset-ip", limit=20, window_seconds=900)
    rate_limit(request, "auth-recovery-reset", subject=identifier, limit=5, window_seconds=900)
    if not validate_password_strength(body.new_password):
        raise HTTPException(
            status_code=400,
            detail="Use at least 8 characters with an uppercase letter, a lowercase letter and a number.",
        )
    conn = get_db_connection()
    try:
        row = conn.execute(
            "SELECT id, recovery_code_hash FROM users WHERE LOWER(username) = ? OR LOWER(email) = ?",
            (identifier, identifier),
        ).fetchone()
        valid = verify_password(body.recovery_code, row["recovery_code_hash"] if row and row["recovery_code_hash"] else _DUMMY_PASSWORD_HASH)
        if not row or not valid:
            raise HTTPException(status_code=400, detail="The recovery details could not be verified.")
        new_recovery_code = f"WCAI-{secrets.token_urlsafe(24)}"
        conn.execute(
            """
            UPDATE users
            SET password_hash = ?, token_version = token_version + 1,
                recovery_code_hash = ?
            WHERE id = ?
            """,
            (hash_password(body.new_password), hash_password(new_recovery_code), row["id"]),
        )
        conn.commit()
    finally:
        conn.close()
    return {
        "success": True,
        "message": "Password updated. Sign in again on every device and save the replacement recovery code.",
        "recoveryCode": new_recovery_code,
    }


@router.post("/logout")
async def logout(response: Response, _: int = Depends(get_current_user_id)):
    response.delete_cookie(settings.auth_cookie_name, path="/")
    response.delete_cookie(settings.csrf_cookie_name, path="/")
    return {"success": True}


@router.get("/me")
async def me(request: Request, user_id: int = Depends(get_current_user_id)):
    conn = get_db_connection()
    try:
        row = conn.execute("SELECT username FROM users WHERE id = ?", (user_id,)).fetchone()
    finally:
        conn.close()
    if not row:
        raise HTTPException(status_code=401, detail="Session is no longer valid.")
    return {
        "authenticated": True,
        "user_id": user_id,
        "username": row["username"],
        "csrfToken": request.cookies.get(settings.csrf_cookie_name),
    }


@router.get("/csrf")
async def csrf_token(request: Request, _: int = Depends(get_current_user_id)):
    token = request.cookies.get(settings.csrf_cookie_name)
    if not token:
        raise HTTPException(status_code=401, detail="CSRF session is unavailable. Please log in again.")
    return {"csrfToken": token}
