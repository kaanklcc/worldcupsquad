from fastapi import APIRouter, HTTPException, Header, Depends, status
from pydantic import BaseModel
from typing import List, Optional, Literal

from ..db import get_db_connection
from ..models import SquadSlot, Player, PremiumStats, Formation
from ..data import get_players
from .auth import decode_token

router = APIRouter(prefix="/api/squad", tags=["squad"])

# ─── Schemas ───────────────────────────────────────────────────────────────────

class SquadSaveRequest(BaseModel):
    budget: float
    cctpUsed: bool
    formation: Formation = '4-3-3'
    squad: List[SquadSlot]
    bench: List[SquadSlot]

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
    cursor.execute("SELECT * FROM players WHERE id = ?", (player_id,))
    r = cursor.fetchone()
    if not r:
        return None
    return Player(
        id=r["id"],
        name=r["name"],
        position=r["position"],
        team=r["team"],
        price=r["price"],
        isAvailable=bool(r["is_available"]),
        points=r["points"],
        premium_stats=PremiumStats(
            xg_per_game=r["xg_per_game"],
            injury_risk=r["injury_risk"],
            scout_note=r["scout_note"]
        ),
        flag=r["flag"],
        number=r["number"]
    )

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
