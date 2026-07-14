"""
GET /api/players - Returns all World Cup players.
"""
from fastapi import APIRouter
from typing import List

from ..db import get_db_connection
from ..models import Player, PremiumStats


router = APIRouter()


@router.get("/api/players", response_model=List[Player])
async def get_all_players():
    """
    Get all available World Cup players from the SQLite database.
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM players")
    rows = cursor.fetchall()
    conn.close()
    
    players_list = []
    for r in rows:
        players_list.append(Player(
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
        ))
    return players_list