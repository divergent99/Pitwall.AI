from typing import Literal

from pydantic import BaseModel, Field, model_validator

Compound = Literal["SOFT", "MEDIUM", "HARD", "INTERMEDIATE"]
Weather = Literal["DRY", "LIGHT_RAIN"]
Circuit = Literal["melbourne", "shanghai", "suzuka", "sakhir", "jeddah", "miami", "montreal", "monaco", "barcelona", "spielberg", "silverstone", "spa", "budapest", "zandvoort", "monza", "madrid", "baku", "marina-bay", "austin", "mexico-city", "sao-paulo", "las-vegas", "lusail", "yas-marina"]


class RaceScenario(BaseModel):
    circuit: Circuit = "marina-bay"
    total_laps: int = Field(default=57, ge=15, le=90)
    current_lap: int = Field(default=18, ge=1)
    compound: Compound = "MEDIUM"
    tyre_age: int = Field(default=18, ge=0, le=60)
    weather: Weather = "DRY"
    rain_lap: int | None = Field(default=38, ge=1, le=90)
    safety_car_lap: int | None = Field(default=None, ge=1, le=90)
    position: int = Field(default=4, ge=1, le=22)
    track_temperature: float = Field(default=31, ge=10, le=70)
    gap_ahead: float = Field(default=2.4, ge=0, le=60)
    gap_behind: float = Field(default=1.8, ge=0, le=60)
    pit_loss: float = Field(default=20.5, ge=8, le=40)

    @model_validator(mode="after")
    def validate_laps(self):
        if self.current_lap >= self.total_laps:
            raise ValueError("current_lap must be before total_laps")
        return self


class LapPoint(BaseModel):
    lap: int
    lap_time: float
    cumulative: float
    compound: Compound
    tyre_age: int
    event: str | None = None


class StrategyResult(BaseModel):
    id: str
    name: str
    summary: str
    total_time: float
    delta: float = 0
    confidence: int
    stops: list[int]
    compounds: list[Compound]
    laps: list[LapPoint]
    risk: Literal["LOW", "MEDIUM", "HIGH"]
    rationale: list[str]


class SimulationResponse(BaseModel):
    recommendation: str
    headline: str
    strategies: list[StrategyResult]
    race_state: dict


class EngineerRequest(BaseModel):
    question: str = Field(min_length=2, max_length=500)
    scenario: RaceScenario
    simulation: SimulationResponse | None = None


class EngineerResponse(BaseModel):
    answer: str
    mode: Literal["gpt-5.6", "demo"]
    model: str
    trace: list[dict] = []
