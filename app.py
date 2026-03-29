"""
Telegram Fitness Coach Bot — Production Entry Point
Connects all engines and runs the Telegram bot via polling.
"""

import json
import traceback
from datetime import date

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    CallbackQueryHandler, filters,
)

from config import BOT_TOKEN, groq_client, spreadsheet
from database import SheetDB
from graph import build_coach_graph
from engines.daily import DailyCoachingEngine
from engines.negotiation import NegotiationEngine
from engines.recovery import RecoveryEngine

# --- Initialize all components ---
db = SheetDB(spreadsheet)
coach_graph = build_coach_graph()
daily_engine = DailyCoachingEngine(db_ref=db, llm_client=groq_client)
negotiation_engine = NegotiationEngine(db_ref=db, llm_client=groq_client)
recovery_engine = RecoveryEngine(db_ref=db, llm_client=groq_client)

print("✅ All engines initialized")


# =============================================
# HELPER FUNCTIONS
# =============================================

def build_task_buttons(plan: dict) -> InlineKeyboardMarkup:
    tasks = plan.get("tasks", [])
    keyboard = []
    for i, task in enumerate(tasks):
        if task.get("completed"):
            keyboard.append([InlineKeyboardButton(f"✅ {task['description'][:40]}", callback_data=f"already_{i}")])
        else:
            keyboard.append([InlineKeyboardButton(f"⬜ Tap when done: {task['description'][:35]}", callback_data=f"done_{i}")])
    return InlineKeyboardMarkup(keyboard)


def build_plan_response_buttons() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[
        InlineKeyboardButton("✅ Accept plan", callback_data="accept_plan"),
        InlineKeyboardButton("🔄 Let's negotiate", callback_data="negotiate_plan"),
    ]])


def build_negotiation_buttons(buttons_data: list) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[InlineKeyboardButton(b["text"], callback_data=b["data"])] for b in buttons_data])



async def start_command(update: Update, context):
    user_id = str(update.effective_user.id)
    first_name = update.effective_user.first_name or "there"
    user = db.get_user(user_id)
    if user and user.get("state") == "ACTIVE":
        await update.message.reply_text(
            f"Welcome back, {first_name}! 💪\n\n"
            f"• /plan — get today's plan\n• /checkin — evening reflection\n"
            f"• /status — see your progress\n• Or just chat with me anytime!"
        )
    else:
        if not user:
            db.create_user(user_id)
        welcome = (
            f"Hey {first_name}! 👋\n\nI'm your personal fitness coach. "
            f"I'm here to help you build healthy habits that actually stick.\n\n"
            f"Before we begin, I'd love to learn a bit about you. "
            f"Let's start simple — what's your main fitness goal right now?"
        )
        db.save_message(user_id, "assistant", welcome, "onboarding")
        await update.message.reply_text(welcome)
    print(f"   /start from {first_name} (ID: {user_id})")


async def plan_command(update: Update, context):
    user_id = str(update.effective_user.id)
    user = db.get_user(user_id)
    if not user or user.get("state") != "ACTIVE":
        await update.message.reply_text("You haven't finished setting up yet! Send /start to begin.")
        return
    await update.message.chat.send_action("typing")
    today_str = date.today().isoformat()
    existing_plan = db.get_today_plan(user_id, today_str)
    if existing_plan and existing_plan.get("status") in ["accepted", "in_progress", "completed", "negotiated"]:
        plan = user.get("today_plan", {})
        tasks = plan.get("tasks", [])
        completed = sum(1 for t in tasks if t.get("completed"))
        await update.message.reply_text(
            f"📋 You already have today's plan ({completed}/{len(tasks)} done).\n\nHere are your tasks:",
            reply_markup=build_task_buttons(plan),
        )
        return
    morning = daily_engine.generate_morning_plan(user_id)
    await update.message.reply_text(morning["message"], reply_markup=build_plan_response_buttons())
    print(f"   📋 Plan generated for {user_id} ({morning['task_count']} tasks)")


async def checkin_command(update: Update, context):
    user_id = str(update.effective_user.id)
    user = db.get_user(user_id)
    if not user or user.get("state") != "ACTIVE":
        await update.message.reply_text("Send /start to begin your journey first!")
        return
    await update.message.chat.send_action("typing")
    today_plan = user.get("today_plan", {})
    if not today_plan.get("tasks"):
        await update.message.reply_text("No plan today to check in on. Send /plan to get one!")
        return
    response = daily_engine.generate_evening_checkin(user_id)
    keyboard = InlineKeyboardMarkup([[
        InlineKeyboardButton("Too easy 😴", callback_data="feel_easy"),
        InlineKeyboardButton("Just right 👌", callback_data="feel_right"),
        InlineKeyboardButton("Too hard 😤", callback_data="feel_hard"),
    ]])
    await update.message.reply_text(response, reply_markup=keyboard)
    print(f"   🌙 Evening check-in for {user_id}")


async def status_command(update: Update, context):
    user_id = str(update.effective_user.id)
    user = db.get_user(user_id)
    if not user:
        await update.message.reply_text("Send /start to begin!")
        return
    profile = user.get("profile", {})
    habits = user.get("current_habits", [])
    streak = int(user.get("streak", 0))
    maturity = user.get("fitness_maturity", "not set")
    days = int(user.get("days_active", 0))
    misses = int(user.get("consecutive_misses", 0))
    streak_bar = "🔥" * min(streak, 10)
    if streak > 10:
        streak_bar += f" +{streak - 10}"
    habits_text = "\n".join([f"  • {h}" for h in habits]) if habits else "  None yet"
    today_plan = user.get("today_plan", {})
    tasks = today_plan.get("tasks", [])
    completed = sum(1 for t in tasks if t.get("completed"))
    today_status = f"{completed}/{len(tasks)} tasks done" if tasks else "No plan yet (/plan)"
    status_msg = (
        f"📊 Your dashboard\n━━━━━━━━━━━━━━━━━━\n\n"
        f"🎯 Goal: {profile.get('goal', 'Not set')}\n💪 Level: {maturity}\n"
        f"📅 Days active: {days}\n\n🔥 Streak: {streak} days\n{streak_bar}\n\n"
        f"📋 Current habits:\n{habits_text}\n\n📌 Today: {today_status}"
    )
    if misses > 0:
        status_msg += f"\n\n⚠️ Missed days in a row: {misses}"
    await update.message.reply_text(status_msg)


async def reset_command(update: Update, context):
    user_id = str(update.effective_user.id)
    try:
        all_users = db.users.get_all_records()
        for i, row in enumerate(all_users):
            if str(row["user_id"]) == str(user_id):
                db.users.delete_rows(i + 2)
                break
    except Exception:
        pass
    await update.message.reply_text("🔄 Data reset. Send /start to begin fresh!")
    print(f"   🔄 User {user_id} reset")


async def resume_command(update: Update, context):
    user_id = str(update.effective_user.id)
    result = recovery_engine.handle_resume(user_id)
    await update.message.reply_text(result["message"])
    print(f"   🔄 User {user_id} resumed")



async def handle_button(update: Update, context):
    query = update.callback_query
    await query.answer()
    user_id = str(query.from_user.id)
    data = query.data

    if data == "accept_plan":
        user = db.get_user(user_id)
        plan = user.get("today_plan", {})
        today_str = date.today().isoformat()
        db.update_user(user_id, {"daily_sub_state": "PLAN_ACCEPTED", "negotiation_round": 0})
        db.update_plan(user_id, today_str, {"status": "accepted"})
        await query.edit_message_text(text=query.message.text + "\n\n✅ Plan accepted! Here are your tasks:", reply_markup=build_task_buttons(plan))

    elif data == "negotiate_plan":
        db.update_user(user_id, {"daily_sub_state": "NEGOTIATING", "negotiation_round": 1})
        await query.edit_message_text(text=query.message.text + "\n\n🔄 No problem! What would you like to change about today's plan?")

    elif data == "neg_accept_original":
        result = negotiation_engine.accept_original(user_id)
        user = db.get_user(user_id)
        plan = user.get("today_plan", {})
        await query.edit_message_text(text=query.message.text + "\n\n✅ Sticking with the plan!")
        await query.message.reply_text(result["message"], reply_markup=build_task_buttons(plan))

    elif data == "neg_continue":
        await query.edit_message_text(text=query.message.text + "\n\n🔄 Tell me what you'd like instead.")

    elif data == "neg_choose_a":
        result = negotiation_engine.accept_option(user_id, "a")
        user = db.get_user(user_id)
        plan = user.get("today_plan", {})
        await query.edit_message_text(text=query.message.text + "\n\n✅ Going with Option A!")
        await query.message.reply_text(result["message"], reply_markup=build_task_buttons(plan))

    elif data == "neg_choose_b":
        result = negotiation_engine.accept_option(user_id, "b")
        user = db.get_user(user_id)
        plan = user.get("today_plan", {})
        await query.edit_message_text(text=query.message.text + "\n\n✅ Going with Option B!")
        await query.message.reply_text(result["message"], reply_markup=build_task_buttons(plan))

    elif data == "neg_reject_both":
        await query.message.chat.send_action("typing")
        result = negotiation_engine.handle_negotiation(user_id, "Neither of those options works for me")
        await query.edit_message_text(text=query.message.text + "\n\n❌ Neither option chosen")
        markup = build_negotiation_buttons(result["buttons"]) if result.get("buttons") else None
        await query.message.reply_text(result["message"], reply_markup=markup)

    elif data == "neg_own_thing":
        result = negotiation_engine.do_own_thing(user_id)
        await query.edit_message_text(text=query.message.text + "\n\n✏️ Going freestyle today")
        await query.message.reply_text(result["message"])

    elif data.startswith("done_"):
        task_index = int(data.split("_")[1])
        await query.message.chat.send_action("typing")
        result = daily_engine.complete_task(user_id, task_index)
        user = db.get_user(user_id)
        plan = user.get("today_plan", {})
        original_text = query.message.text
        for marker in ["\n\n✅ Plan accepted!", "\n\n📋 Progress:", "\n\n✅ Going with", "\n\n🔥 ALL TASKS", "\n\n✅ Sticking"]:
            original_text = original_text.split(marker)[0]
        if result["all_done"]:
            await query.edit_message_text(text=original_text + "\n\n🔥 ALL TASKS COMPLETE!")
        else:
            await query.edit_message_text(
                text=original_text + f"\n\n📋 Progress: {result['completed']}/{result['total']}",
                reply_markup=build_task_buttons(plan),
            )
        await query.message.reply_text(result["message"])

    elif data.startswith("already_"):
        await query.answer("Already completed! 🎉", show_alert=False)

    elif data.startswith("feel_"):
        feeling = data.replace("feel_", "")
        feeling_map = {"easy": "too easy", "right": "just right", "hard": "too hard"}
        feeling_text = feeling_map.get(feeling, feeling)
        today_str = date.today().isoformat()
        db.update_plan(user_id, today_str, {"evening_reflection": feeling_text})
        if feeling == "easy":
            reply = "😏 Too easy, huh? I'll step it up tomorrow. Get some rest — you've earned it!"
        elif feeling == "right":
            reply = "👌 Perfect sweet spot. We'll keep this level steady. Great work today!"
        else:
            reply = "💪 Tough one, but you showed up. I'll dial it back slightly tomorrow. Recovery is part of the process!"
        await query.edit_message_text(text=query.message.text + f"\n\nYou said: {feeling_text}")
        await query.message.reply_text(reply)
        db.save_message(user_id, "user", f"Today felt {feeling_text}", "check_in")
        db.save_message(user_id, "assistant", reply, "check_in")

    elif data.startswith("miss_"):
        reason_key = data.replace("miss_", "")
        await query.message.chat.send_action("typing")
        result = recovery_engine.handle_miss_reason(user_id, reason_key)
        await query.edit_message_text(text=query.message.text + f"\n\n📝 Noted.")
        await query.message.reply_text(result["message"])
        if result.get("trigger_scaledown"):
            scale_result = recovery_engine.trigger_scale_down(user_id)
            await query.message.reply_text(scale_result["message"])


# =============================================
# MESSAGE HANDLER
# =============================================

async def handle_message(update: Update, context):
    user_id = str(update.effective_user.id)
    message = update.message.text
    first_name = update.effective_user.first_name or "there"
    print(f"   📩 {first_name}: {message[:50]}...")
    await update.message.chat.send_action("typing")

    user = db.get_user(user_id)
    if not user:
        db.create_user(user_id)
        user = db.get_user(user_id)

    current_state = user.get("state", "ONBOARDING")

    try:
        if current_state == "ONBOARDING":
            recent_messages = db.get_recent_messages(user_id, limit=10)
            graph_state = {
                "user_id": str(user_id), "state": "ONBOARDING", "daily_sub_state": "",
                "profile": user.get("profile", {}), "fitness_maturity": "",
                "current_habits": [], "messages": recent_messages + [{"role": "user", "content": message}],
                "today_plan": {}, "negotiation_round": 0, "consecutive_misses": 0,
                "streak": 0, "coach_response": "", "days_active": 0,
            }
            result = coach_graph.invoke(graph_state)
            response = result.get("coach_response", "Could you tell me more?")
            db.save_message(user_id, "user", message, "onboarding")
            db.save_message(user_id, "assistant", response, "onboarding")
            updates = {"state": result.get("state", "ONBOARDING")}
            if result.get("profile"):
                updates["profile"] = result["profile"]
            if result.get("fitness_maturity"):
                updates["fitness_maturity"] = result["fitness_maturity"]
            if result.get("current_habits"):
                updates["current_habits"] = result["current_habits"]
            if result.get("days_active"):
                updates["days_active"] = result["days_active"]
            db.update_user(user_id, updates)
            if result.get("state") == "ACTIVE":
                await update.message.reply_text(response)
                await update.message.reply_text("🎉 You're all set! Send /plan to get your first daily plan.")
            else:
                await update.message.reply_text(response)

        elif current_state in ("ACTIVE", "RECOVERY"):
            sub_state = user.get("daily_sub_state", "")
            if sub_state == "NEGOTIATING":
                result = negotiation_engine.handle_negotiation(user_id, message)
                markup = build_negotiation_buttons(result["buttons"]) if result.get("buttons") else None
                await update.message.reply_text(result["message"], reply_markup=markup)
                if result.get("resolved"):
                    db.update_user(user_id, {"daily_sub_state": "PLAN_ACCEPTED", "negotiation_round": 0})
            else:
                response = daily_engine.handle_freeform_chat(user_id, message)
                await update.message.reply_text(response)

        elif current_state == "PAUSED":
            result = recovery_engine.handle_resume(user_id)
            await update.message.reply_text(result["message"])

        else:
            response = daily_engine.handle_freeform_chat(user_id, message)
            await update.message.reply_text(response)

    except Exception as e:
        print(f"   ❌ Error: {e}")
        traceback.print_exc()
        await update.message.reply_text("Oops, I had a brain freeze 🧠❄️ Could you try that again?")


# =============================================
# MAIN — BUILD AND RUN
# =============================================

def main():
    print("=" * 50)
    print("🤖 Starting Telegram Fitness Coach Bot...")

    app = Application.builder().token(BOT_TOKEN).build()

    # Register handlers
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("plan", plan_command))
    app.add_handler(CommandHandler("checkin", checkin_command))
    app.add_handler(CommandHandler("status", status_command))
    app.add_handler(CommandHandler("reset", reset_command))
    app.add_handler(CommandHandler("resume", resume_command))
    app.add_handler(CallbackQueryHandler(handle_button))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    print("✅ Bot is LIVE!")
    print("   Commands: /start /plan /checkin /status /reset /resume")
    print("   Running via polling...\n")

    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
