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

    squad_ids = list(dict.fromkeys(request.squadPlayerIds))
    if request.sellPlayerId not in squad_ids:
        raise HTTPException(status_code=400, detail="The player being sold is not in the current squad")
    if request.buyPlayerId in squad_ids:
        raise HTTPException(status_code=400, detail="The replacement player is already in the current squad")
    if sell_player.position != buy_player.position:
        raise HTTPException(status_code=400, detail="Transfers must keep the same position")

    selected_players = [p for p in players if p.id in squad_ids]
    if len(selected_players) != len(squad_ids):
        raise HTTPException(status_code=400, detail="Current squad contains an unknown player")

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT budget FROM users WHERE id = ?", (user_id,))
    user_row = cursor.fetchone()
    if not user_row:
        conn.close()
        raise HTTPException(status_code=404, detail="User not found")

    current_cost = sum(player.price for player in selected_players)
    replacement_cost = current_cost - sell_player.price + buy_player.price
    if replacement_cost > user_row["budget"]:
        conn.close()
        raise HTTPException(status_code=400, detail="Transfer would exceed the squad budget")
    conn.close()

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
                # The UI saves its current snapshot before this call. Replace
                # the sold player in that persisted snapshot as part of the
                # MCP-backed operation, keeping reloads consistent.
                cursor.execute(
                    "SELECT id FROM squad_slots WHERE user_id = ? AND player_id = ? ORDER BY is_bench LIMIT 1",
                    (user_id, request.sellPlayerId)
                )
                slot = cursor.fetchone()
                if slot:
                    cursor.execute(
                        "UPDATE squad_slots SET player_id = ? WHERE id = ?",
                        (request.buyPlayerId, slot["id"])
                    )
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
                mcpReceipt=result,
                simulated=result.get("simulated", False)
            )
        else:
            raise HTTPException(status_code=500, detail=result.get("error", "Transfer failed"))

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Transfer execution error: {str(e)}")
