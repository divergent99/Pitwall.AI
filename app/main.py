from pathlib import Path
import logging
import threading

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .ai_engineer import ask_engineer
from .engine import monte_carlo, simulate
from .models import EngineerRequest, EngineerResponse, RaceScenario, SimulationResponse
from .season import backtest_round, season_snapshot, simulate_qualifying, strategy_rounds, validation_summary

logger = logging.getLogger("pitwall.main")
load_dotenv()
ROOT = Path(__file__).resolve().parent.parent
STATIC = ROOT / "static"
app = FastAPI(title="PitWall AI", version="0.1.0", description="Explainable motorsport strategy intelligence")
app.mount("/static", StaticFiles(directory=STATIC), name="static")


@app.on_event("startup")
def warm_openf1_cache():
    """Populate the OpenF1 cache once, sequentially, in the background,
    before most page loads hit it -- without blocking startup itself.

    This used to call season_snapshot() directly inside the startup event,
    which blocks Uvicorn from reporting "started" until it returns. That
    was fine when a failed OpenF1 call gave up after one quick retry, but
    with real backoff on 429s (needed so a rate-limited cold start
    eventually succeeds instead of quietly falling back to stale data --
    see openf1_client._RATE_LIMIT_BACKOFF), a heavily-throttled warm-up
    across ~11 completed rounds can take well over Railway's 2-minute
    health-check window. Running it in a background thread lets Uvicorn
    report healthy immediately; the first real request or two may race a
    still-warming cache, but that's far better than the container never
    becoming reachable at all.
    """
    def _warm():
        try:
            season_snapshot()
            logger.info("main: OpenF1 cache warmed at startup")
        except Exception:
            logger.exception("main: startup cache warm-up failed (non-fatal, will retry per-request)")

    threading.Thread(target=_warm, daemon=True, name="openf1-warmup").start()


@app.get("/", include_in_schema=False)
def index():
    return FileResponse(STATIC / "index.html")


@app.get("/api/health")
def health():
    return {"status": "ready", "engine": "deterministic-v1"}


@app.post("/api/simulate", response_model=SimulationResponse)
def run_simulation(scenario: RaceScenario):
    return simulate(scenario)


@app.post("/api/monte-carlo")
def run_monte_carlo(scenario: RaceScenario):
    return monte_carlo(scenario)


@app.post("/api/engineer", response_model=EngineerResponse)
def engineer(request: EngineerRequest):
    return ask_engineer(request)


@app.get("/api/season/2026")
def season_2026():
    return season_snapshot()


@app.get("/api/qualifying")
def qualifying(circuit: str = "Silverstone", trials: int = 2000, wet: bool = False):
    return simulate_qualifying(circuit, max(200, min(trials, 10000)), wet)


@app.get("/api/strategy/rounds")
def all_round_strategies():
    return strategy_rounds()


@app.get("/api/strategy/backtest/{round_number}")
def strategy_backtest(round_number: int):
    return backtest_round(round_number)


@app.get("/api/strategy/validation")
def strategy_validation():
    return validation_summary()
