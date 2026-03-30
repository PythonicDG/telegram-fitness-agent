# 🏋️ Telegram Fitness Coach Bot

> A stateful, psychology-aware fitness agent that lives in your Telegram. Not a chatbot that answers fitness questions — an actual coach that remembers you, pushes back on excuses, and adapts when life gets in the way.

**[Try it live → @YourBotHandle](https://t.me/yourbothandle)**

---

## What makes this different

Most "AI fitness bots" are wrappers — you ask a question, you get an answer, conversation ends. This one runs a full state machine across your fitness journey. It knows if you've been slacking for three days. It remembers you mentioned a knee injury two weeks ago. When you say "I can't do this today," it doesn't fold — it asks why, explains its reasoning, and only then offers alternatives.

That negotiation protocol is the core of the whole thing.

---

## Architecture

```
┌──────────────────────────────────────────────────┐
│                   Telegram Bot (app.py)           │
├──────────┬───────────┬────────────┬──────────────┤
│ Onboard  │  Daily    │ Negotiation│   Recovery   │
│ Graph    │  Engine   │  Engine    │   Engine     │
├──────────┴───────────┴────────────┴──────────────┤
│                  prompts.py (12 prompts)          │
├───────────────────────┬──────────────────────────┤
│    Google Sheets      │   ChromaDB (local)        │
│    Structured data    │   Semantic memory recall  │
└───────────────────────┴──────────────────────────┘
```

**Onboarding Graph** — LangGraph-powered. Collects five data points through natural conversation, extracts structured JSON from each LLM response, then classifies the user's fitness maturity before handing off to the daily loop.

**Daily Engine** — Morning plans built from current habits, streak, and 7-day plan history. Task completion via inline Telegram buttons. Evening check-in adjusts tomorrow's intensity based on difficulty feedback.

**Negotiation Engine** — Three rounds. Round 1: explain the plan's reasoning. Round 2: offer exactly two alternatives. Round 3: reference the user's own stated goal and make them decide. The protocol is borrowed from how real coaches handle resistance.

**Recovery Engine** — After three consecutive "didn't feel like it" misses, it stops motivating and scales the plan down. Once two scaled-down days are completed, it rebuilds gradually. Also handles absences — gentle nudge at day 3, goes silent at day 7.

---

## Long-Term Memory

Every message gets dual-written: once to Google Sheets for structure, once to ChromaDB with a sentence embedding. On each new message, a semantic search runs over the user's full conversation history and the most relevant context gets injected into the prompt.

Practical result: if someone mentioned a knee injury during onboarding and asks for a leg day two weeks later, the bot recalls it without being told again.

> **Deployment note:** ChromaDB stores vectors in `chroma_db/`. On Railway or Heroku, mount a persistent volume here or memory resets on every deploy.

---

## Commands

| Command | What it does |
|---|---|
| `/start` | Onboarding for new users, or welcome back for existing ones |
| `/plan` | Generate today's plan (skips if one already exists) |
| `/checkin` | Evening reflection — collects difficulty feedback |
| `/status` | Dashboard: goal, level, streak, habits, today's progress |
| `/resume` | Re-activates after a 7-day absence pause |
| `/reset` | Wipes everything — Sheets rows + ChromaDB vectors |

---

## Tech Stack

| Layer | Choice |
|---|---|
| LLM | Groq / Llama-3.3-70B |
| Bot | python-telegram-bot v20+ |
| State orchestration | LangGraph |
| Database | Google Sheets via gspread |
| Vector memory | ChromaDB + sentence-transformers |

---

## Setup

**Prerequisites:** Python 3.11+, Telegram bot token, Groq API key, Google Cloud service account with Sheets + Drive APIs.

```bash
git clone https://github.com/PythonicDG/telegram-fitness-agent.git
cd telegram-fitness-agent
pip install -r requirements.txt
```

Create `.env`:
```env
TELEGRAM_BOT_TOKEN="your_token"
GROQ_API_KEY="your_groq_key"
GOOGLE_SHEET_URL="https://docs.google.com/spreadsheets/d/your_sheet_id/"
GOOGLE_SERVICE_ACCOUNT_JSON='{"type":"service_account",...}'
```

```bash
python app.py
```

The bot auto-creates `users`, `messages`, and `daily_plans` worksheet tabs on first run. The Google Sheet just needs to exist and be shared with the service account as Editor.

---

## Project Structure

```
telegram-fitness-agent/
├── app.py               # Telegram handlers, commands, button callbacks
├── config.py            # Env loading, Groq + gspread clients
├── database.py          # SheetDB abstraction layer
├── memory.py            # ChromaDB store / recall / clear
├── graph.py             # LangGraph onboarding state machine
├── prompts.py           # 12 LLM system prompt templates
└── engines/
    ├── daily.py         # Plans, task completion, check-ins, freeform chat
    ├── negotiation.py   # 3-round negotiation protocol
    └── recovery.py      # Miss handling, scale-down, rebuild, absence detection
```

---

## License

MIT