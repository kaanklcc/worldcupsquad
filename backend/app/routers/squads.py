from fastapi import APIRouter, HTTPException, Header, Depends, status
from pydantic import BaseModel
from typing import List, Optional, Literal

from ..db import get_db_connection
from ..models import SquadSlot, Player, PremiumStats
from .auth import decode_token

router = APIRouter(prefix="/api/squad", tags=["squad"])

# ─── Schemas ───────────────────────────────────────────────────────────────────

class SquadSaveRequest(BaseModel):
    budget: float
    cctpUsed: bool
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
    
    # 1. Fetch user budget and cctp state
    cursor.execute("SELECT budget, cctp_used FROM users WHERE id = ?", (user_id,))
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
        "squad": squad_slots,
        "bench": bench_slots
    }

@router.post("/save")
async def save_squad(req: SquadSaveRequest, user_id: int = Depends(get_current_user_id)):
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # 1. Update user budget parameters
        cursor.execute(
            "UPDATE users SET budget = ?, cctp_used = ? WHERE id = ?",
            (req.budget, 1 if req.cctpUsed else 0, user_id)
        )
        
        # 2. Delete all existing squad slots
        cursor.execute("DELETE FROM squad_slots WHERE user_id = ?", (user_id,))
        
        # 3. Insert new squad slots
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
    except Exception as e:
        conn.rollback()
        conn.close()
        raise HTTPException(status_code=500, detail=f"Failed to save squad slots: {str(e)}")
        
    conn.close()
    return {"success": True, "message": "Squad saved successfully to database."}
