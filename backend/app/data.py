"""World Cup 2026 roster and player catalog service.

The catalog is built from a dated FIFA roster snapshot. Fantasy price/points
are application values; tournament facts are kept separate and are never
silently fabricated when the official snapshot does not expose a stat.
"""

import json
import re
import unicodedata
from hashlib import sha256
from pathlib import Path
from typing import Any, Dict, List

from .models import Player, PremiumStats, WorldCupStats
from .live_stats import FIFA_PLAYER_STATS_URL, normalize_name

DATA_DIR = Path(__file__).parent.parent.parent / "data"
ROSTERS_FILE = DATA_DIR / "worldcup_2026_rosters.json"
MATCHES_FILE = DATA_DIR / "worldcup_2026_matches.json"

_players_cache: List[Player] = []
_metadata_cache: Dict[str, Any] = {}

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
STATS_SOURCE_URL = FIFA_PLAYER_STATS_URL
VERIFIED_STATS = {
    "Lionel Messi": {"goals": 8, "assists": 1},
    "Kylian Mbappe": {"goals": 8, "assists": 3},
    "Jude Bellingham": {"goals": 6},
    "Harry Kane": {"goals": 6, "assists": 1},
    "Ousmane Dembele": {"goals": 5, "assists": 2},
}

POSITION_SCOUT_ROLES = {
    "GK": "protect the box, organise the defensive line and launch controlled restarts",
    "DF": "control duels, protect the transition and support the wide progression lane",
    "MF": "connect build-up to the final third while keeping the midfield compact",
    "FW": "attack high-value spaces, finish moves and create a pressing trigger from the front",
}


def _load_roster_source() -> Dict[str, Any]:
    with ROSTERS_FILE.open("r", encoding="utf-8") as file:
        return json.load(file)


def _normalize(value: str) -> str:
    decomposed = unicodedata.normalize("NFD", value.casefold())
    return "".join(char for char in decomposed if not unicodedata.combining(char))


def get_team_aliases() -> Dict[str, str]:
    """All official team names plus the common Turkish/football aliases."""
    source = _load_roster_source()
    aliases = {_normalize(team): team for team in source["teams"]}
    aliases.update({
        "cezayir": "Algeria", "arjantin": "Argentina", "avustralya": "Australia",
        "avusturya": "Austria", "belcika": "Belgium", "bosna hersek": "Bosnia And Herzegovina",
        "brezilya": "Brazil", "yesil burun adalari": "Cabo Verde", "kanada": "Canada",
        "kolombiya": "Colombia", "demokratik kongo": "Congo DR", "fildisi sahili": "Côte D'Ivoire",
        "hirvatistan": "Croatia", "curacao": "Curaçao", "cekya": "Czechia", "ekvador": "Ecuador",
        "misir": "Egypt", "ingiltere": "England", "fransa": "France", "almanya": "Germany",
        "gana": "Ghana", "iran": "IR Iran", "irak": "Iraq", "japonya": "Japan", "urdun": "Jordan",
        "guney kore": "Korea Republic", "meksika": "Mexico", "fas": "Morocco", "hollanda": "Netherlands",
        "yeni zelanda": "New Zealand", "norvec": "Norway", "portekiz": "Portugal", "katar": "Qatar",
        "suudi arabistan": "Saudi Arabia", "iskocya": "Scotland", "guney afrika": "South Africa",
        "ispanya": "Spain", "isvec": "Sweden", "isvicre": "Switzerland", "tunus": "Tunisia",
        "turkiye": "Türkiye", "ozbekistan": "Uzbekistan", "abd": "USA", "amerika": "USA",
        "three lions": "England", "les bleus": "France", "la roja": "Spain", "albiceleste": "Argentina",
    })
    return aliases


def _model_points(player_data: Dict[str, Any]) -> int:
    """Stable application score, intentionally not an official FIFA rating."""
    normalized_name = _normalize(player_data["name"])
    elite = {
        "messi": 95, "mbappe": 94, "haaland": 93, "vinicius": 92,
        "bellingham": 92, "rodri": 93, "yamal": 90, "kane": 89,
        "salah": 90, "dembele": 89, "saka": 87, "saliba": 88,
        "courtois": 88, "alisson": 88, "maignan": 85,
    }
    for surname, score in elite.items():
        if re.search(rf"\b{re.escape(surname)}\b", normalized_name):
            return score
    base = {"GK": 67, "DF": 66, "MF": 69, "FW": 70}[player_data["position"]]
    return base + sha256(player_data["id"].encode("utf-8")).digest()[0] % 12


def _model_price(points: int, position: str) -> float:
    """Return the in-app fantasy price after the universal 2M price reduction."""
    uplift = max(0, min(9.0, (points - 70) * 0.45))
    return round(POSITION_PRICE[position] + uplift - 2.0, 1)


def _model_xg(player_data: Dict[str, Any]) -> float:
    """Give the application estimate player-level variance without calling it FIFA data."""
    base = POSITION_XG[player_data["position"]]
    variance = (sha256(f"{player_data['id']}:xg".encode("utf-8")).digest()[0] % 11 - 5) / 100
    return round(max(0.01, base + variance), 2)


def _scout_note(team: str, player_data: Dict[str, Any], snapshot_date: str) -> str:
    """Create a roster-fact-led, player-specific premium brief.

    This deliberately uses only official squad-list facts plus an explicitly
    labelled tactical inference, instead of turning a generic model disclaimer
    into fake player statistics.
    """
    number = player_data.get("number")
    shirt = f"#{number}" if number is not None else "This squad member"
    club = player_data.get("club")
    club_clause = f" The FIFA list records {club} as the listed club." if club else ""
    role = POSITION_SCOUT_ROLES[player_data["position"]]
    return (
        f"{shirt} {player_data['name']} is a confirmed {team} {player_data['position']} in the "
        f"official FIFA final-squad snapshot ({snapshot_date}). {club_clause} "
        f"WCAI tactical read: use this player to {role}. "
        "The signal bars are an application estimate; official World Cup match-event totals are shown only when FIFA publishes a dated player-stat snapshot."
    )


def _build_player(team: str, player_data: Dict[str, Any], source: Dict[str, Any]) -> Player:
    name = player_data["name"]
    position = player_data["position"]
    points = _model_points(player_data)
    source_url = source["sourceUrls"][team]
    snapshot_date = source["snapshotDate"]

    return Player(
        id=player_data["id"],
        name=name,
        position=position,
        team=team,
        price=_model_price(points, position),
        isAvailable=True,
        points=points,
        premium_stats=PremiumStats(
            xg_per_game=_model_xg(player_data),
            injury_risk="Low",
            scout_note=_scout_note(team, player_data, snapshot_date),
            source_status="app_estimate",
        ),
        flag=source["teams"][team].get("flag"),
        number=player_data.get("number"),
        data_source=source["dataSource"],
        data_updated_at=snapshot_date,
        source_url=source_url,
        official_name=player_data.get("officialName"),
        club=player_data.get("club"),
        date_of_birth=player_data.get("dateOfBirth"),
        roster_status="confirmed",
        availability_status="unknown",
        world_cup_stats=WorldCupStats(
            data_status="not_available",
            source_url=STATS_SOURCE_URL,
            updated_at=snapshot_date,
        ),
    )


def load_players() -> List[Player]:
    """Load FIFA's 48 confirmed final squads (1,248 players)."""
    global _metadata_cache
    source = _load_roster_source()
    _metadata_cache = {
        "tournament": source["tournament"],
        "snapshotDate": source["snapshotDate"],
        "dataSource": source["dataSource"],
        "dataQuality": (
            "Official FIFA final-squad provenance for 48 teams / 1,248 players. "
            "Fantasy price, points, xG and scout signals are WCAI application estimates; "
            "tournament statistics remain unavailable until loaded from a dated official statistics source."
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


def apply_live_player_totals(live_stats: Dict[str, Any]) -> List[Player]:
    """Overlay source-labelled live goal/assist totals onto the catalog cache.

    A successful feed gives every rostered player an explicit 0G/0A baseline,
    while players with named event contributions receive their live totals.
    If the provider is unavailable, the existing source-aware snapshot remains
    unchanged rather than fabricating a statistic.
    """
    global _players_cache
    players = get_players()
    if not live_stats.get("available"):
        return players
    totals = live_stats.get("totals", {})
    updated_at = live_stats.get("updated_at")
    source_url = live_stats.get("source_url") or STATS_SOURCE_URL
    _players_cache = [
        player.model_copy(update={
            "world_cup_stats": WorldCupStats(
                goals=int(totals.get(normalize_name(player.name), {}).get("goals", 0)),
                assists=int(totals.get(normalize_name(player.name), {}).get("assists", 0)),
                data_status="verified",
                source_url=source_url,
                updated_at=updated_at,
            ),
        })
        for player in players
    ]
    _metadata_cache["liveStats"] = {
        "updatedAt": updated_at,
        "sourceUrl": source_url,
        "fifaStatisticsUrl": live_stats.get("fifa_source_url", STATS_SOURCE_URL),
        "eventsProcessed": live_stats.get("events_processed", 0),
    }
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
    from deterministic WCAI model signals. It does not manufacture live
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
            "officialProfile": {
                "officialName": player.official_name or player.name,
                "team": player.team,
                "shirtNumber": player.number,
                "listedClub": player.club,
                "dateOfBirth": player.date_of_birth,
                "source": player.source_url,
                "snapshotDate": player.data_updated_at,
            },
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
                "Official FIFA roster details are displayed separately from the model layer. Overall, trend, xG and "
                "attribute bars are WCAI scouting estimates; live goal and assist totals refresh separately from match events."
            ),
        },
    }


def get_world_cup_snapshot(topic: str = "") -> Dict[str, Any]:
    """Return the dated official 48-team roster and fixture scope used by the agent."""
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
