"""
POST /api/transfers/execute - Execute a transfer via MCP.
"""
from fastapi import APIRouter, HTTPException

from ..models import TransferExecuteRequest, TransferExecuteResponse
from ..mcp.client import get_mcp_client
from ..data import get_players


router = APIRouter()


@router.post("/api/transfers/execute", response_model=TransferExecuteResponse)
async def execute_transfer(request: TransferExecuteRequest):
    """
    Execute a player transfer via the MCP server.

    This endpoint:
    1. Validates that both players exist
    2. Calls the MCP server's apply_transfer tool
    3. Returns the transaction hash and receipt

    The transfer is executed on-chain (or simulated) and the result
    is returned as an MCP receipt that can be used for verification.
    """
    # Validate players exist
    players = get_players()
    sell_player = next((p for p in players if p.id == request.sellPlayerId), None)
    buy_player = next((p for p in players if p.id == request.buyPlayerId), None)

    if not sell_player:
        raise HTTPException(
            status_code=404,
            detail=f"Sell player with ID '{request.sellPlayerId}' not found"
        )

    if not buy_player:
        raise HTTPException(
            status_code=404,
            detail=f"Buy player with ID '{request.buyPlayerId}' not found"
        )

    if not buy_player.isAvailable:
        raise HTTPException(
            status_code=400,
            detail=f"Player {buy_player.name} is not available for selection"
        )

    try:
        # Call MCP server's apply_transfer tool
        mcp_client = get_mcp_client()
        result = await mcp_client.call_tool(
            "apply_transfer",
            {
                "sell_player_id": request.sellPlayerId,
                "buy_player_id": request.buyPlayerId,
                "reasoning": request.reasoning
            }
        )

        if result.get("success"):
            return TransferExecuteResponse(
                success=True,
                txHash=result["tx_hash"],
                message=(
                    f"Transfer executed successfully via MCP: "
                    f"Sold {sell_player.name} → Bought {buy_player.name}"
                ),
                mcpReceipt=result
            )
        else:
            raise HTTPException(status_code=500, detail=result.get("error", "Transfer failed"))

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Transfer execution error: {str(e)}")