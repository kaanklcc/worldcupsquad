"""
POST /api/cctp - CCTP USDC bridging from Ethereum to Injective.
"""
from fastapi import APIRouter, HTTPException, Header, Depends
from typing import Optional

from ..models import CCTPRequest, CCTPResponse
from ..cctp_flow import get_cctp_flow
from .squads import get_current_user_id
from ..db import get_db_connection


router = APIRouter()


@router.post("/api/cctp", response_model=CCTPResponse)
async def bridge_usdc(
    request: CCTPRequest,
    x_payment: Optional[str] = Header(None, alias="X-Payment"),
    user_id: int = Depends(get_current_user_id)
):
    """
    Bridge USDC from source chain (default: Ethereum) to Injective using CCTP.
    """
    # Validate inputs
    if not request.walletAddress or request.walletAddress.strip() == "":
        raise HTTPException(status_code=400, detail="Wallet address is required")

    if request.amount != 20:
        raise HTTPException(status_code=400, detail="Amount must be exactly 20 USDC")

    if not request.sourceChain or request.sourceChain.strip() == "":
        raise HTTPException(status_code=400, detail="Source chain is required")

    try:
        cctp = get_cctp_flow()
        
        # Perform the bridge (real or simulated)
        result = await cctp.real_bridge(
            wallet_address=request.walletAddress,
            amount=request.amount,
            source_chain=request.sourceChain
        )

        if result["success"]:
            # Update user budget and log transaction in database
            conn = get_db_connection()
            cursor = conn.cursor()
            try:
                # 1. Fetch current budget
                cursor.execute("SELECT budget FROM users WHERE id = ?", (user_id,))
                user_row = cursor.fetchone()
                current_budget = user_row["budget"] if user_row else 100.0
                new_budget = current_budget + request.amount
                
                # 2. Update budget and cctp_used
                cursor.execute(
                    "UPDATE users SET budget = ?, cctp_used = 1 WHERE id = ?",
                    (new_budget, user_id)
                )
                
                # 3. Log CCTP bridge transaction
                cursor.execute(
                    """
                    INSERT INTO cctp_transactions (user_id, wallet_address, amount, source_chain, tx_hash)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (user_id, request.walletAddress, request.amount, request.sourceChain, result["final_tx_hash"])
                )
                conn.commit()
            except Exception as db_err:
                conn.rollback()
                conn.close()
                raise HTTPException(status_code=500, detail=f"Database update failed: {str(db_err)}")
            conn.close()

            return CCTPResponse(
                success=True,
                newBudgetBonus=request.amount,
                txHash=result["final_tx_hash"],
                message=result["message"],
                simulated=result.get("simulated", False)
            )
        else:
            raise HTTPException(status_code=500, detail="CCTP bridge failed")

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"CCTP bridge error: {str(e)}")