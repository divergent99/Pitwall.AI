from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .ai_engineer import ask_engineer
from .engine import monte_carlo, simulate
from .models import EngineerRequest, EngineerResponse, RaceScenario, SimulationResponse
from .season import backtest_round, season_snapshot, simulate_qualifying, strategy_rounds, validation_summary

load_dotenv()
ROOT = Path(__file__).resolve().parent.parent
STATIC = ROOT / "static"
app = FastAPI(title="PitWall AI", version="0.1.0", description="Explainable motorsport strategy intelligence")
app.mount("/static", StaticFiles(directory=STATIC), name="static")


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
