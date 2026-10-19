import asyncio
import logging
import os
import sys

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass
from aiogram import Bot, Dispatcher
from aiogram.types import BotCommand
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from aiohttp import web
import config
from handlers import router

# Loglarni sozlash
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

async def health_check(request):
    """Render.com yoki boshqa serverlar uchun salomatlik tekshiruvi (Health Check)"""
    return web.Response(text="Bot is running! 🤖", status=200)

async def start_web_server():
    """Render.com Free Web Service uchun portni tinglash"""
    port = int(os.getenv("PORT", 8080))
    app = web.Application()
    app.router.add_get("/", health_check)
    app.router.add_get("/health", health_check)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()
    logger.info(f"Render health-check server ishga tushdi: port {port}")

async def set_bot_commands(bot: Bot):
    """Telegram menyusida chiqadigan buyruqlar ro'yxatini sozlash"""
    commands = [
        BotCommand(command="start", description="Botni ishga tushirish"),
        BotCommand(command="reset", description="Suhbat tarixini tozalash"),
        BotCommand(command="admin", description="Boshqaruv paneli (Yaratuvchi)"),
        BotCommand(command="help", description="Qo'llanma va yordam"),
        BotCommand(command="about", description="Bot haqida ma'lumot"),
    ]
    await bot.set_my_commands(commands)

async def main():
    logger.info("Bot ishga tushmoqda...")
    
    # Render.com uchun web-serverni ishga tushirish (agar PORT mavjud bo'lsa)
    if os.getenv("PORT") or os.getenv("RENDER"):
        await start_web_server()
    
    # Konfiguratsiya tekshiruvi
    if not config.validate_config():
        logger.error("Konfiguratsiya to'liq emas. Bot to'xtatildi.")
        sys.exit(1)

    # Bot va Dispatcher yaratish
    bot = Bot(
        token=config.BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.MARKDOWN)
    )
    dp = Dispatcher()

    # Routerni ro'yxatdan o'tkazish
    dp.include_router(router)

    # Menyu buyruqlarini o'rnatish
    await set_bot_commands(bot)

    # Bot ma'lumotlarini chop etish
    bot_info = await bot.get_me()
    logger.info(f"Bot muvaffaqiyatli ishga tushdi: @{bot_info.username} ({bot_info.first_name})")
    print(f"\n" + "=" * 50)
    print(f"✅ Bot faol: @{bot_info.username}")
    print(f"🤖 Gemini modeli: {config.GEMINI_MODEL}")
    print(f"👑 Yaratuvchi ID: {config.CREATOR_ID}")
    print("=" * 50 + "\n")

    # Eski kutilayotgan yangilanishlarni o'tkazib yuborish
    await bot.delete_webhook(drop_pending_updates=True)

    # Polling boshlash
    try:
        await dp.start_polling(bot)
    finally:
        await bot.session.close()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Bot to'xtatildi.")
