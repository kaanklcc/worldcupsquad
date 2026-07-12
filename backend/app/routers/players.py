"""
GET /api/players - Returns all World Cup players.
"""
from fastapi import APIRouter
from typing import List

from ..models import Player
from ..data import get_players


router = APIRouter()


@router.get("/api/players", response_model=List[Player])
async def get_all_players():
    """
    Get all available World Cup players.

    Returns a list of 28 players with their stats, prices, and premium analytics.
    """
    return get_players()