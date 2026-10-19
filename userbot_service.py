import asyncio
import time
import logging
from typing import Optional, Dict
from telethon import TelegramClient, events
from telethon.sessions import StringSession
from telethon.tl.types import User

import config
from db_manager import db
from gemini_service import GeminiService

logger = logging.getLogger(__name__)

class UserbotService:
    def __init__(self, gemini_service: Optional[GeminiService] = None):
        self.gemini = gemini_service or GeminiService()
        self.client: Optional[TelegramClient] = None
        self.bot_instance = None
        self.me_id: Optional[int] = None
        self.me_username: Optional[str] = None
        self.me_name: Optional[str] = None
        self.is_running = False
        self._last_reply_times: Dict[int, float] = {}

    def set_bot_instance(self, bot):
        """Xabarnoma yuborish uchun aiogram Bot obyektini o'rnatish"""
        self.bot_instance = bot

    async def start(self) -> bool:
        """Userbot (Telethon) mijozini ishga tushirish"""
        if not config.is_userbot_configured():
            logger.info("Userbot sozlanmagan (TELEGRAM_API_ID, TELEGRAM_API_HASH yoki TELEGRAM_STRING_SESSION kiritilmagan).")
            return False

        try:
            session = StringSession(config.TELEGRAM_STRING_SESSION)
            self.client = TelegramClient(
                session,
                config.TELEGRAM_API_ID,
                config.TELEGRAM_API_HASH,
                device_model="AI Agent Assistant",
                system_version="Linux/Windows",
                app_version="1.0"
            )

            await self.client.connect()

            if not await self.client.is_user_authorized():
                logger.error("Userbot sessiyasi yaroqsiz yoki avtorizatsiyadan o'tmagan!")
                return False

            me = await self.client.get_me()
            self.me_id = me.id
            self.me_username = me.username or ""
            self.me_name = f"{me.first_name or ''} {me.last_name or ''}".strip()
            self.is_running = True

            logger.info(f"✅ Userbot AI Agent muvaffaqiyatli ulandi: {self.me_name} (@{self.me_username} / ID: {self.me_id})")

            # Xabarlarni tinglash handlerini ro'yxatdan o'tkazamiz
            self._register_handlers()
            return True

        except Exception as e:
            logger.error(f"Userbotni ishga tushirishda xatolik: {e}")
            self.is_running = False
            return False

    def _register_handlers(self):
        """Telethon voqealarini (events) ro'yxatdan o'tkazish"""
        @self.client.on(events.NewMessage(incoming=True, func=lambda e: e.is_private))
        async def incoming_private_message_handler(event: events.NewMessage.Event):
            await self._handle_private_message(event)

    async def _handle_private_message(self, event: events.NewMessage.Event):
        """Shaxsiy chatga (lichkaga) kelgan yangi xabarni qayta ishlash"""
        try:
            # 1. AI agent yoqilganligini tekshirish
            if not db.is_agent_enabled():
                return

            sender = await event.get_sender()
            if not isinstance(sender, User):
                return

            # O'zimizga o'zimiz yoki botlarga javob bermaymiz
            if sender.id == self.me_id or sender.bot or sender.is_self:
                return

            # Qora ro'yxat tekshiruvi
            if db.is_blacklisted(sender.id):
                return

            # Xabar matni
            message_text = event.raw_text.strip() if event.raw_text else ""
            if not message_text and event.voice:
                message_text = "[Ovozli xabar yuborildi]"
            elif not message_text and event.media:
                message_text = "[Media fayl yuborildi]"

            if not message_text:
                return

            # Ketma-ket spamni oldini olish (oxirgi 20 soniya ichida javob berilgan bo'lsa kutish)
            now = time.time()
            last_time = self._last_reply_times.get(sender.id, 0)
            if now - last_time < 20:
                logger.info(f"Foydalanuvchi {sender.id} uchun cooldown faol, javob o'tkazib yuborildi.")
                return

            self._last_reply_times[sender.id] = now
            sender_name = f"{sender.first_name or ''} {sender.last_name or ''}".strip() or "Foydalanuvchi"

            # Yozilayotgan holatni bildirish (typing)
            async with self.client.action(event.chat_id, "typing"):
                await asyncio.sleep(2)
                # Gemini orqali aqlli javob olish
                agent_prompt = db.get_agent_prompt()
                ai_reply = await self.gemini.generate_agent_reply(
                    sender_name=sender_name,
                    message_text=message_text,
                    custom_prompt=agent_prompt
                )

            # Javobni shaxsiy chatga jo'natish
            await event.reply(ai_reply)
            db.increment_agent_stat()
            logger.info(f"AI Agent {sender_name} ga javob qaytardi: {ai_reply[:40]}...")

            # Telegram Bot orqali egasiga xabarnoma jo'natish
            if self.bot_instance and config.CREATOR_ID:
                uname = f"@{sender.username}" if sender.username else "mavjud emas"
                notification_text = (
                    "🤖 **[AI Agent Lichka Xabarnomasi]**\n\n"
                    f"👤 **Kimdan:** {sender_name} ({uname})\n"
                    f"🆔 **ID:** `{sender.id}`\n"
                    f"💬 **Xabar:** {message_text}\n"
                    f"✨ **AI Javobi:** {ai_reply}\n\n"
                    f"💡 *Javob yozish uchun:* `/reply {sender.id} <matn>`"
                )
                try:
                    await self.bot_instance.send_message(
                        chat_id=config.CREATOR_ID,
                        text=notification_text,
                        parse_mode="Markdown"
                    )
                except Exception as e:
                    logger.error(f"Xabarnoma jo'natishda xatolik: {e}")

        except Exception as e:
            logger.error(f"Lichka xabarini qayta ishlashda xatolik: {e}")

    async def send_direct_message(self, target_id: int | str, text: str) -> bool:
        """Shaxsiy akkaunt nomidan to'g'ridan-to'g'ri xabar yuborish"""
        if not self.is_running or not self.client:
            return False
        try:
            await self.client.send_message(target_id, text)
            return True
        except Exception as e:
            logger.error(f"Xabar yuborishda xatolik: {e}")
            return False

    async def stop(self):
        """Userbotni to'xtatish"""
        if self.client and self.client.is_connected():
            await self.client.disconnect()
            self.is_running = False
            logger.info("Userbot to'xtatildi.")

    def get_status(self) -> dict:
        """Holat ma'lumotlarini qaytarish"""
        return {
            "configured": config.is_userbot_configured(),
            "connected": self.is_running,
            "user_name": self.me_name,
            "username": self.me_username,
            "user_id": self.me_id,
            "agent_enabled": db.is_agent_enabled(),
            "stats": db.get_agent_stats()
        }

userbot = UserbotService()
