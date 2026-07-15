import json
import os

from openai import OpenAI

from .engine import monte_carlo, simulate
from .models import EngineerRequest, EngineerResponse, RaceScenario
from .season import backtest_round

SYSTEM_PROMPT = """You are ORBIT, a calm elite motorsport strategy agent inside PitWall AI.
You must use the available analysis tools before every recommendation. Use tool results only;
never invent telemetry or claim projections are live race data. Answer in 3 concise sentences: lead with BOX, STAY OUT, PUSH,
CONSERVE, or MONITOR and state the action and lap; explain the decisive trade-off using an
exact delta, stop lap, compound, or confidence; then name the largest uncertainty and the
concrete condition that would invalidate the call. If asked why a call changed, contrast
tool results and changed inputs. This is an educational simulation."""

TOOLS = [
    {"type":"function","name":"run_strategy_model","description":"Run and rank three deterministic pit strategies for a race state.","parameters":{"type":"object","properties":{"overrides":{"type":"object","description":"Optional RaceScenario fields to change for a counterfactual."}},"required":[]}},
    {"type":"function","name":"stress_test_strategy","description":"Run 240 seeded uncertainty trials and model rival response.","parameters":{"type":"object","properties":{"overrides":{"type":"object"}},"required":[]}},
    {"type":"function","name":"inspect_historical_round","description":"Compare a historical baseline with official winner pit execution.","parameters":{"type":"object","properties":{"round_number":{"type":"integer","minimum":1,"maximum":24}},"required":["round_number"]}},
]


def _scenario(request: EngineerRequest, overrides: dict | None = None) -> RaceScenario:
    data=request.scenario.model_dump(); data.update(overrides or {})
    return RaceScenario.model_validate(data)


def _execute_tool(name: str, arguments: dict, request: EngineerRequest) -> dict:
    if name == "run_strategy_model":
        result=simulate(_scenario(request, arguments.get("overrides")))
        return result.model_dump(exclude={"strategies":{"__all__":{"laps"}}})
    if name == "stress_test_strategy":
        return monte_carlo(_scenario(request, arguments.get("overrides")))
    if name == "inspect_historical_round":
        return backtest_round(arguments["round_number"])
    return {"error":f"Unknown tool: {name}"}


def _demo_answer(request: EngineerRequest) -> str:
    sim = request.simulation
    if not sim:
        return "MONITOR. Run the model first so I can base the call on calculated race state."
    best = next(s for s in sim.strategies if s.id == sim.recommendation)
    question = request.question.lower()
    if "rain" in question and request.scenario.rain_lap:
        return f"STAY OUT until the model's lap {best.stops[0]} target. {best.name} leads by {sim.strategies[1].delta:.1f}s with the crossover near lap {request.scenario.rain_lap}. Invalidate the call if rain shifts by more than three laps or a safety car changes the pit window."
    if any(word in question for word in ("pit", "box", "undercut")):
        return f"BOX on lap {best.stops[0]}. {best.name} leads by {sim.strategies[1].delta:.1f}s and transitions to {best.compounds[-1].lower()} tyres. Invalidate the call if the clean-air rejoin disappears or a safety car changes pit loss."
    return f"PUSH to the lap {best.stops[0]} target. {best.name} is quickest by {sim.strategies[1].delta:.1f}s with {best.confidence}% confidence. The call is invalid if weather or a safety car materially changes the stop window."


def ask_engineer(request: EngineerRequest) -> EngineerResponse:
    model = os.getenv("OPENAI_MODEL", "gpt-5.6")
    if not os.getenv("OPENAI_API_KEY"):
        return EngineerResponse(answer=_demo_answer(request), mode="demo", model=model, trace=[{"tool":"run_strategy_model","status":"demo-replay"},{"tool":"stress_test_strategy","status":"demo-replay"}])
    client = OpenAI()
    payload={"question":request.question,"race_state":request.scenario.model_dump(),"instruction":"Use one or more tools, then make the call."}
    inputs=[{"role":"user","content":json.dumps(payload)}]; trace=[]; response=None
    for turn in range(4):
        response=client.responses.create(model=model,reasoning={"effort":"medium"},instructions=SYSTEM_PROMPT,input=inputs,tools=TOOLS,tool_choice="required" if turn==0 else "auto")
        inputs.extend(response.output); calls=[item for item in response.output if item.type=="function_call"]
        if not calls: break
        for call in calls:
            arguments=json.loads(call.arguments or "{}")
            output=_execute_tool(call.name,arguments,request)
            trace.append({"tool":call.name,"status":"completed","evidence":_trace_evidence(call.name,output)})
            inputs.append({"type":"function_call_output","call_id":call.call_id,"output":json.dumps(output)})
    answer=response.output_text if response and response.output_text else "MONITOR. The analysis tools completed, but ORBIT did not return a final call."
    return EngineerResponse(answer=answer,mode="gpt-5.6",model=model,trace=trace)


def _trace_evidence(name: str, output: dict) -> str:
    if name=="run_strategy_model": return output.get("headline","strategy ranking complete")
    if name=="stress_test_strategy": return f"{output.get('trials',0)} trials · {output.get('rival',{}).get('pressure','—')} rival pressure"
    if name=="inspect_historical_round": return f"R{output.get('round','—')} · {output.get('validation',{}).get('status','forecast only') if output.get('validation') else 'forecast only'}"
    return "completed"
