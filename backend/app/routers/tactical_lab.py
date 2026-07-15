"""Premium what-if formation comparison powered by Agent Skills."""

from typing import List, Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from ..access import require_ai_access
from ..agent.skills import analyze_squad, suggest_lineup
from ..data import get_world_cup_snapshot
from ..db import get_db_connection
from ..models import Formation
from .squads import get_current_user_id


router = APIRouter(prefix="/api/tactical-lab", tags=["tactical-lab"])
SUPPORTED_FORMATIONS: tuple[Formation, ...] = ("4-3-3", "4-4-2", "3-5-2", "4-2-3-1", "5-3-2")


class TacticalLabRequest(BaseModel):
    formation: Formation = "4-3-3"
    strategy: Literal["balanced", "attacking", "defensive"] = "balanced"
    squadPlayerIds: List[str] = Field(default_factory=list, max_length=19)
    requiredPlayerIds: List[str] = Field(default_factory=list, max_length=11)
    matchContext: str = Field(default="", max_length=240)


@router.post("/compare")
async def compare_formations(
    request: TacticalLabRequest,
    user_id: int = Depends(get_current_user_id),
):
    """Return a side-by-side budget-valid comparison without mutating the squad."""
    access = require_ai_access(user_id)
    conn = get_db_connection()
    row = conn.execute("SELECT budget FROM users WHERE id = ?", (user_id,)).fetchone()
    conn.close()
    if not row:
        raise HTTPException(status_code=404, detail="User not found")
    max_budget = float(row["budget"])
    current_squad = analyze_squad(request.squadPlayerIds)
    baseline = None
    if "error" not in current_squad:
        baseline = {
            "playerCount": len(request.squadPlayerIds),
            "totalPoints": current_squad["total_points"],
            "budgetUsed": current_squad["total_budget"],
            "positionBreakdown": current_squad["position_breakdown"],
        }

    comparisons = []
    for formation in SUPPORTED_FORMATIONS:
        result = suggest_lineup(
            formation,
            match_context=request.matchContext,
            required_player_ids=request.requiredPlayerIds,
            strategy=request.strategy,
            current_squad_player_ids=request.squadPlayerIds,
            max_budget=max_budget,
        )
        if result.get("error"):
            comparisons.append({
                "formation": formation,
                "status": "unavailable",
                "reason": result["error"],
            })
            continue
        comparisons.append({
            "formation": formation,
            "status": "ready",
            "budgetUsed": result["budget_used"],
            "maxBudget": max_budget,
            "totalPoints": result["total_points"],
            "optimizationScore": round(result["optimization_score"], 2),
            "playerIds": result["starting_player_ids"],
            "requiredPlayerIds": result["required_player_ids"],
        })

    ready = [item for item in comparisons if item["status"] == "ready"]
    if not ready:
        raise HTTPException(status_code=422, detail="No formation is valid for the current budget and constraints")
    ready.sort(key=lambda item: (item["totalPoints"], item["optimizationScore"], -item["budgetUsed"]), reverse=True)
    best = ready[0]
    for item in comparisons:
        if item["status"] == "ready":
            item["pointsDeltaFromBest"] = item["totalPoints"] - best["totalPoints"]

    snapshot = get_world_cup_snapshot()
    return {
        "success": True,
        "feature": "what_if_tactical_lab",
        "selectedFormation": request.formation,
        "strategy": request.strategy,
        "serverBudget": max_budget,
        "baseline": baseline,
        "recommended": best,
        "comparisons": comparisons,
        "accessSource": access["accessSource"],
        "snapshotDate": snapshot["snapshotDate"],
        "dataQuality": snapshot["dataQuality"],
        "notice": "What-if proposals do not mutate the saved squad; apply requires a separate explicit confirmation.",
    }
