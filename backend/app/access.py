"""Central membership and paid-access policy for Auto-Gaffer.

The browser never decides whether premium functionality is available.  Every
protected endpoint asks this module for the authenticated user's current
server-side entitlement.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import re
from typing import Any, Dict, Optional

from fastapi import HTTPException, status

from .config import settings
from .db import get_db_connection


DEMO_USERNAME = "kaan"
MEMBERSHIP_PRICE_USDC = 4.99
SINGLE_ACCESS_PRICE_USDC = 0.05
MEMBERSHIP_DAYS = 30
SINGLE_ACCESS_MINUTES = 15

LOCKED_CAPABILITIES_MESSAGE = """🔒 **Auto-Gaffer AI erişimi kilitli**

AI danışmanı ve Deep Tactical Analytics yalnızca aktif üyelik veya x402 ile alınan süreli erişimle kullanılabilir. Erişim açıldığında şunları yapabilirsin:

• Güncel World Cup 2026 veri snapshot'ına göre oyuncu, takım ve maç analizi
• Seçtiğin dizilişe tam uyan, bütçe sınırını aşmayan ideal 11 oluşturma
• Messi, Yamal veya Mbappé gibi zorunlu oyuncuları ve ülke/bölge tercihlerini kadroya uygulama
• Gol, asist, xG, form ve müsaitlik sinyallerine göre hücum/savunma optimizasyonu
• Mevcut kadronun pozisyon dengesi, zayıf noktaları ve bütçe verimliliği analizi
• Daha güçlü transfer ve oyuncu değişikliği önerileri
• Onayından sonra MCP aracılığıyla önerilen transferi veya kadroyu sahaya uygulama
• Kaynak durumu açıkça belirtilen derin oyuncu raporları ve sakatlık risk değerlendirmesi

**Erişim seçenekleri**
• Pro Membership: 30 gün boyunca AI, Analytics ve finans özellikleri — **4.99 USDC**
• x402 Match Pass: AI ve Analytics için 15 dakikalık erişim — **0.05 USDC**

Üyelik kartını açmak için **Unlock Deep Tactical Analytics** veya üst menüdeki üyelik durumuna tıkla. Kaan demo hesabında gerçek para kesilmez; ücretsiz demo üyeliği açıkça etkinleştirilir."""


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

    membership_active = row["membership_status"] == "active" and (
        membership_expires_at is None or membership_expires_at > now
    )
    access_pass_active = pass_expires_at is not None and pass_expires_at > now
    source = row["membership_source"] if membership_active else (
        "x402_access_pass" if access_pass_active else None
    )

    return {
        "username": row["username"],
        "isDemoAccount": row["username"].strip().lower() == DEMO_USERNAME,
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
        "paymentMode": "demo" if settings.x402_demo_mode else "verified_x402",
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


def grant_demo_membership(user_id: int) -> Dict[str, Any]:
    """Activate the no-charge judge/demo membership for Kaan only."""
    row = _load_user(user_id)
    if row["username"].strip().lower() != DEMO_USERNAME:
        raise HTTPException(status_code=403, detail="Free demo membership is limited to the Kaan demo account")

    conn = get_db_connection()
    cursor = conn.cursor()
    receipt = f"demo_membership_{user_id}_{int(_utc_now().timestamp())}"
    try:
        cursor.execute(
            """
            UPDATE users
            SET membership_tier = 'demo_pro', membership_status = 'active',
                membership_source = 'kaan_demo', membership_expires_at = NULL
            WHERE id = ?
            """,
            (user_id,),
        )
        _record_transaction(
            cursor,
            user_id=user_id,
            mode="membership",
            amount=0.0,
            source="kaan_demo",
            receipt=receipt,
            simulated=True,
        )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
    return {**get_access_status(user_id), "receipt": receipt, "simulated": True}


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
                SET access_pass_expires_at = ?, wallet_address = COALESCE(?, wallet_address)
                WHERE id = ?
                """,
                (expires_at, normalized_wallet, user_id),
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
