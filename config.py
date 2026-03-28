import os
import json
import gspread
from google.oauth2.service_account import Credentials
from groq import Groq
from dotenv import load_dotenv

load_dotenv()

# --- Environment Variables ---
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
SHEET_URL = os.getenv("GOOGLE_SHEET_URL")
GOOGLE_SERVICE_ACCOUNT_JSON = os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON")

if not all([BOT_TOKEN, GROQ_API_KEY, SHEET_URL, GOOGLE_SERVICE_ACCOUNT_JSON]):
    raise ValueError("❌ Missing environment variables! Set TELEGRAM_BOT_TOKEN, GROQ_API_KEY, GOOGLE_SHEET_URL, GOOGLE_SERVICE_ACCOUNT_JSON")

# --- Groq Client ---
groq_client = Groq(api_key=GROQ_API_KEY)

def call_llm(system_prompt: str, messages: list) -> str:
    response = groq_client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[{"role": "system", "content": system_prompt}] + messages,
        temperature=0.7,
        max_tokens=600,
    )
    return response.choices[0].message.content

# --- Google Sheets Client ---
def get_gspread_client():
    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive",
    ]
    try:
        creds_dict = json.loads(GOOGLE_SERVICE_ACCOUNT_JSON)
        creds = Credentials.from_service_account_info(creds_dict, scopes=scopes)
    except (json.JSONDecodeError, TypeError):
        creds = Credentials.from_service_account_file(GOOGLE_SERVICE_ACCOUNT_JSON, scopes=scopes)
    return gspread.authorize(creds)

gc = get_gspread_client()
spreadsheet = gc.open_by_url(SHEET_URL)
print("✅ Google Sheets connected")
