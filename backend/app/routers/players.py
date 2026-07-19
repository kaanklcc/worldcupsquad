"""Player catalog endpoints backed by the current World Cup snapshot."""

from fastapi import APIRouter, Path
from typing import List

from ..data import apply_live_player_totals, get_data_metadata, get_player_intel, get_players
from ..live_stats import get_live_player_totals
from ..config import settings
from ..models import Player

router = APIRouter()


async def _refresh_live_stats() -> None:
    if settings.live_stats_enabled:
        apply_live_player_totals(await get_live_player_totals())


@router.get("/api/players", response_model=List[Player])
async def get_all_players():
    """Return all official squads with a one-minute refreshable goal/assist overlay."""
    await _refresh_live_stats()
    return get_players()


@router.get("/api/players/meta")
async def get_players_metadata():
    """Return the snapshot date and official source URLs used by the catalog."""
    await _refresh_live_stats()
    return get_data_metadata()


@router.get("/api/players/{player_id}/intel")
async def get_player_intelligence(player_id: str = Path(..., min_length=1, max_length=80, pattern=r"^[A-Za-z0-9_-]+$")):
    """Return one player's source-aware scouting card payload."""
    await _refresh_live_stats()
    intel = get_player_intel(player_id)
    if not intel:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Player not found in the current roster snapshot")
    return intel
