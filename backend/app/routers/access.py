"""Membership, x402 unlock, and wallet endpoints."""
from __future__ import annotations

import base64
import json
import time
from typing import Literal, Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Response, status
from pydantic import BaseModel

from ..access import (
    MEMBERSHIP_PRICE_USDC,
    SINGLE_ACCESS_PRICE_USDC,
    get_access_status,
    grant_demo_membership,
    grant_paid_access,
    save_wallet,
)
from ..config import settings
from ..x402 import get_x402_verifier
from .squads import get_current_user_id


router = APIRouter(prefix="/api/access", tags=["access"])


class AccessUnlockRequest(BaseModel):
    mode: Literal["membership", "single_use"] = "membership"
    hasPaidX402: bool = False
    walletAddress: Optional[str] = None


class WalletUpdateRequest(BaseModel):
    walletAddress: str


def _is_local_demo() -> bool:
    return settings.x402_demo_mode and settings.x402_facilitator_url in {
        "",
        "https://facilitator.x402.co/verify",
    }


def _payment_requirement(mode: str) -> dict:
    zero_address = "0x0000000000000000000000000000000000000000"
    if not settings.x402_demo_mode and (
        settings.x402_pay_to == zero_address or settings.x402_asset == zero_address
    ):
        raise HTTPException(status_code=503, detail="X402_PAY_TO and X402_ASSET must be configured before production payments are enabled")
    price = MEMBERSHIP_PRICE_USDC if mode == "membership" else SINGLE_ACCESS_PRICE_USDC
    amount_atomic = str(round(price * 1_000_000))
    description = "Auto-Gaffer Pro membership" if mode == "membership" else "Auto-Gaffer Match Pass"
    return {
        "x402Version": 2,
        "error": "PAYMENT-SIGNATURE is required",
        "resource": {
            "url": f"{settings.x402_resource_base_url.rstrip('/')}/api/access/unlock",
            "description": description,
            "mimeType": "application/json",
        },
        "accepts": [{
            "scheme": "exact",
            "network": settings.x402_network,
            "amount": amount_atomic,
            "asset": settings.x402_asset,
            "payTo": settings.x402_pay_to,
            "maxTimeoutSeconds": 60,
            "extra": {"name": "USDC", "version": "2"},
        }],
    }


def _raise_payment_required(mode: str) -> None:
    requirement = _payment_requirement(mode)
    encoded = base64.b64encode(json.dumps(requirement).encode("utf-8")).decode("ascii")
    raise HTTPException(
        status_code=status.HTTP_402_PAYMENT_REQUIRED,
        detail=requirement,
        headers={"PAYMENT-REQUIRED": encoded},
    )


@router.get("/status")
async def access_status(user_id: int = Depends(get_current_user_id)):
    return get_access_status(user_id)


@router.post("/wallet")
async def update_wallet(
    request: WalletUpdateRequest,
    user_id: int = Depends(get_current_user_id),
):
    return {"success": True, **save_wallet(user_id, request.walletAddress)}


@router.post("/unlock")
async def unlock_access(
    body: AccessUnlockRequest,
    response: Response,
    payment_signature: Optional[str] = Header(None, alias="PAYMENT-SIGNATURE"),
    legacy_payment: Optional[str] = Header(None, alias="X-Payment"),
    legacy_receipt: Optional[str] = Header(None, alias="X-Payment-Receipt"),
    user_id: int = Depends(get_current_user_id),
):
    current = get_access_status(user_id)

    # The named judge/demo account is always explicit, free, and labelled as
    # simulated.  It never enters a payment or wallet-signing flow.
    if current["isDemoAccount"]:
        result = grant_demo_membership(user_id)
        return {
            "success": True,
            "message": "Kaan demo membership activated. No payment was charged.",
            **result,
        }

    signature = payment_signature or legacy_payment
    receipt = legacy_receipt

    # Local hackathon demo: the UI deliberately asks the user to start a
    # simulated x402 purchase.  This branch must be disabled in production.
    if _is_local_demo() and settings.x402_allow_simulated_purchases and body.hasPaidX402:
        demo_receipt = f"x402_demo_{body.mode}_{user_id}_{int(time.time())}"
        result = grant_paid_access(
            user_id,
            mode=body.mode,
            source="x402_demo",
            receipt=demo_receipt,
            simulated=True,
            wallet_address=body.walletAddress,
        )
        response.headers["PAYMENT-RESPONSE"] = demo_receipt
        return {
            "success": True,
            "message": "Simulated x402 access activated; no real USDC was transferred.",
            **result,
        }

    if not signature and not receipt:
        _raise_payment_required(body.mode)

    verifier = get_x402_verifier()
    requirement = _payment_requirement(body.mode)
    verification = await verifier.verify_and_settle(
        payment_signature=signature,
        payment_requirements=requirement["accepts"][0],
    )
    expected = MEMBERSHIP_PRICE_USDC if body.mode == "membership" else SINGLE_ACCESS_PRICE_USDC
    amount = float(verification.get("amount") or 0)
    currency = str(verification.get("currency") or "").upper()
    if not verification.get("verified") or currency != "USDC" or amount < expected:
        _raise_payment_required(body.mode)

    verified_receipt = str(verification.get("receipt") or receipt or f"x402_verified_{user_id}_{int(time.time())}")
    result = grant_paid_access(
        user_id,
        mode=body.mode,
        source="x402_verified",
        receipt=verified_receipt,
        simulated=False,
        wallet_address=body.walletAddress,
    )
    response.headers["PAYMENT-RESPONSE"] = str(verification.get("paymentResponse") or verified_receipt)
    return {"success": True, "message": "x402 payment verified and access activated.", **result}
