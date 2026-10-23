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

    print(f"🔑 Aniqlangan API kalitlar soni: {len(config.GEMINI_API_KEYS)}")
    print(f"📡 Asosiy model: {config.GEMINI_MODEL}")
    print(f"🛡 Zaxira modellar: {', '.join(config.GEMINI_FALLBACK_MODELS)}")
    print("⏳ Test so'rovi yuborilmoqda...")

    success = False
    for model in config.GEMINI_FALLBACK_MODELS:
        for key in config.GEMINI_API_KEYS:
            try:
                client = genai.Client(api_key=key)
                response = client.models.generate_content(
                    model=model,
                    contents="Salom! O'zingni qisqacha bir gap bilan tanishtir.",
                    config=types.GenerateContentConfig(
                        system_instruction="Siz aqlli o'zbek AI yordamchisiz.",
                    )
                )
                print("\n✅ API MUVAFFAQIYATLI ULINDI!")
                print(f"Ishlagan model: {model}")
                print(f"Javob: {response.text.strip()}")
                print("=" * 50)
                print("Endi botni ishga tushirishingiz mumkin: python main.py\n")
                success = True
                break
            except Exception as e:
                print(f"⚠️ Model {model} bilan sinovda xatolik: {e}")
        if success:
            break

    if not success:
        print("\n❌ Barcha kalitlar va modellar bilan ulanish amalga oshmadi.")
        print("Iltimos, API kalitlaringiz to'g'riligini va internet ulanishini tekshiring.")
        sys.exit(1)

if __name__ == "__main__":
    test_connection()
