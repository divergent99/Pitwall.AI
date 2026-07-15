from dataclasses import dataclass
import random

from .models import LapPoint, RaceScenario, SimulationResponse, StrategyResult

PACE = {"SOFT": -0.75, "MEDIUM": 0.0, "HARD": 0.58, "INTERMEDIATE": 4.4}
DEG = {"SOFT": 0.075, "MEDIUM": 0.035, "HARD": 0.025, "INTERMEDIATE": 0.05}
CIRCUITS = {
    "melbourne":{"base_lap":80.8,"degradation":.96,"undercut":1.02,"energy":"BALANCED","aero":"MIXED X/Z"},
    "shanghai":{"base_lap":94.5,"degradation":1.12,"undercut":1.08,"energy":"HIGH DEPLOYMENT","aero":"MIXED X/Z"},
    "suzuka":{"base_lap":91.8,"degradation":1.30,"undercut":.96,"energy":"BALANCED","aero":"Z-MODE PRIORITY"},
    "sakhir":{"base_lap":92.2,"degradation":1.34,"undercut":1.12,"energy":"HIGH DEPLOYMENT","aero":"MIXED X/Z"},
    "jeddah":{"base_lap":88.5,"degradation":.82,"undercut":.90,"energy":"MAX DEPLOYMENT","aero":"X-MODE PRIORITY"},
    "miami":{"base_lap":91.2,"degradation":1.02,"undercut":1.04,"energy":"HIGH DEPLOYMENT","aero":"MIXED X/Z"},
    "montreal":{"base_lap":73.8,"degradation":.92,"undercut":1.05,"energy":"MAX DEPLOYMENT","aero":"X-MODE PRIORITY"},
    "monaco":{"base_lap":72.9,"degradation":.78,"undercut":.62,"energy":"HARVEST-RICH","aero":"Z-MODE PRIORITY"},
    "barcelona":{"base_lap":79.8,"degradation":1.32,"undercut":1.08,"energy":"BALANCED","aero":"Z-MODE PRIORITY"},
    "spielberg":{"base_lap":69.7,"degradation":.94,"undercut":1.02,"energy":"MAX DEPLOYMENT","aero":"X-MODE PRIORITY"},
    "marina-bay": {"base_lap": 89.4, "degradation": 1.15, "undercut": 1.12, "energy":"HARVEST-RICH", "aero":"Z-MODE PRIORITY"},
    "monza": {"base_lap": 81.2, "degradation": .72, "undercut": .78, "energy":"MAX DEPLOYMENT", "aero":"X-MODE PRIORITY"},
    "silverstone": {"base_lap": 87.8, "degradation": 1.28, "undercut": 1.0, "energy":"BALANCED", "aero":"MIXED X/Z"},
    "spa":{"base_lap":104.5,"degradation":1.18,"undercut":.95,"energy":"MAX DEPLOYMENT","aero":"X-MODE PRIORITY"},
    "budapest":{"base_lap":77.9,"degradation":1.20,"undercut":1.10,"energy":"HARVEST-RICH","aero":"Z-MODE PRIORITY"},
    "zandvoort":{"base_lap":71.6,"degradation":1.14,"undercut":1.06,"energy":"BALANCED","aero":"Z-MODE PRIORITY"},
    "madrid":{"base_lap":88.0,"degradation":1.05,"undercut":1.00,"energy":"BALANCED","aero":"MIXED X/Z"},
    "baku":{"base_lap":103.2,"degradation":.76,"undercut":.86,"energy":"MAX DEPLOYMENT","aero":"X-MODE PRIORITY"},
    "austin":{"base_lap":96.8,"degradation":1.25,"undercut":1.07,"energy":"BALANCED","aero":"MIXED X/Z"},
    "mexico-city":{"base_lap":77.5,"degradation":.98,"undercut":1.02,"energy":"ALTITUDE LIMITED","aero":"Z-MODE PRIORITY"},
    "sao-paulo":{"base_lap":70.8,"degradation":1.12,"undercut":1.06,"energy":"HIGH DEPLOYMENT","aero":"MIXED X/Z"},
    "las-vegas":{"base_lap":94.0,"degradation":.66,"undercut":.82,"energy":"MAX DEPLOYMENT","aero":"X-MODE PRIORITY"},
    "lusail":{"base_lap":82.4,"degradation":1.38,"undercut":1.02,"energy":"HIGH DEPLOYMENT","aero":"Z-MODE PRIORITY"},
    "yas-marina":{"base_lap":86.2,"degradation":1.02,"undercut":1.04,"energy":"HIGH DEPLOYMENT","aero":"MIXED X/Z"},
}


@dataclass(frozen=True)
class Plan:
    id: str
    name: str
    stops: tuple[int, ...]
    compounds: tuple[str, ...]
    summary: str
    risk: str


def _plans(s: RaceScenario) -> list[Plan]:
    remaining = s.total_laps - s.current_lap
    position_bias = 2 if s.position <= 3 else 0 if s.position <= 10 else -1
    undercut_offset = max(1, (1 if CIRCUITS[s.circuit]["undercut"] > 1 else 3) + position_bias)
    early = min(s.total_laps - 3, s.current_lap + max(undercut_offset, min(4, remaining // 5)))
    middle = min(s.total_laps - 2, s.current_lap + max(6, remaining // 2))
    late = min(s.total_laps - 2, s.current_lap + max(9, int(remaining * 0.66)))
    rain = s.rain_lap if s.rain_lap and s.current_lap < s.rain_lap < s.total_laps else None
    if rain:
        split_lap = max(s.current_lap + 2, rain - 10)
        return [
            Plan("box-now", "Attack the undercut", (early, rain), (s.compound, "SOFT", "INTERMEDIATE"), "Create clean air now, then cover the rain window.", "MEDIUM"),
            Plan("extend", "Extend to crossover", (rain,), (s.compound, "INTERMEDIATE"), "Protect track position and stop once at the wet crossover.", "LOW"),
            Plan("split", "Two-stop pressure", (split_lap, rain), (s.compound, "MEDIUM", "INTERMEDIATE"), "Use fresh rubber to force the cars ahead to react.", "HIGH"),
        ]
    return [
        Plan("box-now", "Attack the undercut", (early,), (s.compound, "HARD"), "Pit early for clean air and commit to the finish.", "MEDIUM"),
        Plan("extend", "Extend the first stint", (late,), (s.compound, "SOFT"), "Preserve track position, then attack on softs.", "LOW"),
        Plan("two-stop", "Two-stop attack", (middle, late), (s.compound, "MEDIUM", "SOFT"), "Trade pit loss for sustained tyre advantage.", "HIGH"),
    ]


def _lap_time(s: RaceScenario, lap: int, compound: str, age: int) -> float:
    circuit = CIRCUITS[s.circuit]
    fuel_effect = (s.total_laps - lap) * 0.031
    heat_factor = 1 + max(-.12, (s.track_temperature - 30) * .009)
    degradation = DEG[compound] * circuit["degradation"] * heat_factor * max(age, 0) ** 1.17
    wet = s.rain_lap is not None and lap >= s.rain_lap
    weather_penalty = 0.0
    if wet and compound != "INTERMEDIATE":
        weather_penalty = 8.5 + (lap - s.rain_lap) * 0.32
    elif not wet and compound == "INTERMEDIATE":
        weather_penalty = 5.8
    safety = 8.0 if s.safety_car_lap and abs(lap - s.safety_car_lap) <= 1 else 0.0
    traffic = min(.48, max(0, s.position - 1) * .022)
    temperature_penalty = max(0, s.track_temperature - 38) * .012 + max(0, 22 - s.track_temperature) * .02
    return circuit["base_lap"] + PACE[compound] + fuel_effect + degradation + weather_penalty + safety + traffic + temperature_penalty


def _rationale(s: RaceScenario, plan: Plan) -> list[str]:
    if plan.stops[0] <= s.current_lap + 4:
        first = f"A stop on lap {plan.stops[0]} targets the undercut before tyre loss accelerates."
    else:
        first = f"Extending to lap {plan.stops[0]} protects track position but increases degradation exposure."
    notes = [first]
    if s.rain_lap:
        notes.append(f"Forecast crossover is lap {s.rain_lap}; timing uncertainty is the main strategic risk.")
    if len(plan.stops) > 1:
        notes.append(f"Two stops add pit-loss exposure but deliver {plan.compounds[-1].lower()}-tyre pace late in the race.")
    else:
        notes.append("A single-stop profile minimizes time lost in pit lane.")
    return notes


def _simulate_plan(s: RaceScenario, plan: Plan) -> StrategyResult:
    current, age, compound_index, cumulative = plan.compounds[0], s.tyre_age, 0, 0.0
    laps: list[LapPoint] = []
    for lap in range(s.current_lap + 1, s.total_laps + 1):
        event = None
        pit_loss = 0.0
        if lap in plan.stops:
            compound_index += 1
            current, age, event = plan.compounds[compound_index], 0, f"PIT · {plan.compounds[compound_index]}"
            pit_loss = s.pit_loss * 0.56 if s.safety_car_lap and abs(lap - s.safety_car_lap) <= 1 else s.pit_loss
            if lap == plan.stops[0]:
                if plan.id == "box-now": pit_loss -= min(1.8, max(0, s.position - 1) * .09)
                elif plan.id == "extend" and s.position <= 3: pit_loss -= .65
                elif len(plan.stops) > 1 and s.position >= 12: pit_loss += .45
        age += 1
        lap_time = _lap_time(s, lap, current, age) + pit_loss
        cumulative += lap_time
        laps.append(LapPoint(lap=lap, lap_time=round(lap_time, 3), cumulative=round(cumulative, 3), compound=current, tyre_age=age, event=event))
    confidence = {"LOW": 88, "MEDIUM": 78, "HIGH": 66}[plan.risk] - min(8, abs(s.position - 6) // 3)
    return StrategyResult(id=plan.id, name=plan.name, summary=plan.summary, total_time=round(cumulative, 3), confidence=confidence, stops=list(plan.stops), compounds=list(plan.compounds), laps=laps, risk=plan.risk, rationale=_rationale(s, plan))


def simulate(s: RaceScenario) -> SimulationResponse:
    results = sorted((_simulate_plan(s, p) for p in _plans(s)), key=lambda item: item.total_time)
    best = results[0].total_time
    for result in results:
        result.delta = round(result.total_time - best, 2)
    return SimulationResponse(
        recommendation=results[0].id,
        headline=f"{results[0].name} is projected {results[1].delta:.1f}s faster",
        strategies=results,
        race_state={"lap": s.current_lap, "remaining": s.total_laps - s.current_lap, "position":s.position, "track_temperature":s.track_temperature, "traffic_exposure":"HIGH" if s.position>=12 else "MEDIUM" if s.position>=5 else "LOW", "track_status": "LIGHT RAIN FORECAST" if s.rain_lap else "TRACK CLEAR", "gap_ahead": s.gap_ahead, "gap_behind": s.gap_behind, "circuit":s.circuit, "energy_profile":CIRCUITS[s.circuit]["energy"], "active_aero":CIRCUITS[s.circuit]["aero"], "regulation_basis":"2026 educational approximation"},
    )


def monte_carlo(s: RaceScenario, trials: int = 240) -> dict:
    """Stress-test strategy ranking against forecast and pit-loss uncertainty."""
    rng = random.Random(f"{s.circuit}:{s.total_laps}:{s.current_lap}:{s.tyre_age}:{s.rain_lap}:{s.safety_car_lap}")
    wins: dict[str, int] = {}
    deltas: dict[str, list[float]] = {}
    rain_samples: list[int] = []
    for _ in range(trials):
        rain_lap = s.rain_lap
        if rain_lap:
            rain_lap = max(s.current_lap + 2, min(s.total_laps - 1, round(rng.gauss(rain_lap, 3.2))))
            rain_samples.append(rain_lap)
        trial = s.model_copy(update={"rain_lap": rain_lap, "pit_loss": max(12.0, rng.gauss(s.pit_loss, 1.35))})
        result = simulate(trial)
        wins[result.recommendation] = wins.get(result.recommendation, 0) + 1
        for strategy in result.strategies:
            deltas.setdefault(strategy.id, []).append(strategy.delta)

    base = simulate(s)
    strategies = []
    for strategy in base.strategies:
        samples = sorted(deltas[strategy.id])
        strategies.append({
            "id": strategy.id,
            "name": strategy.name,
            "win_probability": round(wins.get(strategy.id, 0) / trials * 100, 1),
            "mean_delta": round(sum(samples) / len(samples), 2),
            "p90_delta": round(samples[int(len(samples) * .9)], 2),
        })
    strategies.sort(key=lambda item: item["win_probability"], reverse=True)
    rival_pressure = "HIGH" if s.gap_behind < 2.5 or s.position >= 12 else "MEDIUM" if s.gap_behind < 5 or s.position >= 6 else "LOW"
    response_lap = min(s.total_laps - 1, base.strategies[0].stops[0] + (1 if s.gap_behind < 2.5 else 2))
    return {
        "trials": trials,
        "strategies": strategies,
        "weather_window": {"earliest": min(rain_samples), "latest": max(rain_samples)} if rain_samples else None,
        "rival": {
            "pressure": rival_pressure,
            "predicted_response_lap": response_lap,
            "undercut_risk": round(max(8, min(92, 74 - s.gap_behind * 13 + max(0,s.position-6)*1.2)), 1),
            "call": "Cover the response" if rival_pressure == "HIGH" else "Prioritize our race",
        },
    }
