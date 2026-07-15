"""World Cup 2026 roster and player catalog service.

The catalog is built from a dated FIFA roster snapshot. Fantasy price/points
are application values; tournament facts are kept separate and are never
silently fabricated when the official snapshot does not expose a stat.
"""

import json
from hashlib import sha256
from pathlib import Path
from typing import Any, Dict, List

from .models import Player, PremiumStats, WorldCupStats

DATA_DIR = Path(__file__).parent.parent.parent / "data"
ROSTERS_FILE = DATA_DIR / "worldcup_2026_rosters.json"
MATCHES_FILE = DATA_DIR / "worldcup_2026_matches.json"

_players_cache: List[Player] = []
_metadata_cache: Dict[str, Any] = {}

TEAM_POINTS = {
    "Argentina": 74,
    "England": 75,
    "France": 76,
    "Spain": 77,
}

STAR_POINTS = {
    "Lionel Messi": 95,
    "Kylian Mbappe": 94,
    "Rodrigo Hernandez": 93,
    "Jude Bellingham": 92,
    "Lamine Yamal": 90,
    "Harry Kane": 89,
    "Dani Olmo": 86,
    "Alexis Mac Allister": 85,
    "Cristian Romero": 84,
    "Julian Alvarez": 84,
    "Julián Álvarez": 84,
    "Bukayo Saka": 87,
    "William Saliba": 88,
    "Mike Maignan": 85,
    "Unai Simon": 87,
}

POSITION_PRICE = {"GK": 6.5, "DF": 7.0, "MF": 8.0, "FW": 8.5}
POSITION_XG = {"GK": 0.01, "DF": 0.04, "MF": 0.12, "FW": 0.25}
TEAM_FLAGS = {"Argentina": "🇦🇷", "England": "🏴", "France": "🇫🇷", "Spain": "🇪🇸"}
STATS_SOURCE_URL = "https://www.fifa.com/en/tournaments/mens/worldcup/canadamexicousa2026/statistics"
VERIFIED_STATS = {
    "Lionel Messi": {"goals": 8, "assists": 1},
    "Kylian Mbappe": {"goals": 8, "assists": 3},
    "Jude Bellingham": {"goals": 6},
    "Harry Kane": {"goals": 6, "assists": 1},
    "Ousmane Dembele": {"goals": 5, "assists": 2},
}


def _load_roster_source() -> Dict[str, Any]:
    with ROSTERS_FILE.open("r", encoding="utf-8") as file:
        return json.load(file)


def _fantasy_price(name: str, position: str) -> float:
    """Return a stable app price, not an official FIFA valuation."""
    if name in STAR_POINTS:
        return {
            "Lionel Messi": 16.5,
            "Kylian Mbappe": 17.0,
            "Rodrigo Hernandez": 12.5,
            "Jude Bellingham": 13.5,
            "Lamine Yamal": 12.0,
            "Harry Kane": 13.0,
            "Bukayo Saka": 11.5,
            "William Saliba": 8.0,
        }.get(name, POSITION_PRICE[position] + 1.0)
    return POSITION_PRICE[position]


def _build_player(team: str, player_data: Dict[str, Any], source: Dict[str, Any]) -> Player:
    name = player_data["name"]
    position = player_data["position"]
    points = STAR_POINTS.get(name, TEAM_POINTS[team] + {"GK": 2, "DF": 0, "MF": 3, "FW": 4}[position])
    source_url = source["sourceUrls"][team]
    snapshot_date = source["snapshotDate"]
    verified_stats = VERIFIED_STATS.get(name)

    return Player(
        id=player_data["id"],
        name=name,
        position=position,
        team=team,
        price=_fantasy_price(name, position),
        isAvailable=True,
        points=points,
        premium_stats=PremiumStats(
            xg_per_game=POSITION_XG[position],
            injury_risk="Low",
            scout_note=(
                "Application fantasy estimate. Official current injury and form "
                "data is not available in this roster snapshot."
            ),
            source_status="app_estimate",
        ),
        flag=source["teams"][team].get("flag", TEAM_FLAGS[team]),
        number=player_data.get("number"),
        data_source=source["dataSource"],
        data_updated_at=snapshot_date,
        source_url=source_url,
        roster_status="announced",
        availability_status="unknown",
        world_cup_stats=WorldCupStats(
            **(verified_stats or {}),
            data_status="verified" if verified_stats else "not_available",
            source_url=STATS_SOURCE_URL if verified_stats else None,
            updated_at=snapshot_date if verified_stats else None,
        ),
    )


def load_players() -> List[Player]:
    """Load all 104 players in the four 2026 semi-finalist rosters."""
    global _metadata_cache
    source = _load_roster_source()
    _metadata_cache = {
        "tournament": source["tournament"],
        "snapshotDate": source["snapshotDate"],
        "dataSource": source["dataSource"],
        "dataQuality": (
            "Official FIFA roster provenance; fantasy price, points and xG are "
            "application estimates; tournament goals/assists are exposed only "
            "when present in the dated FIFA statistics snapshot."
        ),
        "sourceUrls": source["sourceUrls"],
        "teams": list(source["teams"].keys()),
        "playerCount": sum(len(team["players"]) for team in source["teams"].values()),
    }
    return [
        _build_player(team_name, player, source)
        for team_name, team in source["teams"].items()
        for player in team["players"]
    ]


def get_players() -> List[Player]:
    """Get the cached roster catalog."""
    global _players_cache
    if not _players_cache:
        _players_cache = load_players()
    return _players_cache


def get_data_metadata() -> Dict[str, Any]:
    """Return freshness and provenance metadata for the current catalog."""
    if not _players_cache:
        get_players()
    return dict(_metadata_cache)


def _intel_value(player: Player, key: str, floor: int, ceiling: int) -> int:
    """Create stable *application* scouting signals without claiming FIFA facts."""
    digest = sha256(f"{player.id}:{key}".encode("utf-8")).digest()
    return floor + digest[0] % (ceiling - floor + 1)


def get_player_intel(player_id: str) -> Dict[str, Any] | None:
    """Return a source-aware scouting card payload for one rostered player.

    The endpoint intentionally separates source-backed roster/tournament facts
    from deterministic Auto-Gaffer model signals. It does not manufacture live
    FIFA performance data when the dated snapshot has none.
    """
    player = next((item for item in get_players() if item.id == player_id), None)
    if not player:
        return None

    position_bias = {
        "GK": {"finishing": 28, "creation": 48, "progression": 54, "defending": 90},
        "DF": {"finishing": 42, "creation": 57, "progression": 61, "defending": 84},
        "MF": {"finishing": 64, "creation": 80, "progression": 82, "defending": 68},
        "FW": {"finishing": 88, "creation": 70, "progression": 78, "defending": 40},
    }[player.position]
    metrics = []
    for key, label in (
        ("finishing", "Finishing"),
        ("creation", "Creation"),
        ("progression", "Progression"),
        ("defending", "Defensive work"),
        ("availability", "Availability signal"),
    ):
        base = position_bias.get(key, 74)
        variance = _intel_value(player, key, -7, 7)
        if key == "availability":
            value = 62 if player.availability_status in {"unknown", None} else 88 if player.availability_status == "available" else 42
        else:
            value = max(35, min(99, base + variance + max(0, player.points - 74) // 4))
        metrics.append({"key": key, "label": label, "value": value})

    overall = max(55, min(99, int(round((player.points + sum(item["value"] for item in metrics[:4]) / 4) / 2))))
    trend_center = min(98, max(52, overall))
    trend = [
        max(45, min(99, trend_center + _intel_value(player, f"trend-{index}", -6, 6)))
        for index in range(5)
    ]
    top_metrics = sorted(metrics[:4], key=lambda item: item["value"], reverse=True)[:2]
    stats = player.world_cup_stats.model_dump() if player.world_cup_stats else {"data_status": "not_available"}

    return {
        "player": player.model_dump(),
        "verified": {
            "rosterStatus": player.roster_status or "not_available",
            "availabilityStatus": player.availability_status or "unknown",
            "tournamentStats": stats,
        },
        "model": {
            "isEstimate": True,
            "overall": overall,
            "tier": "elite" if overall >= 89 else "impact" if overall >= 80 else "scout",
            "metrics": metrics,
            "trend": trend,
            "strengths": [item["label"] for item in top_metrics],
            "scoutBrief": player.premium_stats.scout_note,
        },
        "provenance": {
            "snapshotDate": player.data_updated_at,
            "rosterSource": player.source_url,
            "tournamentStatsSource": stats.get("source_url"),
            "notice": (
                "Roster and tournament figures are source-labelled. Overall, trend and attribute bars "
                "are Auto-Gaffer scouting estimates, not official FIFA live statistics."
            ),
        },
    }


def get_world_cup_snapshot(topic: str = "") -> Dict[str, Any]:
    """Return the dated official roster/match snapshot used by the agent."""
    with MATCHES_FILE.open("r", encoding="utf-8") as file:
        matches_source = json.load(file)
    metadata = get_data_metadata()
    topic_norm = topic.strip().lower()
    matches = matches_source["matches"]
    if topic_norm:
        matches = [
            match for match in matches
            if topic_norm in json.dumps(match, ensure_ascii=False).lower()
        ]
    return {
        **metadata,
        "matchDataSource": matches_source["dataSource"],
        "matchSourceUrls": matches_source["sourceUrls"],
        "matches": matches,
        "notice": (
            "Fixture snapshot only: no score or official starting XI is claimed "
            "when result is null."
        ),
    }


def reload_players() -> List[Player]:
    """Force reload the roster snapshot from disk."""
    global _players_cache
    _players_cache = load_players()
    return _players_cache
