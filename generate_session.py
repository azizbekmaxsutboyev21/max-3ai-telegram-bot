import os
import sys
import asyncio
from telethon import TelegramClient
from telethon.sessions import StringSession
from dotenv import load_dotenv

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

load_dotenv(override=True)

API_ID = int(os.getenv("TELEGRAM_API_ID", "38828334"))
API_HASH = os.getenv("TELEGRAM_API_HASH", "0ce78aa086473d016693c143e499b63b")

def save_session_to_env(session_str: str):
    env_file = ".env"
    if not os.path.exists(env_file):
        with open(env_file, "w", encoding="utf-8") as f:
            f.write(f"TELEGRAM_STRING_SESSION={session_str}\n")
        return

    with open(env_file, "r", encoding="utf-8") as f:
        lines = f.readlines()

    found = False
    new_lines = []
    for line in lines:
        if line.startswith("TELEGRAM_STRING_SESSION="):
            new_lines.append(f"TELEGRAM_STRING_SESSION={session_str}\n")
            found = True
        else:
            new_lines.append(line)

    if not found:
        new_lines.append(f"\nTELEGRAM_STRING_SESSION={session_str}\n")

    with open(env_file, "w", encoding="utf-8") as f:
        f.writelines(new_lines)

async def main():
    print("=" * 60)
    print("🤖 Telegram AI Agent - Sessiya Yaratish Dasturi")
    print("=" * 60)
    print(f"API_ID: {API_ID}")
    print(f"API_HASH: {API_HASH[:6]}...{API_HASH[-4:]}")
    print("-" * 60)

    client = TelegramClient(StringSession(), API_ID, API_HASH)
    await client.start()

    session_str = client.session.save()
    me = await client.get_me()

    print("\n" + "=" * 60)
    print("✅ Muvaffaqiyatli ulandi!")
    print(f"👤 Ism: {me.first_name} {me.last_name or ''}")
    print(f"🆔 Telegram ID: {me.id}")
    print(f"🔗 Username: @{me.username or 'mavjud emas'}")
    print("=" * 60)

    # .env ga avtomatik saqlash
    save_session_to_env(session_str)
    print("💾 Sessiya kodi .env fayliga avtomatik saqlandi!")
    print("\n🔑 Render.com uchun TELEGRAM_STRING_SESSION qiymati:\n")
    print(session_str)
    print("\n" + "=" * 60)

    await client.disconnect()

if __name__ == "__main__":
    asyncio.run(main())
