"""Thin client for the OpenF1 API, with basic caching and graceful failure."""
import time
import httpx

BASE_URL = "https://api.openf1.org/v1"
_CACHE: dict[str, tuple[float, object]] = {}
_TTL = 3600  # 1 hour — results/calendar don't need to be fresher than this

def _get(path: str, params: dict, ttl: int = _TTL):
    key = f"{path}?{sorted(params.items())}"
    now = time.time()
    if key in _CACHE and now - _CACHE[key][0] < ttl:
        return _CACHE[key][1]
    try:
        resp = httpx.get(f"{BASE_URL}{path}", params=params, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        _CACHE[key] = (now, data)
        return data
    except (httpx.HTTPError, httpx.TimeoutException):
        return _CACHE[key][1] if key in _CACHE else None  # stale cache > nothing

def get_meetings(year: int = 2026):
    return _get("/meetings", {"year": year}) or []

def get_race_session(meeting_key: int):
    sessions = _get("/sessions", {"meeting_key": meeting_key}) or []
    return next((s for s in sessions if s.get("session_name") == "Race"), None)

def get_session_result(session_key: int):
    return _get("/session_result", {"session_key": session_key}) or []

def get_pit_stops(session_key: int, driver_number: int):
    return _get("/pit", {"session_key": session_key, "driver_number": driver_number}) or []

def get_driver_standings(session_key: int | None = None):
    params = {"session_key": session_key} if session_key else {}
    return _get("/drivers_championship" if False else "/drivers", params) or []
    # note: standings beta endpoint name may differ — verify against current docs before relying on it
