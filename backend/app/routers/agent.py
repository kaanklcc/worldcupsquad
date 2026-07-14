"""
POST /api/agent - AI-powered football consultant with x402 payment gating.
"""
from fastapi import APIRouter, HTTPException, Header, Request, Depends
from typing import Optional

from ..models import AgentRequest, AgentResponse
from ..agent.gemini_client import get_agent_client
from ..x402 import get_x402_verifier
from .squads import get_current_user_id


router = APIRouter()


@router.post("/api/agent", response_model=AgentResponse)
async def chat_with_agent(
    request: Request,
    x_payment: Optional[str] = Header(None, alias="X-Payment"),
    x_payment_receipt: Optional[str] = Header(None, alias="X-Payment-Receipt"),
    user_id: int = Depends(get_current_user_id)
):
    """
    Chat with the Auto-Gaffer AI consultant.

    This endpoint:
    1. Verifies x402 payment receipt for premium access
    2. Calls the Gemini LLM with tool-calling capabilities
    3. Returns tactical advice, player analysis, or transfer suggestions

    **Free Tier:**
    - Basic player information
    - General squad overview
    - Position rankings

    **Premium Tier (via x402):**
    - Deep scouting reports with xG data
    - Injury risk analysis
    - AI-powered transfer suggestions with executable actions
    - Advanced squad diagnostics

    The agent uses Gemini function-calling to invoke skills like:
    - search_player, rank_position, analyze_squad
    - suggest_transfer, validate_budget, get_player_report
    """
    try:
        body = await request.json()
        agent_request = AgentRequest(**body)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid request body: {str(e)}")

    # Validate prompt
    if not agent_request.prompt or agent_request.prompt.strip() == "":
        raise HTTPException(status_code=400, detail="Prompt is required")

    try:
        # Verify x402 payment for premium access
        verifier = get_x402_verifier()
        x402_verified = await verifier.verify_premium_access(
            has_paid_x402=agent_request.hasPaidX402,
            receipt=x_payment_receipt,
            payment_header=x_payment
        )

        # Determine access level
        is_premium = agent_request.hasPaidX402 and x402_verified

        # Get agent client and process the request
        agent_client = get_agent_client()
        response = await agent_client.chat(
            prompt=agent_request.prompt,
            squad_player_ids=agent_request.squadPlayerIds,
            is_premium=is_premium,
            x402_verified=x402_verified
        )

        # Ensure payment status is reflected in the response
        response.paymentVerified = x402_verified

        return response

    except Exception as e:
        print(f"Agent error: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Agent processing error: {str(e)}"
        )