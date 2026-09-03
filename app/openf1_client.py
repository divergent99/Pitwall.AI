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
_RETRIES = 1  # non-429 transient failures (timeouts, network blips): quick retry
_RETRY_DELAY = 0.3

# 429s need real patience, not the quick retry above: OpenF1's 10s rate
# window doesn't clear in 0.3s, so a 429 got exactly one useless retry and
# then a minute of cached failure -- which is what "not getting live data
# right after a fresh deploy" actually was. Retry_After (seconds) is
# honored when OpenF1 sends it; otherwise back off on a fixed schedule.
_RATE_LIMIT_RETRIES = 4
_RATE_LIMIT_BACKOFF = (1.0, 2.0, 4.0, 6.0)

_CACHE: dict[str, tuple[float, object]] = {}
_LOCKS: dict[str, threading.Lock] = {}
_LOCKS_GUARD = threading.Lock()

# OpenF1 caps requests at 30 per 10s per IP. The per-key lock above only
# de-dupes identical concurrent requests -- it does nothing to cap the
# *overall* rate across the many different endpoints one season snapshot
# touches (meetings, sessions, session_result, drivers, pit, laps -- times
# every completed round). Without this, one page load easily fires 40+
# distinct requests in a couple seconds and 429s almost everything.
_RATE_LIMIT = 15          # conservative margin below the documented 30 --
                          # Railway egress IPs are often shared across
                          # tenants, so 25 of *our own* requests per 10s
                          # wasn't leaving enough room
_RATE_WINDOW = 10.0       # seconds
_request_times: list[float] = []
_RATE_GUARD = threading.Lock()


def _throttle() -> None:
    with _RATE_GUARD:
        now = time.time()
        while _request_times and now - _request_times[0] > _RATE_WINDOW:
            _request_times.pop(0)
        if len(_request_times) >= _RATE_LIMIT:
            sleep_for = _RATE_WINDOW - (now - _request_times[0]) + 0.05
        else:
            sleep_for = 0
        _request_times.append(now + sleep_for)
    if sleep_for > 0:
        time.sleep(sleep_for)


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
        attempts = 0
        rate_limit_attempts = 0
        max_attempts = 1 + _RETRIES + _RATE_LIMIT_RETRIES
        while attempts < max_attempts:
            attempts += 1
            try:
                _throttle()
                resp = httpx.get(f"{BASE_URL}{path}", params=params, timeout=_TIMEOUT)
                resp.raise_for_status()
                data = resp.json()
                _CACHE[key] = (time.time(), data)
                return data
            except httpx.HTTPStatusError as exc:
                last_exc = exc
                if exc.response is not None and exc.response.status_code == 429 and rate_limit_attempts < _RATE_LIMIT_RETRIES:
                    retry_after = exc.response.headers.get("Retry-After")
                    try:
                        delay = float(retry_after) if retry_after else _RATE_LIMIT_BACKOFF[rate_limit_attempts]
                    except (TypeError, ValueError):
                        delay = _RATE_LIMIT_BACKOFF[rate_limit_attempts]
                    rate_limit_attempts += 1
                    time.sleep(delay)
                    continue
                break
            except (httpx.HTTPError, httpx.TimeoutException, ValueError) as exc:
                last_exc = exc
                if attempts <= _RETRIES:
                    time.sleep(_RETRY_DELAY)
                    continue
                break

        status = getattr(getattr(last_exc, "response", None), "status_code", None)
        logger.warning(
            "openf1: request failed for %s%s after %d attempt(s): %r",
            path, f" [status={status}]" if status else "", attempts, last_exc,
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


def get_race_sessions_for_year(year: int = 2026) -> dict[int, dict]:
    """All Race sessions for the year in ONE call, keyed by meeting_key.

    Replaces calling /sessions once per meeting -- that's what was blowing
    through OpenF1's 30 req/10s rate limit and causing every round past
    Great Britain to 429 and silently fall back to stale bundled data.
    """
    sessions = _get("/sessions", {"year": year, "session_name": "Race"}) or []
    # Defensive: filter client-side too, in case the server-side filter is
    # ever ignored/unsupported and returns every session type for the year.
    return {
        s["meeting_key"]: s
        for s in sessions
        if s.get("meeting_key") is not None and s.get("session_name") == "Race"
    }


def get_race_session(meeting_key: int) -> dict | None:
    """Kept for callers that only have one meeting_key; prefer
    get_race_sessions_for_year() when checking multiple rounds."""
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
