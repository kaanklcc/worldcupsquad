"""Live-friendly World Cup tournament directory with an honest local fallback."""
from __future__ import annotations

import asyncio
from collections import defaultdict
import time
from typing import Any

import httpx

from .config import settings
from .data import get_data_metadata, get_players, get_world_cup_snapshot


LIVE_BASE_URL = "https://site.api.espn.com/apis/site/v2/sports/soccer/fifa.world/scoreboard?limit=500&dates=20260601-20260731"
CACHE_TTL_SECONDS = 60
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


def _normalize_espn(payload: dict[str, Any]) -> dict[str, Any]:
    """Normalize ESPN's live World Cup scoreboard into the app's stable shape."""
    events = payload.get("events", [])
    if len(events) < 80:
        raise ValueError("Live World Cup scoreboard is incomplete")
    teams_by_name: dict[str, dict[str, Any]] = {}
    matches = []
    for index, event in enumerate(events, start=1):
        competition = (event.get("competitions") or [{}])[0]
        competitors = competition.get("competitors") or []
        home = next((item for item in competitors if item.get("homeAway") == "home"), {})
        away = next((item for item in competitors if item.get("homeAway") == "away"), {})
        home_team = home.get("team") or {}
        away_team = away.get("team") or {}
        for team in (home_team, away_team):
            if team.get("displayName"):
                teams_by_name[team["displayName"]] = {
                    "id": str(team.get("id", team["displayName"])),
                    "code": team.get("abbreviation", "TBD"),
                    "name": team["displayName"],
                    "group": event.get("season", {}).get("slug", "Tournament").replace("-", " ").title(),
                    "flag": team.get("logo", ""),
                }
        status = competition.get("status", {}).get("type", {})
        state = status.get("state", "pre")
        stage_key = event.get("season", {}).get("slug", "group")
        venue = competition.get("venue", {})
        matches.append({
            "id": f"espn_{event.get('id')}",
            "matchNumber": index,
            "stageKey": stage_key,
            "stage": competition.get("altGameNote") or stage_key.replace("-", " ").title(),
            "group": stage_key.replace("-", " ").title(),
            "homeTeam": home_team.get("displayName", "TBD"),
            "awayTeam": away_team.get("displayName", "TBD"),
            "homeCode": home_team.get("abbreviation", "TBD"),
            "awayCode": away_team.get("abbreviation", "TBD"),
            "homeScore": _int(home.get("score")) if state != "pre" else None,
            "awayScore": _int(away.get("score")) if state != "pre" else None,
            "status": "final" if status.get("completed") else "live" if state == "in" else "scheduled",
            "kickoffLocal": event.get("date", ""),
            "venue": venue.get("fullName", "Venue pending"),
            "city": (venue.get("address") or {}).get("city", ""),
        })
    teams = sorted(teams_by_name.values(), key=lambda team: team["name"])
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for team in teams:
        groups[team["group"]].append(team)
    return {
        "mode": "live_event_feed",
        "updatedAt": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "teams": teams,
        "groups": [{"name": name, "teams": members} for name, members in sorted(groups.items())],
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
    teams = [{"id": name.lower(), "code": name[:3].upper(), "name": name, "group": "Official squad list", "flag": ""} for name in snapshot["teams"]]
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
        "groups": [{"name": "Official 48-team squad list", "teams": teams}],
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
            if not settings.live_event_feed_enabled:
                raise RuntimeError("Live event feed disabled")
            async with httpx.AsyncClient(timeout=10.0, headers={"accept": "application/json"}) as client:
                response = await client.get(LIVE_BASE_URL)
                response.raise_for_status()
                overview = _normalize_espn(response.json())
        except Exception as error:
            overview = _fallback()
            overview["liveError"] = str(error)

        overview["rosters"] = _local_roster_details()
        overview["stageOrder"] = STAGE_ORDER
        overview["sources"] = {
            "liveSchedule": LIVE_BASE_URL,
            "localRoster": get_data_metadata()["sourceUrls"],
            "notice": (
                "Fixtures and scores refresh from a public live event feed every 60 seconds. "
                "Detailed player rosters remain linked to the dated official FIFA squad list."
            ),
        }
        _cache = overview
        _cache_expires_at = time.monotonic() + CACHE_TTL_SECONDS
        return overview
