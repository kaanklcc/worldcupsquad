"""Wallet-signed CCTP v2 intent, attestation and confirmation endpoints."""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Header

from ..access import require_membership, validate_wallet
from ..cctp_flow import cctp_public_config, get_attestation, verify_cctp_receipts
from ..config import settings
from ..db import get_db_connection
from ..models import CCTPAttestationRequest, CCTPConfirmRequest, CCTPIntentRequest, CCTPResponse
from ..operation_ledger import begin_operation, confirm_operation, fail_operation, get_operation
from .squads import get_current_user_id


router = APIRouter()


def _require_saved_evm_wallet(user_id: int, wallet_address: str) -> str:
    access = require_membership(user_id)
    wallet = validate_wallet(wallet_address)
    if not wallet.startswith("0x"):
        raise HTTPException(status_code=400, detail="CCTP testnet requires the EVM address connected in MetaMask")
    if not access.get("walletAddress"):
        raise HTTPException(status_code=400, detail="Save the connected EVM wallet before starting CCTP")
    if access["walletAddress"].lower() != wallet.lower():
        raise HTTPException(status_code=400, detail="CCTP wallet must match the wallet saved in your membership profile")
    return wallet


@router.post("/api/cctp/intent")
async def create_cctp_intent(
    request: CCTPIntentRequest,
    idempotency_key: str | None = Header(None, alias="Idempotency-Key"),
    user_id: int = Depends(get_current_user_id),
):
    """Create a replay-safe intent before the browser opens MetaMask."""
    wallet = _require_saved_evm_wallet(user_id, request.walletAddress)
    if request.amount != 20:
        raise HTTPException(status_code=400, detail="The WCAI CCTP backing amount is exactly 20 USDC")

    conn = get_db_connection()
    try:
        row = conn.execute("SELECT cctp_used FROM users WHERE id = ?", (user_id,)).fetchone()
    finally:
        conn.close()
    if not row:
        raise HTTPException(status_code=404, detail="User not found")
    if row["cctp_used"]:
        raise HTTPException(status_code=409, detail="CCTP backing has already been acquired")

    operation, replay = begin_operation(
        user_id=user_id,
        action_type="acquire_cctp_backing",
        provider="circle_cctp_v2",
        network=settings.x402_network,
        idempotency_key=idempotency_key,
        payload={"walletAddress": wallet.lower(), "amount": request.amount, "sourceChain": "Sepolia"},
    )
    if replay:
        if operation["status"] == "confirmed" and operation["receipt"]:
            return {"success": True, "replayed": True, "operation": operation, "receipt": operation["receipt"]}
        if operation["status"] == "processing":
            return {"success": True, "replayed": True, "operation": operation, "config": cctp_public_config()}
        raise HTTPException(status_code=409, detail="The previous CCTP intent failed; start a new bridge intent")
    return {
        "success": True,
        "operation": operation,
        "amount": request.amount,
        "walletAddress": wallet,
        "config": cctp_public_config(),
        "notice": "Sign Sepolia and Injective transactions in your own wallet. WCAI only credits the budget after both receipts are verified.",
    }


@router.post("/api/cctp/attestation")
async def read_cctp_attestation(
    request: CCTPAttestationRequest,
    user_id: int = Depends(get_current_user_id),
):
    """Proxy public Circle Iris status so the browser does not need a secret."""
    require_membership(user_id)
    return await get_attestation(request.burnTxHash)


@router.post("/api/cctp/confirm", response_model=CCTPResponse)
async def confirm_cctp_backing(
    request: CCTPConfirmRequest,
    user_id: int = Depends(get_current_user_id),
):
    """Verify actual CCTP receipts and then perform the one-time budget credit."""
    wallet = _require_saved_evm_wallet(user_id, request.walletAddress)
    if request.amount != 20:
        raise HTTPException(status_code=400, detail="The WCAI CCTP backing amount is exactly 20 USDC")
    operation = get_operation(request.operationId, user_id)
    if operation["actionType"] != "acquire_cctp_backing":
        raise HTTPException(status_code=409, detail="Operation is not a CCTP backing intent")
    if operation["status"] == "confirmed" and operation["receipt"]:
        return CCTPResponse(**operation["receipt"], operation=operation)
    if operation["status"] != "processing":
        raise HTTPException(status_code=409, detail=f"CCTP operation is {operation['status']}; create a new intent to retry")

    try:
        proof = await verify_cctp_receipts(
            wallet_address=wallet,
            amount_usdc=request.amount,
            burn_tx_hash=request.burnTxHash,
            mint_tx_hash=request.mintTxHash,
        )
        conn = get_db_connection()
        cursor = conn.cursor()
        try:
            row = cursor.execute("SELECT budget, cctp_used FROM users WHERE id = ?", (user_id,)).fetchone()
            if not row:
                raise HTTPException(status_code=404, detail="User not found")
            if row["cctp_used"]:
                raise HTTPException(status_code=409, detail="CCTP backing has already been acquired")
            new_budget = float(row["budget"]) + request.amount
            cursor.execute(
                "UPDATE users SET budget = ?, cctp_used = 1 WHERE id = ? AND cctp_used = 0",
                (new_budget, user_id),
            )
            if cursor.rowcount != 1:
                raise HTTPException(status_code=409, detail="CCTP backing has already been acquired")
            cursor.execute(
                """
                INSERT INTO cctp_transactions (user_id, wallet_address, amount, source_chain, tx_hash)
                VALUES (?, ?, ?, ?, ?)
                """,
                (user_id, wallet, request.amount, "Ethereum Sepolia -> Injective EVM Testnet", request.mintTxHash),
            )
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

        response_payload: dict[str, Any] = {
            "success": True,
            "newBudgetBonus": request.amount,
            "txHash": request.mintTxHash,
            "burnTxHash": request.burnTxHash,
            "mintTxHash": request.mintTxHash,
            "message": "Circle CCTP v2 burn and Injective mint were confirmed on testnet.",
            "simulated": False,
        }
        confirmed = confirm_operation(
            operation["operationId"],
            receipt=response_payload,
            tx_hash=request.mintTxHash,
            simulated=False,
        )
        return CCTPResponse(**response_payload, operation=confirmed)
    except HTTPException as error:
        fail_operation(operation["operationId"], str(error.detail))
        raise
    except Exception as error:
        fail_operation(operation["operationId"], str(error))
        raise HTTPException(status_code=500, detail=f"CCTP confirmation failed: {error}") from error
