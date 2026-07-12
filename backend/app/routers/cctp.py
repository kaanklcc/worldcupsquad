"""
POST /api/cctp - CCTP USDC bridging from Ethereum to Injective.
"""
from fastapi import APIRouter, HTTPException, Header
from typing import Optional

from ..models import CCTPRequest, CCTPResponse
from ..cctp_flow import get_cctp_flow


router = APIRouter()


@router.post("/api/cctp", response_model=CCTPResponse)
async def bridge_usdc(
    request: CCTPRequest,
    x_payment: Optional[str] = Header(None, alias="X-Payment")
):
    """
    Bridge USDC from source chain (default: Ethereum) to Injective using CCTP.

    This endpoint:
    1. Validates the request parameters
    2. Performs a CCTP burn → attest → mint flow
    3. Returns the transaction hash and budget increase

    For demo/local development without credentials, this returns a realistic simulation.
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