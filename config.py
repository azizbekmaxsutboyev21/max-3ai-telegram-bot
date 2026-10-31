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
    keys = get_gemini_api_keys()
    return keys[0] if keys else ""

def get_gemini_api_keys() -> list[str]:
    load_dotenv(override=True)
    raw = os.getenv("GEMINI_API_KEYS", "") or os.getenv("GEMINI_API_KEY", "")
    keys = [k.strip() for k in raw.split(",") if k.strip()]
    return keys

def get_gemini_model() -> str:
    m = os.getenv("GEMINI_MODEL", "gemini-2.5-flash").strip()
    if m in ["gemini-3.5-flash-lite", "gemini-3.1-flash-lite"]:
        m = "gemini-2.5-flash"
    return m or "gemini-2.5-flash"

def get_gemini_fallback_models() -> list[str]:
    """Asosiy model 503 yoki limitga tushganda avtomatik o'tish uchun zaxira modellar"""
    primary = get_gemini_model()
    defaults = ["gemini-2.5-flash", "gemini-2.0-flash", "gemini-1.5-flash", "gemini-3.8-flash"]
    models = [primary]
    for m in defaults:
        if m not in models:
            models.append(m)
    return models

def get_creator_id() -> int:
    try:
        return int(os.getenv("CREATOR_ID", "5772939710"))
    except ValueError:
        return 5772939710

def get_access_code() -> str:
    load_dotenv(override=True)
    return os.getenv("ACCESS_CODE", "7777").strip()

BOT_TOKEN = get_bot_token()
GEMINI_API_KEYS = get_gemini_api_keys()
GEMINI_API_KEY = get_gemini_api_key()
GEMINI_MODEL = get_gemini_model()
GEMINI_FALLBACK_MODELS = get_gemini_fallback_models()
CREATOR_ID = get_creator_id()
ACCESS_CODE = get_access_code()

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
    "Siz Azizbekning shaxsiy Telegram AI Boshqaruvchisiz (Executive AI Assistant). "
    "Siz foydalanuvchilar bilan asosan o'zbek tilida samimiy, aniq va madaniyatli muloqot qilasiz. "
    "Dasturlash, tahlil, maslahat va har qanday savollarga sifatli javob berasiz.\n\n"
    "MUHIM IMKONIYAT: Sizda butun boshli Telegram akkauntini boshqarish (Userbot Telethon) tizimi to'liq ulangan! "
    "Foydalanuvchi sizdan biror chatga, shaxsga, guruhga yoki kanalga xabar yuborishni yoki biror amal bajarishni so'rasa, "
    "ASLO 'men boshqa chatlarga yoza olmayman' yoki 'mening bunday imkoniyatim yo'q' deb aytmang!\n\n"
    "Buning o'rniga, quyidagi maxsus amallarni chiqarasiz:\n"
    "1. Biror chat/odam/guruhga xabar yuborish buyurilsa:\n"
    "[ACTION:SEND_MESSAGE|TARGET:<chat_id, @username yoki ism>|TEXT:<yuboriladigan aniq xabar>]\n"
    "QOIDALAR:\n"
    "- TARGET uchun shaxs nomidagi qo'shimchalarni tozalang (masalan: 'Munisaga salom jonim deb yoz' -> TARGET:Munisa, 'Aliga xabar yubor' -> TARGET:Ali).\n"
    "- Agar foydalanuvchi keyingi xabarida chat ID yoki @username yoki raqam bersa (masalan: '8927070806 bu uni chat id si' yoki '@munisa bu uning profili'), "
    "darhol avvalgi xabarni o'sha aniq ID ga yuborish uchun amal chiqaring: [ACTION:SEND_MESSAGE|TARGET:8927070806|TEXT:<avvalgi xabar>].\n\n"
    "2. Bir nechta chatlarga xabar yuborish buyurilsa:\n"
    "[ACTION:SEND_MULTIPLE|TARGETS:<chat1,chat2,...>|TEXT:<yuboriladigan xabar>]\n\n"
    "3. Reaksiya (emoji) bildirish buyurilsa:\n"
    "[ACTION:REACT|TARGET:<chat>|MSG_ID:<xabar_id>|EMOJI:<emoji>]\n\n"
    "Oddiy savol va maslahatlarda esa odatdagidek chiroyli va mukammal matn bilan javob bering."
)

SYSTEM_PROMPT = os.getenv("SYSTEM_PROMPT", DEFAULT_SYSTEM_PROMPT).strip()

def validate_config() -> bool:
    """Konfiguratsiya parametrlarini tekshirish"""
    missing = []
    if not BOT_TOKEN:
        missing.append("BOT_TOKEN (Telegram @BotFather orqali olingan token)")
    if not GEMINI_API_KEYS:
        missing.append("GEMINI_API_KEY yoki GEMINI_API_KEYS (Google AI Studio orqali olingan API kalit)")
    
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
