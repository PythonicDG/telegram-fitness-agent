"""Recovery Engine — miss handling, scale-down, recovery rebuild, absence detection."""

import json
from datetime import datetime, date, timedelta

from database import SheetDB
from prompts import (
    MISS_RESPONSE_PROMPT, SCALE_DOWN_PROMPT,
    RECOVERY_REBUILD_PROMPT, ABSENCE_CHECKIN_PROMPT,
)


class RecoveryEngine:
    MISS_REASONS = {
        "didnt_feel": "Just didn't feel like it",
        "sick": "Feeling sick",
        "work": "Work emergency",
        "weather": "Bad weather",
        "guests": "Guests / social plans",
    }

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

    def get_miss_reason_buttons(self) -> list:
        return [
            {"text": "😐 Didn't feel like it", "data": "miss_didnt_feel"},
            {"text": "🤒 Feeling sick", "data": "miss_sick"},
            {"text": "💼 Work emergency", "data": "miss_work"},
            {"text": "🌧️ Bad weather", "data": "miss_weather"},
            {"text": "👥 Guests / social", "data": "miss_guests"},
        ]

    def handle_miss_reason(self, user_id: str, reason_key: str) -> dict:
        user = self.db.get_user(user_id)
        profile = user.get("profile", {})
        goal = profile.get("goal", "your fitness goal")
        today_plan = user.get("today_plan", {})
        maturity = user.get("fitness_maturity", "beginner")
        streak = int(user.get("streak", 0))
        days_active = int(user.get("days_active", 0))
        consecutive_misses = int(user.get("consecutive_misses", 0))
        reason_text = self.MISS_REASONS.get(reason_key, reason_key)

        counts_as_miss = reason_key in ["didnt_feel", "work", "weather"]

        prompt = MISS_RESPONSE_PROMPT.format(
            profile=json.dumps(profile, indent=2), maturity=maturity, goal=goal,
            today_plan=json.dumps(today_plan, indent=2), streak=streak,
            days_active=days_active, reason=reason_text,
        )
        response = self._call_llm(prompt, [{"role": "user", "content": f"I missed today's tasks. Reason: {reason_text}"}])

        if counts_as_miss:
            new_misses = consecutive_misses + 1
            self.db.update_user(user_id, {"consecutive_misses": new_misses})
            if reason_key == "didnt_feel":
                self.db.update_user(user_id, {"streak": 0})
        else:
            new_misses = consecutive_misses

        today_str = date.today().isoformat()
        miss_status = "missed" if counts_as_miss else "excused"
        self.db.update_plan(user_id, today_str, {"status": miss_status, "miss_reason": reason_key, "completion_pct": 0.0})
        self.db.save_message(user_id, "user", f"Missed today: {reason_text}", "miss_reason")
        self.db.save_message(user_id, "assistant", response, "miss_reason")

        trigger_scaledown = (reason_key == "didnt_feel" and new_misses >= 3)
        return {"message": response, "counts_as_miss": counts_as_miss, "micro_alternative": None, "trigger_scaledown": trigger_scaledown}

    def trigger_scale_down(self, user_id: str) -> dict:
        user = self.db.get_user(user_id)
        profile = user.get("profile", {})
        goal = profile.get("goal", "your fitness goal")
        maturity = user.get("fitness_maturity", "beginner")
        current_habits = user.get("current_habits", [])
        consecutive_misses = int(user.get("consecutive_misses", 0))

        prompt = SCALE_DOWN_PROMPT.format(
            profile=json.dumps(profile, indent=2), maturity=maturity, goal=goal,
            current_habits=", ".join(current_habits) if current_habits else "None",
            consecutive_misses=consecutive_misses,
        )
        response = self._call_llm(prompt, [{"role": "user", "content": "I've been struggling to do the tasks."}])

        coach_message = response
        scaled_data = {}
        if "<<<SCALED>>>" in response and "<<<END>>>" in response:
            parts = response.split("<<<SCALED>>>")
            coach_message = parts[0].strip()
            json_str = parts[1].split("<<<END>>>")[0].strip()
            try:
                scaled_data = json.loads(json_str)
            except json.JSONDecodeError:
                scaled_data = {
                    "scaled_tasks": [{"id": i+1, "description": f"Just 5 minutes: {h}", "category": "exercise", "why": "Any movement counts."} for i, h in enumerate(current_habits[:2])],
                    "scaled_habits": [f"5-min version of: {h}" for h in current_habits[:2]],
                }

        scaled_tasks = scaled_data.get("scaled_tasks", [])
        scaled_habits = scaled_data.get("scaled_habits", current_habits)
        scaled_plan = {
            "greeting": "Let's keep it simple today.",
            "tasks": scaled_tasks,
            "coach_note": "Any movement counts. Just show up.",
            "_is_scaled": True, "_original_habits": current_habits,
        }

        today_str = date.today().isoformat()
        self.db.update_user(user_id, {
            "state": "RECOVERY", "daily_sub_state": "AWAITING_PLAN_RESPONSE",
            "current_habits": scaled_habits, "today_plan": scaled_plan, "consecutive_misses": 0,
        })
        self.db.save_plan(user_id, today_str, scaled_plan)
        self.db.update_plan(user_id, today_str, {"status": "pending"})
        self.db.save_message(user_id, "assistant", coach_message, "scale_down")

        task_lines = []
        for t in scaled_tasks:
            emoji = {"exercise": "🏋️", "mobility": "🧘", "nutrition": "🥗", "mindset": "🧠"}.get(t.get("category", ""), "📌")
            task_lines.append(f"{emoji} {t['description']}\n   ↳ {t.get('why', '')}")
        full_message = f"{coach_message}\n\n🎯 Here's your lighter plan:\n\n" + "\n\n".join(task_lines) + "\n\n💬 Just these. Nothing more. You've got this."
        return {"message": full_message, "scaled_plan": scaled_plan, "scaled_habits": scaled_habits}

    def track_recovery_completion(self, user_id: str) -> dict:
        user = self.db.get_user(user_id)
        profile = user.get("profile", {})
        goal = profile.get("goal", "your fitness goal")
        maturity = user.get("fitness_maturity", "beginner")
        today_plan = user.get("today_plan", {})
        current_habits = user.get("current_habits", [])

        all_plans = self.db.plans.get_all_records()
        user_plans = [p for p in all_plans if str(p["user_id"]) == str(user_id)]
        recent_plans = user_plans[-5:]
        recovery_completions = min(sum(1 for p in recent_plans if p.get("status") in ["completed", "partial"] and float(p.get("completion_pct", 0)) >= 0.8), 3)
        original_habits = today_plan.get("_original_habits", current_habits)

        prompt = RECOVERY_REBUILD_PROMPT.format(
            profile=json.dumps(profile, indent=2), maturity=maturity, goal=goal,
            scaled_habits=", ".join(current_habits), original_habits=", ".join(original_habits),
            recovery_completions=recovery_completions,
        )
        response = self._call_llm(prompt, [{"role": "user", "content": f"I completed today's scaled-down tasks. Day {recovery_completions} of recovery."}])

        if recovery_completions >= 2:
            coach_message = response
            rebuild_data = {}
            if "<<<REBUILD>>>" in response and "<<<END>>>" in response:
                parts = response.split("<<<REBUILD>>>")
                coach_message = parts[0].strip()
                json_str = parts[1].split("<<<END>>>")[0].strip()
                try:
                    rebuild_data = json.loads(json_str)
                except json.JSONDecodeError:
                    rebuild_data = {"rebuild_habits": original_habits}
            rebuild_habits = rebuild_data.get("rebuild_habits", original_habits)
            self.db.update_user(user_id, {"state": "ACTIVE", "current_habits": rebuild_habits, "consecutive_misses": 0})
            self.db.save_message(user_id, "assistant", coach_message, "recovery_rebuild")
            return {"message": f"🏆 {coach_message}", "rebuilt": True, "rebuild_plan": rebuild_data}
        else:
            self.db.save_message(user_id, "assistant", response, "recovery_progress")
            return {"message": response, "rebuilt": False, "rebuild_plan": None}

    def check_absence(self, user_id: str) -> dict:
        user = self.db.get_user(user_id)
        if not user:
            return {"action": "none", "message": None, "days_absent": 0}
        if user.get("state") == "PAUSED":
            return {"action": "already_paused", "message": None, "days_absent": 0}

        all_msgs = self.db.messages.get_all_records()
        user_msgs = [m for m in all_msgs if str(m["user_id"]) == str(user_id) and m["role"] == "user"]
        if not user_msgs:
            return {"action": "none", "message": None, "days_absent": 0}

        try:
            last_active = datetime.fromisoformat(user_msgs[-1].get("created_at", ""))
            days_absent = (datetime.now() - last_active).days
        except (ValueError, TypeError):
            days_absent = 0

        profile = user.get("profile", {})
        goal = profile.get("goal", "your fitness goal")

        if days_absent >= 7:
            prompt = ABSENCE_CHECKIN_PROMPT.format(profile=json.dumps(profile, indent=2), goal=goal, last_streak=user.get("streak", 0), days_active=user.get("days_active", 0), days_absent=7)
            response = self._call_llm(prompt, [{"role": "user", "content": "Generate the 7-day absence message."}])
            self.db.update_user(user_id, {"state": "PAUSED"})
            self.db.save_message(user_id, "assistant", response, "absence_final")
            return {"action": "final_7day", "message": response, "days_absent": days_absent}
        elif days_absent >= 3:
            prompt = ABSENCE_CHECKIN_PROMPT.format(profile=json.dumps(profile, indent=2), goal=goal, last_streak=user.get("streak", 0), days_active=user.get("days_active", 0), days_absent=3)
            response = self._call_llm(prompt, [{"role": "user", "content": "Generate the 3-day absence check-in."}])
            self.db.save_message(user_id, "assistant", response, "absence_nudge")
            return {"action": "nudge_3day", "message": response, "days_absent": days_absent}
        return {"action": "none", "message": None, "days_absent": days_absent}

    def handle_resume(self, user_id: str) -> dict:
        user = self.db.get_user(user_id)
        if not user:
            return {"message": "User not found.", "state": ""}
        streak = int(user.get("streak", 0))
        days_active = int(user.get("days_active", 0))
        habits = user.get("current_habits", [])
        self.db.update_user(user_id, {"state": "ACTIVE", "daily_sub_state": "", "consecutive_misses": 0})
        habits_str = "\n".join([f"  • {h}" for h in habits]) if habits else "  • We'll set these up fresh"
        message = (
            f"Welcome back! 🎉\n\n"
            f"Your progress is exactly where you left it:\n"
            f"  📊 {days_active} days tracked\n"
            f"  🔥 Last streak: {streak} days\n\n"
            f"Your current habits:\n{habits_str}\n\n"
            f"I'll send your plan tomorrow morning. "
            f"For now, just showing up and saying 'I'm back' is the win today. 💪"
        )
        self.db.save_message(user_id, "assistant", message, "resume")
        return {"message": message, "state": "ACTIVE"}
