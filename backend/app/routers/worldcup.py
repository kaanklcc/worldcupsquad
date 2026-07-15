"""Current World Cup 2026 snapshot endpoints for the fan dashboard."""

from fastapi import APIRouter

from ..data import get_world_cup_snapshot

router = APIRouter(prefix="/api/worldcup", tags=["worldcup"])


@router.get("/snapshot")
async def world_cup_snapshot(topic: str = ""):
    """Return the dated FIFA roster and semifinal fixture snapshot."""
    return get_world_cup_snapshot(topic)
