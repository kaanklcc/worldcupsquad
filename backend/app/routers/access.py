"""Membership, x402 unlock, and wallet endpoints."""
from __future__ import annotations

import base64
import json
import re
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
    validate_wallet,
)
from ..config import settings
from ..operation_ledger import begin_operation, confirm_operation, fail_operation
from ..x402 import get_x402_verifier
from .squads import get_current_user_id


router = APIRouter(prefix="/api/access", tags=["access"])


class AccessUnlockRequest(BaseModel):
    mode: Literal["membership", "single_use"] = "membership"
    hasPaidX402: bool = False
    walletAddress: Optional[str] = None


class WalletUpdateRequest(BaseModel):
    walletAddress: str


def _payment_requirement(mode: str) -> dict:
    zero_address = "0x0000000000000000000000000000000000000000"
    facilitator = settings.x402_facilitator_url.strip()
    pay_to = settings.x402_pay_to.strip()
    asset = settings.x402_asset.strip()
    valid_receiver = bool(re.fullmatch(r"0x[a-fA-F0-9]{40}", pay_to)) and pay_to.lower() != zero_address
    valid_asset = bool(re.fullmatch(r"0x[a-fA-F0-9]{40}", asset)) and asset.lower() != zero_address
    if not facilitator or not valid_receiver or not valid_asset:
        raise HTTPException(status_code=503, detail="Configure X402_FACILITATOR_URL, X402_PAY_TO and X402_ASSET before accepting real x402 payments")
    price = MEMBERSHIP_PRICE_USDC if mode == "membership" else SINGLE_ACCESS_PRICE_USDC
    amount_atomic = str(round(price * 1_000_000))
    description = "WCAI Pro membership" if mode == "membership" else "WCAI Match Pass"
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
            "asset": asset,
            "payTo": pay_to,
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
    idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key"),
    user_id: int = Depends(get_current_user_id),
):
    current = get_access_status(user_id)
    action_type = "unlock_membership" if body.mode == "membership" else "unlock_match_pass"

    def begin_unlock_operation():
        operation, replay = begin_operation(
            user_id=user_id,
            action_type=action_type,
            provider="x402",
            network=settings.x402_network,
            idempotency_key=idempotency_key,
            payload={"mode": body.mode, "walletAddress": body.walletAddress or ""},
        )
        if replay:
            if operation["status"] == "confirmed" and operation["receipt"]:
                return operation, operation["receipt"]
            raise HTTPException(status_code=409, detail=f"Access operation is {operation['status']}; create a new intent to retry")
        return operation, None

    # The named judge/demo account is always explicit, free, and labelled as
    # simulated.  It never enters a payment or wallet-signing flow.
    if current["isDemoAccount"]:
        operation, replay_receipt = begin_unlock_operation()
        if replay_receipt:
            return {**replay_receipt, "operation": operation}
        try:
            result = grant_demo_membership(user_id)
            payload = {
                "success": True,
                "message": "Kaan demo membership activated. No payment was charged.",
                **result,
            }
            confirmed = confirm_operation(
                operation["operationId"],
                receipt=payload,
                tx_hash=result["receipt"],
                simulated=True,
            )
            return {**payload, "operation": confirmed}
        except HTTPException as error:
            fail_operation(operation["operationId"], str(error.detail))
            raise
        except Exception as error:
            fail_operation(operation["operationId"], str(error))
            raise HTTPException(status_code=500, detail=f"Demo membership activation failed: {error}")

    signature = payment_signature or legacy_payment
    receipt = legacy_receipt

    if not signature and not receipt:
        _raise_payment_required(body.mode)

    operation, replay_receipt = begin_unlock_operation()
    if replay_receipt:
        return {**replay_receipt, "operation": operation}
    try:
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

        payer = str(verification.get("payer") or "").strip()
        if not payer:
            raise HTTPException(status_code=502, detail="x402 facilitator did not return the verified payer address")
        verified_wallet = validate_wallet(payer)
        if body.walletAddress and body.walletAddress.lower() != verified_wallet.lower():
            raise HTTPException(status_code=422, detail="The x402 signer must match the wallet selected for this access grant")
        save_wallet(user_id, verified_wallet)

        verified_receipt = str(verification.get("receipt") or receipt or f"x402_verified_{user_id}_{int(time.time())}")
        result = grant_paid_access(
            user_id,
            mode=body.mode,
            source="x402_verified",
            receipt=verified_receipt,
            simulated=False,
            wallet_address=verified_wallet,
        )
        response.headers["PAYMENT-RESPONSE"] = str(verification.get("paymentResponse") or verified_receipt)
        payload = {"success": True, "message": "x402 payment verified and access activated.", **result}
        confirmed = confirm_operation(
            operation["operationId"],
            receipt=payload,
            tx_hash=verified_receipt,
            simulated=False,
        )
        return {**payload, "operation": confirmed}
    except HTTPException as error:
        fail_operation(operation["operationId"], str(error.detail))
        raise
    except Exception as error:
        fail_operation(operation["operationId"], str(error))
        raise HTTPException(status_code=500, detail=f"x402 access activation failed: {error}")
