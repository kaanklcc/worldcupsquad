"""Current World Cup 2026 snapshot and matchday briefing endpoints."""

from fastapi import APIRouter, Depends, HTTPException
from typing import Optional

from ..agent.skills import suggest_lineup
from ..data import get_players, get_world_cup_snapshot
from ..models import Formation
from ..db import get_db_connection
from ..tournament_data import get_tournament_overview
from .squads import get_current_user_id

router = APIRouter(prefix="/api/worldcup", tags=["worldcup"])


@router.get("/snapshot")
async def world_cup_snapshot(topic: str = ""):
    """Return the dated FIFA roster and semifinal fixture snapshot."""
    return get_world_cup_snapshot(topic)


@router.get("/tournament")
async def tournament_overview(refresh: bool = False):
    """Return bracket, fixtures, groups and locally sourced squad details."""
    return await get_tournament_overview(force_refresh=refresh)


def _contribution_score(player) -> float:
    stats = player.world_cup_stats
    verified = stats and stats.data_status == "verified"
    return float(player.points) + ((stats.goals or 0) * 4 if verified else 0) + ((stats.assists or 0) * 3 if verified else 0)


@router.get("/matchday-brief")
async def matchday_brief(
    formation: Formation = "4-3-3",
    match_id: Optional[str] = None,
    user_id: int = Depends(get_current_user_id),
):
    """Build a dated, source-aware pre-match briefing from the local snapshot.

    This is intentionally deterministic: the fixture, lineup IDs, budget and
    provenance are server-owned. Gemini can discuss the brief after access is
    unlocked, but the dashboard never presents an unverified starting XI as a
    fact.
    """
    snapshot = get_world_cup_snapshot()
    matches = snapshot["matches"]
    match = next((item for item in matches if item["id"] == match_id), None) if match_id else None
    match = match or next((item for item in matches if item.get("status") == "fixture"), None)
    if not match:
        raise HTTPException(status_code=404, detail="No fixture is available in the current World Cup snapshot")

    conn = get_db_connection()
    row = conn.execute("SELECT budget FROM users WHERE id = ?", (user_id,)).fetchone()
    conn.close()
    if not row:
        raise HTTPException(status_code=404, detail="User not found")
    max_budget = float(row["budget"])

    proposal = suggest_lineup(
        formation,
        match_context=f"{match['homeTeam']} {match['awayTeam']}",
        strategy="attacking",
        max_budget=max_budget,
    )
    if proposal.get("error"):
        raise HTTPException(status_code=422, detail=proposal["error"])

    catalog = {player.id: player for player in get_players()}
    lineup_players = [catalog[player_id] for player_id in proposal["starting_player_ids"]]
    captain = max(lineup_players, key=_contribution_score)
    vice_candidates = [player for player in lineup_players if player.id != captain.id]
    vice_captain = max(vice_candidates, key=_contribution_score)
    unavailable_status = sorted({
        player.availability_status or "unknown"
        for player in lineup_players
        if (player.availability_status or "unknown") != "available"
    })

    return {
        "success": True,
        "briefType": "gaffer_matchday_brief",
        "match": match,
        "lineup": {
            "formation": formation,
            "playerIds": proposal["starting_player_ids"],
            "players": [player.model_dump() for player in lineup_players],
            "budgetUsed": proposal["budget_used"],
            "maxBudget": max_budget,
            "totalPoints": proposal["total_points"],
        },
        "captain": captain.model_dump(),
        "viceCaptain": vice_captain.model_dump(),
        "watchouts": [
            "Verify the official starting XI and late injury news before kickoff.",
            "Verified tournament goals/assists are used where FIFA exposes them; model xG is an application estimate.",
            f"The proposal uses {proposal['budget_used']:g}M of the server-side {max_budget:g}M budget.",
        ],
        "availabilitySignals": unavailable_status,
        "dataConfidence": "medium",
        "snapshotDate": snapshot["snapshotDate"],
        "dataQuality": snapshot["dataQuality"],
        "sourceUrls": [*snapshot["sourceUrls"], *snapshot["matchSourceUrls"]],
        "scenarios": [
            {"id": "chase", "label": "Chase the game", "formation": "4-3-3", "instruction": "Keep two wide outlets and prioritize verified attacking contribution."},
            {"id": "control", "label": "Control a lead", "formation": "3-5-2", "instruction": "Add a midfield connection and protect central progression."},
        ],
    }
