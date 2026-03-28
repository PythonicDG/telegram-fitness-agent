"""LangGraph onboarding state machine."""

import json
from typing import TypedDict
from langgraph.graph import StateGraph, END
from config import call_llm
from prompts import ONBOARDING_SYSTEM_PROMPT, CLASSIFIER_SYSTEM_PROMPT


class CoachState(TypedDict):
    user_id: str
    state: str
    daily_sub_state: str
    profile: dict
    fitness_maturity: str
    current_habits: list
    messages: list
    today_plan: dict
    negotiation_round: int
    consecutive_misses: int
    streak: int
    coach_response: str
    days_active: int


def onboarding_node(state: CoachState) -> dict:
    response = call_llm(ONBOARDING_SYSTEM_PROMPT, state["messages"])
    coach_message = response
    extracted_update = {}
    all_collected = False
    if "<<<DATA>>>" in response and "<<<END>>>" in response:
        parts = response.split("<<<DATA>>>")
        coach_message = parts[0].strip()
        json_str = parts[1].split("<<<END>>>")[0].strip()
        try:
            data = json.loads(json_str)
            for key, value in data.get("extracted", {}).items():
                if value is not None:
                    extracted_update[key] = value
            all_collected = data.get("all_collected", False)
        except json.JSONDecodeError:
            pass
    updated_profile = {**state["profile"], **extracted_update}
    updated_messages = state["messages"] + [{"role": "assistant", "content": coach_message}]
    next_state = "CLASSIFYING" if all_collected else "ONBOARDING"
    return {
        "profile": updated_profile,
        "messages": updated_messages,
        "coach_response": coach_message,
        "state": next_state,
    }


def classifying_node(state: CoachState) -> dict:
    profile_summary = json.dumps(state["profile"], indent=2)
    response = call_llm(
        CLASSIFIER_SYSTEM_PROMPT,
        [{"role": "user", "content": f"User profile:\n{profile_summary}"}]
    )
    try:
        classification = json.loads(response)
    except json.JSONDecodeError:
        classification = {
            "maturity": "beginner",
            "reasoning": "Could not classify, defaulting to beginner",
            "first_habit": "15-minute walk after dinner"
        }
    maturity = classification["maturity"]
    first_habit = classification["first_habit"]
    reasoning = classification["reasoning"]
    coach_message = (
        f"Alright, I've got a good picture of where you are! "
        f"Based on what you've told me, I'd say you're at a {maturity.replace('_', ' ')} level — {reasoning}\n\n"
        f"Here's how we're going to start. Your first mission is simple:\n"
        f"👉 {first_habit}\n\n"
        f"That's it. Just this one thing. We're going to nail this before adding anything else. "
        f"I'll check in with you tomorrow to see how it went. Sound good?"
    )
    updated_messages = state["messages"] + [{"role": "assistant", "content": coach_message}]
    return {
        "fitness_maturity": maturity,
        "current_habits": [first_habit],
        "messages": updated_messages,
        "coach_response": coach_message,
        "state": "ACTIVE",
        "days_active": 1,
    }


def route_after_onboarding(state: CoachState) -> str:
    if state["state"] == "CLASSIFYING":
        return "classifying"
    return END


def build_coach_graph():
    graph = StateGraph(CoachState)
    graph.add_node("onboarding", onboarding_node)
    graph.add_node("classifying", classifying_node)
    graph.set_entry_point("onboarding")
    graph.add_conditional_edges("onboarding", route_after_onboarding, {"classifying": "classifying", END: END})
    graph.add_edge("classifying", END)
    return graph.compile()
