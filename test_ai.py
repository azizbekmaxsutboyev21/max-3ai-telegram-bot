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

    if not config.GEMINI_API_KEY:
        print("❌ XATOLIK: .env faylida GEMINI_API_KEY topilmadi!")
        print("Iltimos, .env faylini ochib, GEMINI_API_KEY qiymatini kiriting.")
        sys.exit(1)

    try:
        client = genai.Client(api_key=config.GEMINI_API_KEY)
        print(f"📡 Model: {config.GEMINI_MODEL}")
        print("⏳ Test so'rovi yuborilmoqda...")

        response = client.models.generate_content(
            model=config.GEMINI_MODEL,
            contents="Salom! O'zingni qisqacha bir gap bilan tanishtir.",
            config=types.GenerateContentConfig(
                system_instruction="Siz aqlli o'zbek AI yordamchisiz.",
            )
        )

        print("\n✅ API MUVAFFAQIYATLI ULINDI!")
        print(f"Javob: {response.text.strip()}")
        print("=" * 50)
        print("Endi botni ishga tushirishingiz mumkin: python main.py\n")

    except Exception as e:
        print(f"\n❌ XATOLIK YUZ BERDI: {e}")
        print("Iltimos, API kalitingiz to'g'riligini va internet ulanishini tekshiring.")
        sys.exit(1)

if __name__ == "__main__":
    test_connection()
