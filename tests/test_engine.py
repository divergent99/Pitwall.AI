from app.engine import CIRCUITS, monte_carlo, simulate
from app.ai_engineer import _execute_tool
from app.models import EngineerRequest, RaceScenario
from app.season import backtest_round, season_snapshot, simulate_qualifying, strategy_rounds, validation_summary


def test_simulation_returns_ranked_strategies():
    result = simulate(RaceScenario())
    assert len(result.strategies) == 3
    assert result.strategies[0].delta == 0
    assert result.strategies[1].delta >= 0
    assert result.recommendation == result.strategies[0].id


def test_rain_scenario_uses_intermediates():
    result = simulate(RaceScenario(rain_lap=35))
    assert all("INTERMEDIATE" in strategy.compounds for strategy in result.strategies)


def test_safety_car_changes_strategy_times():
    normal = simulate(RaceScenario(rain_lap=None, safety_car_lap=None))
    safety = simulate(RaceScenario(rain_lap=None, safety_car_lap=22))
    assert [s.total_time for s in normal.strategies] != [s.total_time for s in safety.strategies]


def test_monte_carlo_is_reproducible_and_models_rival():
    scenario = RaceScenario()
    first = monte_carlo(scenario, trials=40)
    second = monte_carlo(scenario, trials=40)
    assert first == second
    assert round(sum(item["win_probability"] for item in first["strategies"])) == 100
    assert first["weather_window"]["earliest"] < first["weather_window"]["latest"]
    assert first["rival"]["pressure"] == "HIGH"


def test_circuit_profiles_change_pace_and_strategy_physics():
    marina = simulate(RaceScenario(circuit="marina-bay", total_laps=53, rain_lap=None))
    monza = simulate(RaceScenario(circuit="monza", total_laps=53, rain_lap=None, pit_loss=24.3))
    silverstone = simulate(RaceScenario(circuit="silverstone", total_laps=53, rain_lap=None, pit_loss=21.5))
    assert monza.strategies[0].total_time < silverstone.strategies[0].total_time < marina.strategies[0].total_time
    assert len({marina.strategies[0].stops[0], monza.strategies[0].stops[0]}) > 1


def test_season_snapshot_has_provenance_and_full_grid():
    data = season_snapshot()
    assert len(data["rounds"]) == 24
    assert len(data["drivers"]) == 22
    assert len(data["teams"]) == 11
    assert data["sources"]["drivers"].startswith("https://www.formula1.com")


def test_qualifying_probabilities_are_reproducible():
    first = simulate_qualifying("Spa-Francorchamps", 250, wet=True)
    second = simulate_qualifying("Spa-Francorchamps", 250, wet=True)
    assert first == second
    assert len(first["results"]) == 22
    assert round(sum(x["pole_probability"] for x in first["results"])) == 100


def test_all_round_strategy_coverage_and_backtest_states():
    data = strategy_rounds()
    assert len(data["rounds"]) == 24
    australia = backtest_round(1)
    assert australia["actual"]["first_stop_lap"] == 12
    assert australia["validation"]["status"] == "validated"
    belgium = backtest_round(12)
    assert belgium["actual"] is None
    assert belgium["validation"] is None


def test_live_strategy_room_supports_all_24_circuits():
    assert len(CIRCUITS) == 24
    for circuit in CIRCUITS:
        result = simulate(RaceScenario(circuit=circuit, total_laps=50, current_lap=18, rain_lap=None))
        assert len(result.strategies) == 3
        assert result.race_state["circuit"] == circuit


def test_position_changes_traffic_and_strategy_output():
    leader = simulate(RaceScenario(position=1, rain_lap=None))
    traffic = simulate(RaceScenario(position=18, rain_lap=None))
    assert leader.race_state["traffic_exposure"] == "LOW"
    assert traffic.race_state["traffic_exposure"] == "HIGH"
    assert leader.strategies[0].total_time != traffic.strategies[0].total_time
    assert leader.strategies[0].stops != traffic.strategies[0].stops


def test_orbit_agent_tools_return_grounded_outputs():
    request = EngineerRequest(question="Should we box?", scenario=RaceScenario(position=12))
    strategy = _execute_tool("run_strategy_model", {}, request)
    uncertainty = _execute_tool("stress_test_strategy", {}, request)
    history = _execute_tool("inspect_historical_round", {"round_number": 1}, request)
    assert strategy["race_state"]["position"] == 12
    assert uncertainty["trials"] == 240
    assert history["validation"]["status"] == "validated"


def test_validation_scorecard_discloses_coverage_and_error():
    score = validation_summary()
    assert score["coverage"]["completed_rounds"] == 9
    assert score["coverage"]["validated_rounds"] == 8
    assert score["metrics"]["mean_absolute_stop_lap_error"] >= 0
    assert "retrospectively" in score["disclosure"]


def test_temperature_and_gaps_change_model_outputs():
    cool = simulate(RaceScenario(track_temperature=20, gap_behind=6, rain_lap=None))
    hot = simulate(RaceScenario(track_temperature=48, gap_behind=.6, rain_lap=None))
    assert cool.strategies[0].total_time != hot.strategies[0].total_time
    cool_rival = monte_carlo(RaceScenario(track_temperature=20, gap_behind=6), trials=20)
    hot_rival = monte_carlo(RaceScenario(track_temperature=48, gap_behind=.6), trials=20)
    assert cool_rival["rival"]["pressure"] != hot_rival["rival"]["pressure"]
