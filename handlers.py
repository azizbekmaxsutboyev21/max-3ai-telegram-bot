import io
import logging
from aiogram import Router, F, Bot
from aiogram.filters import CommandStart, Command
from aiogram.types import (
    Message,
    ReplyKeyboardMarkup,
    KeyboardButton,
    BufferedInputFile,
    ChatMemberUpdated
)
from aiogram.enums import ChatAction, ChatMemberStatus
import config
from gemini_service import GeminiService
from tts_service import synthesize_voice
from db_manager import db

logger = logging.getLogger(__name__)

router = Router()
gemini = GeminiService()

# Asosiy tugmalar (Reply Keyboard)
main_keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="💬 Yangi suhbat"), KeyboardButton(text="🎙 Ovozli yordam")],
        [KeyboardButton(text="ℹ️ Bot haqida"), KeyboardButton(text="💡 Yordam")]
    ],
    resize_keyboard=True
)

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
        "Men **Google Gemini 3.8 Flash AI** texnologiyasiga asoslangan aqlli Telegram botman.\n"
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
        "\n\n👑 **Yaratuvchi (Admin) buyruqlari:**\n"
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
