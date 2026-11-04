"""
Gemini API ulanishini tekshirish uchun yordamchi test skripti.
Ishga tushirish: python test_ai.py
"""
import sys
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

from google import genai
from google.genai import types
import config

def test_connection():
    print("=" * 50)
    print("🤖 Google Gemini API ulanishini tekshirish...")
    print("=" * 50)

    if not config.GEMINI_API_KEYS:
        print("❌ XATOLIK: .env faylida GEMINI_API_KEY yoki GEMINI_API_KEYS topilmadi!")
        print("Iltimos, .env faylini ochib, GEMINI_API_KEY qiymatini kiriting.")
        sys.exit(1)

    print(f"🔑 Aniqlangan API kalitlar soni: {len(config.GEMINI_API_KEYS)} ta")
    print(f"📡 Asosiy model: {config.GEMINI_MODEL}")
    print("⏳ Har bir API kalit alohida sinovdan o'tkazilmoqda...\n")

    active_count = 0
    for idx, key in enumerate(config.GEMINI_API_KEYS, 1):
        masked = f"{key[:6]}...{key[-4:]}" if len(key) > 10 else f"Key #{idx}"
        try:
            client = genai.Client(api_key=key)
            resp = client.models.generate_content(
                model=config.GEMINI_MODEL,
                contents="ping",
                config=types.GenerateContentConfig(max_output_tokens=5)
            )
            print(f"  [{idx}/{len(config.GEMINI_API_KEYS)}] {masked} -> ✅ FAOL (Ishlayapti)")
            active_count += 1
        except Exception as e:
            err = str(e)
            if "429" in err or "quota" in err.lower():
                status = "⚠️ KVOTA TO'LGAN (429)"
            elif "api_key_invalid" in err.lower() or "not valid" in err.lower():
                status = "❌ YAROQSIZ KALIT"
            elif "location is not supported" in err.lower():
                status = "❌ HUDUD CHEKLOVI (IP)"
            else:
                status = f"❌ XATOLIK: {err[:45]}"
            print(f"  [{idx}/{len(config.GEMINI_API_KEYS)}] {masked} -> {status}")

    print("\n" + "=" * 50)
    print(f"📊 NATIJA: Jami {len(config.GEMINI_API_KEYS)} ta kalitdan {active_count} tasi FAOL!")
    if active_count > 0:
        print("Bot muvaffaqiyatli ishlashga tayyor: python main.py")
    else:
        print("Barcha kalitlar nosoz yoki limitda. Yangi kalit qo'shing.")
    print("=" * 50 + "\n")

if __name__ == "__main__":
    test_connection()
