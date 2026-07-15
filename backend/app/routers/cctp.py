"""
POST /api/cctp - CCTP USDC bridging from Ethereum to Injective.
"""
from fastapi import APIRouter, HTTPException, Header, Depends
from typing import Optional

from ..models import CCTPRequest, CCTPResponse
from ..cctp_flow import get_cctp_flow
from .squads import get_current_user_id
from ..db import get_db_connection
from ..access import require_membership, validate_wallet
from ..config import settings
from ..operation_ledger import begin_operation, confirm_operation, fail_operation


router = APIRouter()


@router.post("/api/cctp", response_model=CCTPResponse)
async def bridge_usdc(
    request: CCTPRequest,
    x_payment: Optional[str] = Header(None, alias="X-Payment"),
    idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key"),
    user_id: int = Depends(get_current_user_id)
):
    """
    Bridge USDC from source chain (default: Ethereum) to Injective using CCTP.
    """
    access = require_membership(user_id)
    # Validate inputs
    if not request.walletAddress or request.walletAddress.strip() == "":
        raise HTTPException(status_code=400, detail="Wallet address is required")

    wallet_address = validate_wallet(request.walletAddress)
    if not access.get("walletAddress"):
        raise HTTPException(status_code=400, detail="Save an Injective wallet in your membership profile before using CCTP")
    if access["walletAddress"] != wallet_address:
        raise HTTPException(status_code=400, detail="CCTP wallet must match the wallet saved in your membership profile")

    if request.amount != 20:
        raise HTTPException(status_code=400, detail="Amount must be exactly 20 USDC")

    if not request.sourceChain or request.sourceChain.strip() == "":
        raise HTTPException(status_code=400, detail="Source chain is required")

    try:
        # The bridge is a one-time budget boost. Enforce this on the server as
        # well as in the UI so repeated requests cannot mint budget twice.
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT budget, cctp_used FROM users WHERE id = ?", (user_id,))
        user_row = cursor.fetchone()
        conn.close()

        if not user_row:
            raise HTTPException(status_code=404, detail="User not found")

        operation, replay = begin_operation(
            user_id=user_id,
            action_type="acquire_cctp_backing",
            provider="cctp",
            network=settings.x402_network,
            idempotency_key=idempotency_key,
            payload={
                "walletAddress": wallet_address,
                "amount": request.amount,
                "sourceChain": request.sourceChain,
            },
        )
        if replay:
            if operation["status"] == "confirmed" and operation["receipt"]:
                return CCTPResponse(**operation["receipt"], operation=operation)
            raise HTTPException(status_code=409, detail=f"CCTP operation is {operation['status']}; create a new intent to retry")
        if user_row["cctp_used"]:
            fail_operation(operation["operationId"], "CCTP backing has already been acquired")
            raise HTTPException(status_code=409, detail="CCTP backing has already been acquired")

        cctp = get_cctp_flow()
        
        # Perform the bridge (real or simulated)
        result = await cctp.real_bridge(
            wallet_address=wallet_address,
            amount=request.amount,
            source_chain=request.sourceChain
        )

        if result["success"]:
            # Update user budget and log transaction in database
            conn = get_db_connection()
            cursor = conn.cursor()
            try:
                # 1. Use the current server-side budget, never a client value.
                current_budget = user_row["budget"]
                new_budget = current_budget + request.amount
                
                # 2. Update budget and cctp_used
                cursor.execute(
                    "UPDATE users SET budget = ?, cctp_used = 1 WHERE id = ? AND cctp_used = 0",
                    (new_budget, user_id)
                )
                if cursor.rowcount != 1:
                    conn.rollback()
                    raise HTTPException(status_code=409, detail="CCTP backing has already been acquired")
                
                # 3. Log CCTP bridge transaction
                cursor.execute(
                    """
                    INSERT INTO cctp_transactions (user_id, wallet_address, amount, source_chain, tx_hash)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (user_id, wallet_address, request.amount, request.sourceChain, result["final_tx_hash"])
                )
                conn.commit()
            except HTTPException:
                conn.rollback()
                conn.close()
                raise
            except Exception as db_err:
                conn.rollback()
                conn.close()
                raise HTTPException(status_code=500, detail=f"Database update failed: {str(db_err)}")
            conn.close()

            response_payload = {
                "success": True,
                "newBudgetBonus": request.amount,
                "txHash": result["final_tx_hash"],
                "message": result["message"],
                "simulated": result.get("simulated", False),
            }
            confirmed = confirm_operation(
                operation["operationId"],
                receipt=response_payload,
                tx_hash=result["final_tx_hash"],
                simulated=result.get("simulated", False),
            )
            return CCTPResponse(**response_payload, operation=confirmed)
        else:
            raise HTTPException(status_code=500, detail="CCTP bridge failed")

    except HTTPException as error:
        if "operation" in locals():
            fail_operation(operation["operationId"], str(error.detail))
        raise
    except Exception as e:
        if "operation" in locals():
            fail_operation(operation["operationId"], str(e))
        raise HTTPException(status_code=500, detail=f"CCTP bridge error: {str(e)}")
