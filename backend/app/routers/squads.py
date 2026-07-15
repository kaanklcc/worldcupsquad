from fastapi import APIRouter, HTTPException, Header, Depends, status
from pydantic import BaseModel
from typing import List, Optional, Literal

from ..db import get_db_connection
from ..models import (
    SquadSlot,
    Player,
    Formation,
    LineupApplyRequest,
    LineupApplyResponse,
)
from ..data import get_players
from ..access import require_ai_access
from ..config import settings
from ..operation_ledger import begin_operation, confirm_operation, fail_operation
from .auth import decode_token

router = APIRouter(prefix="/api/squad", tags=["squad"])

# ─── Schemas ───────────────────────────────────────────────────────────────────

class SquadSaveRequest(BaseModel):
    budget: float
    cctpUsed: bool
    formation: Formation = '4-3-3'
    squad: List[SquadSlot]
    bench: List[SquadSlot]


FORMATION_COUNTS = {
    '4-3-3': {'GK': 1, 'DF': 4, 'MF': 3, 'FW': 3},
    '4-4-2': {'GK': 1, 'DF': 4, 'MF': 4, 'FW': 2},
    '3-5-2': {'GK': 1, 'DF': 3, 'MF': 5, 'FW': 2},
    '4-2-3-1': {'GK': 1, 'DF': 4, 'MF': 5, 'FW': 1},
    '5-3-2': {'GK': 1, 'DF': 5, 'MF': 3, 'FW': 2},
}

# ─── Auth Dependency Helper ────────────────────────────────────────────────────

def get_current_user_id(authorization: Optional[str] = Header(None)) -> int:
    if not authorization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authorization token is missing."
        )
    payload = decode_token(authorization)
    return payload["user_id"]

# ─── Helper to fetch player model ──────────────────────────────────────────────

def fetch_player_by_id(cursor, player_id: Optional[str]) -> Optional[Player]:
    if not player_id:
        return None
    return next((player for player in get_players() if player.id == player_id), None)

# ─── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("/load")
async def load_squad(user_id: int = Depends(get_current_user_id)):
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # 1. Fetch user budget, CCTP state, and formation
    cursor.execute("SELECT budget, cctp_used, formation FROM users WHERE id = ?", (user_id,))
    user_row = cursor.fetchone()
    if not user_row:
        conn.close()
        raise HTTPException(status_code=404, detail="User not found")

    budget = user_row["budget"]
    cctp_used = bool(user_row["cctp_used"])
    
    # 2. Fetch squad slots
    cursor.execute("SELECT * FROM squad_slots WHERE user_id = ?", (user_id,))
    slot_rows = cursor.fetchall()
    
    squad_slots = []
    bench_slots = []
    
    for r in slot_rows:
        player_obj = fetch_player_by_id(cursor, r["player_id"])
        slot = SquadSlot(
            position=r["position"],
            slotIndex=r["slot_index"],
            player=player_obj
        )
        if r["is_bench"]:
            bench_slots.append(slot)
        else:
            squad_slots.append(slot)
            
    conn.close()
    
    return {
        "success": True,
        "budget": budget,
        "cctpUsed": cctp_used,
        "formation": user_row["formation"] or "4-3-3",
        "squad": squad_slots,
        "bench": bench_slots
    }

@router.post("/save")
async def save_squad(req: SquadSaveRequest, user_id: int = Depends(get_current_user_id)):
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # Treat the database/catalog as the source of truth. The nested Player
        # objects sent by the browser are display data, not authoritative data.
        cursor.execute("SELECT budget, cctp_used FROM users WHERE id = ?", (user_id,))
        user_row = cursor.fetchone()
        if not user_row:
            raise HTTPException(status_code=404, detail="User not found")

        catalog = {player.id: player for player in get_players()}
        all_slots = [*req.squad, *req.bench]
        expected_counts = FORMATION_COUNTS[req.formation]
        if len(req.squad) != sum(expected_counts.values()):
            raise HTTPException(
                status_code=400,
                detail=f"A {req.formation} squad must contain exactly {sum(expected_counts.values())} starting slots",
            )
        actual_counts = {position: 0 for position in expected_counts}
        starting_keys = set()
        for slot in req.squad:
            if slot.slotIndex < 0:
                raise HTTPException(status_code=400, detail="Slot indexes cannot be negative")
            key = (slot.position, slot.slotIndex)
            if key in starting_keys:
                raise HTTPException(status_code=400, detail="Starting slots cannot be duplicated")
            starting_keys.add(key)
            actual_counts[slot.position] += 1
        if actual_counts != expected_counts:
            raise HTTPException(
                status_code=400,
                detail=f"Starting slots do not match {req.formation}: {actual_counts}",
            )
        bench_keys = set()
        for slot in req.bench:
            if slot.slotIndex < 10:
                raise HTTPException(status_code=400, detail="Bench slot indexes must start at 10")
            key = (slot.position, slot.slotIndex)
            if key in bench_keys:
                raise HTTPException(status_code=400, detail="Bench slots cannot be duplicated")
            bench_keys.add(key)
        selected_ids = [slot.player.id for slot in all_slots if slot.player]

        if len(selected_ids) != len(set(selected_ids)):
            raise HTTPException(status_code=400, detail="A player cannot occupy more than one slot")

        selected_players = []
        for slot in all_slots:
            if not slot.player:
                continue
            player = catalog.get(slot.player.id)
            if not player:
                raise HTTPException(status_code=400, detail=f"Unknown player: {slot.player.id}")
            if player.position != slot.position:
                raise HTTPException(status_code=400, detail=f"{player.name} cannot fill a {slot.position} slot")
            if not player.isAvailable:
                raise HTTPException(status_code=400, detail=f"{player.name} is not available for selection")
            selected_players.append(player)

        total_cost = sum(player.price for player in selected_players)
        if total_cost > user_row["budget"]:
            raise HTTPException(
                status_code=400,
                detail=f"Squad cost ({total_cost:g}M) exceeds the {user_row['budget']:g}M budget"
            )

        # cctpUsed and budget are intentionally not taken from the request;
        # only the CCTP endpoint may mutate the backing state.
        cursor.execute(
            "UPDATE users SET formation = ? WHERE id = ?",
            (req.formation, user_id)
        )
        # Delete all existing squad slots.
        cursor.execute("DELETE FROM squad_slots WHERE user_id = ?", (user_id,))
        
        # Insert the new slot layout using only catalog IDs.
        for s in req.squad:
            player_id = s.player.id if s.player else None
            cursor.execute(
                """
                INSERT INTO squad_slots (user_id, position, slot_index, player_id, is_bench)
                VALUES (?, ?, ?, ?, 0)
                """,
                (user_id, s.position, s.slotIndex, player_id)
            )
            
        for s in req.bench:
            player_id = s.player.id if s.player else None
            cursor.execute(
                """
                INSERT INTO squad_slots (user_id, position, slot_index, player_id, is_bench)
                VALUES (?, ?, ?, ?, 1)
                """,
                (user_id, s.position, s.slotIndex, player_id)
            )
            
        conn.commit()
    except HTTPException:
        conn.rollback()
        conn.close()
        raise
    except Exception as e:
        conn.rollback()
        conn.close()
        raise HTTPException(status_code=500, detail=f"Failed to save squad slots: {str(e)}")
        
    conn.close()
    return {"success": True, "message": "Squad saved successfully to database."}


@router.post("/apply-lineup", response_model=LineupApplyResponse)
async def apply_lineup(
    req: LineupApplyRequest,
    idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key"),
    user_id: int = Depends(get_current_user_id),
):
    """Apply a confirmed AI lineup using catalog IDs only."""
    require_ai_access(user_id)
    counts = FORMATION_COUNTS[req.formation]
    catalog = {player.id: player for player in get_players()}
    all_ids = [*req.startingPlayerIds, *req.benchPlayerIds]

    if len(set(all_ids)) != len(all_ids):
        raise HTTPException(status_code=400, detail="A player cannot occupy more than one slot")

    starting_players = []
    for player_id in req.startingPlayerIds:
        player = catalog.get(player_id)
        if not player:
            raise HTTPException(status_code=400, detail=f"Unknown player: {player_id}")
        if not player.isAvailable:
            raise HTTPException(status_code=400, detail=f"{player.name} is not available")
        starting_players.append(player)

    position_counts = {position: 0 for position in counts}
    for player in starting_players:
        position_counts[player.position] += 1
    if position_counts != counts:
        raise HTTPException(
            status_code=400,
            detail=f"Lineup does not match {req.formation}: {position_counts}",
        )

    bench_players = []
    for player_id in req.benchPlayerIds:
        player = catalog.get(player_id)
        if not player:
            raise HTTPException(status_code=400, detail=f"Unknown bench player: {player_id}")
        if not player.isAvailable:
            raise HTTPException(status_code=400, detail=f"{player.name} is not available")
        bench_players.append(player)

    total_cost = sum(player.price for player in [*starting_players, *bench_players])
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT budget FROM users WHERE id = ?", (user_id,))
        user_row = cursor.fetchone()
        if not user_row:
            raise HTTPException(status_code=404, detail="User not found")
        if total_cost > user_row["budget"]:
            raise HTTPException(
                status_code=400,
                detail=f"Lineup cost ({total_cost:g}M) exceeds the {user_row['budget']:g}M budget",
            )
    except HTTPException:
        conn.rollback()
        raise
    except Exception as error:
        conn.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to apply lineup: {error}")
    finally:
        conn.close()

    operation, replay = begin_operation(
        user_id=user_id,
        action_type="apply_lineup",
        provider="mcp",
        network=settings.x402_network,
        idempotency_key=idempotency_key,
        payload={
            "formation": req.formation,
            "startingPlayerIds": req.startingPlayerIds,
            "benchPlayerIds": req.benchPlayerIds,
            "reasoning": req.reasoning,
            "budget": total_cost,
        },
    )
    if replay:
        if operation["status"] == "confirmed" and operation["receipt"]:
            return LineupApplyResponse(**operation["receipt"], operation=operation)
        raise HTTPException(status_code=409, detail=f"Lineup operation is {operation['status']}; create a new intent to retry")

    try:
        # The action intent is now durable. A retry with the same key returns
        # its receipt instead of replaying an MCP mutation.
        from ..mcp.client import get_mcp_client
        mcp_result = await get_mcp_client().call_tool(
            "apply_lineup",
            {
                "formation": req.formation,
                "starting_player_ids": req.startingPlayerIds,
                "bench_player_ids": req.benchPlayerIds,
                "reasoning": req.reasoning,
            },
        )
        if not mcp_result.get("success"):
            raise HTTPException(status_code=502, detail=mcp_result.get("error", "MCP lineup validation failed"))

        conn = get_db_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("UPDATE users SET formation = ? WHERE id = ?", (req.formation, user_id))
            cursor.execute("DELETE FROM squad_slots WHERE user_id = ?", (user_id,))

            position_indices = {position: 0 for position in counts}
            for player in starting_players:
                index = position_indices[player.position]
                cursor.execute(
                    """
                    INSERT INTO squad_slots (user_id, position, slot_index, player_id, is_bench)
                    VALUES (?, ?, ?, ?, 0)
                    """,
                    (user_id, player.position, index, player.id),
                )
                position_indices[player.position] += 1

            bench_indices = {"GK": 10, "DF": 10, "MF": 10, "FW": 10}
            for player in bench_players:
                index = bench_indices[player.position]
                cursor.execute(
                    """
                    INSERT INTO squad_slots (user_id, position, slot_index, player_id, is_bench)
                    VALUES (?, ?, ?, ?, 1)
                    """,
                    (user_id, player.position, index, player.id),
                )
                bench_indices[player.position] += 1
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

        response_payload = {
            "success": True,
            "message": f"{req.formation} AI lineup applied after explicit confirmation.",
            "formation": req.formation,
            "appliedPlayerIds": all_ids,
            "mcpReceipt": mcp_result,
            "simulated": mcp_result.get("simulated", False),
        }
        confirmed = confirm_operation(
            operation["operationId"],
            receipt=response_payload,
            tx_hash=mcp_result.get("tx_hash"),
            simulated=mcp_result.get("simulated", False),
        )
        return LineupApplyResponse(**response_payload, operation=confirmed)
    except HTTPException as error:
        fail_operation(operation["operationId"], str(error.detail))
        raise
    except Exception as error:
        fail_operation(operation["operationId"], str(error))
        raise HTTPException(status_code=500, detail=f"Failed to apply lineup: {error}")
