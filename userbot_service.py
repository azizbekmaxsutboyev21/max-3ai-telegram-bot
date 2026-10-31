import asyncio
import time
import logging
import re
from typing import Optional, Dict, List, Any
from telethon import TelegramClient, events
from telethon.sessions import StringSession
from telethon.tl.types import User, Channel, Chat, PeerUser, PeerChat, PeerChannel, InputPhoneContact
from telethon.tl.functions.channels import JoinChannelRequest, LeaveChannelRequest
from telethon.tl.functions.messages import ImportChatInviteRequest
from telethon.tl.functions.contacts import GetContactsRequest, ImportContactsRequest
from telethon.errors import ChatWriteForbiddenError, UserBannedInChannelError
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

import config
from db_manager import db
from gemini_service import GeminiService

logger = logging.getLogger(__name__)

# Keraksiz bir martalik reaksiyalar va filler so'zlar
TRIVIAL_WORDS = {
    "ok", "xo'p", "hop", "xop", "ha", "xa", "yo'q", "yoq", "rahmat", "raxmat", "tushundim",
    "+", ".", "..", "...", "👍", "👌", "🤝", "🙏", "❤️", "😊", "😂", "hm", "hmm"
}

class UserbotService:
    def __init__(self, gemini_service: Optional[GeminiService] = None):
        self.gemini = gemini_service or GeminiService()
        self.client: Optional[TelegramClient] = None
        self.bot_instance = None
        self.me_id: Optional[int] = None
        self.me_username: Optional[str] = None
        self.me_name: Optional[str] = None
        self.is_running = False
        
        # Har bir chat bo'yicha suhbat tarixi va salomlashish holati
        self._chat_histories: Dict[int, List[Dict[str, str]]] = {}
        self._greeted_senders: Dict[int, float] = {}
        self._last_owner_outgoing: Dict[int, float] = {}
        
        # Ketma-ket kelgan xabarlarni bitta qilib olish (Debounce / Message Batching)
        self._pending_buffers: Dict[int, List[str]] = {}
        self._buffer_tasks: Dict[int, asyncio.Task] = {}
        
        # Bot xabarnomalari ID si orqali kim yozganini topish xaritasi
        self.notification_map: Dict[int, int] = {}

        # Kontaktlar va dialoglarni keshda saqlash (qidiruv tezligi < 1ms)
        self._cached_contacts: Optional[List[Any]] = None
        self._contacts_cache_time: float = 0
        self._cached_dialogs: Optional[List[Any]] = None
        self._dialogs_cache_time: float = 0

    async def get_cached_contacts(self, force_refresh: bool = False) -> List[Any]:
        """Kontaktlarni xotirada keshlab tezkor qaytarish"""
        now = time.time()
        if not force_refresh and self._cached_contacts is not None and (now - self._contacts_cache_time < 300):
            return self._cached_contacts
        if not self.client or not self.is_running:
            return self._cached_contacts or []
        try:
            res = await self.client(GetContactsRequest(hash=0))
            self._cached_contacts = res.users
            self._contacts_cache_time = now
            return self._cached_contacts
        except Exception as e:
            logger.warning(f"Kontaktlarni keshga yuklashda xatolik: {e}")
            return self._cached_contacts or []

    async def get_cached_dialogs(self, limit: int = 120, force_refresh: bool = False) -> List[Any]:
        """Dialoglarni xotirada keshlab tezkor qaytarish"""
        now = time.time()
        if not force_refresh and self._cached_dialogs is not None and (now - self._dialogs_cache_time < 180):
            return self._cached_dialogs
        if not self.client or not self.is_running:
            return self._cached_dialogs or []
        try:
            dialogs = []
            async for d in self.client.iter_dialogs(limit=limit):
                dialogs.append(d)
            self._cached_dialogs = dialogs
            self._dialogs_cache_time = now
            return self._cached_dialogs
        except Exception as e:
            logger.warning(f"Dialoglarni keshga yuklashda xatolik: {e}")
            return self._cached_dialogs or []

    def get_sender_for_notification(self, bot_msg_id: int) -> Optional[int]:
        return self.notification_map.get(bot_msg_id)

    def set_bot_instance(self, bot):
        """Xabarnoma yuborish uchun aiogram Bot obyektini o'rnatish"""
        self.bot_instance = bot

    async def start(self) -> bool:
        """Userbot (Telethon) mijozini ishga tushirish"""
        if not config.is_userbot_configured():
            logger.info("Userbot sozlanmagan (TELEGRAM_STRING_SESSION kiritilmagan).")
            return False

        try:
            session = StringSession(config.TELEGRAM_STRING_SESSION)
            self.client = TelegramClient(
                session,
                config.TELEGRAM_API_ID,
                config.TELEGRAM_API_HASH,
                device_model="AI Personal Assistant",
                system_version="Linux/Windows",
                app_version="2.0"
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

            logger.info(f"✅ Userbot AI Agent ulandi: {self.me_name} (@{self.me_username} / ID: {self.me_id})")

            self._register_handlers()
            # Keshni fonda oldindan yuklash (warm-up)
            asyncio.create_task(self.get_cached_contacts(force_refresh=True))
            asyncio.create_task(self.get_cached_dialogs(limit=100, force_refresh=True))
            return True

        except Exception as e:
            logger.error(f"Userbotni ishga tushirishda xatolik: {e}")
            self.is_running = False
            return False

    def _register_handlers(self):
        """Telethon voqealarini ro'yxatdan o'tkazish"""
        # Egasi (Azizbek) shaxsan o'zi xabar yozganda - o'sha chatda AI aralashmasligi uchun belgilaymiz
        @self.client.on(events.NewMessage(outgoing=True, func=lambda e: e.is_private))
        async def outgoing_message_tracker(event: events.NewMessage.Event):
            self._last_owner_outgoing[event.chat_id] = time.time()

        # Lichkaga kelgan kiruvchi xabarlar
        @self.client.on(events.NewMessage(incoming=True, func=lambda e: e.is_private))
        async def incoming_private_message_handler(event: events.NewMessage.Event):
            await self._buffer_incoming_message(event)

    def _is_message_relevant(self, text: str) -> bool:
        """Xabar chindan ham AI javobiga loyiqmi yoki shunchaki fon / emoji / bir martalik so'zmi?"""
        cleaned = text.strip().lower()
        if not cleaned:
            return False
        # Faqat 1-2 ta belgidan iborat yoki keraksiz filler bo'lsa
        if cleaned in TRIVIAL_WORDS:
            return False
        # Agar faqat bitta emoji yoki belgi bo'lsa
        if len(cleaned) <= 2 and not cleaned.isalnum():
            return False
        # Xizmat ko'rsatish parollari (SMS kodlar)
        if re.search(r"\b\d{4,6}\b", cleaned) and any(w in cleaned for w in ["kod", "code", "parol", "password"]):
            return False
        return True

    async def _buffer_incoming_message(self, event: events.NewMessage.Event):
        """
        Bir nechta xabarlarni bitta qilib to'plash (Debouncing).
        Masalan, foydalanuvchi 3 soniya ichida 3 ta xabar yozsa:
        1. Salom
        2. Ishlar qalay
        3. Bir savolim bor edi
        Ular bitta matnga jamlanadi va bitta javob qaytariladi.
        """
        try:
            if not db.is_agent_enabled():
                return

            sender = await event.get_sender()
            if not isinstance(sender, User):
                return

            if sender.id == self.me_id or sender.bot or sender.is_self:
                return

            if db.is_blacklisted(sender.id):
                return

            # Agar egasi shu chatda yaqinda (oxirgi 2 daqiqada) o'zi javob yozgan bo'lsa, AI aralashmaydi
            last_manual = self._last_owner_outgoing.get(sender.id, 0)
            if time.time() - last_manual < 120:
                logger.info(f"Egasi {sender.id} bilan shaxsan yozishmoqda, AI to'xtatildi.")
                return

            msg_text = event.raw_text.strip() if event.raw_text else ""
            if not msg_text and event.voice:
                msg_text = "[Ovozli xabar]"
            elif not msg_text and event.media:
                msg_text = "[Media fayl]"

            # Aqlli filtr
            if db.is_smart_filter_enabled() and not self._is_message_relevant(msg_text):
                logger.info(f"Keraksiz/filler xabar o'tkazib yuborildi: '{msg_text}'")
                return

            # Buferga qo'shish
            buf = self._pending_buffers.setdefault(sender.id, [])
            buf.append(msg_text)

            # Agar eski taymer bo'lsa, bekor qilamiz (chunki yangi xabar keldi)
            if sender.id in self._buffer_tasks and not self._buffer_tasks[sender.id].done():
                self._buffer_tasks[sender.id].cancel()

            # Yangi 3.5 soniyalik kechikish taymeri o'rnatamiz
            self._buffer_tasks[sender.id] = asyncio.create_task(
                self._process_buffered_messages(sender, event.chat_id)
            )

        except Exception as e:
            logger.error(f"Xabarni buferlashda xatolik: {e}")

    async def _process_buffered_messages(self, sender: User, chat_id: int):
        """Kechikishdan so'ng to'plangan xabarlarni Gemini orqali qayta ishlash"""
        try:
            await asyncio.sleep(3.5)
            messages = self._pending_buffers.pop(sender.id, [])
            if not messages:
                return

            combined_message = "\n".join(messages).strip()
            sender_name = f"{sender.first_name or ''} {sender.last_name or ''}".strip() or "Foydalanuvchi"

            # Salomlashilganligini tekshirish (oxirgi 6 soat ichida salom berilgan bo'lsa - qayta salom yo'q)
            last_greeted = self._greeted_senders.get(sender.id, 0)
            now = time.time()
            already_greeted = (now - last_greeted < 21600) or (sender.id in self._chat_histories and len(self._chat_histories[sender.id]) > 0)

            # Typing animatsiyasi
            async with self.client.action(chat_id, "typing"):
                agent_prompt = db.get_agent_prompt()
                agent_mode = db.get_agent_mode()
                persona = db.get_persona()
                history = self._chat_histories.get(sender.id, [])

                ai_reply = await self.gemini.generate_agent_reply(
                    sender_name=sender_name,
                    message_text=combined_message,
                    custom_prompt=agent_prompt,
                    mode=agent_mode,
                    owner_info=persona.get("about_me", ""),
                    chat_history=history,
                    already_greeted=already_greeted,
                    persona=persona
                )

            # Javobni shaxsiy chatga yuborish
            await self.client.send_message(chat_id, ai_reply)
            db.increment_agent_stat()
            self._greeted_senders[sender.id] = now

            # Suhbat tarixini saqlab qo'yish (keyingi xabarlarda AI kontekstni bilishi uchun)
            if sender.id not in self._chat_histories:
                self._chat_histories[sender.id] = []
            self._chat_histories[sender.id].append({"role": "user", "text": combined_message})
            self._chat_histories[sender.id].append({"role": "model", "text": ai_reply})
            self._chat_histories[sender.id] = self._chat_histories[sender.id][-8:]

            logger.info(f"AI Agent {sender_name} ga javob qaytardi: {ai_reply[:40]}...")

            # Egasiga (Bot orqali) xabarnoma jo'natish
            if self.bot_instance and config.CREATOR_ID:
                uname = f"@{sender.username}" if sender.username else "mavjud emas"
                mode_label = "👤 Sizning nomingizdan" if agent_mode == "as_me" else "🤖 AI Kotib sifatida"
                notification_text = (
                    "📩 **[Lichka Xabarnomasi]**\n\n"
                    f"👤 **Kimdan:** {sender_name} ({uname})\n"
                    f"🆔 **ID:** `{sender.id}`\n"
                    f"💬 **Xabar:**\n{combined_message}\n\n"
                    f"✨ **AI Javobi ({mode_label}):**\n_{ai_reply}_\n\n"
                    f"💡 *Javob yozish uchun: ushbu xabarga Reply (Ответить) qilib yozing!*"
                )
                kb = InlineKeyboardMarkup(inline_keyboard=[
                    [
                        InlineKeyboardButton(text="🚫 Bloklash (Qora ro'yxat)", callback_data=f"agent_block_{sender.id}")
                    ]
                ])
                try:
                    sent_msg = await self.bot_instance.send_message(
                        chat_id=config.CREATOR_ID,
                        text=notification_text,
                        reply_markup=kb,
                        parse_mode="Markdown"
                    )
                    self.notification_map[sent_msg.message_id] = sender.id
                except Exception as e:
                    logger.error(f"Xabarnoma jo'natishda xatolik: {e}")

        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error(f"Buferlangan xabarlarni qayta ishlashda xatolik: {e}")

    # ---------------- TELEGRAM AKKAUNTINI BOSHQARISH FUNKSIYALARI ----------------

    async def get_dialogs_list(self, filter_type: str = "all", limit: int = 25) -> List[Dict[str, Any]]:
        """Akkauntdagi guruhlar, kanallar, botlar va chatlar ro'yxatini olish"""
        if not self.is_running or not self.client:
            return []

        result = []
        try:
            cached = await self.get_cached_dialogs(limit=max(limit, 50))
            for dialog in cached[:limit]:
                entity = dialog.entity
                d_type = "user"
                username = getattr(entity, "username", None) or ""
                title = dialog.name or "Nomsiz"

                if dialog.is_channel:
                    d_type = "channel"
                elif dialog.is_group:
                    d_type = "group"
                elif getattr(entity, "bot", False):
                    d_type = "bot"

                if filter_type != "all" and d_type != filter_type:
                    continue

                result.append({
                    "id": dialog.id,
                    "title": title,
                    "type": d_type,
                    "username": username,
                    "unread_count": dialog.unread_count
                })
        except Exception as e:
            logger.error(f"Dialoglarni olishda xatolik: {e}")
        return result

    async def get_chat_history_text(self, target: Any, limit: int = 15) -> str:
        """Istalgan guruh, kanal yoki chatdan so'nggi xabarlarni o'qish"""
        if not self.is_running or not self.client:
            return "Userbot ulanmagan."

        try:
            messages = []
            async for msg in self.client.iter_messages(target, limit=limit):
                if not msg.text:
                    continue
                sender_name = "Noma'lum"
                if msg.sender:
                    sender_name = getattr(msg.sender, "first_name", "") or getattr(msg.sender, "title", "Chat")
                messages.append(f"[{sender_name}]: {msg.text}")

            messages.reverse()
            return "\n".join(messages) if messages else "Chatda matnli xabarlar topilmadi."
        except Exception as e:
            logger.error(f"Chat tarixini o'qishda xatolik: {e}")
            return f"Xatolik: {e}"

    async def interact_with_bot(self, bot_username: str, command: str) -> str:
        """Boshqa Telegram botga buyruq yoki xabar yuborib, uning javobini qabul qilish"""
        if not self.is_running or not self.client:
            return "Userbot ulanmagan."

        try:
            bot_entity = await self.client.get_input_entity(bot_username)
            sent_msg = await self.client.send_message(bot_entity, command)
            
            # Botning javobini 6 soniya kutamiz
            await asyncio.sleep(4)
            replies = []
            async for msg in self.client.iter_messages(bot_entity, limit=3):
                if msg.id > sent_msg.id and msg.text:
                    replies.append(msg.text)

            if replies:
                return "\n\n".join(reversed(replies))
            return f"@{bot_username} ga '{command}' yuborildi, ammo javob kelmadi yoki javob matnsiz."
        except Exception as e:
            logger.error(f"Bot bilan muloqotda xatolik: {e}")
            return f"Xatolik yuz berdi: {e}"

    def can_write_to_entity(self, entity: Any) -> bool:
        """Ushbu chat/kanalga xabar yozish huquqimiz bormi?"""
        if isinstance(entity, User):
            return True
        if isinstance(entity, Chat):
            return not getattr(entity, 'kicked', False) and not getattr(entity, 'left', False)
        if isinstance(entity, Channel):
            if getattr(entity, 'broadcast', False):
                if getattr(entity, 'creator', False):
                    return True
                admin_rights = getattr(entity, 'admin_rights', None)
                if admin_rights and getattr(admin_rights, 'post_messages', False):
                    return True
                return False
            else:
                if getattr(entity, 'left', False) or getattr(entity, 'kicked', False):
                    return False
                banned_rights = getattr(entity, 'banned_rights', None)
                if banned_rights and getattr(banned_rights, 'send_messages', False):
                    return False
                default_banned = getattr(entity, 'default_banned_rights', None)
                if default_banned and getattr(default_banned, 'send_messages', False):
                    if not getattr(entity, 'creator', False) and not getattr(entity, 'admin_rights', None):
                        return False
                return True
        return True

    async def find_entity_by_name_or_username(self, query: Any) -> Optional[Any]:
        """Foydalanuvchi, guruh yoki kanalni ID, username, telefon yoki nomi bo'yicha aniq topish"""
        if not self.is_running or not self.client:
            return None

        query_str = str(query).strip()
        if not query_str:
            return None

        # 1. Agar sonli ID bo'lsa (masalan 8927070806 yoki -100123456789)
        if query_str.lstrip("-").isdigit():
            target_id = int(query_str)
            # A) To'g'ridan-to'g'ri get_entity
            try:
                ent = await self.client.get_entity(target_id)
                if ent and self.can_write_to_entity(ent):
                    return ent
            except Exception:
                pass

            # B) Dialoglar orasidan qidirish (ID bo'yicha)
            dialogs = await self.get_cached_dialogs()
            for dialog in dialogs:
                if dialog.id == target_id or getattr(dialog.entity, 'id', None) == target_id:
                    if self.can_write_to_entity(dialog.entity):
                        return dialog.entity

            # C) Kontaktlar ro'yxatidan qidirish (ID bo'yicha)
            contacts = await self.get_cached_contacts()
            for u in contacts:
                if u.id == target_id:
                    return u

            # D) PeerUser orqali get_entity
            try:
                ent = await self.client.get_entity(PeerUser(target_id))
                if ent and self.can_write_to_entity(ent):
                    return ent
            except Exception:
                pass

        # 2. Agar @username yoki t.me havola bo'lsa
        if query_str.startswith("@") or "t.me/" in query_str:
            clean = query_str.replace("https://t.me/", "").replace("t.me/", "").lstrip("@")
            try:
                ent = await self.client.get_entity(clean)
                if ent and self.can_write_to_entity(ent):
                    return ent
            except Exception:
                pass

        # 3. Agar telefon raqam bo'lsa
        if query_str.startswith("+") and query_str[1:].isdigit():
            try:
                ent = await self.client.get_entity(query_str)
                if ent and self.can_write_to_entity(ent):
                    return ent
            except Exception:
                pass

        # 4. Ism yoki so'z bo'yicha qidirish (masalan: "Munisaga", "Munisa")
        query_lower = query_str.lower().strip()
        clean_name = query_lower
        for suffix in ["ga", "ka", "qa", "ge", "ni", "ning", "da", "dan"]:
            if clean_name.endswith(suffix) and len(clean_name) > len(suffix) + 2:
                clean_name = clean_name[:-len(suffix)]
                break

        # A) BIRINCHI NAVBATDA: Shaxsiy kontaktlar ro'yxati (Keshdan)
        contacts = await self.get_cached_contacts()
        # 1. Exact match (to'liq mos)
        for u in contacts:
            first = (u.first_name or "").lower()
            last = (u.last_name or "").lower()
            full = f"{first} {last}".strip()
            uname = (u.username or "").lower()
            if clean_name in [first, last, full, uname] or query_lower in [first, last, full, uname]:
                return u

        # 2. Substring match
        for u in contacts:
            first = (u.first_name or "").lower()
            last = (u.last_name or "").lower()
            full = f"{first} {last}".strip()
            uname = (u.username or "").lower()
            if (clean_name and (clean_name in first or clean_name in full or clean_name in uname)) or \
               (query_lower in first or query_lower in full or query_lower in uname):
                return u

        # B) IKKINCHI NAVBATDA: Dialoglar (chatlar) ro'yxati (Keshdan)
        user_exact = None
        user_partial = None
        group_exact = None
        group_partial = None
        channel_admin = None

        dialogs = await self.get_cached_dialogs()
        for dialog in dialogs:
            ent = dialog.entity
            if not self.can_write_to_entity(ent):
                continue

            d_name = dialog.name.lower() if dialog.name else ""
            d_uname = (getattr(ent, "username", None) or "").lower()

            is_exact = (clean_name in [d_name, d_uname] or query_lower in [d_name, d_uname])
            is_partial = (clean_name and (clean_name in d_name or clean_name in d_uname)) or \
                         (query_lower in d_name or query_lower in d_uname)

            if dialog.is_user:
                if is_exact and not user_exact:
                    user_exact = ent
                elif is_partial and not user_partial:
                    user_partial = ent
            elif dialog.is_group:
                if is_exact and not group_exact:
                    group_exact = ent
                elif is_partial and not group_partial:
                    group_partial = ent
            elif dialog.is_channel and getattr(ent, "broadcast", False):
                if (is_exact or is_partial) and not channel_admin:
                    channel_admin = ent

        if user_exact:
            return user_exact
        if user_partial:
            return user_partial
        if group_exact:
            return group_exact
        if group_partial:
            return group_partial
        if channel_admin:
            return channel_admin

        # C) Oxirgi urinish: get_entity
        try:
            ent = await self.client.get_entity(clean_name if clean_name else query_str)
            if ent and self.can_write_to_entity(ent):
                return ent
        except Exception:
            pass

        return None

    async def send_to_target(
        self,
        target: Any,
        text: str,
        silent: bool = False,
        schedule_in_seconds: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Istalgan chat, kanal yoki shaxsga xabar yuborish (Telegram Premium xususiyatlari bilan):
        - Uzun xabarlar (4096 belgigacha)
        - Ovoz bildirishnomasisiz (silent) yuborish
        - Rejalashtirilgan (schedule) vaqtda yuborish
        """
        if not self.is_running or not self.client:
            return {"success": False, "error": "Userbot ulanmagan. Iltimos, .env da sessiyani tekshiring.", "chat_title": str(target)}

        try:
            entity = await self.find_entity_by_name_or_username(target)
            if not entity:
                return {
                    "success": False,
                    "error": (
                        f"'{target}' nomli chat, kontakt yoki kanal topilmadi.\n\n"
                        "💡 *Maslahat:* Aniqroq topish uchun uning @username ini (masalan: @munisa) "
                        "yoki Telegram kontaktlaringizdagi to'liq ismini kiriting."
                    ),
                    "chat_title": str(target)
                }

            title = getattr(entity, "title", None)
            if not title:
                title = f"{getattr(entity, 'first_name', '')} {getattr(entity, 'last_name', '')}".strip()
            if not title:
                title = getattr(entity, "username", None) or str(target)

            if not self.can_write_to_entity(entity):
                return {
                    "success": False,
                    "error": f"'{title}' chatiga yozish huquqi yo'q (bu ommaviy kanal yoki yozish cheklangan guruh).",
                    "chat_title": title
                }

            schedule = None
            if schedule_in_seconds and schedule_in_seconds > 0:
                import datetime
                schedule = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(seconds=schedule_in_seconds)

            sent = await self.client.send_message(
                entity,
                text,
                silent=silent,
                schedule=schedule
            )

            return {
                "success": True,
                "chat_title": title,
                "chat_id": getattr(entity, "id", None),
                "message_id": sent.id
            }
        except Exception as e:
            logger.error(f"Xabar yuborishda xatolik: {e}")
            err_str = str(e)
            target_str = str(target)

            if "can't write in this chat" in err_str.lower() or "chatwriteforbiddenerror" in err_str.lower():
                user_friendly_err = f"'{target_str}' chatiga yozish huquqi yo'q (bu kanal yoki yozish cheklangan guruh bo'lishi mumkin)."
            elif "peeruser" in err_str.lower() or "could not find the input entity" in err_str.lower():
                user_friendly_err = (
                    f"'{target_str}' identifikatori bo'yicha foydalanuvchi topilmadi. "
                    "Telegram qoidasiga ko'ra, siz bilan avval yozishmagan shaxsga faqat raqamli ID orqali yozib bo'lmaydi. "
                    "Iltimos, uning @username ini (masalan @profil) yoki telefon raqamini bering yoki uni kontaktlaringizga qo'shing."
                )
            elif "user_is_blocked" in err_str.lower():
                user_friendly_err = "Foydalanuvchi sizni bloklagan yoki siz uni bloklagansiz."
            elif "privacy" in err_str.lower():
                user_friendly_err = "Foydalanuvchi Telegram maxfiylik sozlamalarida begonalardan xabar olishni cheklagan."
            else:
                user_friendly_err = err_str

            return {"success": False, "error": user_friendly_err, "chat_title": target_str}

    async def send_to_multiple_targets(self, targets: List[str], text: str, silent: bool = False) -> Dict[str, Any]:
        """Bir nechta chatlarga bir vaqtda xabar tarqatish"""
        results = {"success": [], "failed": []}
        for t in targets:
            t_clean = t.strip()
            if not t_clean:
                continue
            res = await self.send_to_target(t_clean, text, silent=silent)
            if res["success"]:
                results["success"].append(f"{res['chat_title']}")
            else:
                results["failed"].append(f"{t_clean}: {res['error']}")
        return results

    async def react_to_message(self, target: Any, message_id: int, emoji: str = "🔥") -> Dict[str, Any]:
        """Xabarga reaksiya bildirish (Telegram Premium / Standart emojilar)"""
        if not self.is_running or not self.client:
            return {"success": False, "error": "Userbot ulanmagan."}

        try:
            entity = await self.find_entity_by_name_or_username(target)
            if not entity:
                return {"success": False, "error": f"'{target}' topilmadi."}

            await self.client.send_reaction(entity, message_id, emoji)
            return {"success": True, "chat": str(target), "emoji": emoji}
        except Exception as e:
            logger.error(f"Reaksiya bildirishda xatolik: {e}")
            return {"success": False, "error": str(e)}

    async def send_direct_message(self, target_id: Any, text: str) -> bool:
        """Eski kod bilan moslik uchun"""
        res = await self.send_to_target(target_id, text)
        return res["success"]

    async def join_chat(self, link_or_username: str) -> str:
        """Guruh yoki kanalga a'zo bo'lish"""
        if not self.is_running or not self.client:
            return "Userbot ulanmagan."
        try:
            if "t.me/+" in link_or_username or "joinchat" in link_or_username:
                hash_val = link_or_username.split("+")[-1].split("/")[-1]
                await self.client(ImportChatInviteRequest(hash_val))
            else:
                await self.client(JoinChannelRequest(link_or_username))
            return f"✅ '{link_or_username}' ga muvaffaqiyatli qo'shildingiz!"
        except Exception as e:
            return f"❌ Qo'shilishda xatolik: {e}"

    async def leave_chat(self, chat_id: Any) -> str:
        """Guruh yoki kanaldan chiqish"""
        if not self.is_running or not self.client:
            return "Userbot ulanmagan."
        try:
            await self.client(LeaveChannelRequest(chat_id))
            return f"✅ `{chat_id}` dan muvaffaqiyatli chiqildi!"
        except Exception as e:
            return f"❌ Chiqishda xatolik: {e}"

    async def stop(self):
        """Userbotni to'xtatish"""
        if self.client and self.client.is_connected():
            await self.client.disconnect()
            self.is_running = False
            logger.info("Userbot to'xtatildi.")

    def get_status(self) -> dict:
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
