"""2026 season data. Round status and results come from OpenF1 live,
falling back to a bundled snapshot (dated BUNDLED_SNAPSHOT_DATE) if OpenF1
is unreachable, so the app stays functional offline -- per the README's
"fully functional deterministic demo mode" behavior.

This fixes the bug where completed rounds (e.g. Belgium, Hungary) kept
showing as "upcoming" because status used to be decided purely by whether
the race name appeared in a hand-typed RESULTS list that stopped being
updated after 2026-07-14. Status is now decided by comparing today's date
to the race date, then checking for a live (or fallback) result.

Known gap, not fixed here: driver/team championship standings and
fastest-lap-of-the-race are still served from the bundled fallback lists
below. OpenF1 exposes beta "championship" endpoints for this, but their
exact field names weren't confirmed against live docs before writing this,
so wiring them in speculatively risked shipping something silently wrong.
Treat _standings() as the next thing to live-wire once you've checked
https://openf1.org/docs/ for the current shape of those endpoints.
"""
from __future__ import annotations

from datetime import date
import random

from . import openf1_client as of1

# Date the FALLBACK_* data below was last hand-curated. Only surfaces when
# a live OpenF1 lookup fails for a given round -- it's no longer treated
# as "the" snapshot date for the whole app.
BUNDLED_SNAPSHOT_DATE = "2026-07-14"

SOURCES = {
    "calendar": "https://www.formula1.com/en/latest/article/formula-1-reveals-calendar-for-2026-season.YctbMZWqBvrgyddrnauo8",
    "drivers": "https://www.formula1.com/en/results/2026/drivers",
    "teams": "https://www.formula1.com/en/results/2026/team",
    "races": "https://www.formula1.com/en/results/2026/races",
    "fastest_laps": "https://www.formula1.com/en/results/2026/awards/fastest-laps",
    "aduo": "https://www.fia.com/news/power-ups-how-f1s-additional-development-upgrade-opportunities-will-be-applied-and-whats",
    "live_results": "https://openf1.org",
}

CALENDAR = [
    (1,"Australia","Melbourne","2026-03-08",False),(2,"China","Shanghai","2026-03-15",True),(3,"Japan","Suzuka","2026-03-29",False),
    (4,"Bahrain","Sakhir","2026-04-12",False),(5,"Saudi Arabia","Jeddah","2026-04-19",False),(6,"Miami","Miami","2026-05-03",True),
    (7,"Canada","Montreal","2026-05-24",True),(8,"Monaco","Monaco","2026-06-07",False),(9,"Barcelona-Catalunya","Barcelona","2026-06-14",False),
    (10,"Austria","Spielberg","2026-06-28",False),(11,"Great Britain","Silverstone","2026-07-05",True),(12,"Belgium","Spa-Francorchamps","2026-07-19",False),
    (13,"Hungary","Budapest","2026-07-26",False),(14,"Netherlands","Zandvoort","2026-08-23",True),(15,"Italy","Monza","2026-09-06",False),
    (16,"Madrid","Madrid","2026-09-13",False),(17,"Azerbaijan","Baku","2026-09-26",False),(18,"Singapore","Marina Bay","2026-10-11",True),
    (19,"United States","Austin","2026-10-25",False),(20,"Mexico","Mexico City","2026-11-01",False),(21,"Brazil","Sao Paulo","2026-11-08",False),
    (22,"Las Vegas","Las Vegas","2026-11-21",False),(23,"Qatar","Lusail","2026-11-29",False),(24,"Abu Dhabi","Yas Marina","2026-12-06",False),
]

# Venues where OpenF1's meeting `location` field is not a clean substring
# match against the CALENDAR venue above. Verify against a live
# GET /v1/meetings?year=2026 response and adjust as needed -- these are
# best-guess and not confirmed live.
VENUE_ALIASES = {
    "Sao Paulo": "Interlagos",
    "Marina Bay": "Singapore",
}

DISRUPTED_ROUNDS = {"Bahrain", "Saudi Arabia"}

# --- Fallback data (bundled snapshot, used only if OpenF1 is unreachable) ---

FALLBACK_DRIVERS = [
    ("ANT","Kimi Antonelli","ITA","Mercedes",179),("RUS","George Russell","GBR","Mercedes",154),("HAM","Lewis Hamilton","GBR","Ferrari",147),
    ("LEC","Charles Leclerc","MON","Ferrari",108),("NOR","Lando Norris","GBR","McLaren",97),("PIA","Oscar Piastri","AUS","McLaren",82),
    ("VER","Max Verstappen","NED","Red Bull Racing",76),("HAD","Isack Hadjar","FRA","Red Bull Racing",52),("GAS","Pierre Gasly","FRA","Alpine",42),
    ("LAW","Liam Lawson","NZL","Racing Bulls",39),("LIN","Arvid Lindblad","GBR","Racing Bulls",20),("BEA","Oliver Bearman","GBR","Haas F1 Team",18),
    ("COL","Franco Colapinto","ARG","Alpine",18),("BOR","Gabriel Bortoleto","BRA","Audi",6),("SAI","Carlos Sainz","ESP","Williams",6),
    ("ALB","Alexander Albon","THA","Williams",5),("OCO","Esteban Ocon","FRA","Haas F1 Team",3),("ALO","Fernando Alonso","ESP","Aston Martin",1),
    ("HUL","Nico Hulkenberg","GER","Audi",0),("BOT","Valtteri Bottas","FIN","Cadillac",0),("PER","Sergio Perez","MEX","Cadillac",0),("STR","Lance Stroll","CAN","Aston Martin",0),
]
FALLBACK_TEAM_POINTS = {"Mercedes":333,"Ferrari":255,"McLaren":179,"Red Bull Racing":128,"Alpine":60,"Racing Bulls":59,"Haas F1 Team":21,"Williams":11,"Audi":6,"Aston Martin":1,"Cadillac":0}
FALLBACK_POWER_UNITS = {"Mercedes":"Mercedes","Ferrari":"Ferrari","McLaren":"Mercedes","Red Bull Racing":"Red Bull Ford","Alpine":"Mercedes","Racing Bulls":"Red Bull Ford","Haas F1 Team":"Ferrari","Williams":"Mercedes","Audi":"Audi","Aston Martin":"Honda","Cadillac":"Ferrari"}
FALLBACK_RESULTS = [("Australia","George Russell","Mercedes",58),("China","Kimi Antonelli","Mercedes",56),("Japan","Kimi Antonelli","Mercedes",53),("Miami","Kimi Antonelli","Mercedes",57),("Canada","Kimi Antonelli","Mercedes",68),("Monaco","Kimi Antonelli","Mercedes",78),("Barcelona-Catalunya","Lewis Hamilton","Ferrari",66),("Austria","George Russell","Mercedes",71),("Great Britain","Charles Leclerc","Ferrari",52)]
FALLBACK_FASTEST_LAPS = [("Australia","Max Verstappen","1:22.091"),("China","Kimi Antonelli","1:35.275"),("Japan","Kimi Antonelli","1:32.432"),("Miami","Lando Norris","1:31.869"),("Canada","Kimi Antonelli","1:14.210"),("Monaco","Kimi Antonelli","1:13.481"),("Barcelona-Catalunya","Lewis Hamilton","1:20.122"),("Austria","Kimi Antonelli","1:10.374"),("Great Britain","Kimi Antonelli","1:31.777")]
FALLBACK_ACTUAL_EXECUTION = {
    "Australia":(12,1),"China":(10,1),"Japan":(22,1),"Miami":(26,1),"Canada":(31,1),"Monaco":(37,2),"Barcelona-Catalunya":(11,3),"Austria":(None,None),"Great Britain":(25,1),
}
FALLBACK_PIT_SOURCE_IDS = {"Australia":1279,"China":1280,"Japan":1281,"Miami":1284,"Canada":1285,"Monaco":1286,"Barcelona-Catalunya":1287,"Austria":1288,"Great Britain":1289}

# Public-data strategy baselines for every announced round. Historical entries
# are retrospective baselines, not predictions claimed to have existed before
# the event. This is Pitwall's own modeling, independent of live results.
STRATEGY_PROFILES = {
    "Australia":(58,18,"MEDIUM","HARD","MEDIUM"),"China":(56,15,"MEDIUM","HARD","LOW"),"Japan":(53,20,"MEDIUM","HARD","MEDIUM"),
    "Bahrain":(57,18,"SOFT","HARD","HIGH"),"Saudi Arabia":(50,19,"MEDIUM","HARD","MEDIUM"),"Miami":(57,24,"MEDIUM","HARD","MEDIUM"),
    "Canada":(70,25,"MEDIUM","HARD","HIGH"),"Monaco":(78,34,"MEDIUM","HARD","HIGH"),"Barcelona-Catalunya":(66,18,"SOFT","MEDIUM","HIGH"),
    "Austria":(71,24,"MEDIUM","HARD","MEDIUM"),"Great Britain":(52,23,"MEDIUM","HARD","HIGH"),"Belgium":(44,16,"MEDIUM","HARD","HIGH"),
    "Hungary":(70,21,"MEDIUM","HARD","HIGH"),"Netherlands":(72,24,"MEDIUM","HARD","MEDIUM"),"Italy":(53,22,"MEDIUM","HARD","LOW"),
    "Madrid":(57,20,"MEDIUM","HARD","HIGH"),"Azerbaijan":(51,20,"MEDIUM","HARD","HIGH"),"Singapore":(62,24,"MEDIUM","HARD","HIGH"),
    "United States":(56,19,"MEDIUM","HARD","MEDIUM"),"Mexico":(71,24,"MEDIUM","HARD","MEDIUM"),"Brazil":(71,23,"MEDIUM","HARD","HIGH"),
    "Las Vegas":(50,21,"MEDIUM","HARD","HIGH"),"Qatar":(57,18,"MEDIUM","HARD","HIGH"),"Abu Dhabi":(58,22,"MEDIUM","HARD","MEDIUM"),
}

_TEAM_ALIASES = {
    "Oracle Red Bull Racing": "Red Bull Racing",
    "Mercedes-AMG Petronas F1 Team": "Mercedes",
    "Mercedes AMG Petronas F1 Team": "Mercedes",
    "Scuderia Ferrari": "Ferrari",
    "McLaren Formula 1 Team": "McLaren",
    "BWT Alpine F1 Team": "Alpine",
    "Visa Cash App Racing Bulls F1 Team": "Racing Bulls",
    "MoneyGram Haas F1 Team": "Haas F1 Team",
    "Williams Racing": "Williams",
    "Audi F1 Team": "Audi",
    "Aston Martin Aramco F1 Team": "Aston Martin",
    "Cadillac F1 Team": "Cadillac",
}


def _normalize_team(name: str | None) -> str | None:
    if not name:
        return name
    name = name.strip()
    return _TEAM_ALIASES.get(name, name)


def _live_round_result(name: str, venue: str) -> dict | None:
    """Best-effort live result for one round via OpenF1. Returns None if
    the meeting/session/result can't be found (race hasn't happened yet,
    OpenF1 hasn't ingested it, or a network error occurred)."""
    try:
        meetings = of1.get_meetings(2026)
        meeting = of1.find_meeting(meetings, VENUE_ALIASES.get(venue, venue))
        if not meeting:
            return None

        session = of1.get_race_session(meeting["meeting_key"])
        if not session:
            return None

        classification = of1.get_session_result(session["session_key"])
        winner_row = next((r for r in classification if r.get("position") == 1), None)
        if not winner_row:
            return None

        driver_number = winner_row.get("driver_number")
        drivers = of1.get_drivers(session["session_key"], driver_number)
        driver_info = drivers[0] if drivers else {}

        pits = sorted(
            of1.get_pit_stops(session["session_key"], driver_number),
            key=lambda p: p.get("lap_number", 0),
        )

        return {
            "winner": driver_info.get("full_name") or driver_info.get("broadcast_name"),
            "winner_team": _normalize_team(driver_info.get("team_name")),
            "first_stop_lap": pits[0]["lap_number"] if pits else None,
            "stop_count": len(pits) if pits else None,
            "source": f"https://openf1.org (session_key={session['session_key']})",
        }
    except Exception:
        return None


def _fallback_round_result(name: str) -> dict | None:
    row = next((r for r in FALLBACK_RESULTS if r[0] == name), None)
    if not row:
        return None
    _, winner, team, _laps = row
    actual = FALLBACK_ACTUAL_EXECUTION.get(name, (None, None))
    source = None
    if name in FALLBACK_PIT_SOURCE_IDS:
        slug = "spain" if name == "Barcelona-Catalunya" else name.lower().replace(" ", "-")
        source = f"https://www.formula1.com/en/results/2026/races/{FALLBACK_PIT_SOURCE_IDS[name]}/{slug}/pit-stop-summary"
    return {
        "winner": winner,
        "winner_team": team,
        "first_stop_lap": actual[0],
        "stop_count": actual[1],
        "source": source,
    }


def _round_status(name: str, venue: str, race_date: str) -> tuple[str, dict | None]:
    if name in DISRUPTED_ROUNDS:
        return "disrupted", None

    if date.fromisoformat(race_date) > date.today():
        return "upcoming", None

    result = _live_round_result(name, venue) or _fallback_round_result(name)
    if result:
        return "completed", result

    # Race day has passed but neither OpenF1 nor the fallback has a result
    # yet (e.g. just finished, or fallback simply doesn't cover it).
    return "pending", None


def _fallback_standings() -> tuple[list, list]:
    drivers_data = [
        {"position": i + 1, "code": code, "name": name, "nationality": nat, "team": team, "points": points}
        for i, (code, name, nat, team, points) in enumerate(FALLBACK_DRIVERS)
    ]
    teams_data = [
        {
            "position": i + 1,
            "name": team,
            "points": points,
            "power_unit": FALLBACK_POWER_UNITS[team],
            "drivers": [d[1] for d in FALLBACK_DRIVERS if d[3] == team],
        }
        for i, (team, points) in enumerate(sorted(FALLBACK_TEAM_POINTS.items(), key=lambda x: x[1], reverse=True))
    ]
    return drivers_data, teams_data


def _standings() -> tuple[list, list]:
    # TODO: wire to OpenF1's beta championship endpoints once their field
    # names are confirmed against https://openf1.org/docs/. Left on the
    # bundled fallback for now rather than guessing an endpoint shape.
    return _fallback_standings()


def strategy_rounds() -> dict:
    calendar = {r[1]: r for r in CALENDAR}
    items = []
    for name, profile in STRATEGY_PROFILES.items():
        laps, stop, start, end, risk = profile
        round_number, _, venue, race_date, _sprint = calendar[name]
        status, result = _round_status(name, venue, race_date)
        strategy_status = "completed" if status == "completed" else "disrupted" if status == "disrupted" else "forecast"

        actual = None
        if strategy_status == "completed" and result:
            actual = {
                "winner": result["winner"],
                "winner_team": result["winner_team"],
                "first_stop_lap": result["first_stop_lap"],
                "stop_count": result["stop_count"],
                "source": result["source"],
            }

        items.append({
            "round": round_number,
            "race": name,
            "venue": venue,
            "status": strategy_status,
            "forecast": {
                "classification": "retrospective-baseline" if strategy_status == "completed" else "timestamped-forecast",
                "generated_at": date.today().isoformat(),
                "total_laps": laps,
                "first_stop_lap": stop,
                "pit_window": [max(2, stop - 3), stop + 3],
                "start_compound": start,
                "target_compound": end,
                "uncertainty": risk,
            },
            "actual": actual,
        })

    return {
        "snapshot_date": date.today().isoformat(),
        "methodology": {
            "historical": "retrospective baselines; not claimed as prior predictions",
            "future": "timestamped before event completion",
            "leakage_rule": "actual pit, result, weather and safety-car timing excluded from forecast inputs",
        },
        "rounds": sorted(items, key=lambda x: x["round"]),
    }


def backtest_round(round_number: int) -> dict:
    item = next((x for x in strategy_rounds()["rounds"] if x["round"] == round_number), None)
    if not item:
        return {"error": "round not found"}
    if item["status"] != "completed":
        return {**item, "validation": None, "message": "Forecast only; actual execution is not available."}

    forecast = item["forecast"]
    actual = item["actual"]
    if actual["first_stop_lap"] is None:
        return {**item, "validation": {"status": "source-gap", "score": None, "explanation": "Winner pit-stop data not yet available for this round."}}

    error = abs(forecast["first_stop_lap"] - actual["first_stop_lap"])
    agreement = max(0, 100 - error * 8)
    counter = max(2, actual["first_stop_lap"] - 2)
    return {
        **item,
        "validation": {
            "status": "validated",
            "pit_window_hit": forecast["pit_window"][0] <= actual["first_stop_lap"] <= forecast["pit_window"][1],
            "pit_lap_error": error,
            "agreement_score": agreement,
            "explanation": f"The baseline stop was {error} lap{'s' if error != 1 else ''} from the winner's first recorded stop.",
        },
        "counterfactual": {
            "first_stop_lap": counter,
            "classification": "model-estimate",
            "claim": f"Tests an earlier lap {counter} stop; no position gain is claimed without lap-level traffic data.",
        },
    }


def validation_summary() -> dict:
    rounds = strategy_rounds()["rounds"]
    completed = [backtest_round(item["round"]) for item in rounds if item["status"] == "completed"]
    validated = [item for item in completed if item.get("validation", {}).get("status") == "validated"]
    errors = [item["validation"]["pit_lap_error"] for item in validated]
    hits = sum(1 for item in validated if item["validation"]["pit_window_hit"])
    gaps = [item["race"] for item in completed if item.get("validation", {}).get("status") == "source-gap"]

    return {
        "snapshot_date": date.today().isoformat(),
        "classification": "retrospective-validation",
        "coverage": {"completed_rounds": len(completed), "validated_rounds": len(validated), "source_gaps": gaps},
        "metrics": {
            "mean_absolute_stop_lap_error": round(sum(errors) / len(errors), 2) if errors else None,
            "pit_window_hit_rate": round(hits / len(validated) * 100, 1) if validated else None,
            "mean_agreement_score": round(sum(item["validation"]["agreement_score"] for item in validated) / len(validated), 1) if validated else None,
        },
        "disclosure": "Historical baselines were created retrospectively and are not claimed as frozen pre-race forecasts. Actual execution is used only for validation.",
    }


def season_snapshot() -> dict:
    rounds = []
    for number, name, venue, race_date, sprint in CALENDAR:
        status, result = _round_status(name, venue, race_date)
        item = {"round": number, "name": name, "venue": venue, "date": race_date, "sprint": sprint, "status": status}
        if status == "completed" and result:
            laps = STRATEGY_PROFILES.get(name, (None,))[0]
            item.update({"winner": result["winner"], "team": result["winner_team"], "laps": laps})
        rounds.append(item)

    drivers_data, teams_data = _standings()
    completed_count = sum(1 for r in rounds if r["status"] == "completed")

    return {
        "season": 2026,
        "snapshot_date": date.today().isoformat(),
        "provenance": "live-openf1-with-bundled-fallback",
        "sources": SOURCES,
        "summary": {
            "announced_rounds": len(CALENDAR),
            "active_results_rounds": completed_count,
            "teams": len(teams_data),
            "drivers": len(drivers_data),
        },
        "rounds": rounds,
        "drivers": drivers_data,
        "teams": teams_data,
        "fastest_laps": [{"grand_prix": gp, "driver": driver, "time": time} for gp, driver, time in FALLBACK_FASTEST_LAPS],
    }


def simulate_qualifying(circuit: str, trials: int = 2000, wet: bool = False) -> dict:
    """Monte Carlo estimate; explicitly not an official prediction.
    Uses fallback standings as the team-strength proxy -- see _standings()."""
    rng = random.Random(f"{BUNDLED_SNAPSHOT_DATE}:{circuit}:{trials}:{wet}")
    team_rank = {name: i for i, (name, _) in enumerate(sorted(FALLBACK_TEAM_POINTS.items(), key=lambda x: x[1], reverse=True))}
    counts = {d[0]: {"q2": 0, "q3": 0, "pole": 0, "positions": []} for d in FALLBACK_DRIVERS}
    max_points = max(d[4] for d in FALLBACK_DRIVERS)

    for _ in range(trials):
        laps = []
        for code, name, _nat, team, points in FALLBACK_DRIVERS:
            strength = team_rank[team] * .16 + (1 - points / max_points) * .30
            experience = -.05 if name in {"Max Verstappen", "Lewis Hamilton", "Fernando Alonso"} and wet else 0
            laps.append((strength + experience + rng.gauss(0, .16 if wet else .11), code))
        laps.sort()
        order = [code for _, code in laps]
        for pos, code in enumerate(order, 1):
            counts[code]["positions"].append(pos)
            if pos <= 16:
                counts[code]["q2"] += 1
            if pos <= 10:
                counts[code]["q3"] += 1
            if pos == 1:
                counts[code]["pole"] += 1

    results = []
    for code, name, _nat, team, _points in FALLBACK_DRIVERS:
        c = counts[code]
        results.append({
            "code": code,
            "driver": name,
            "team": team,
            "expected_grid": round(sum(c["positions"]) / trials, 1),
            "q2_probability": round(c["q2"] / trials * 100, 1),
            "q3_probability": round(c["q3"] / trials * 100, 1),
            "pole_probability": round(c["pole"] / trials * 100, 1),
        })
    results.sort(key=lambda x: x["expected_grid"])

    high_deployment = any(x in circuit.lower() for x in ("monza", "spa", "baku", "las vegas"))
    harvest_limited = any(x in circuit.lower() for x in ("monaco", "singapore"))
    energy = {
        "deployment_demand": "HIGH" if high_deployment else "LOW" if harvest_limited else "MEDIUM",
        "harvest_opportunity": "LOW" if high_deployment else "HIGH" if harvest_limited else "MEDIUM",
        "active_aero": "X-MODE PRIORITY" if high_deployment else "Z-MODE PRIORITY" if harvest_limited else "BALANCED",
        "boost_call": "Protect charge for final sector" if high_deployment else "Use tactically on the longest passing straight",
        "regulatory_inputs": {
            "maximum_recharge": "7 MJ post-Miami parameter",
            "peak_superclip_power": "350 kW",
            "race_boost_delta_cap": "+150 kW",
        },
    }
    return {
        "circuit": circuit,
        "trials": trials,
        "wet": wet,
        "classification": "pitwall-estimate",
        "snapshot_date": date.today().isoformat(),
        "assumptions": ["2026 championship points proxy team and driver form", "Gaussian lap variance", "No private telemetry or unpublished ICE index"],
        "energy_strategy": energy,
        "results": results,
    }
