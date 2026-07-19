"""
POST /api/agent - membership/x402-gated AI football consultant.
"""
import logging

from fastapi import APIRouter, HTTPException, Request, Depends

from ..models import AgentRequest, AgentResponse
from ..agent.gemini_client import get_agent_client
from ..access import LOCKED_CAPABILITIES_MESSAGE, get_access_status
from ..db import get_db_connection
from .squads import get_current_user_id
from ..security import rate_limit


router = APIRouter()
logger = logging.getLogger(__name__)


@router.post("/api/agent", response_model=AgentResponse)
async def chat_with_agent(
    agent_request: AgentRequest,
    request: Request,
    user_id: int = Depends(get_current_user_id)
):
    """
    Chat with WCAI. No prompt is sent to Gemini before a server-side
    membership or x402 Match Pass has been activated.
    """
    if not agent_request.prompt.strip():
        raise HTTPException(status_code=400, detail="Prompt is required")

    access = get_access_status(user_id)
    if not access["hasAiAccess"]:
        return AgentResponse(
            message=LOCKED_CAPABILITIES_MESSAGE,
            suggestedAction=None,
            isPremium=False,
            paymentVerified=False,
            provider="locked",
            accessRequired=True,
            membershipActive=False,
        )

    # Protect the public Gemini quota after entitlement has been established.
    rate_limit(request, "agent-user", subject=str(user_id), limit=30, window_seconds=60)
    rate_limit(request, "agent-ip", limit=60, window_seconds=60)

    conn = get_db_connection()
    user_row = conn.execute("SELECT budget FROM users WHERE id = ?", (user_id,)).fetchone()
    conn.close()
    if not user_row:
        raise HTTPException(status_code=404, detail="User not found")
    max_budget = float(user_row["budget"])

    try:
        # Get agent client and process the request
        agent_client = get_agent_client()
        response = await agent_client.chat(
            prompt=agent_request.prompt,
            squad_player_ids=agent_request.squadPlayerIds,
            is_premium=True,
            x402_verified=access["accessSource"] == "x402_verified",
            formation=agent_request.formation,
            max_budget=max_budget,
            analysis_mode=agent_request.analysisMode,
        )

        response.isPremium = True
        response.paymentVerified = access["accessSource"] == "x402_verified"
        response.accessRequired = False
        response.membershipActive = access["membershipActive"]
        response.accessSource = access["accessSource"]

        return response

    except Exception:
        logger.exception("Agent processing failed for user_id=%s", user_id)
        raise HTTPException(status_code=502, detail="The AI provider could not complete this request. Please try again.")
