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
    raw_json = os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON")
    if not raw_json:
        raise ValueError("❌ GOOGLE_SERVICE_ACCOUNT_JSON not found in environment!")

    # Try to clean common escaping / formatting artifacts
    json_str = raw_json.strip()
    
    # Handle double escaping if present (e.g. from some .env loaders)
    if '\\"' in json_str:
        json_str = json_str.replace('\\"', '"')
    
    # If it's a path to a file, use that
    if os.path.isfile(json_str):
        creds = Credentials.from_service_account_file(json_str, scopes=scopes)
    else:
        # Otherwise treat as string
        try:
            creds_dict = json.loads(json_str)
            creds = Credentials.from_service_account_info(creds_dict, scopes=scopes)
        except json.JSONDecodeError as e:
            # Final fallback: Maybe it was just a filename after all that doesn't exist
            if json_str.startswith('{'):
                 raise ValueError(f"❌ GOOGLE_SERVICE_ACCOUNT_JSON looks like JSON but is invalid: {e}")
            else:
                 raise ValueError(f"❌ GOOGLE_SERVICE_ACCOUNT_JSON is not a valid JSON string and file not found: {json_str[:50]}...")

    return gspread.authorize(creds)


gc = get_gspread_client()
spreadsheet = gc.open_by_url(SHEET_URL)
print("✅ Google Sheets connected")
