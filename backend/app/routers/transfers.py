"""
POST /api/transfers/execute - Execute a transfer via MCP.
"""
from fastapi import APIRouter, HTTPException, Depends

from ..models import TransferExecuteRequest, TransferExecuteResponse
from ..mcp.client import get_mcp_client
from ..data import get_players
from .squads import get_current_user_id
from ..db import get_db_connection


router = APIRouter()


@router.post("/api/transfers/execute", response_model=TransferExecuteResponse)
async def execute_transfer(
    request: TransferExecuteRequest,
    user_id: int = Depends(get_current_user_id)
):
    """
    Execute a player transfer via the MCP server and log the transaction in the database.
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
            # Log completed transfer transaction in database
            conn = get_db_connection()
            cursor = conn.cursor()
            try:
                cursor.execute(
                    """
                    INSERT INTO transfers (user_id, sell_player_id, buy_player_id, reasoning, tx_hash)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (user_id, request.sellPlayerId, request.buyPlayerId, request.reasoning, result["tx_hash"])
                )
                conn.commit()
            except Exception as db_err:
                conn.rollback()
                conn.close()
                raise HTTPException(status_code=500, detail=f"Database logging failed: {str(db_err)}")
            conn.close()

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