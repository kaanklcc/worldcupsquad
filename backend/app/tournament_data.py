"""Live-friendly World Cup tournament directory with an honest local fallback."""
from __future__ import annotations

import asyncio
from collections import defaultdict
import time
from typing import Any

import httpx

from .data import get_data_metadata, get_players, get_world_cup_snapshot


LIVE_BASE_URL = "https://worldcup26.ir/get"
CACHE_TTL_SECONDS = 300
_cache: dict[str, Any] | None = None
_cache_expires_at = 0.0
_cache_lock = asyncio.Lock()

STAGE_LABELS = {
    "group": "Group stage",
    "r32": "Round of 32",
    "r16": "Round of 16",
    "qf": "Quarter-final",
    "sf": "Semi-final",
    "third": "Third-place play-off",
    "final": "Final",
}
STAGE_ORDER = {stage: index for index, stage in enumerate(STAGE_LABELS)}


def _list(payload: Any, key: str) -> list[dict[str, Any]]:
    if isinstance(payload, dict):
        value = payload.get(key, payload)
    else:
        value = payload
    return [item for item in value if isinstance(item, dict)] if isinstance(value, list) else []


def _value(record: dict[str, Any], key: str, fallback: str = "") -> str:
    value = record.get(key)
    if value is None or str(value).lower() == "null":
        return fallback
    return str(value)


def _int(value: Any) -> int:
    """Parse provider values defensively; a feed must not break the UI."""
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return 0


def _normalize_live(teams_payload: Any, games_payload: Any, stadiums_payload: Any) -> dict[str, Any]:
    raw_teams = _list(teams_payload, "teams")
    raw_games = _list(games_payload, "games")
    raw_stadiums = _list(stadiums_payload, "stadiums")
    if len(raw_teams) < 40 or len(raw_games) < 60:
        raise ValueError("Live tournament payload is incomplete")

    stadiums = {
        _value(item, "id"): {
            "name": _value(item, "name_en", _value(item, "name", "Venue pending")),
            "city": _value(item, "city_en", _value(item, "city")),
        }
        for item in raw_stadiums
    }
    teams = []
    for item in raw_teams:
        code = _value(item, "fifa_code", "TBD")
        teams.append({
            "id": _value(item, "id", code),
            "code": code,
            "name": _value(item, "name_en", _value(item, "name", "TBD")),
            "group": _value(item, "groups", _value(item, "group", "Unassigned")),
            "flag": _value(item, "flag"),
        })
    team_by_id = {team["id"]: team for team in teams}
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for team in teams:
        groups[team["group"]].append(team)

    matches = []
    for item in raw_games:
        stage_key = _value(item, "type", "group").lower()
        home = team_by_id.get(_value(item, "home_team_id"))
        away = team_by_id.get(_value(item, "away_team_id"))
        finished = _value(item, "finished").lower() == "true"
        elapsed = _value(item, "time_elapsed").lower()
        status = "final" if finished else "live" if elapsed and elapsed not in {"scheduled", "not started", "-"} else "scheduled"
        home_score = _value(item, "home_score")
        away_score = _value(item, "away_score")
        venue = stadiums.get(_value(item, "stadium_id"), {})
        matches.append({
            "id": f"live_{_value(item, 'id')}",
            "matchNumber": _int(_value(item, "id", "0")),
            "stageKey": stage_key,
            "stage": STAGE_LABELS.get(stage_key, stage_key.upper()),
            "group": _value(item, "group"),
            "homeTeam": home["name"] if home else _value(item, "home_team_name_en", _value(item, "home_team_label", "TBD")),
            "awayTeam": away["name"] if away else _value(item, "away_team_name_en", _value(item, "away_team_label", "TBD")),
            "homeCode": home["code"] if home else "TBD",
            "awayCode": away["code"] if away else "TBD",
            "homeScore": _int(home_score) if home_score.strip().lstrip("-").isdigit() else None,
            "awayScore": _int(away_score) if away_score.strip().lstrip("-").isdigit() else None,
            "status": status,
            "kickoffLocal": _value(item, "local_date"),
            "venue": venue.get("name", "Venue pending"),
            "city": venue.get("city", ""),
        })
    matches.sort(key=lambda match: match["matchNumber"])
    return {
        "mode": "live_community_feed",
        "updatedAt": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "teams": teams,
        "groups": [{"name": name, "teams": sorted(members, key=lambda team: team["name"])} for name, members in sorted(groups.items())],
        "matches": matches,
    }


def _local_roster_details() -> list[dict[str, Any]]:
    metadata = get_data_metadata()
    players_by_team: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for player in get_players():
        players_by_team[player.team].append(player.model_dump())
    return [
        {
            "team": team,
            "rosterAvailable": True,
            "sourceUrl": metadata["sourceUrls"].get(team),
            "players": players,
        }
        for team, players in sorted(players_by_team.items())
    ]


def _fallback() -> dict[str, Any]:
    snapshot = get_world_cup_snapshot()
    teams = [{"id": name.lower(), "code": name[:3].upper(), "name": name, "group": "Semi-finalists", "flag": ""} for name in snapshot["teams"]]
    matches = [
        {
            "id": match["id"],
            "matchNumber": index + 1,
            "stageKey": "sf",
            "stage": "Semi-final",
            "group": "SF",
            "homeTeam": match["homeTeam"],
            "awayTeam": match["awayTeam"],
            "homeCode": match["homeTeam"][:3].upper(),
            "awayCode": match["awayTeam"][:3].upper(),
            "homeScore": None,
            "awayScore": None,
            "status": "scheduled",
            "kickoffLocal": f"{match['date']} {match['kickoffLocal']}",
            "venue": match["venue"],
            "city": "",
        }
        for index, match in enumerate(snapshot["matches"])
    ]
    return {
        "mode": "local_fallback",
        "updatedAt": snapshot["snapshotDate"],
        "teams": teams,
        "groups": [{"name": "Semi-finalists", "teams": teams}],
        "matches": matches,
    }


async def get_tournament_overview(force_refresh: bool = False) -> dict[str, Any]:
    global _cache, _cache_expires_at
    now = time.monotonic()
    if not force_refresh and _cache and _cache_expires_at > now:
        return _cache

    async with _cache_lock:
        if not force_refresh and _cache and _cache_expires_at > time.monotonic():
            return _cache
        try:
            async with httpx.AsyncClient(timeout=10.0, headers={"accept": "application/json"}) as client:
                teams_response, games_response, stadiums_response = await asyncio.gather(
                    client.get(f"{LIVE_BASE_URL}/teams"),
                    client.get(f"{LIVE_BASE_URL}/games"),
                    client.get(f"{LIVE_BASE_URL}/stadiums"),
                )
                teams_response.raise_for_status()
                games_response.raise_for_status()
                stadiums_response.raise_for_status()
                overview = _normalize_live(teams_response.json(), games_response.json(), stadiums_response.json())
        except Exception as error:
            overview = _fallback()
            overview["liveError"] = str(error)

        overview["rosters"] = _local_roster_details()
        overview["stageOrder"] = STAGE_ORDER
        overview["sources"] = {
            "liveSchedule": f"{LIVE_BASE_URL}/teams, /games, /stadiums",
            "localRoster": get_data_metadata()["sourceUrls"],
            "notice": (
                "The 48-team schedule is a community live feed and is labelled as such. "
                "Detailed player rosters are only shown for Auto-Gaffer's dated FIFA roster snapshot."
            ),
        }
        _cache = overview
        _cache_expires_at = time.monotonic() + CACHE_TTL_SECONDS
        return overview
