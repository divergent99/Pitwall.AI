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

import logging
import threading
import time
import unicodedata
import httpx

logger = logging.getLogger("pitwall.openf1")

BASE_URL = "https://api.openf1.org/v1"
_TIMEOUT = 10
_TTL = 3600  # 1 hour: results/calendar data doesn't need to be fresher than this
_NEGATIVE_TTL = 60  # cache *failures* briefly too, so a burst of page loads
                     # doesn't hammer OpenF1 retrying the same failing call
_RETRIES = 1  # one retry on transient failure before caching a miss
_RETRY_DELAY = 0.3

_CACHE: dict[str, tuple[float, object]] = {}
_LOCKS: dict[str, threading.Lock] = {}
_LOCKS_GUARD = threading.Lock()


def _lock_for(key: str) -> threading.Lock:
    with _LOCKS_GUARD:
        lock = _LOCKS.get(key)
        if lock is None:
            lock = threading.Lock()
            _LOCKS[key] = lock
        return lock


def _cached(key: str, ttl: int):
    entry = _CACHE.get(key)
    if entry is None:
        return None, False
    cached_at, value = entry
    effective_ttl = ttl if value is not None else _NEGATIVE_TTL
    if time.time() - cached_at < effective_ttl:
        return value, True
    return None, False


def _get(path: str, params: dict | None = None, ttl: int = _TTL):
    params = params or {}
    key = f"{path}?{sorted(params.items())}"

    value, hit = _cached(key, ttl)
    if hit:
        return value

    # Serialize concurrent requests for the *same* key so a burst of
    # simultaneous page loads on a cold cache makes one network call, not
    # N of them. Everyone else just waits for the first to finish, then
    # reads the cache the first caller populated.
    with _lock_for(key):
        value, hit = _cached(key, ttl)  # another thread may have just filled it
        if hit:
            return value

        last_exc = None
        for attempt in range(_RETRIES + 1):
            try:
                resp = httpx.get(f"{BASE_URL}{path}", params=params, timeout=_TIMEOUT)
                resp.raise_for_status()
                data = resp.json()
                _CACHE[key] = (time.time(), data)
                return data
            except (httpx.HTTPError, httpx.TimeoutException, ValueError) as exc:
                last_exc = exc
                if attempt < _RETRIES:
                    time.sleep(_RETRY_DELAY)

        status = getattr(getattr(last_exc, "response", None), "status_code", None)
        logger.warning(
            "openf1: request failed for %s%s after %d attempt(s): %r",
            path, f" [status={status}]" if status else "", _RETRIES + 1, last_exc,
        )
        _CACHE[key] = (time.time(), None)
        return None


def _normalize(text: str) -> str:
    """Lowercase and strip accents so 'Montréal' matches 'Montreal'."""
    text = unicodedata.normalize("NFKD", text)
    text = "".join(c for c in text if not unicodedata.combining(c))
    return text.strip().lower()


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


def get_championship_drivers(session_key: int) -> list:
    """Driver standings as of this race session. Race sessions only."""
    return _get("/championship_drivers", {"session_key": session_key}) or []


def get_championship_teams(session_key: int) -> list:
    """Constructor standings as of this race session. Race sessions only."""
    return _get("/championship_teams", {"session_key": session_key}) or []


def get_laps(session_key: int) -> list:
    return _get("/laps", {"session_key": session_key}) or []


def find_meeting(meetings: list, venue_or_location: str) -> dict | None:
    """Match a CALENDAR venue string against an OpenF1 meeting.

    Checked against `location`, `circuit_short_name`, and `country_name` --
    OpenF1 doesn't always use the same string a CALENDAR venue uses (e.g.
    Monaco's `location` is "Monte Carlo", but `country_name` is "Monaco").
    Comparison is accent-normalized so "Montreal" matches "Montréal".
    A few venues still need aliasing (see season.VENUE_ALIASES) for names
    that don't overlap with any of these three fields at all.
    """
    needle = _normalize(venue_or_location)
    fields = ("location", "circuit_short_name", "country_name")
    for m in meetings:
        for field in fields:
            value = _normalize(m.get(field) or "")
            if not value:
                continue
            if needle == value or needle in value or value in needle:
                return m
    return None
