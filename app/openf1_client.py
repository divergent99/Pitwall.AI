"""Thin client for the OpenF1 API (https://openf1.org).

No API key required for historical data. Every function is defensive:
network failures, timeouts, or unexpected shapes return None/[] rather than
raising, so callers can fall back to bundled static data. Results are
cached in-process for _TTL seconds to avoid re-fetching on every request.

NOTE: OpenF1's driver/team championship endpoints are labelled "beta" as of
this writing. Verify current field names against https://openf1.org/docs/
before depending on get_driver_standings()/get_team_standings() in
production -- they're written defensively (return [] on any surprise) for
that reason.
"""
from __future__ import annotations

import time
import httpx

BASE_URL = "https://api.openf1.org/v1"
_TIMEOUT = 10
_TTL = 3600  # 1 hour: results/calendar data doesn't need to be fresher than this

_CACHE: dict[str, tuple[float, object]] = {}


def _get(path: str, params: dict | None = None, ttl: int = _TTL):
    params = params or {}
    key = f"{path}?{sorted(params.items())}"
    now = time.time()

    cached = _CACHE.get(key)
    if cached and now - cached[0] < ttl:
        return cached[1]

    try:
        resp = httpx.get(f"{BASE_URL}{path}", params=params, timeout=_TIMEOUT)
        resp.raise_for_status()
        data = resp.json()
        _CACHE[key] = (now, data)
        return data
    except (httpx.HTTPError, httpx.TimeoutException, ValueError):
        # ValueError covers bad JSON. Serve stale cache if we have it,
        # otherwise let the caller fall back to static data.
        return cached[1] if cached else None


def get_meetings(year: int = 2026) -> list:
    return _get("/meetings", {"year": year}) or []


def get_race_session(meeting_key: int) -> dict | None:
    sessions = _get("/sessions", {"meeting_key": meeting_key}) or []
    return next((s for s in sessions if s.get("session_name") == "Race"), None)


def get_session_result(session_key: int) -> list:
    return _get("/session_result", {"session_key": session_key}) or []


def get_drivers(session_key: int, driver_number: int | None = None) -> list:
    params = {"session_key": session_key}
    if driver_number is not None:
        params["driver_number"] = driver_number
    return _get("/drivers", params) or []


def get_pit_stops(session_key: int, driver_number: int) -> list:
    return _get("/pit", {"session_key": session_key, "driver_number": driver_number}) or []


def find_meeting(meetings: list, venue_or_location: str) -> dict | None:
    """Match a CALENDAR venue string against OpenF1 meeting `location`.

    OpenF1's `location` field (e.g. "Spa-Francorchamps", "Silverstone",
    "Sakhir") lines up closely with the venue strings already used in
    season.CALENDAR, so a normalized substring match is enough for most
    rounds. A few venues need aliasing (see season.VENUE_ALIASES).
    """
    needle = venue_or_location.strip().lower()
    for m in meetings:
        loc = (m.get("location") or "").strip().lower()
        if not loc:
            continue
        if needle == loc or needle in loc or loc in needle:
            return m
    return None
