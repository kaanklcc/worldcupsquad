"""Central membership and paid-access policy for WCAI.

The browser never decides whether premium functionality is available.  Every
protected endpoint asks this module for the authenticated user's current
server-side entitlement.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import re
import sqlite3
from typing import Any, Dict, Optional
from uuid import uuid4

from fastapi import HTTPException, status

from .config import settings
from .db import get_db_connection


MEMBERSHIP_PRICE_USDC = 4.99
SINGLE_ACCESS_PRICE_USDC = 0.05
MEMBERSHIP_DAYS = 30
SINGLE_ACCESS_MINUTES = 15
# ``kaan_demo`` is retained only so pre-hardening database rows without an
# expiry are treated as expired. It no longer grants username-based access.
DEMO_SOURCES = {"kaan_demo", "hackathon_demo_pro", "hackathon_demo_match_pass"}

LOCKED_CAPABILITIES_MESSAGE = """🔒 **WCAI access is locked**

WCAI chat and Deep Tactical Analytics require an active membership or a time-limited x402 Match Pass. When unlocked, you can use:

• Current World Cup 2026 player, team and match analysis
• Budget-valid starting XIs that honour the selected formation
• Required players such as Messi, Yamal or Mbappé plus country/position preferences
• Attack and defence optimisation using goals, assists, xG, form and availability signals
• Squad balance, weak-point and budget-efficiency analysis
• Stronger transfer and single-player replacement recommendations
• Explicitly confirmed MCP lineup or transfer actions
• Source-labelled player reports and injury-risk assessment

**Access options**
• Pro Membership: AI, Analytics and finance tools for 30 days — **4.99 USDC**
• x402 Match Pass: 15 minutes of AI and Analytics — **0.05 USDC**

Open **Unlock Deep Tactical Analytics** or the membership status in the header. Hackathon Demo checkout, when enabled, grants a visibly simulated 30-minute pass without charging funds."""


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _to_iso(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat()


def _parse_iso(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)
    except (TypeError, ValueError):
        return None


def _load_user(user_id: int):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT id, username, membership_tier, membership_status,
               membership_source, membership_expires_at,
               access_pass_expires_at, wallet_address
        FROM users WHERE id = ?
        """,
        (user_id,),
    )
    row = cursor.fetchone()
    conn.close()
    if not row:
        raise HTTPException(status_code=404, detail="User not found")
    return row


def get_access_status(user_id: int) -> Dict[str, Any]:
    """Return the normalized, expiry-aware entitlement for a user."""
    row = _load_user(user_id)
    now = _utc_now()
    membership_expires_at = _parse_iso(row["membership_expires_at"])
    pass_expires_at = _parse_iso(row["access_pass_expires_at"])

    # Legacy demo grants without an expiry are treated as expired so every
    # judge explicitly activates the same renewable, time-boxed experience.
    membership_has_valid_expiry = membership_expires_at is not None or row["membership_source"] not in DEMO_SOURCES
    membership_active = row["membership_status"] == "active" and membership_has_valid_expiry and (
        membership_expires_at is None or membership_expires_at > now
    )
    access_pass_active = pass_expires_at is not None and pass_expires_at > now
    source = row["membership_source"] if membership_active else (
        (row["membership_source"] or "x402_access_pass") if access_pass_active else None
    )
    zero_address = "0x0000000000000000000000000000000000000000"
    pay_to = settings.x402_pay_to.strip()
    asset = settings.x402_asset.strip()
    x402_ready = bool(
        settings.x402_facilitator_url.strip()
        and re.fullmatch(r"0x[a-fA-F0-9]{40}", pay_to)
        and pay_to.lower() != zero_address
        and re.fullmatch(r"0x[a-fA-F0-9]{40}", asset)
        and asset.lower() != zero_address
    )

    demo_duration = max(5, min(int(settings.hackathon_demo_minutes), 120))
    demo_available = bool(settings.x402_demo_mode and settings.x402_allow_simulated_purchases)

    return {
        "username": row["username"],
        "demoAccessAvailable": demo_available,
        "demoDurationMinutes": demo_duration,
        "membershipTier": row["membership_tier"] if membership_active else "free",
        "membershipStatus": "active" if membership_active else "inactive",
        "membershipActive": membership_active,
        "membershipSource": row["membership_source"] if membership_active else None,
        "membershipExpiresAt": _to_iso(membership_expires_at) if membership_expires_at else None,
        "accessPassActive": access_pass_active,
        "accessPassExpiresAt": _to_iso(pass_expires_at) if pass_expires_at else None,
        "hasAiAccess": membership_active or access_pass_active,
        "hasAnalyticsAccess": membership_active or access_pass_active,
        "hasFinanceAccess": membership_active,
        "accessSource": source,
        "walletAddress": row["wallet_address"],
        "paymentMode": "verified_x402" if x402_ready else "demo",
        "x402Ready": x402_ready,
        "x402Network": settings.x402_network,
        "pricing": {
            "membershipUsdc": MEMBERSHIP_PRICE_USDC,
            "singleAccessUsdc": SINGLE_ACCESS_PRICE_USDC,
            "membershipDays": MEMBERSHIP_DAYS,
            "singleAccessMinutes": SINGLE_ACCESS_MINUTES,
        },
    }


def _record_transaction(
    cursor,
    *,
    user_id: int,
    mode: str,
    amount: float,
    source: str,
    receipt: str,
    simulated: bool,
) -> None:
    cursor.execute(
        """
        INSERT INTO access_transactions
            (user_id, access_mode, amount, currency, source, receipt, simulated)
        VALUES (?, ?, ?, 'USDC', ?, ?, ?)
        """,
        (user_id, mode, amount, source, receipt, 1 if simulated else 0),
    )


def grant_demo_access(user_id: int, mode: str) -> Dict[str, Any]:
    """Activate an explicit, short-lived and auditable hackathon demo pass."""
    if mode not in {"membership", "single_use"}:
        raise HTTPException(status_code=400, detail="Unsupported access mode")

    row = _load_user(user_id)
    demo_available = settings.x402_demo_mode and settings.x402_allow_simulated_purchases
    if not demo_available:
        raise HTTPException(status_code=403, detail="Hackathon Demo checkout is not enabled")

    duration_minutes = max(5, min(int(settings.hackathon_demo_minutes), 120))
    now = _utc_now()
    expires_at = _to_iso(now + timedelta(minutes=duration_minutes))
    source = "hackathon_demo_pro" if mode == "membership" else "hackathon_demo_match_pass"
    conn = get_db_connection()
    cursor = conn.cursor()
    receipt = f"demo_{mode}_{user_id}_{uuid4().hex}"
    try:
        if mode == "membership":
            cursor.execute(
                """
                UPDATE users
                SET membership_tier = 'demo_pro', membership_status = 'active',
                    membership_source = ?, membership_expires_at = ?
                WHERE id = ?
                """,
                (source, expires_at, user_id),
            )
        else:
            cursor.execute(
                """
                UPDATE users
                SET membership_source = ?, access_pass_expires_at = ?
                WHERE id = ?
                """,
                (source, expires_at, user_id),
            )
        if cursor.rowcount != 1:
            raise HTTPException(status_code=404, detail="User not found")
        _record_transaction(
            cursor,
            user_id=user_id,
            mode=mode,
            amount=0.0,
            source=source,
            receipt=receipt,
            simulated=True,
        )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
    return {
        **get_access_status(user_id),
        "receipt": receipt,
        "simulated": True,
        "chargedAmountUsdc": 0.0,
        "demoExpiresAt": expires_at,
    }


def grant_paid_access(
    user_id: int,
    *,
    mode: str,
    source: str,
    receipt: str,
    simulated: bool,
    wallet_address: Optional[str] = None,
) -> Dict[str, Any]:
    if mode not in {"membership", "single_use"}:
        raise HTTPException(status_code=400, detail="Unsupported access mode")

    normalized_wallet = validate_wallet(wallet_address) if wallet_address else None
    now = _utc_now()
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        if not simulated:
            cursor.execute(
                """
                INSERT INTO consumed_chain_receipts (provider, network, tx_hash, user_id)
                VALUES ('x402', ?, ?, ?)
                """,
                (settings.x402_network, receipt.lower(), user_id),
            )
        if mode == "membership":
            expires_at = _to_iso(now + timedelta(days=MEMBERSHIP_DAYS))
            cursor.execute(
                """
                UPDATE users
                SET membership_tier = 'pro', membership_status = 'active',
                    membership_source = ?, membership_expires_at = ?,
                    wallet_address = COALESCE(?, wallet_address)
                WHERE id = ?
                """,
                (source, expires_at, normalized_wallet, user_id),
            )
            amount = MEMBERSHIP_PRICE_USDC
        else:
            expires_at = _to_iso(now + timedelta(minutes=SINGLE_ACCESS_MINUTES))
            cursor.execute(
                """
                UPDATE users
                SET membership_source = ?, access_pass_expires_at = ?,
                    wallet_address = COALESCE(?, wallet_address)
                WHERE id = ?
                """,
                (source, expires_at, normalized_wallet, user_id),
            )
            amount = SINGLE_ACCESS_PRICE_USDC

        if cursor.rowcount != 1:
            raise HTTPException(status_code=404, detail="User not found")
        _record_transaction(
            cursor,
            user_id=user_id,
            mode=mode,
            amount=amount,
            source=source,
            receipt=receipt,
            simulated=simulated,
        )
        conn.commit()
    except sqlite3.IntegrityError as error:
        conn.rollback()
        raise HTTPException(status_code=409, detail="This x402 settlement receipt has already been consumed.") from error
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
    return {**get_access_status(user_id), "receipt": receipt, "simulated": simulated}


def validate_wallet(wallet_address: Optional[str]) -> str:
    value = (wallet_address or "").strip()
    is_cosmos = bool(re.fullmatch(r"inj1[0-9a-z]{20,80}", value.lower()))
    is_evm = bool(re.fullmatch(r"0x[0-9a-fA-F]{40}", value))
    if not (is_cosmos or is_evm):
        raise HTTPException(
            status_code=400,
            detail="Enter a valid Injective inj1... or EVM 0x... wallet address",
        )
    return value


def save_wallet(user_id: int, wallet_address: str) -> Dict[str, Any]:
    normalized = validate_wallet(wallet_address)
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET wallet_address = ? WHERE id = ?", (normalized, user_id))
    if cursor.rowcount != 1:
        conn.close()
        raise HTTPException(status_code=404, detail="User not found")
    conn.commit()
    conn.close()
    return get_access_status(user_id)


def require_ai_access(user_id: int) -> Dict[str, Any]:
    access = get_access_status(user_id)
    if not access["hasAiAccess"]:
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail="Active membership or an x402 Match Pass is required",
        )
    return access


def require_membership(user_id: int) -> Dict[str, Any]:
    access = get_access_status(user_id)
    if not access["membershipActive"]:
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail="Active Pro membership is required for wallet and CCTP finance features",
        )
    return access
