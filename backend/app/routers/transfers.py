"""
POST /api/transfers/execute - Execute a transfer via MCP.
"""
import logging

from fastapi import APIRouter, HTTPException, Depends, Header, Request
from typing import Optional

from ..models import TransferExecuteRequest, TransferExecuteResponse
from ..mcp.client import get_mcp_client
from ..data import get_players
from .squads import get_current_user_id
from ..db import get_db_connection
from ..access import require_ai_access
from ..config import settings
from ..operation_ledger import begin_operation, confirm_operation, fail_operation
from ..security import rate_limit


router = APIRouter()
logger = logging.getLogger(__name__)


@router.post("/api/transfers/execute", response_model=TransferExecuteResponse)
async def execute_transfer(
    body: TransferExecuteRequest,
    request: Request,
    idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key"),
    user_id: int = Depends(get_current_user_id)
):
    """
    Execute a player transfer via the MCP server and log the transaction in the database.
    """
    require_ai_access(user_id)
    rate_limit(request, "transfer-execute", subject=str(user_id), limit=20, window_seconds=60)
    # Validate players exist
    players = get_players()
    sell_player = next((p for p in players if p.id == body.sellPlayerId), None)
    buy_player = next((p for p in players if p.id == body.buyPlayerId), None)

    if not sell_player:
        raise HTTPException(
            status_code=404,
            detail=f"Sell player with ID '{body.sellPlayerId}' not found"
        )

    if not buy_player:
        raise HTTPException(
            status_code=404,
            detail=f"Buy player with ID '{body.buyPlayerId}' not found"
        )

    if not buy_player.isAvailable:
        raise HTTPException(
            status_code=400,
            detail=f"Player {buy_player.name} is not available for selection"
        )

    squad_ids = body.squadPlayerIds
    if len(squad_ids) != len(set(squad_ids)):
        raise HTTPException(status_code=400, detail="The current squad cannot contain duplicate player IDs")
    if body.sellPlayerId not in squad_ids:
        raise HTTPException(status_code=400, detail="The player being sold is not in the current squad")
    if body.buyPlayerId in squad_ids:
        raise HTTPException(status_code=400, detail="The replacement player is already in the current squad")
    if sell_player.position != buy_player.position:
        raise HTTPException(status_code=400, detail="Transfers must keep the same position")

    selected_players = [p for p in players if p.id in squad_ids]
    if len(selected_players) != len(squad_ids):
        raise HTTPException(status_code=400, detail="Current squad contains an unknown player")

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT 1 FROM squad_slots WHERE user_id = ? AND player_id = ? LIMIT 1",
        (user_id, body.sellPlayerId),
    )
    if not cursor.fetchone():
        conn.close()
        raise HTTPException(status_code=400, detail="The player being sold is not persisted in the current squad")
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

    operation, replay = begin_operation(
        user_id=user_id,
        action_type="execute_transfer",
        provider="mcp",
        network=settings.x402_network,
        idempotency_key=idempotency_key,
        payload={
            "sellPlayerId": body.sellPlayerId,
            "buyPlayerId": body.buyPlayerId,
            "squadPlayerIds": body.squadPlayerIds,
            "reasoning": body.reasoning,
            "projectedCost": replacement_cost,
        },
    )
    if replay:
        if operation["status"] == "confirmed" and operation["receipt"]:
            return TransferExecuteResponse(**operation["receipt"], operation=operation)
        raise HTTPException(status_code=409, detail=f"Transfer operation is {operation['status']}; create a new intent to retry")

    try:
        # Call MCP server's apply_transfer tool
        mcp_client = get_mcp_client()
        result = await mcp_client.call_tool(
            "apply_transfer",
            {
                "sell_player_id": body.sellPlayerId,
                "buy_player_id": body.buyPlayerId,
                "reasoning": body.reasoning
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
                    "UPDATE squad_slots SET player_id = ? WHERE user_id = ? AND player_id = ?",
                    (body.buyPlayerId, user_id, body.sellPlayerId),
                )
                if cursor.rowcount != 1:
                    raise HTTPException(status_code=409, detail="The squad changed before this transfer was confirmed")
                cursor.execute(
                    """
                    INSERT INTO transfers (user_id, sell_player_id, buy_player_id, reasoning, tx_hash)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (user_id, body.sellPlayerId, body.buyPlayerId, body.reasoning, result["tx_hash"])
                )
                conn.commit()
            except HTTPException:
                conn.rollback()
                conn.close()
                raise
            except Exception as db_err:
                conn.rollback()
                conn.close()
                logger.exception("Transfer database update failed for user_id=%s", user_id)
                raise HTTPException(status_code=500, detail="The transfer could not be persisted. Please retry with a fresh proposal.") from db_err
            conn.close()

            response_payload = {
                "success": True,
                "txHash": result["tx_hash"],
                "message": (
                    f"Transfer executed successfully via MCP: "
                    f"Sold {sell_player.name} → Bought {buy_player.name}"
                ),
                "mcpReceipt": result,
                "simulated": result.get("simulated", False),
            }
            confirmed = confirm_operation(
                operation["operationId"],
                receipt=response_payload,
                tx_hash=result["tx_hash"],
                simulated=result.get("simulated", False),
            )
            return TransferExecuteResponse(**response_payload, operation=confirmed)
        else:
            raise HTTPException(status_code=500, detail=result.get("error", "Transfer failed"))

    except HTTPException as error:
        fail_operation(operation["operationId"], str(error.detail))
        raise
    except Exception as error:
        fail_operation(operation["operationId"], "Internal transfer execution error")
        logger.exception("Transfer execution failed for user_id=%s", user_id)
        raise HTTPException(status_code=500, detail="The transfer could not be executed. Please try again.") from error
