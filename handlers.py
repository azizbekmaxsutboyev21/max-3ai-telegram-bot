import io
import logging
from aiogram import Router, F, Bot, BaseMiddleware
from aiogram.filters import CommandStart, Command
from aiogram.types import (
    Message,
    ReplyKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardRemove,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    CallbackQuery,
    BufferedInputFile,
    ChatMemberUpdated
)
from aiogram.enums import ChatAction, ChatMemberStatus
import config
from gemini_service import GeminiService
from tts_service import synthesize_voice
from db_manager import db
from userbot_service import userbot

logger = logging.getLogger(__name__)

router = Router()
gemini = GeminiService()

# Asosiy tugmalar (Reply Keyboard)
main_keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="💬 Yangi suhbat"), KeyboardButton(text="🎙 Ovozli yordam")],
        [KeyboardButton(text="ℹ️ Bot haqida"), KeyboardButton(text="💡 Yordam")],
        [KeyboardButton(text="🔒 Qulflash"), KeyboardButton(text="🔑 Kodni o'zgartirish")]
    ],
    resize_keyboard=True
)

class PrivateAuthMiddleware(BaseMiddleware):
    """
    Faqat bot egasiga ruxsat berish va maxfiy PIN-kod (passcode) bilan
    avtorizatsiya qilish xavfsizlik middleware-si.
    """
    async def __call__(self, handler, event, data):
        user = getattr(event, "from_user", None)
        if not user:
            return await handler(event, data)

        # 1. Begonalarni to'liq bloklash (Faqat egasi foydalana oladi)
        if user.id != config.CREATOR_ID:
            if isinstance(event, Message):
                await event.answer(
                    "⛔️ **Kirish taqiqlangan!**\n\n"
                    "Ushbu bot shaxsiy bot bo'lib, faqat uning egasi uchun mo'ljallangan.",
                    parse_mode="Markdown"
                )
            elif isinstance(event, CallbackQuery):
                await event.answer("⛔️ Kirish taqiqlangan! Ushbu bot shaxsiy.", show_alert=True)
            return

        # 2. Bot egasi uchun xavfsizlik tekshiruvi (Kod / Parol)
        if isinstance(event, Message) and event.text:
            text = event.text.strip()

            # Qulflash buyrug'i
            if text in ["/lock", "🔒 Qulflash"]:
                db.set_authenticated(user.id, False)
                await event.answer(
                    "🔒 **Bot muvaffaqiyatli qulflandi!**\n\n"
                    "Qayta kirish uchun maxfiy kodingizni kiriting:",
                    reply_markup=ReplyKeyboardRemove(),
                    parse_mode="Markdown"
                )
                return

            # Kodni o'zgartirish buyrug'i
            if text.startswith("/setcode") or text.startswith("/setpass"):
                if not db.is_authenticated(user.id):
                    await event.answer("🔐 Avval joriy maxfiy kodni kiritib, botni oching!")
                    return
                parts = text.split(maxsplit=1)
                if len(parts) == 2 and parts[1].strip():
                    new_code = parts[1].strip()
                    db.set_access_code(new_code)
                    await event.answer(
                        f"✅ **Yangi kirish kodi muvaffaqiyatli o'rnatildi:** `{new_code}`\n\n"
                        "Uni eslab qoling! Botni qulflash uchun: /lock",
                        parse_mode="Markdown"
                    )
                else:
                    await event.answer(
                        "❗ **Format:** `/setcode <yangi_kod>`\n"
                        "Misol: `/setcode 9988` yoki `/setcode maxfiy_parol`",
                        parse_mode="Markdown"
                    )
                return

            if text == "🔑 Kodni o'zgartirish":
                await event.answer(
                    "🔑 **Kodni o'zgartirish:**\n\n"
                    "Yangi kod o'rnatish uchun quyidagi formatda yuboring:\n"
                    "`/setcode <yangi_kod>`\n\n"
                    "Misol: `/setcode 9988`",
                    parse_mode="Markdown"
                )
                return

            # Agar egasi hali tasdiqlanmagan (bot qulflangan) bo'lsa
            if not db.is_authenticated(user.id):
                current_code = db.get_access_code()
                if text == current_code:
                    db.set_authenticated(user.id, True)
                    await event.answer(
                        "🔓 **Muvaffaqiyatli tasdiqlandi!** Xush kelibsiz, xo'jayin.\n\n"
                        "Botdan to'liq foydalanishingiz mumkin. Savolingizni bemalol yuboring!\n\n"
                        "🔒 Qulflash: `/lock`\n"
                        "🔑 Kodni o'zgartirish: `/setcode <yangi_kod>`",
                        reply_markup=main_keyboard,
                        parse_mode="Markdown"
                    )
                    return
                else:
                    await event.answer(
                        "🔐 **Xavfsizlik tekshiruvi (Bot qulflangan):**\n\n"
                        "Iltimos, botdan foydalanish uchun maxfiy kirish kodingizni kiriting:",
                        parse_mode="Markdown"
                    )
                    return

        # Qulflangan paytda matnsiz xabarlar (audio, rasm va h.k.)
        if not db.is_authenticated(user.id):
            if isinstance(event, Message):
                await event.answer(
                    "🔐 **Bot qulflangan!**\n\n"
                    "Iltimos, avval maxfiy kirish kodingizni matn ko'rinishida kiriting.",
                    parse_mode="Markdown"
                )
            elif isinstance(event, CallbackQuery):
                await event.answer("🔐 Avval maxfiy kodni kiriting!", show_alert=True)
            return

        # Tasdiqlangan foydalanuvchi xabarlarini normal handlerlarga yo'naltirish
        return await handler(event, data)

# Middleware-ni barcha xabarlar va callback-lar uchun ro'yxatdan o'tkazamiz
router.message.middleware(PrivateAuthMiddleware())
router.callback_query.middleware(PrivateAuthMiddleware())

def split_message(text: str, max_length: int = 4000) -> list[str]:
    """Telegram xabar cheklovi (4096 belgi) uchun matnni bo'laklarga ajratish"""
    if len(text) <= max_length:
        return [text]
    
    parts = []
    while len(text) > max_length:
        split_idx = text.rfind("\n", 0, max_length)
        if split_idx == -1:
            split_idx = text.rfind(" ", 0, max_length)
        if split_idx == -1:
            split_idx = max_length
        
        parts.append(text[:split_idx].strip())
        text = text[split_idx:].strip()
    
    if text:
        parts.append(text)
    return parts

async def safe_reply(message: Message, text: str):
    """Xabarni xavfsiz jo'natish (Markdown parsing xatosi bo'lsa oddiy matn sifatida)"""
    parts = split_message(text)
    for part in parts:
        try:
            await message.reply(part, parse_mode="Markdown")
        except Exception:
            await message.reply(part, parse_mode=None)

# ----------------- GURUH VA KANALLAR KUZATUVI -----------------

@router.my_chat_member()
async def handle_my_chat_member(event: ChatMemberUpdated):
    """Bot guruh yoki kanalga qo'shilganda yoki chiqarilganda eslab qolish"""
    chat = event.chat
    new_status = event.new_chat_member.status
    if new_status in [ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.MEMBER]:
        db.register_chat(
            chat_id=chat.id,
            title=chat.title or "Nomsiz",
            chat_type=chat.type,
            username=chat.username
        )
        logger.info(f"Bot yangi chatga qo'shildi: {chat.title} ({chat.id}) - {chat.type}")
    elif new_status in [ChatMemberStatus.LEFT, ChatMemberStatus.KICKED]:
        db.remove_chat(chat.id)
        logger.info(f"Bot chatdan chiqarildi: {chat.title} ({chat.id})")

# ----------------- BUYRUQLAR -----------------

@router.message(CommandStart())
async def handle_start(message: Message):
    user = message.from_user
    db.register_user(user.id, user.full_name, user.username)
    is_creator = (user.id == config.CREATOR_ID)
    
    creator_badge = "\n👑 **Siz ushbu botning Yaratuvchisi (Egasi)siz!**\nBoshqaruv paneli uchun: /admin" if is_creator else ""

    text = (
        f"Assalomu alaykum, {user.first_name}! 👋\n\n"
        "Men **Google Gemini AI** texnologiyasiga asoslangan aqlli Telegram botman.\n"
        f"{creator_badge}\n\n"
        "Quyidagi imkoniyatlarga egaman:\n"
        "🔹 **Matnli savol-javob:** Istalgan mavzuda yozing\n"
        "🔹 **Ovozli muloqot 🎙:** Menga ovozli xabar (audio) yuboring, men ham sizga ovoz bilan javob qaytaraman!\n"
        "🔹 **Rasm tahlili 🖼:** Rasm yuboring, uni ko'rib tahlil qilaman\n"
        "🔹 **Suhbat konteksti 🧠:** Oldingi aytganlaringizni eslab qolaman\n\n"
        "Savolingizni yoki ovozli xabaringizni bemalol yuboring!"
    )
    await message.answer(text, reply_markup=main_keyboard, parse_mode="Markdown")

@router.message(Command("help"))
@router.message(F.text == "💡 Yordam")
async def handle_help(message: Message):
    is_creator = (message.from_user.id == config.CREATOR_ID)
    admin_help = (
        "\n\n👑 **Xavfsizlik va Boshqaruv buyruqlari:**\n"
        "🔒 `/lock` - Botni qulflash (qayta kirishda kod so'raydi)\n"
        "🔑 `/setcode <kod>` - Maxfiy kirish kodini o'zgartirish\n"
        "/admin - Boshqaruv paneli va statistika\n"
        "/send <ID/@username> <matn> - Belgilangan odam yoki chatga xabar yuborish\n"
        "/broadcast <matn> - Barcha a'zolarga va guruhlarga e'lon tarqatish\n"
        "/chats - Bot ulangan barcha guruh va kanallar ro'yxati\n"
        "/post <kanal_id> <matn> - Kanalga post joylash"
    ) if is_creator else ""

    text = (
        "💡 **Botdan foydalanish bo'yicha qo'llanma:**\n\n"
        "1. **Matnli muloqot:** Istalgan savolingizni yozing.\n"
        "2. **Ovozli muloqot 🎙:** Ovozli xabar jo'nating, AI uni tinglab, sizga o'zbek tilida ovoz bilan javob qaytaradi.\n"
        "3. **Rasmlar:** Rasmni izohi bilan yuboring.\n"
        "4. **Yangi suhbat:** Tarixni tozalash uchun /reset buyrug'i yoki **💬 Yangi suhbat** tugmasidan foydalaning."
        f"{admin_help}"
    )
    await message.answer(text, parse_mode="Markdown")

@router.message(F.text == "🎙 Ovozli yordam")
async def handle_voice_help(message: Message):
    text = (
        "🎙 **Ovozli muloqot rejimi faol!**\n\n"
        "Menga Telegram orqali oddiy **ovozli xabar (Voice message)** yuboring.\n"
        "Google Gemini ovozingizni tinglab, nima deganingizni tushunadi va javobni ham **tabiiy o'zbekcha ovozda** qaytaradi!"
    )
    await message.answer(text, parse_mode="Markdown")

@router.message(Command("reset"))
@router.message(Command("clear"))
@router.message(F.text == "💬 Yangi suhbat")
async def handle_reset(message: Message):
    user_id = message.from_user.id
    gemini.reset_chat(user_id)
    await message.answer("🧹 **Suhbat xotirasi tozalandi!** Yangi mavzuni boshlashingiz mumkin.", parse_mode="Markdown")

@router.message(Command("about"))
@router.message(F.text == "ℹ️ Bot haqida")
async def handle_about(message: Message):
    stats = db.get_stats()
    text = (
        "ℹ️ **Bot haqida ma'lumot:**\n\n"
        f"🤖 **AI Modeli:** {gemini.model_name}\n"
        f"🎙 **Ovoz sintezi:** Microsoft Edge Neural TTS (O'zbekcha)\n"
        f"👑 **Yaratuvchi ID:** `{config.CREATOR_ID}`\n"
        f"👥 **Foydalanuvchilar:** {stats['total_users']}\n"
        f"📢 **Guruh va kanallar:** {stats['total_chats']}\n"
        "⚡ **Platforma:** aiogram 3 & Google GenAI"
    )
    await message.answer(text, parse_mode="Markdown")

# ----------------- SHAXSIY AI AGENT (USERBOT) BOSHQARUVI -----------------

@router.message(Command("agent"))
async def handle_agent_command(message: Message):
    """Shaxsiy Telegram AI Agentini boshqarish"""
    if message.from_user.id != config.CREATOR_ID:
        await message.reply("⛔ Kechirasiz, bu buyruq faqat bot egasi uchun!")
        return

    args = message.text.split(maxsplit=2)

    # 1. /agent on
    if len(args) > 1 and args[1].lower() == "on":
        db.set_agent_enabled(True)
        await message.reply("🟢 **AI Agent (Auto-Responder) yoqildi!**\nShaxsiy lichkangizga kelgan xabarlarga AI sizning nomingizdan javob qaytaradi.", parse_mode="Markdown")
        return

    # 2. /agent off
    if len(args) > 1 and args[1].lower() == "off":
        db.set_agent_enabled(False)
        await message.reply("🔴 **AI Agent o'chirildi!**\nShaxsiy xabarlarga avtomatik javob berilmaydi.", parse_mode="Markdown")
        return

    # 3. /agent mode as_me | assistant
    if len(args) > 1 and args[1].lower() == "mode":
        if len(args) < 3:
            current_mode = db.get_agent_mode()
            mode_desc = "👤 To'g'ridan-to'g'ri mening nomimdan (As Me)" if current_mode == "as_me" else "🤖 AI Kotib sifatida"
            await message.reply(f"🎭 **Hozirgi uslub:** {mode_desc}\n\nO'zgartirish uchun:\n`/agent mode as_me` (Mening nomimdan)\n`/agent mode assistant` (Kotib sifatida)", parse_mode="Markdown")
            return
        new_mode = args[2].lower()
        if new_mode in ["as_me", "me", "men"]:
            db.set_agent_mode("as_me")
            await message.reply("✅ **Javob berish uslubi: 👤 To'g'ridan-to'g'ri sizning nomingizdan!**\nAI birinchi shaxsda ('men') javob beradi va o'zini bot deb tanishtirmaydi.", parse_mode="Markdown")
        elif new_mode in ["assistant", "kotib", "bot"]:
            db.set_agent_mode("assistant")
            await message.reply("✅ **Javob berish uslubi: 🤖 AI Kotib sifatida!**\nAI sizning yordamchingiz sifatida javob beradi.", parse_mode="Markdown")
        else:
            await message.reply("Noto'g'ri uslub. Tanlang: `/agent mode as_me` yoki `/agent mode assistant`")
        return

    # 4. /agent myinfo <matn>
    if len(args) > 1 and args[1].lower() == "myinfo":
        if len(args) < 3:
            current_info = db.get_owner_info()
            await message.reply(f"ℹ️ **Siz haqingizdagi hozirgi ma'lumotlar:**\n\n_{current_info}_\n\nO'zgartirish uchun:\n`/agent myinfo <o'zingiz haqingizda ma'lumot>`", parse_mode="Markdown")
            return
        new_info = args[2].strip()
        db.set_owner_info(new_info)
        await message.reply("✅ **Shaxsiy ma'lumotlaringiz yangilandi!**\nAI sizning nomingizdan gapirganda ushbu ma'lumotlarga asoslanadi.", parse_mode="Markdown")
        return

    # 5. /agent prompt
    if len(args) > 1 and args[1].lower() == "prompt":
        if len(args) < 3:
            current_prompt = db.get_agent_prompt()
            await message.reply(f"📝 **Hozirgi AI Agent ko'rsatmasi (Prompt):**\n\n_{current_prompt}_\n\nO'zgartirish uchun: `/agent prompt <yangi ko'rsatma>`", parse_mode="Markdown")
            return
        new_prompt = args[2].strip()
        db.set_agent_prompt(new_prompt)
        await message.reply("✅ **AI Agent ko'rsatmasi yangilandi!**\nAI endi yangi ko'rsatma bo'yicha javob qaytaradi.", parse_mode="Markdown")
        return

    # 6. /agent ignore <user_id>
    if len(args) > 1 and args[1].lower() == "ignore":
        if len(args) < 3 or not args[2].isdigit():
            await message.reply("Format: `/agent ignore <user_id>`")
            return
        uid = int(args[2])
        db.add_to_blacklist(uid)
        await message.reply(f"🚫 `{uid}` ID li foydalanuvchi qora ro'yxatga olindi (AI unga javob bermaydi).", parse_mode="Markdown")
        return

    # 7. /agent unignore <user_id>
    if len(args) > 1 and args[1].lower() == "unignore":
        if len(args) < 3 or not args[2].isdigit():
            await message.reply("Format: `/agent unignore <user_id>`")
            return
        uid = int(args[2])
        db.remove_from_blacklist(uid)
        await message.reply(f"✅ `{uid}` qora ro'yxatdan chiqarildi.", parse_mode="Markdown")
        return

    # 8. /agent status va menyu
    await send_agent_dashboard(message)

def build_agent_dashboard():
    status = userbot.get_status()
    conn_text = "🟢 Ulangan (Faol)" if status["connected"] else ("⚠️ Sozlangan, lekin ulanmagan" if status["configured"] else "🔴 Ulanmagan (.env da sessiya yo'q)")
    agent_switch = "🟢 Yoqilgan" if status["agent_enabled"] else "🔴 O'chirilgan"
    mode_text = "👤 To'g'ridan-to'g'ri sizning nomingizdan" if db.get_agent_mode() == "as_me" else "🤖 AI Kotib sifatida"
    user_info = f"{status['user_name']} (@{status['username']})" if status['user_name'] else "Aniqlanmagan"

    text = (
        "🤖 **Telegram AI Agent (Shaxsiy Kotib) Paneli**\n\n"
        f"📱 **Shaxsiy akkaunt:** {user_info}\n"
        f"🔌 **Ulanish holati:** {conn_text}\n"
        f"⚡ **AI Avto-javob:** {agent_switch}\n"
        f"🎭 **Javob berish uslubi:** {mode_text}\n"
        f"💬 **Javob berilgan xabarlar:** {status['stats']['replied_count']} ta\n"
        f"🚫 **Qora ro'yxatdagi shaxslar:** {status['stats']['blacklist_count']} ta\n\n"
        "🛠 **Asosiy buyruqlar:**\n"
        "🔹 `/agent mode as_me` — To'g'ridan-to'g'ri mening nomimdan javob berish\n"
        "🔹 `/agent mode assistant` — AI kotib sifatida javob berish\n"
        "🔹 `/agent myinfo <matn>` — O'zingiz haqingizda ma'lumot kiritish\n"
        "🔹 `/agent prompt <matn>` — AI xarakterini sozlash\n"
        "🔹 `/reply <user_id> <matn>` — Shaxsiy nomingizdan xabar yozish\n"
        "🔹 *Yoki bot yuborgan xabarnomaga shunchaki Reply (Ответить) qiling!*"
    )

    mode_btn = "🔄 Uslub: Kotibga o'tish" if db.get_agent_mode() == "as_me" else "🔄 Uslub: Mening nomimga o'tish"
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🟢 Yoqish" if not status["agent_enabled"] else "🔴 O'chirish", callback_data="agent_toggle"),
            InlineKeyboardButton(text=mode_btn, callback_data="agent_toggle_mode")
        ],
        [
            InlineKeyboardButton(text="📝 Prompt", callback_data="agent_show_prompt"),
            InlineKeyboardButton(text="ℹ️ Ma'lumotim", callback_data="agent_show_myinfo")
        ],
        [
            InlineKeyboardButton(text="🔄 Yangilash", callback_data="agent_refresh")
        ]
    ])
    return text, kb

async def send_agent_dashboard(message: Message):
    text, kb = build_agent_dashboard()
    await message.answer(text, reply_markup=kb, parse_mode="Markdown")

@router.callback_query(F.data.startswith("agent_"))
async def handle_agent_callback(callback: CallbackQuery):
    if callback.from_user.id != config.CREATOR_ID:
        await callback.answer("Ruxsat berilmagan!", show_alert=True)
        return

    data = callback.data
    if data == "agent_toggle":
        new_state = not db.is_agent_enabled()
        db.set_agent_enabled(new_state)
        state_msg = "yoqildi" if new_state else "o'chirildi"
        await callback.answer(f"AI Agent {state_msg}!")
        text, kb = build_agent_dashboard()
        try:
            await callback.message.edit_text(text, reply_markup=kb, parse_mode="Markdown")
        except Exception:
            pass

    elif data == "agent_toggle_mode":
        current = db.get_agent_mode()
        new_mode = "assistant" if current == "as_me" else "as_me"
        db.set_agent_mode(new_mode)
        mode_desc = "Sizning nomingizdan" if new_mode == "as_me" else "AI Kotib sifatida"
        await callback.answer(f"Uslub o'zgardi: {mode_desc}!")
        text, kb = build_agent_dashboard()
        try:
            await callback.message.edit_text(text, reply_markup=kb, parse_mode="Markdown")
        except Exception:
            pass

    elif data == "agent_show_prompt":
        prompt = db.get_agent_prompt()
        await callback.message.answer(f"📝 **Hozirgi AI Agent ko'rsatmasi (Prompt):**\n\n_{prompt}_\n\nO'zgartirish uchun:\n`/agent prompt <yangi ko'rsatma>`", parse_mode="Markdown")
        await callback.answer()

    elif data == "agent_show_myinfo":
        info = db.get_owner_info()
        await callback.message.answer(f"ℹ️ **Siz haqingizdagi ma'lumotlar:**\n\n_{info}_\n\nO'zgartirish uchun:\n`/agent myinfo <o'zingiz haqingizda ma'lumot>`", parse_mode="Markdown")
        await callback.answer()

    elif data.startswith("agent_block_"):
        uid = int(data.split("_")[2])
        db.add_to_blacklist(uid)
        await callback.answer(f"Foydalanuvchi {uid} bloklandi!", show_alert=True)
        try:
            await callback.message.edit_reply_markup(reply_markup=None)
        except Exception:
            pass

    elif data == "agent_refresh":
        await callback.answer("Yangilandi!")
        text, kb = build_agent_dashboard()
        try:
            await callback.message.edit_text(text, reply_markup=kb, parse_mode="Markdown")
        except Exception:
            pass

@router.message(F.reply_to_message)
async def handle_reply_to_notification(message: Message):
    """Egasining bot xabarnomalariga Reply (Ответить) qilib yozgan javobini shaxsiy akkauntdan yuborish"""
    if message.from_user.id != config.CREATOR_ID:
        return

    replied_msg = message.reply_to_message
    target_sender_id = userbot.get_sender_for_notification(replied_msg.message_id)
    if target_sender_id:
        reply_text = message.text.strip() if message.text else ""
        if not reply_text:
            await message.reply("❗ Iltimos, jo'natish uchun matnli xabar yozing.")
            return

        success = await userbot.send_direct_message(target_sender_id, reply_text)
        if success:
            await message.reply(
                f"✅ **Sizning shaxsiy Telegramingiz nomidan jo'natildi!**\n"
                f"👤 Qabul qiluvchi ID: `{target_sender_id}`\n"
                f"💬 Matn: _{reply_text}_",
                parse_mode="Markdown"
            )
        else:
            await message.reply("❌ Xabar jo'natishda xatolik yuz berdi. Userbot faol ekanligini tekshiring.")
        return

@router.message(Command("reply"))
async def handle_direct_reply(message: Message):
    """Shaxsiy Telegram akkaunti nomidan belgilangan chat/shaxsga xabar yuborish"""
    if message.from_user.id != config.CREATOR_ID:
        return

    args = message.text.split(maxsplit=2)
    if len(args) < 3:
        await message.reply("❗ Format: `/reply <user_id yoki @username> <xabar matni>`\nMisol: `/reply 1234567 Salom, yaxshimisiz?`", parse_mode="Markdown")
        return

    target = args[1].strip()
    reply_text = args[2].strip()
    target_id = int(target) if (target.isdigit() or target.startswith("-")) else target

    success = await userbot.send_direct_message(target_id, reply_text)
    if success:
        await message.reply(f"✅ Shaxsiy Telegram akkauntingiz nomidan `{target}` ga xabar yuborildi!", parse_mode="Markdown")
    else:
        await message.reply(f"❌ Xabar yuborishda xatolik. Shaxsiy akkaunt (Userbot) ulanganini tekshiring: /agent")

# ----------------- YARATUVCHI (CREATOR / ADMIN) PANEL -----------------

@router.message(Command("admin"))
async def handle_admin(message: Message):
    if message.from_user.id != config.CREATOR_ID:
        await message.reply("⛔ Kechirasiz, bu buyruq faqat bot yaratuvchisi uchun!")
        return

    stats = db.get_stats()
    text = (
        "👑 **Yaratuvchi Boshqaruv Paneli**\n\n"
        f"👤 **Yaratuvchi ID:** `{config.CREATOR_ID}`\n"
        f"👥 **Jami foydalanuvchilar:** {stats['total_users']}\n"
        f"👥 **Guruhlar:** {stats['total_groups']}\n"
        f"📢 **Kanallar:** {stats['total_channels']}\n\n"
        "🛠 **Boshqaruv buyruqlari:**\n"
        "🤖 `/agent` — Shaxsiy AI Agent (Kotib) boshqaruv paneli\n"
        "💬 `/reply <ID/@username> <matn>` — Shaxsiy akkauntingiz nomidan xabar yozish\n"
        "🔹 `/send <ID/@username> <matn>` — Belgilangan odamga/guruhga bot nomidan xabar yuborish\n"
        "🔹 `/broadcast <matn>` — Barcha bot foydalanuvchilari va guruhlariga e'lon yuborish\n"
        "🔹 `/chats` — Bot a'zo bo'lgan barcha guruh va kanallar ro'yxati\n"
        "🔹 `/post <chat_id> <matn>` — Belgilangan kanalga post joylash\n"
        "🔹 `/pin` — Guruhda reply qilingan xabarni qadab qo'yish\n"
    )
    await message.answer(text, parse_mode="Markdown")

@router.message(Command("send"))
async def handle_send_message(message: Message, bot: Bot):
    """Yaratuvchi xohlagan shaxsga yoki chatga bot orqali xabar yuborishi"""
    if message.from_user.id != config.CREATOR_ID:
        return

    args = message.text.split(maxsplit=2)
    if len(args) < 3:
        await message.reply("❗ Format noto'g'ri.\nFoydalanish: `/send <ID yoki @username> <xabar matni>`\nMisol: `/send 1234567 Salom!`", parse_mode="Markdown")
        return

    target = args[1].strip()
    msg_text = args[2].strip()

    try:
        # ID raqam yoki username bo'lishi mumkin
        chat_target = int(target) if (target.isdigit() or target.startswith("-")) else target
        await bot.send_message(chat_id=chat_target, text=msg_text)
        await message.reply(f"✅ Xabar muvaffaqiyatli yuborildi: `{target}`", parse_mode="Markdown")
    except Exception as e:
        await message.reply(f"❌ Xatolik yuz berdi: {e}")

@router.message(Command("broadcast"))
async def handle_broadcast(message: Message, bot: Bot):
    """Barcha a'zolarga va guruhlarga e'lon tarqatish"""
    if message.from_user.id != config.CREATOR_ID:
        return

    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        await message.reply("❗ Format: `/broadcast <xabar matni>`", parse_mode="Markdown")
        return

    broadcast_text = args[1].strip()
    users = db.get_users()
    chats = db.get_chats()

    sent_count = 0
    fail_count = 0

    status_msg = await message.reply("⏳ Xabar tarqatilmoqda...")

    # Shaxsiy foydalanuvchilarga yuborish
    for uid in users.keys():
        try:
            await bot.send_message(chat_id=int(uid), text=broadcast_text)
            sent_count += 1
        except Exception:
            fail_count += 1

    # Guruh va kanallarga yuborish
    for cid in chats.keys():
        try:
            await bot.send_message(chat_id=int(cid), text=broadcast_text)
            sent_count += 1
        except Exception:
            fail_count += 1

    await status_msg.edit_text(
        f"📢 **E'lon yakunlandi!**\n\n"
        f"✅ Yuborildi: {sent_count}\n"
        f"❌ Yetib bormadi (bloklangan/o'chirilgan): {fail_count}",
        parse_mode="Markdown"
    )

@router.message(Command("chats"))
@router.message(Command("channels"))
async def handle_list_chats(message: Message):
    """Ulangan guruh va kanallar ro'yxati"""
    if message.from_user.id != config.CREATOR_ID:
        return

    chats = db.get_chats()
    if not chats:
        await message.reply("Hozircha bot hech qanday guruh yoki kanalga qo'shilmagan.\nBotni guruh yoki kanalingizga admin qilib qo'shing!")
        return

    lines = ["📋 **Bot a'zo bo'lgan guruh va kanallar:**\n"]
    for cid, info in chats.items():
        title = info.get("title", "Nomsiz")
        ctype = info.get("type", "chat")
        uname = f"(@{info['username']})" if info.get("username") else ""
        lines.append(f"• **{title}** {uname}\n  ID: `{cid}` | Turi: {ctype}")

    await message.reply("\n".join(lines), parse_mode="Markdown")

@router.message(Command("post"))
async def handle_post_to_channel(message: Message, bot: Bot):
    """Kanalga post joylash"""
    if message.from_user.id != config.CREATOR_ID:
        return

    args = message.text.split(maxsplit=2)
    if len(args) < 3:
        await message.reply("❗ Format: `/post <kanal_id yoki @username> <matn>`\nMisol: `/post -100123456789 Yangi post matni`", parse_mode="Markdown")
        return

    target = args[1].strip()
    content = args[2].strip()

    try:
        chat_target = int(target) if (target.isdigit() or target.startswith("-")) else target
        await bot.send_message(chat_id=chat_target, text=content, parse_mode="Markdown")
        await message.reply(f"✅ Kanalga post joylandi: `{target}`", parse_mode="Markdown")
    except Exception as e:
        await message.reply(f"❌ Kanalga post joylashda xatolik: {e}\n(Bot kanalga admin qilib qo'shilganini tekshiring)")

@router.message(Command("pin"))
async def handle_pin_message(message: Message, bot: Bot):
    """Guruhda xabarni qadash"""
    if message.from_user.id != config.CREATOR_ID:
        return

    if not message.reply_to_message:
        await message.reply("❗ Xabarni qadash uchun o'sha xabarga reply qilib /pin deb yozing.")
        return

    try:
        await bot.pin_chat_message(chat_id=message.chat.id, message_id=message.reply_to_message.message_id)
        await message.reply("📌 Xabar qadab qo'yildi!")
    except Exception as e:
        await message.reply(f"❌ Xatolik: {e}")

# ----------------- OVOZLI XABARLAR (VOICE & AUDIO) -----------------

@router.message(F.voice | F.audio)
async def handle_voice(message: Message):
    """Foydalanuvchi yuborgan ovozli xabarni qabul qilish va ovoz bilan javob qaytarish"""
    user_id = message.from_user.id
    db.register_user(user_id, message.from_user.full_name, message.from_user.username)

    # Foydalanuvchiga ovoz yozilayotganini bildirish
    await message.bot.send_chat_action(chat_id=message.chat.id, action=ChatAction.RECORD_VOICE)

    # Ovoz faylini xotiraga yuklab olish
    voice_obj = message.voice if message.voice else message.audio
    file_io = io.BytesIO()
    await message.bot.download(voice_obj, destination=file_io)
    audio_bytes = file_io.getvalue()

    mime_type = "audio/ogg" if message.voice else "audio/mp3"

    # 1. Gemini AI orqali ovozni eshitib javob olish
    ai_reply = await gemini.process_audio(user_id=user_id, audio_bytes=audio_bytes, mime_type=mime_type)

    # 2. AI javobini ovozga (TTS) aylantirish
    try:
        voice_bytes = await synthesize_voice(ai_reply)
        voice_file = BufferedInputFile(voice_bytes, filename="reply.ogg")
        
        # Ovozli xabar va matnli nusxasini jo'natamiz
        caption = ai_reply if len(ai_reply) <= 1000 else ai_reply[:1000] + "..."
        await message.reply_voice(voice=voice_file, caption=caption)
    except Exception as e:
        logger.error(f"Ovoz jo'natishda xatolik: {e}")
        # Agar TTS xato bersa, matnli javob qaytaramiz
        await safe_reply(message, f"🗣 {ai_reply}")

# ----------------- RASMLAR (PHOTOS) -----------------

@router.message(F.photo)
async def handle_photo(message: Message):
    """Foydalanuvchi yuborgan rasmni qabul qilish va tahlil qilish"""
    user_id = message.from_user.id
    db.register_user(user_id, message.from_user.full_name, message.from_user.username)

    photo = message.photo[-1]
    caption = message.caption

    await message.bot.send_chat_action(chat_id=message.chat.id, action=ChatAction.TYPING)

    file_io = io.BytesIO()
    await message.bot.download(photo, destination=file_io)
    image_bytes = file_io.getvalue()

    response_text = await gemini.analyze_image(user_id=user_id, image_bytes=image_bytes, caption=caption)
    await safe_reply(message, response_text)

# ----------------- MATNLI XABARLAR (TEXT) -----------------

@router.message(F.text)
async def handle_text(message: Message):
    """Foydalanuvchi matnli xabarlarini qayta ishlash"""
    user_id = message.from_user.id
    user_text = message.text.strip()

    # Chat turini ro'yxatga olish (guruh/kanal bo'lsa)
    if message.chat.type != "private":
        db.register_chat(
            chat_id=message.chat.id,
            title=message.chat.title or "Nomsiz guruh",
            chat_type=message.chat.type,
            username=message.chat.username
        )

    db.register_user(user_id, message.from_user.full_name, message.from_user.username)

    if user_text.startswith("/"):
        await message.reply("Noma'lum buyruq. Yordam uchun /help deb yozing.")
        return

    await message.bot.send_chat_action(chat_id=message.chat.id, action=ChatAction.TYPING)

    ai_reply = await gemini.generate_response(user_id=user_id, user_message=user_text)
    await safe_reply(message, ai_reply)
