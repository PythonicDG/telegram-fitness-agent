"""Daily Coaching Engine — morning plans, task tracking, evening check-ins, freeform chat."""

import json
import re
from datetime import date, timedelta

from database import SheetDB
from prompts import MORNING_PLAN_PROMPT, EVENING_CHECKIN_PROMPT, FREEFORM_CHAT_PROMPT


class DailyCoachingEngine:
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

    def _get_plan_history(self, user_id: str, days: int = 7) -> str:
        try:
            all_plans = self.db.plans.get_all_records()
            user_plans = [p for p in all_plans if str(p["user_id"]) == str(user_id)]
            recent = user_plans[-days:]
            if not recent:
                return "No previous plans yet."
            lines = []
            for p in recent:
                line = f"- {p.get('date', '?')}: {p.get('status', '?')} ({int(float(p.get('completion_pct', 0)) * 100)}%)"
                if p.get("miss_reason"):
                    line += f" — {p['miss_reason']}"
                lines.append(line)
            return "\n".join(lines)
        except Exception:
            return "No plan history available."

    def _get_yesterday_result(self, user_id: str) -> str:
        yesterday = (date.today() - timedelta(days=1)).isoformat()
        plan = self.db.get_today_plan(user_id, yesterday)
        if not plan:
            return "No data from yesterday."
        return f"Yesterday: {plan.get('status', '?')} ({int(float(plan.get('completion_pct', 0)) * 100)}%)"

    def generate_morning_plan(self, user_id: str) -> dict:
        user = self.db.get_user(user_id)
        if not user:
            return {"message": "Error: user not found", "plan": {}, "task_count": 0}
        profile = user.get("profile", {})
        habits = user.get("current_habits", [])
        prompt = MORNING_PLAN_PROMPT.format(
            profile=json.dumps(profile, indent=2),
            maturity=user.get("fitness_maturity", "beginner"),
            habits=", ".join(habits) if habits else "None",
            days_active=user.get("days_active", 0),
            streak=user.get("streak", 0),
            yesterday_result=self._get_yesterday_result(user_id),
            plan_history=self._get_plan_history(user_id),
        )
        response = self._call_llm(prompt, [{"role": "user", "content": "Generate today's plan."}])
        try:
            cleaned = re.sub(r'^```json\s*', '', response.strip())
            cleaned = re.sub(r'\s*```$', '', cleaned)
            plan = json.loads(cleaned)
        except json.JSONDecodeError:
            plan = {
                "greeting": "Good morning! Let's make today count.",
                "tasks": [{"id": i+1, "description": h, "category": "exercise", "why": "Building consistency."} for i, h in enumerate(habits[:3])],
                "coach_note": "Every day you show up is a win."
            }
        tasks = plan.get("tasks", [])
        task_lines = []
        for t in tasks:
            emoji = {"exercise": "🏋️", "mobility": "🧘", "nutrition": "🥗", "mindset": "🧠"}.get(t.get("category", ""), "📌")
            task_lines.append(f"{emoji} {t['description']}\n   ↳ {t.get('why', '')}")
        message = f"{plan.get('greeting', 'Good morning!')}\n\n🎯 Your mission for today:\n\n" + "\n\n".join(task_lines) + f"\n\n💬 {plan.get('coach_note', '')}"
        today_str = date.today().isoformat()
        self.db.save_plan(user_id, today_str, plan)
        self.db.update_user(user_id, {"daily_sub_state": "AWAITING_PLAN_RESPONSE", "today_plan": plan})
        return {"message": message, "plan": plan, "task_count": len(tasks)}

    def complete_task(self, user_id: str, task_index: int) -> dict:
        user = self.db.get_user(user_id)
        today_plan = user.get("today_plan", {})
        tasks = today_plan.get("tasks", [])
        if task_index >= len(tasks):
            return {"message": "Task not found.", "all_done": False, "completed": 0, "total": 0}
        tasks[task_index]["completed"] = True
        today_plan["tasks"] = tasks
        completed_count = sum(1 for t in tasks if t.get("completed"))
        total = len(tasks)
        all_done = completed_count == total
        completion_pct = completed_count / total if total > 0 else 0
        self.db.update_user(user_id, {"today_plan": today_plan})
        today_str = date.today().isoformat()
        self.db.update_plan(user_id, today_str, {"plan_json": json.dumps(today_plan), "completion_pct": completion_pct, "status": "completed" if all_done else "in_progress"})
        if all_done:
            self.db.update_user(user_id, {"daily_sub_state": "DAY_COMPLETE"})
        completed_task = tasks[task_index]
        remaining = total - completed_count
        if all_done:
            streak = int(user.get("streak", 0)) + 1
            self.db.update_user(user_id, {"streak": streak})
            message = f"✅ {completed_task['description']} — DONE!\n\n🔥 ALL TASKS COMPLETE! That's a perfect day!\nYour streak: {streak} days and counting.\n\nI'll check in with you this evening to see how everything felt."
        else:
            message = f"✅ {completed_task['description']} — DONE!\n\nNice work! {remaining} {'task' if remaining == 1 else 'tasks'} left for today. You've got this 💪"
        self.db.save_message(user_id, "assistant", message, "task_completion")
        return {"message": message, "all_done": all_done, "completed": completed_count, "total": total}

    def generate_evening_checkin(self, user_id: str) -> str:
        user = self.db.get_user(user_id)
        today_plan = user.get("today_plan", {})
        tasks = today_plan.get("tasks", [])
        completed = [t for t in tasks if t.get("completed")]
        incomplete = [t for t in tasks if not t.get("completed")]
        prompt = EVENING_CHECKIN_PROMPT.format(
            profile=json.dumps(user.get("profile", {}), indent=2),
            maturity=user.get("fitness_maturity", "beginner"),
            today_plan=json.dumps(today_plan, indent=2),
            completed_tasks=len(completed), total_tasks=len(tasks),
            completed_list=", ".join([t["description"] for t in completed]) or "None",
            incomplete_list=", ".join([t["description"] for t in incomplete]) or "All done!",
            streak=user.get("streak", 0), days_active=user.get("days_active", 0),
        )
        response = self._call_llm(prompt, [{"role": "user", "content": "Do my evening check-in."}])
        days = int(user.get("days_active", 0)) + 1
        self.db.update_user(user_id, {"daily_sub_state": "CHECKED_IN", "days_active": days})
        if not completed and tasks:
            misses = int(user.get("consecutive_misses", 0)) + 1
            self.db.update_user(user_id, {"consecutive_misses": misses})
        elif completed:
            self.db.update_user(user_id, {"consecutive_misses": 0})
        self.db.save_message(user_id, "assistant", response, "check_in")
        return response

    def handle_freeform_chat(self, user_id: str, message: str) -> str:
        user = self.db.get_user(user_id)
        today_plan = user.get("today_plan", {})
        tasks = today_plan.get("tasks", [])
        completed_today = [t["description"] for t in tasks if t.get("completed")]
        recent_messages = self.db.get_recent_messages(user_id, limit=5)
        prompt = FREEFORM_CHAT_PROMPT.format(
            profile=json.dumps(user.get("profile", {}), indent=2),
            maturity=user.get("fitness_maturity", "beginner"),
            habits=", ".join(user.get("current_habits", [])),
            today_plan=json.dumps(today_plan, indent=2) if today_plan.get("tasks") else "No plan yet today",
            completed_today=", ".join(completed_today) if completed_today else "None yet",
            streak=user.get("streak", 0), days_active=user.get("days_active", 0),
            sub_state=user.get("daily_sub_state", ""),
        )
        messages = recent_messages + [{"role": "user", "content": message}]
        response = self._call_llm(prompt, messages)
        self.db.save_message(user_id, "user", message, "daily_chat")
        self.db.save_message(user_id, "assistant", response, "daily_chat")
        return response
