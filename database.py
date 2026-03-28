import json
from datetime import datetime
from typing import Optional


class SheetDB:
    """Simple database using Google Sheets."""

    def __init__(self, spreadsheet):
        self.users = spreadsheet.worksheet("users")
        self.messages = spreadsheet.worksheet("messages")
        self.plans = spreadsheet.worksheet("daily_plans")

    # ---------- USER OPERATIONS ----------

    def get_user(self, user_id: str) -> Optional[dict]:
        try:
            all_users = self.users.get_all_records()
            for row in all_users:
                if str(row["user_id"]) == str(user_id):
                    row["profile"] = json.loads(row["profile_json"]) if row["profile_json"] else {}
                    row["current_habits"] = json.loads(row["current_habits_json"]) if row["current_habits_json"] else []
                    row["today_plan"] = json.loads(row["today_plan_json"]) if row["today_plan_json"] else {}
                    return row
            return None
        except Exception as e:
            print(f"Error fetching user: {e}")
            return None

    def create_user(self, user_id: str) -> dict:
        now = datetime.now().isoformat()
        new_user = {
            "user_id": str(user_id), "state": "ONBOARDING", "daily_sub_state": "",
            "profile_json": "{}", "fitness_maturity": "", "current_habits_json": "[]",
            "today_plan_json": "{}", "negotiation_round": 0, "consecutive_misses": 0,
            "streak": 0, "days_active": 0, "created_at": now,
        }
        self.users.append_row(list(new_user.values()))
        return new_user

    def update_user(self, user_id: str, updates: dict):
        try:
            all_users = self.users.get_all_records()
            for i, row in enumerate(all_users):
                if str(row["user_id"]) == str(user_id):
                    row_number = i + 2
                    headers = self.users.row_values(1)
                    if "profile" in updates:
                        updates["profile_json"] = json.dumps(updates.pop("profile"))
                    if "current_habits" in updates:
                        updates["current_habits_json"] = json.dumps(updates.pop("current_habits"))
                    if "today_plan" in updates:
                        updates["today_plan_json"] = json.dumps(updates.pop("today_plan"))
                    for key, value in updates.items():
                        if key in headers:
                            col = headers.index(key) + 1
                            self.users.update_cell(row_number, col, value)
                    return True
            return False
        except Exception as e:
            print(f"Error updating user: {e}")
            return False

    # ---------- MESSAGE OPERATIONS ----------

    def save_message(self, user_id: str, role: str, content: str, context_type: str = "general"):
        now = datetime.now().isoformat()
        self.messages.append_row([str(user_id), role, content, context_type, now])

    def get_recent_messages(self, user_id: str, limit: int = 10) -> list:
        all_msgs = self.messages.get_all_records()
        user_msgs = [m for m in all_msgs if str(m["user_id"]) == str(user_id)]
        recent = user_msgs[-limit:]
        return [{"role": m["role"], "content": m["content"]} for m in recent]

    # ---------- DAILY PLAN OPERATIONS ----------

    def save_plan(self, user_id: str, date_str: str, plan: dict):
        self.plans.append_row([
            str(user_id), date_str, json.dumps(plan), "pending", 0.0, 0, "", ""
        ])

    def get_today_plan(self, user_id: str, date_str: str) -> Optional[dict]:
        all_plans = self.plans.get_all_records()
        for plan in all_plans:
            if str(plan["user_id"]) == str(user_id) and plan["date"] == date_str:
                plan["plan"] = json.loads(plan["plan_json"]) if plan["plan_json"] else {}
                return plan
        return None

    def update_plan(self, user_id: str, date_str: str, updates: dict):
        all_plans = self.plans.get_all_records()
        headers = self.plans.row_values(1)
        for i, plan in enumerate(all_plans):
            if str(plan["user_id"]) == str(user_id) and plan["date"] == date_str:
                row_number = i + 2
                for key, value in updates.items():
                    if key in headers:
                        col = headers.index(key) + 1
                        self.plans.update_cell(row_number, col, value)
                return True
        return False
