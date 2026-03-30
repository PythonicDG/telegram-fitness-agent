# Telegram Fitness Agent: AI Personal Coach

A production-grade Telegram fitness agent built with Python, LangGraph, and Groq. This agent functions as a persistent fitness coach that tracks progress, negotiates daily plans, and adapts to user feedback through a multi-engine state machine.

Unlike standard fitness bots, this agent implements a **Psychology-Based Negotiation protocol** and a **Recovery & Scaling system** to ensure long-term habit adherence.

---

## 🏗️ System Architecture

The project follows a modular "Engine" architecture to maintain clean separation of concerns:

- **LangGraph State Machine**: Manages the multi-turn onboarding process and persistent user state.
- **Negotiation Engine**: A 3-round negotiation protocol for plan adjustments (Explain → Offer Alternatives → Pull Rank).
- **Recovery & Scaling Engine**: Detects consistency gaps and automatically triggers "Micro-Habit" scaling to prevent burnout.
- **Daily Coaching Engine**: Handles morning plan generation, interactive task tracking, and evening reflections.
- **Google Sheets Database**: Serves as a real-time, low-latency persistent store for user profiles, history, and message logs.

---

## 🔥 Key Features

- **Adaptive Onboarding**: Uses LLM-driven classification to determine "Fitness Maturity" (Beginner to Elite).
- **Interactive Task Management**: Plans are delivered with inline buttons for real-time progress tracking.
- **Evening Reflection**: Collects qualitative feedback (RPE/Difficulty) to adjust tomorrow's plan intensity.
- **Smart Streak Handling**: Differentiates between excused misses (sickness/work) and habit breaks to manage motivation.
- **Automatic Scaledown**: If a user misses multiple days, the bot scales tasks down to 5-10 minute "Micro-Habits" to rebuild momentum.

---

## 🛠️ Technical Stack

- **Linguistic Engine**: [Groq](https://groq.com/) (Llama-3.3-70B-Versatile)
- **Framework**: `python-telegram-bot` (v20+)
- **State Orchestration**: `LangGraph` & `LangChain`
- **Database**: Google Sheets API via `gspread`
- **Environment**: Python 3.11+

---

## 🚀 Installation & Setup

### 1. Prerequisites
- Python 3.11 or higher.
- A Telegram Bot token from [@BotFather](https://t.me/botfather).
- A Groq API Key from [Groq Console](https://console.groq.com/).
- A Google Cloud Project with a Service Account (JSON key).

### 2. Google Sheets Configuration
1. Create a new Google Sheet.
2. Enable **Google Sheets API** and **Google Drive API** in your Google Cloud Console.
3. Create a **Service Account**, download the JSON key file.
4. Share the Google Sheet with the Service Account email address as "Editor".
5. Copy the **Google Sheet URL**.

### 3. Clone and Install
```bash
git clone https://github.com/PythonicDG/telegram-fitness-agent.git
cd telegram-fitness-agent
pip install -r requirements.txt
```

### 4. Environment Variables
Create a `.env` file in the root directory:
```env
TELEGRAM_BOT_TOKEN="your_telegram_bot_token"
GROQ_API_KEY="your_groq_api_key"
GOOGLE_SHEET_URL="https://docs.google.com/spreadsheets/d/your_sheet_id/"
GOOGLE_SERVICE_ACCOUNT_JSON='{"type": "service_account", ...}'
```
> **Note**: For `GOOGLE_SERVICE_ACCOUNT_JSON`, paste the entire content of your JSON key file as a single-line string or ensure your environment loader handles multi-line strings.

---

## 🎮 Bot Commands

| Command | Description |
|:---|:---|
| `/start` | Initializes onboarding or resumes active coaching session. |
| `/plan` | Generates the daily mission with interactive task buttons. |
| `/checkin` | Evening reflection to evaluate performance and adjust difficulty. |
| `/status` | Displays the user dashboard: Goal, Level, Streak, and Habits. |
| `/resume` | Manual trigger for the Recovery Engine after a period of inactivity. |
| `/reset` | Completely wipes all user data for a fresh start. |

---

## 📂 Project Structure

```text
├── app.py                # Main entry point & Telegram bot handlers
├── config.py             # Environment config & client initializations
├── database.py           # Google Sheets abstraction layer (SheetDB)
├── graph.py              # LangGraph onboarding state machine logic
├── prompts.py            # System prompts & persona definitions
├── engines/              # Modular business logic
│   ├── daily.py          # Daily generation & task completion
│   ├── negotiation.py    # Psychology-based plan negotiation
│   └── recovery.py       # Missed days & scaling logic
└── requirements.txt      # Project dependencies
```

---

## 🚢 Deployment

The repository is deployment-ready for platforms like **Railway**, **Koyeb**, or **Heroku**.

---

## 📝 License

This project is licensed under the MIT License - see the LICENSE file for details.

