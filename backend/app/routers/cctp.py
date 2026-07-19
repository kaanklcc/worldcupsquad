"""Wallet-signed CCTP v2 intent, attestation and confirmation endpoints."""
from __future__ import annotations

from typing import Any
import logging
import sqlite3

from fastapi import APIRouter, Depends, HTTPException, Header, Request

from ..access import require_membership, validate_wallet
from ..cctp_flow import cctp_public_config, get_attestation, verify_cctp_receipts
from ..config import settings
from ..db import get_db_connection
from ..models import CCTPAttestationRequest, CCTPConfirmRequest, CCTPIntentRequest, CCTPResponse
from ..operation_ledger import begin_operation, confirm_operation, fail_operation, get_operation, request_hash
from ..security import rate_limit
from .squads import get_current_user_id


router = APIRouter()
logger = logging.getLogger(__name__)


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
    body: CCTPIntentRequest,
    request: Request,
    idempotency_key: str | None = Header(None, alias="Idempotency-Key"),
    user_id: int = Depends(get_current_user_id),
):
    """Create a replay-safe intent before the browser opens MetaMask."""
    rate_limit(request, "cctp-intent", subject=str(user_id), limit=10, window_seconds=3600)
    wallet = _require_saved_evm_wallet(user_id, body.walletAddress)
    if body.amount != 20:
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
        payload={"walletAddress": wallet.lower(), "amount": body.amount, "sourceChain": "Sepolia"},
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
        "amount": body.amount,
        "walletAddress": wallet,
        "config": cctp_public_config(),
        "notice": "Sign Sepolia and Injective transactions in your own wallet. WCAI only credits the budget after both receipts are verified.",
    }


@router.post("/api/cctp/attestation")
async def read_cctp_attestation(
    body: CCTPAttestationRequest,
    request: Request,
    user_id: int = Depends(get_current_user_id),
):
    """Proxy public Circle Iris status so the browser does not need a secret."""
    require_membership(user_id)
    rate_limit(request, "cctp-attestation", subject=str(user_id), limit=30, window_seconds=60)
    return await get_attestation(body.burnTxHash)


@router.post("/api/cctp/confirm", response_model=CCTPResponse)
async def confirm_cctp_backing(
    body: CCTPConfirmRequest,
    request: Request,
    user_id: int = Depends(get_current_user_id),
):
    """Verify actual CCTP receipts and then perform the one-time budget credit."""
    rate_limit(request, "cctp-confirm", subject=str(user_id), limit=10, window_seconds=3600)
    wallet = _require_saved_evm_wallet(user_id, body.walletAddress)
    if body.amount != 20:
        raise HTTPException(status_code=400, detail="The WCAI CCTP backing amount is exactly 20 USDC")
    operation = get_operation(body.operationId, user_id)
    if operation["actionType"] != "acquire_cctp_backing":
        raise HTTPException(status_code=409, detail="Operation is not a CCTP backing intent")
    if operation["status"] == "confirmed" and operation["receipt"]:
        return CCTPResponse(**operation["receipt"], operation=operation)
    if operation["status"] != "processing":
        raise HTTPException(status_code=409, detail=f"CCTP operation is {operation['status']}; create a new intent to retry")
    expected_intent_hash = request_hash({"walletAddress": wallet.lower(), "amount": body.amount, "sourceChain": "Sepolia"})
    if operation.get("requestHash") != expected_intent_hash:
        raise HTTPException(status_code=409, detail="CCTP confirmation does not match its original intent")

    try:
        proof = await verify_cctp_receipts(
            wallet_address=wallet,
            amount_usdc=body.amount,
            burn_tx_hash=body.burnTxHash,
            mint_tx_hash=body.mintTxHash,
        )
        conn = get_db_connection()
        cursor = conn.cursor()
        try:
            row = cursor.execute("SELECT budget, cctp_used FROM users WHERE id = ?", (user_id,)).fetchone()
            if not row:
                raise HTTPException(status_code=404, detail="User not found")
            if row["cctp_used"]:
                raise HTTPException(status_code=409, detail="CCTP backing has already been acquired")
            for network, tx_hash in (
                ("eip155:11155111", body.burnTxHash.lower()),
                ("eip155:1439", body.mintTxHash.lower()),
            ):
                cursor.execute(
                    """
                    INSERT INTO consumed_chain_receipts (provider, network, tx_hash, user_id)
                    VALUES ('circle_cctp_v2', ?, ?, ?)
                    """,
                    (network, tx_hash, user_id),
                )
            new_budget = float(row["budget"]) + body.amount
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
                (user_id, wallet, body.amount, "Ethereum Sepolia -> Injective EVM Testnet", body.mintTxHash),
            )
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

        response_payload: dict[str, Any] = {
            "success": True,
            "newBudgetBonus": body.amount,
            "txHash": body.mintTxHash,
            "burnTxHash": body.burnTxHash,
            "mintTxHash": body.mintTxHash,
            "message": "Circle CCTP v2 burn and Injective mint were confirmed on testnet.",
            "simulated": False,
        }
        confirmed = confirm_operation(
            operation["operationId"],
            receipt=response_payload,
            tx_hash=body.mintTxHash,
            simulated=False,
        )
        return CCTPResponse(**response_payload, operation=confirmed)
    except HTTPException as error:
        fail_operation(operation["operationId"], str(error.detail))
        raise
    except sqlite3.IntegrityError as error:
        fail_operation(operation["operationId"], "CCTP receipt replay blocked")
        raise HTTPException(status_code=409, detail="One of these CCTP receipts has already been consumed.") from error
    except Exception as error:
        fail_operation(operation["operationId"], "Internal CCTP confirmation error")
        logger.exception("CCTP confirmation failed for user_id=%s", user_id)
        raise HTTPException(status_code=502, detail="CCTP confirmation could not be verified. No budget credit was applied.") from error
