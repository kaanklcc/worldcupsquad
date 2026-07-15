"""Player catalog endpoints backed by the current World Cup snapshot."""

from fastapi import APIRouter
from typing import List

from ..data import get_data_metadata, get_players
from ..models import Player

router = APIRouter()


@router.get("/api/players", response_model=List[Player])
async def get_all_players():
    """Return the 2026 semi-finalist roster catalog with provenance metadata."""
    return get_players()


@router.get("/api/players/meta")
async def get_players_metadata():
    """Return the snapshot date and official source URLs used by the catalog."""
    return get_data_metadata()
