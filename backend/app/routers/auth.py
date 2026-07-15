from fastapi import APIRouter, HTTPException, Header, status
from pydantic import BaseModel, Field
import hashlib
import os
import jwt
import datetime
from typing import Optional

from ..db import get_db_connection
from ..config import settings

router = APIRouter(prefix="/api/auth", tags=["auth"])

SECRET_KEY = settings.jwt_secret_key
ALGORITHM = "HS256"

# ─── Pydantic Schemas ──────────────────────────────────────────────────────────

class UserRegister(BaseModel):
    username: str = Field(..., min_length=3, max_length=20)
    email: str
    password: str = Field(..., min_length=6)
    security_question: str
    security_answer: str

class UserLogin(BaseModel):
    username_or_email: str
    password: str

class ForgotPasswordRequest(BaseModel):
    username_or_email: str

class ResetPasswordRequest(BaseModel):
    username_or_email: str
    security_answer: str
    new_password: str = Field(..., min_length=6)

# ─── Encryption Utilities ──────────────────────────────────────────────────────

def hash_password(password: str) -> str:
    """Hash password using native hashlib PBKDF2 with salt."""
    salt = os.urandom(16)
    db_hash = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt, 100000)
    return f"{salt.hex()}:{db_hash.hex()}"

def verify_password(password: str, hashed: str) -> bool:
    """Verify password by checking PBKDF2 match."""
    try:
        salt_hex, hash_hex = hashed.split(':')
        salt = bytes.fromhex(salt_hex)
        db_hash = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt, 100000)
        return db_hash.hex() == hash_hex
    except Exception:
        return False

# ─── Token Utilities ───────────────────────────────────────────────────────────

def create_token(user_id: int, username: str) -> str:
    """Generate stateless JWT access token valid for 3 days."""
    payload = {
        "user_id": user_id,
        "username": username,
        "exp": datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=3)
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)

def decode_token(token: str) -> dict:
    """Decode and validate JWT access token."""
    try:
        if token.startswith("Bearer "):
            token = token.removeprefix("Bearer ").strip()
        if not token:
            raise jwt.InvalidTokenError("Empty token")
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session has expired. Please log in again."
        )
    except jwt.InvalidTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication token."
        )

import re

def validate_password_strength(password: str) -> bool:
    """Validate that password contains at least 1 uppercase, 1 lowercase, 1 digit, and is min 6 chars."""
    if len(password) < 6:
        return False
    if not re.search(r"[A-Z]", password):
        return False
    if not re.search(r"[a-z]", password):
        return False
    if not re.search(r"[0-9]", password):
        return False
    return True

def validate_email_format(email: str) -> bool:
    """Validate basic email pattern."""
    return bool(re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email))

# ─── Endpoints ─────────────────────────────────────────────────────────────────

@router.post("/register")
async def register(user: UserRegister):
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Trim and normalize inputs
    username_norm = user.username.strip()
    email_norm = user.email.strip().lower()
    
    if not validate_email_format(email_norm):
        conn.close()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Geçersiz e-posta formatı. Lütfen doğru bir e-posta adresi girin (örn: manager@example.com)."
        )
        
    if not validate_password_strength(user.password):
        conn.close()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Şifre gücü yetersiz! Şifreniz en az 6 karakter olmalı; en az bir büyük harf (A-Z), bir küçük harf (a-z) ve bir rakam (0-9) içermelidir."
        )
    
    # Check if username already exists (case-insensitive check)
    cursor.execute("SELECT id FROM users WHERE LOWER(username) = LOWER(?)", (username_norm,))
    if cursor.fetchone():
        conn.close()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Bu kullanıcı adı zaten alınmış. Lütfen başka bir kullanıcı adı seçin."
        )
        
    # Check if email already exists
    cursor.execute("SELECT id FROM users WHERE LOWER(email) = LOWER(?)", (email_norm,))
    if cursor.fetchone():
        conn.close()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Bu e-posta adresi zaten kayıtlı. Lütfen giriş yapmayı deneyin."
        )
        
    # Hash password and security answer
    pw_hash = hash_password(user.password)
    ans_hash = hash_password(user.security_answer.strip().lower())
    
    # Insert new user
    cursor.execute(
        """
        INSERT INTO users (username, email, password_hash, security_question, security_answer_hash)
        VALUES (?, ?, ?, ?, ?)
        """,
        (username_norm, email_norm, pw_hash, user.security_question, ans_hash)
    )
    conn.commit()
    conn.close()
    
    return {"success": True, "message": "Manager kaydı başarıyla tamamlandı!"}

@router.post("/login")
async def login(user: UserLogin):
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Fetch user by username or email
    cursor.execute(
        "SELECT id, username, password_hash FROM users WHERE LOWER(username) = LOWER(?) OR LOWER(email) = LOWER(?)",
        (user.username_or_email, user.username_or_email)
    )
    row = cursor.fetchone()
    conn.close()
    
    if not row or not verify_password(user.password, row["password_hash"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username/email or password."
        )
        
    # Create token
    token = create_token(row["id"], row["username"])
    return {
        "success": True,
        "token": token,
        "username": row["username"]
    }

@router.post("/forgot-password-question")
async def forgot_password_question(req: ForgotPasswordRequest):
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute(
        "SELECT security_question FROM users WHERE LOWER(username) = LOWER(?) OR LOWER(email) = LOWER(?)",
        (req.username_or_email, req.username_or_email)
    )
    row = cursor.fetchone()
    conn.close()
    
    if not row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No manager found with this username or email."
        )
        
    return {"success": True, "security_question": row["security_question"]}

@router.post("/reset-password")
async def reset_password(req: ResetPasswordRequest):
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Fetch security answer and ID
    cursor.execute(
        "SELECT id, security_answer_hash FROM users WHERE LOWER(username) = LOWER(?) OR LOWER(email) = LOWER(?)",
        (req.username_or_email, req.username_or_email)
    )
    row = cursor.fetchone()
    
    if not row:
        conn.close()
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No manager found."
        )
        
    # Verify security answer
    if not verify_password(req.security_answer.strip().lower(), row["security_answer_hash"]):
        conn.close()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Incorrect answer to the security question."
        )
        
    # Hash new password
    if not validate_password_strength(req.new_password):
        conn.close()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="New password must contain at least 6 characters, one uppercase letter, one lowercase letter, and one number."
        )
    new_pw_hash = hash_password(req.new_password)
    
    # Update password
    cursor.execute(
        "UPDATE users SET password_hash = ? WHERE id = ?",
        (new_pw_hash, row["id"])
    )
    conn.commit()
    conn.close()
    
    return {"success": True, "message": "Password updated successfully! You can now log in."}

@router.get("/me")
async def me(authorization: Optional[str] = Header(None)):
    if not authorization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authorization token missing."
        )
    
    payload = decode_token(authorization)
    return {
        "authenticated": True,
        "user_id": payload["user_id"],
        "username": payload["username"]
    }
