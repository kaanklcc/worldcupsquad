"""Refreshable World Cup goal and assist totals from public live match events.

FIFA's statistics page is the canonical presentation link. The event feed is
used to keep the application current between FIFA page refreshes: every scored
goal and named assist is aggregated from completed or live 2026 World Cup
matches, then mapped to the official FIFA final-squad catalog.
"""
from __future__ import annotations

import asyncio
import time
import unicodedata
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any

import httpx


ESPN_SCOREBOARD_URL = (
    "https://site.api.espn.com/apis/site/v2/sports/soccer/fifa.world/scoreboard"
    "?limit=500&dates=20260601-20260731"
)
ESPN_SUMMARY_URL = "https://site.api.espn.com/apis/site/v2/sports/soccer/fifa.world/summary?event={}"
FIFA_PLAYER_STATS_URL = "https://www.fifa.com/en/tournaments/mens/worldcup/canadamexicousa2026/statistics/player-statistics"
EVENT_SOURCE_URL = "https://site.api.espn.com/apis/site/v2/sports/soccer/fifa.world/scoreboard"
CACHE_TTL_SECONDS = 60

_cache: dict[str, Any] | None = None
_cache_expires_at = 0.0
_cache_lock = asyncio.Lock()


def normalize_name(value: str) -> str:
    decomposed = unicodedata.normalize("NFD", value.casefold())
    return "".join(char for char in decomposed if not unicodedata.combining(char) and char.isalnum())


def _event_ids(payload: dict[str, Any]) -> list[str]:
    return [
        str(event.get("id"))
        for event in payload.get("events", [])
        if isinstance(event, dict)
        and event.get("id")
        and str(event.get("status", {}).get("type", {}).get("state", "")) in {"in", "post"}
    ]


def _aggregate_summary(summary: dict[str, Any], totals: dict[str, dict[str, int]]) -> None:
    for event in summary.get("keyEvents", []) or []:
        if not isinstance(event, dict) or not event.get("scoringPlay"):
            continue
        participants = event.get("participants") or []
        if not participants:
            continue
        scorer = ((participants[0] or {}).get("athlete") or {}).get("displayName")
        if scorer:
            totals[normalize_name(str(scorer))]["goals"] += 1
        # ESPN's ordered participant list places the credited assister second
        # for a normal assisted goal. Own goals and penalties have no assister.
        assister = ((participants[1] or {}).get("athlete") or {}).get("displayName") if len(participants) > 1 else None
        if assister:
            totals[normalize_name(str(assister))]["assists"] += 1


async def get_live_player_totals(force_refresh: bool = False) -> dict[str, Any]:
    """Return a one-minute cached event tally, without failing the app offline."""
    global _cache, _cache_expires_at
    now = time.monotonic()
    if not force_refresh and _cache and _cache_expires_at > now:
        return _cache

    async with _cache_lock:
        if not force_refresh and _cache and _cache_expires_at > time.monotonic():
            return _cache
        try:
            async with httpx.AsyncClient(timeout=12.0, headers={"accept": "application/json"}) as client:
                scoreboard = (await client.get(ESPN_SCOREBOARD_URL)).json()
                event_ids = _event_ids(scoreboard)
                semaphore = asyncio.Semaphore(12)

                async def fetch_summary(event_id: str) -> dict[str, Any] | None:
                    async with semaphore:
                        response = await client.get(ESPN_SUMMARY_URL.format(event_id))
                        response.raise_for_status()
                        return response.json()

                summaries = await asyncio.gather(*(fetch_summary(event_id) for event_id in event_ids), return_exceptions=True)

            totals: dict[str, dict[str, int]] = defaultdict(lambda: {"goals": 0, "assists": 0})
            for summary in summaries:
                if isinstance(summary, dict):
                    _aggregate_summary(summary, totals)
            _cache = {
                "available": True,
                "totals": dict(totals),
                "updated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
                "source_url": EVENT_SOURCE_URL,
                "fifa_source_url": FIFA_PLAYER_STATS_URL,
                "events_processed": len(event_ids),
            }
        except Exception as error:
            _cache = {
                "available": False,
                "totals": {},
                "updated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
                "source_url": EVENT_SOURCE_URL,
                "fifa_source_url": FIFA_PLAYER_STATS_URL,
                "error": str(error),
                "events_processed": 0,
            }
        _cache_expires_at = time.monotonic() + CACHE_TTL_SECONDS
        return _cache
