# 🏋️ Telegram Fitness Coach: Adaptive AI Agent

A production-ready Telegram fitness agent that acts as a real personal coach. Unlike static fitness bots, this agent uses **LangGraph** for state-aware onboarding and a **Multi-Engine Adaptive System** that negotiates plans, tracks consistency, and automatically adjusts difficulty based on user feedback and life events (missed days, sickness, etc.).

---

## 🏗️ Core Architecture

This project is built using a modular engine-based architecture designed for long-term reliability and easy maintenance.

### 1. The Onboarding State Machine (LangGraph)
Uses a persistent state graph to navigate a nuanced conversation with new users. Instead of a boring form, the bot learns about goals, injuries, and experience naturally through chat, eventually "classifying" the user's fitness maturity level before starting their journey.

### 2. The Negotiation Engine (Psychology-Based)
When a user rejects a daily plan, the bot doesn't just give up. It enters a **3-round protocol**:
*   **Round 1:** Explains the "Why" behind the original plan.
*   **Round 2:** Offers exactly two constrained alternatives based on user objections.
*   **Round 3:** Sets boundaries and reminds the user of their core goal (the "Pulling Rank" phase).

### 3. The Recovery & Scaling Engine
The most "human" part of the bot. It detects gaps in consistency and handles them gracefully:
*   **Excuse Handling:** Differentiates between "just didn't feel like it" (streak reset) and "it was raining/I'm sick" (excused).
*   **Auto-Scaledown:** If tasks are consistently missed, the bot automatically scales the original habits down to "Micro-Habits" (5-10 mins) to rebuild momentum.

### 4. Lightweight Database (Google Sheets)
Uses Google Sheets as a low-cost, real-time database. You can literally watch your project populate and edit user data in real-time in the sheet while the bot is running.

---

## 🛠️ Tech Stack

*   **Logic:** Python 3.11
*   **LLM Interface:** Groq (using `llama-3.3-70b-versatile` for high-speed reasoning)
*   **State Management:** LangGraph (onboarding & persistence)
*   **Database:** Google Sheets API (`gspread`)
*   **Bot Framework:** `python-telegram-bot`
*   **Deployment:** Railway / Docker-ready

---

## 🚀 Quick Setup Guide

### 1. Preparation
1. Create a **Google Service Account** and download the JSON key.
2. Enable both **Google Sheets** and **Google Drive** APIs in the Google Cloud Console.
3. Share your target Google Sheet with the Service Account email (Editor access).
4. Get your bot token from **@BotFather** on Telegram.

### 2. Environment Variables
Add these to your `.env` file or Railway dashboard:
*   `TELEGRAM_BOT_TOKEN`: The full token from @BotFather.
*   `GROQ_API_KEY`: Your key from console.groq.com.
*   `GOOGLE_SHEET_URL`: The full URL to your Google Sheet.
*   `GOOGLE_SERVICE_ACCOUNT_JSON`: The **entire** content of your JSON key file.

### 3. Deploy
The project includes a `Procfile` and `requirements.txt` for one-click deployment to platforms like Railway or Koyeb.
```bash
# Bot automatically sets up tabs & headers on first run!
python app.py
```

---

## 🎮 How to Interact

| Command | Action |
|---|---|
| `/start` | Begins onboarding or welcomes you back. |
| `/plan` | Generates today's missions with interactive task buttons. |
| `/checkin` | Evening reflection (updates difficulty for tomorrow). |
| `/status` | View your 🔥 Streak, goal progress, and habits. |
| `/resume` | Use this if you've been inactive for a while to wake the bot. |
| `/reset` | Completely wipes your data for a fresh start. |

---
