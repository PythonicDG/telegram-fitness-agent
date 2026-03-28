"""Negotiation Engine — 3-round negotiation protocol when user rejects daily plan."""

import json
from datetime import date

from database import SheetDB
from prompts import NEGOTIATION_ROUND1_PROMPT, NEGOTIATION_ROUND2_PROMPT, NEGOTIATION_ROUND3_PROMPT


class NegotiationEngine:
    def __init__(self, db_ref: SheetDB, llm_client):
        self.db = db_ref
        self.client = llm_client

    def _call_llm(self, system_prompt: str, messages: list) -> str:
        response = self.client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "system", "content": system_prompt}] + messages,
            temperature=0.7, max_tokens=600,
        )
        return response.choices[0].message.content

    def handle_negotiation(self, user_id: str, message: str) -> dict:
        user = self.db.get_user(user_id)
        current_round = int(user.get("negotiation_round", 1))
        profile = user.get("profile", {})
        today_plan = user.get("today_plan", {})
        maturity = user.get("fitness_maturity", "beginner")
        recent = self.db.get_recent_messages(user_id, limit=10)
        neg_history = "\n".join([f"{'User' if m['role']=='user' else 'Coach'}: {m['content']}" for m in recent[-6:]])
        neg_messages = [m for m in recent if m["role"] == "user"]
        original_objection = neg_messages[-1]["content"] if neg_messages else message

        if current_round == 1:
            return self._round1(user_id, message, profile, maturity, today_plan)
        elif current_round == 2:
            return self._round2(user_id, message, original_objection, profile, maturity, today_plan)
        elif current_round == 3:
            return self._round3(user_id, message, original_objection, profile, maturity, today_plan, neg_history)
        else:
            return self._finalize(user_id, message)

    def _round1(self, user_id, message, profile, maturity, today_plan) -> dict:
        prompt = NEGOTIATION_ROUND1_PROMPT.format(
            profile=json.dumps(profile, indent=2), maturity=maturity,
            original_plan=json.dumps(today_plan, indent=2), objection=message,
        )
        response = self._call_llm(prompt, [{"role": "user", "content": message}])
        self.db.save_message(user_id, "user", message, "negotiation")
        self.db.save_message(user_id, "assistant", response, "negotiation")
        self.db.update_user(user_id, {"negotiation_round": 2})
        return {
            "message": response,
            "buttons": [
                {"text": "🔄 I still want to change it", "data": "neg_continue"},
                {"text": "✅ Okay, let's keep the plan", "data": "neg_accept_original"},
            ],
            "round": 2, "resolved": False, "new_plan": None,
        }

    def _round2(self, user_id, message, original_objection, profile, maturity, today_plan) -> dict:
        prompt = NEGOTIATION_ROUND2_PROMPT.format(
            profile=json.dumps(profile, indent=2), maturity=maturity,
            original_plan=json.dumps(today_plan, indent=2),
            objection=original_objection, latest_message=message,
        )
        response = self._call_llm(prompt, [{"role": "user", "content": message}])
        coach_message = response
        options = None
        if "<<<OPTIONS>>>" in response and "<<<END>>>" in response:
            parts = response.split("<<<OPTIONS>>>")
            coach_message = parts[0].strip()
            json_str = parts[1].split("<<<END>>>")[0].strip()
            try:
                options = json.loads(json_str)
            except json.JSONDecodeError:
                options = None
        self.db.save_message(user_id, "user", message, "negotiation")
        self.db.save_message(user_id, "assistant", coach_message, "negotiation")
        self.db.update_user(user_id, {"negotiation_round": 3})
        if options:
            plan_with_options = {**today_plan, "_neg_options": options}
            self.db.update_user(user_id, {"today_plan": plan_with_options})
        buttons = []
        if options:
            buttons = [
                {"text": f"A: {options.get('option_a', 'Option A')[:30]}", "data": "neg_choose_a"},
                {"text": f"B: {options.get('option_b', 'Option B')[:30]}", "data": "neg_choose_b"},
                {"text": "❌ Neither works for me", "data": "neg_reject_both"},
            ]
        else:
            buttons = [
                {"text": "✅ Okay, let's keep the plan", "data": "neg_accept_original"},
                {"text": "❌ I want something else", "data": "neg_reject_both"},
            ]
        return {"message": coach_message, "buttons": buttons, "round": 3, "resolved": False, "new_plan": None}

    def _round3(self, user_id, message, original_objection, profile, maturity, today_plan, neg_history) -> dict:
        goal = profile.get("goal", "your fitness goal")
        prompt = NEGOTIATION_ROUND3_PROMPT.format(
            profile=json.dumps(profile, indent=2), maturity=maturity, goal=goal,
            original_plan=json.dumps(today_plan, indent=2),
            objection=original_objection, negotiation_history=neg_history,
        )
        response = self._call_llm(prompt, [{"role": "user", "content": message}])
        self.db.save_message(user_id, "user", message, "negotiation")
        self.db.save_message(user_id, "assistant", response, "negotiation")
        return {
            "message": response,
            "buttons": [
                {"text": "✅ Alright, let's go with your plan", "data": "neg_accept_original"},
                {"text": "✏️ I'll do my own thing today", "data": "neg_own_thing"},
            ],
            "round": 3, "resolved": False, "new_plan": None,
        }

    def _finalize(self, user_id, message) -> dict:
        self.db.save_message(user_id, "user", message, "negotiation")
        return {
            "message": "Got it! Whatever you do today, just make sure you move. 💪",
            "buttons": None, "round": 4, "resolved": True, "new_plan": None,
        }

    def accept_original(self, user_id: str) -> dict:
        user = self.db.get_user(user_id)
        today_plan = user.get("today_plan", {})
        today_plan.pop("_neg_options", None)
        today_str = date.today().isoformat()
        self.db.update_user(user_id, {"daily_sub_state": "PLAN_ACCEPTED", "negotiation_round": 0, "today_plan": today_plan})
        self.db.update_plan(user_id, today_str, {"status": "accepted", "negotiation_count": 0})
        return {"message": "That's the spirit! 💪 Here are your tasks for today:", "plan": today_plan}

    def accept_option(self, user_id: str, option: str) -> dict:
        user = self.db.get_user(user_id)
        today_plan = user.get("today_plan", {})
        options = today_plan.get("_neg_options", {})
        if option == "a":
            new_tasks = options.get("option_a_plan", [])
            label = options.get("option_a", "Option A")
        else:
            new_tasks = options.get("option_b_plan", [])
            label = options.get("option_b", "Option B")
        today_plan["tasks"] = new_tasks
        today_plan.pop("_neg_options", None)
        today_str = date.today().isoformat()
        self.db.update_user(user_id, {"daily_sub_state": "PLAN_ACCEPTED", "negotiation_round": 0, "today_plan": today_plan})
        self.db.update_plan(user_id, today_str, {"status": "negotiated", "plan_json": json.dumps(today_plan)})
        return {"message": f"Great choice — going with \"{label}\"! Here are your tasks:", "plan": today_plan}

    def do_own_thing(self, user_id: str) -> dict:
        today_str = date.today().isoformat()
        self.db.update_user(user_id, {"daily_sub_state": "PLAN_ACCEPTED", "negotiation_round": 0})
        self.db.update_plan(user_id, today_str, {"status": "self_directed", "negotiation_count": 3})
        return {"message": "Totally fair. Do what feels right today — just make sure you move. Send me a message later and tell me what you ended up doing! 💪", "plan": None}
