import os
import sys

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass
from dotenv import load_dotenv

# .env faylini yuklash
load_dotenv(override=True)

def get_bot_token() -> str:
    load_dotenv(override=True)
    return os.getenv("BOT_TOKEN", "").strip()

def get_gemini_api_key() -> str:
    load_dotenv(override=True)
    return os.getenv("GEMINI_API_KEY", "").strip()

def get_gemini_model() -> str:
    return os.getenv("GEMINI_MODEL", "gemini-3.8-flash").strip()

def get_creator_id() -> int:
    try:
        return int(os.getenv("CREATOR_ID", "5772939710"))
    except ValueError:
        return 5772939710

BOT_TOKEN = get_bot_token()
GEMINI_API_KEY = get_gemini_api_key()
GEMINI_MODEL = get_gemini_model()
CREATOR_ID = get_creator_id()

def get_telegram_api_id() -> int:
    val = os.getenv("TELEGRAM_API_ID", "").strip()
    try:
        return int(val) if val else 0
    except ValueError:
        return 0

def get_telegram_api_hash() -> str:
    return os.getenv("TELEGRAM_API_HASH", "").strip()

def get_telegram_string_session() -> str:
    return os.getenv("TELEGRAM_STRING_SESSION", "").strip()

TELEGRAM_API_ID = get_telegram_api_id()
TELEGRAM_API_HASH = get_telegram_api_hash()
TELEGRAM_STRING_SESSION = get_telegram_string_session()

def is_userbot_configured() -> bool:
    return bool(TELEGRAM_API_ID and TELEGRAM_API_HASH and TELEGRAM_STRING_SESSION)

DEFAULT_SYSTEM_PROMPT = (
    "Siz aqlli, do'stona va har tomonlama yordam beruvchi universal AI yordamchisiz. "
    "Foydalanuvchilar bilan asosan o'zbek tilida (yoki foydalanuvchi qaysi tilda yozsa, o'sha tilda) "
    "samimiy, aniq va tushunarli tarzda muloqot qilasiz. "
    "Dasturlash, ta'lim, maslahat, tahlil va har qanday savollarga sifatli javob berasiz. "
    "Javoblaringizda matnni chiroyli va qulay formatlash uchun Telegram markdown/formatting uslublaridan unumli foydalaning."
)

SYSTEM_PROMPT = os.getenv("SYSTEM_PROMPT", DEFAULT_SYSTEM_PROMPT).strip()

def validate_config() -> bool:
    """Konfiguratsiya parametrlarini tekshirish"""
    missing = []
    if not BOT_TOKEN:
        missing.append("BOT_TOKEN (Telegram @BotFather orqali olingan token)")
    if not GEMINI_API_KEY:
        missing.append("GEMINI_API_KEY (Google AI Studio orqali olingan API kalit)")
    
    if missing:
        print("\n" + "=" * 60)
        print("XATOLIK: Quyidagi muhit o'zgaruvchilari sozlanmagan:")
        for item in missing:
            print(f"  - {item}")
        print("\nIltimos, .env faylini ochib, kerakli kalitlarni kiriting!")
        print("Misol uchun .env.example fayliga qarang.")
        print("=" * 60 + "\n")
        return False
    return True
