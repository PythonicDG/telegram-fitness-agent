import json
import gspread
from datetime import datetime
from typing import Optional, List
from gspread.exceptions import WorksheetNotFound

class SheetDB:
    """Simple database using Google Sheets with auto-setup."""

    # Define headers exactly as they should appear in the sheet
    USER_HEADERS = ["user_id", "state", "daily_sub_state", "profile_json", "fitness_maturity", "current_habits_json", "today_plan_json", "negotiation_round", "consecutive_misses", "streak", "days_active", "created_at"]
    MESSAGE_HEADERS = ["user_id", "role", "content", "context_type", "created_at"]
    PLAN_HEADERS = ["user_id", "date", "plan_json", "status", "completion_pct", "negotiation_count", "miss_reason", "evening_reflection"]

    def __init__(self, spreadsheet):
        self._spreadsheet = spreadsheet
        # Auto-setup worksheets if they don't exist
        self.users = self._ensure_worksheet("users", self.USER_HEADERS)
        self.messages = self._ensure_worksheet("messages", self.MESSAGE_HEADERS)
        self.plans = self._ensure_worksheet("daily_plans", self.PLAN_HEADERS)

    def _ensure_worksheet(self, name: str, headers: List[str]):
        try:
            return self._spreadsheet.worksheet(name)
        except WorksheetNotFound:
            print(f"   🛠️ Sheet tab '{name}' not found. Creating it now...")
            # Create with 1000 rows to start
            ws = self._spreadsheet.add_worksheet(title=name, rows="1000", cols=str(len(headers)))
            ws.append_row(headers)
            return ws

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
        # Create user dictionary matching USER_HEADERS order
        new_user = {
            "user_id": str(user_id),
            "state": "ONBOARDING",
            "daily_sub_state": "",
            "profile_json": "{}",
            "fitness_maturity": "",
            "current_habits_json": "[]",
            "today_plan_json": "{}",
            "negotiation_round": 0,
            "consecutive_misses": 0,
            "streak": 0,
            "days_active": 0,
            "created_at": now,
        }
        # Use headers to ensure correct value order
        row_values = [new_user.get(h, "") for h in self.USER_HEADERS]
        self.users.append_row(row_values)
        
        # Attach dict versions for in-memory use
        new_user["profile"] = {}
        new_user["current_habits"] = []
        new_user["today_plan"] = {}
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
