"""Current World Cup 2026 snapshot and matchday briefing endpoints."""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from typing import Optional

from ..agent.skills import suggest_lineup
from ..data import apply_live_player_totals, get_players, get_world_cup_snapshot
from ..live_stats import get_live_player_totals
from ..models import Formation
from ..db import get_db_connection
from ..tournament_data import get_tournament_overview
from .squads import get_current_user_id

router = APIRouter(prefix="/api/worldcup", tags=["worldcup"])


@router.get("/snapshot")
async def world_cup_snapshot(topic: str = ""):
    """Return the dated FIFA 48-team roster snapshot and fixture scope."""
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
    """Build a current source-aware briefing from the live fixture feed."""
    live_stats = await get_live_player_totals()
    apply_live_player_totals(live_stats)
    overview = await get_tournament_overview(force_refresh=True)
    matches = overview["matches"]
    match = next((item for item in matches if item["id"] == match_id), None) if match_id else None
    now = datetime.now(timezone.utc)

    def kickoff(match_item):
        try:
            parsed = datetime.fromisoformat(match_item.get("kickoffLocal", "").replace("Z", "+00:00"))
            return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
        except ValueError:
            return now

    if not match:
        match = next((item for item in matches if item.get("status") == "live"), None)
    if not match:
        scheduled = sorted((item for item in matches if item.get("status") == "scheduled"), key=lambda item: abs((kickoff(item) - now).total_seconds()))
        match = scheduled[0] if scheduled else None
    if not match:
        completed = sorted((item for item in matches if item.get("status") == "final"), key=kickoff, reverse=True)
        match = completed[0] if completed else None
    if not match:
        raise HTTPException(status_code=404, detail="No fixture is available in the current live World Cup feed")

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
        "briefType": "wcai_matchday_brief",
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
            "Goal and assist totals refresh from live match events; the FIFA player-statistics page remains linked as the official reference.",
            f"The proposal uses {proposal['budget_used']:g}M of the server-side {max_budget:g}M budget.",
        ],
        "availabilitySignals": unavailable_status,
        "dataConfidence": "medium",
        "snapshotDate": overview["updatedAt"],
        "dataQuality": "Current fixture feed plus live goal/assist event aggregation and source-labelled FIFA squad data.",
        "sourceUrls": [overview["sources"]["liveSchedule"], live_stats["source_url"], live_stats["fifa_source_url"]],
        "scenarios": [
            {"id": "chase", "label": "Chase the game", "formation": "4-3-3", "instruction": "Keep two wide outlets and prioritize verified attacking contribution."},
            {"id": "control", "label": "Control a lead", "formation": "3-5-2", "instruction": "Add a midfield connection and protect central progression."},
        ],
    }
