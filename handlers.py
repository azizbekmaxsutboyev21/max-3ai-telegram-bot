import io
import logging
from typing import Dict, Any, List, Optional
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

# Asosiy klaviatura tugmalari
main_keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="💬 Yangi suhbat"), KeyboardButton(text="🎙 Ovozli yordam")],
        [KeyboardButton(text="👑 Admin Panel"), KeyboardButton(text="🤖 AI Kotib (Userbot)")],
        [KeyboardButton(text="🧠 Menga moslashish"), KeyboardButton(text="🚫 Qora ro'yxat")],
        [KeyboardButton(text="🔒 Qulflash"), KeyboardButton(text="🔑 Kodni o'zgartirish")]
    ],
    resize_keyboard=True
)

class PrivateAuthMiddleware(BaseMiddleware):
    """
    Xavfsizlik Middleware-si:
    - Guruhlar va kanallardagi xabarlarni to'sib qo'ymaydi (u yerda bot erkin ishlaydi).
    - Shaxsiy (Private) chatda esa har qanday akkaunt o'rnatilgan maxfiy kodni kiritib
      o'zini tasdiqlashi (admin bo'lishi) mumkin!
    """
    async def __call__(self, handler, event, data):
        # Guruh yoki kanal bo'lsa - autentifikatsiya talab qilinmaydi
        chat = getattr(event, "chat", None)
        if chat and chat.type != "private":
            return await handler(event, data)

        user = getattr(event, "from_user", None)
        if not user:
            return await handler(event, data)

        # Agar foydalanuvchi allaqachon tasdiqlangan bo'lsa
        if db.is_authenticated(user.id):
            return await handler(event, data)

        # Tasdiqlanmagan foydalanuvchi shaxsiy chatda kod kiritishi kerak
        if isinstance(event, Message) and event.text:
            text = event.text.strip()
            current_code = db.get_access_code()

            # Kod to'g'ri kiritilsa
            if text == current_code:
                db.set_authenticated(user.id, True)
                await event.answer(
                    "🔓 **Muvaffaqiyatli tasdiqlandi!** Xush kelibsiz.\n\n"
                    "Siz botning to'liq boshqaruviga ega bo'ldingiz. Barcha funksiyalar va Admin panel ochildi!",
                    reply_markup=main_keyboard,
                    parse_mode="Markdown"
                )
                return
            elif text.startswith("/start"):
                await event.answer(
                    "🔐 **Xavfsizlik tekshiruvi (Bot qulflangan):**\n\n"
                    "Ushbu bot shaxsiy bot hisoblanadi. Undan to'liq foydalanish va akkauntni boshqarish uchun "
                    "iltimos, o'zingiz o'rnatgan **maxfiy kirish kodingizni** yuboring:",
                    parse_mode="Markdown"
                )
                return
            else:
                await event.answer(
                    "❌ **Noto'g'ri kod kiritildi!**\n\n"
                    "Iltimos, to'g'ri maxfiy kirish kodini kiriting:",
                    parse_mode="Markdown"
                )
                return

        # Qulflangan paytda matnsiz xabarlar yuborilsa
        if isinstance(event, Message):
            await event.answer(
                "🔐 **Bot qulflangan!**\n\n"
                "Iltimos, avval maxfiy kirish kodingizni matn ko'rinishida yuboring.",
                parse_mode="Markdown"
            )
        elif isinstance(event, CallbackQuery):
            await event.answer("🔐 Avval maxfiy kodni kiriting!", show_alert=True)
        return

router.message.middleware(PrivateAuthMiddleware())
router.callback_query.middleware(PrivateAuthMiddleware())

def split_message(text: str, max_length: int = 4000) -> list[str]:
    """Telegram xabar cheklovi uchun matnni bo'laklarga ajratish"""
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
    """Xabarni xavfsiz jo'natish"""
    parts = split_message(text)
    for part in parts:
        try:
            await message.reply(part, parse_mode="Markdown")
        except Exception:
            await message.reply(part, parse_mode=None)

# ----------------- GURUH VA KANAL KUZATUVI -----------------

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

# ----------------- ASOSIY BUYRUQLAR -----------------

@router.message(CommandStart())
async def handle_start(message: Message):
    user = message.from_user
    db.register_user(user.id, user.full_name, user.username)

    text = (
        f"Assalomu alaykum, {user.first_name}! 👋\n\n"
        "Men **Google Gemini AI** texnologiyasiga asoslangan kuchli Telegram Bot va Shaxsiy AI Yordamchingizman.\n\n"
        "✨ **Imkoniyatlarim:**\n"
        "🔹 **Matnli va Ovozli muloqot:** Ovozli xabar jo'nating, ovoz bilan javob qaytaraman.\n"
        "🔹 **Rasm tahlili:** Rasmni ko'rib, savollarga javob beraman.\n"
        "🔹 **Guruhlarda ishlash:** Guruhga qo'shib, `@bot` deb yozsangiz javob beraman.\n"
        "🔹 **Shaxsiy Telegram nazorati (Userbot):** Lichkaga kelgan xabarlarga aqlli avto-javob, kanallarni o'qish va tahlil qilish.\n"
        "🔹 **Menga moslashish:** Sizning fe'l-atvoringiz va uslubingizga to'liq moslashish."
    )
    await message.answer(text, reply_markup=main_keyboard, parse_mode="Markdown")

@router.message(Command("help"))
@router.message(F.text == "💡 Yordam")
async def handle_help(message: Message):
    text = (
        "💡 **Buyruqlar va qo'llanma:**\n\n"
        "👑 **Boshqaruv:**\n"
        "• `/admin` — To'liq interaktiv boshqaruv paneli\n"
        "• `/agent` — Shaxsiy AI Kotib (Userbot) paneli\n"
        "• `/lock` — Botni qulflash\n"
        "• `/setcode <kod>` — Yangi maxfiy kod o'rnatish\n\n"
        "🧠 **Moslashish va Persona:**\n"
        "• `/adapt <matn>` — AI ga sizning shaxsiyatingiz va uslubingizga moslashish buyrug'i\n"
        "• `/persona` — Hozirgi shaxsiyat sozlamalarini ko'rish\n\n"
        "🚫 **Qora ro'yxat (Bloklash):**\n"
        "• `/blacklist` — Bloklangan shaxslar ro'yxati\n"
        "• `/block <id>` — Foydalanuvchini bloklash\n"
        "• `/unblock <id>` — Blokdan chiqarish\n\n"
        "📱 **Akkaunt nazorati (Userbot):**\n"
        "• `/mychats` — Guruhlar va kanallar ro'yxati\n"
        "• `/read <chat_id> [soni]` — Xabarlarni o'qish va AI konspektini olish\n"
        "• `/botcall <@bot> <buyruq>` — Boshqa botlarga buyruq jo'natish\n"
        "• `/reply <id> <matn>` — O'z nomingizdan xabar yozish\n\n"
        "👥 **Guruhlar:**\n"
        "• `/ai <savol>` — Guruhda sun'iy intellektdan javob olish"
    )
    await message.answer(text, parse_mode="Markdown")

@router.message(Command("reset"))
@router.message(Command("clear"))
@router.message(F.text == "💬 Yangi suhbat")
async def handle_reset(message: Message):
    gemini.reset_chat(message.chat.id)
    await message.answer("🧹 **Suhbat xotirasi tozalandi!** Yangi mavzuni boshlashingiz mumkin.", parse_mode="Markdown")

@router.message(F.text == "🎙 Ovozli yordam")
async def handle_voice_help(message: Message):
    text = (
        "🎙 **Ovozli muloqot rejimi faol!**\n\n"
        "Menga shunchaki oddiy **ovozli xabar (Voice message)** yuboring. "
        "Google Gemini uni eshitadi va javobni ham o'zbek tilida **tabiiy ovozda** qaytaradi!"
    )
    await message.answer(text, parse_mode="Markdown")

# ----------------- XAVFSIZLIK VA KOD BOSHQARUVI -----------------

@router.message(Command("lock"))
@router.message(F.text == "🔒 Qulflash")
async def handle_lock(message: Message):
    db.set_authenticated(message.from_user.id, False)
    await message.answer(
        "🔒 **Bot qulflandi!**\n\n"
        "Qayta kirish uchun maxfiy kodingizni yuboring:",
        reply_markup=ReplyKeyboardRemove(),
        parse_mode="Markdown"
    )

@router.message(Command("setcode"))
@router.message(Command("setpass"))
async def handle_setcode(message: Message):
    parts = message.text.split(maxsplit=1)
    if len(parts) == 2 and parts[1].strip():
        new_code = parts[1].strip()
        db.set_access_code(new_code)
        await message.answer(
            f"✅ **Yangi kirish kodi muvaffaqiyatli o'rnatildi:** `{new_code}`\n\n"
            "Uni eslab qoling! Botni qulflash uchun: `/lock`",
            parse_mode="Markdown"
        )
    else:
        await message.answer("Format: `/setcode <yangi_kod>`\nMisol: `/setcode 7788`", parse_mode="Markdown")

@router.message(F.text == "🔑 Kodni o'zgartirish")
async def handle_change_code_btn(message: Message):
    await message.answer("🔑 Yangi kod o'rnatish uchun quyidagicha yuboring:\n`/setcode <yangi_kod>`\n\nMisol: `/setcode 9988`", parse_mode="Markdown")

# ----------------- MENGA MOSLASHISH (PERSONA & ADAPTATION) -----------------

@router.message(Command("adapt"))
async def handle_adapt_command(message: Message):
    """Botni egasiga moslashtirish buyrug'i"""
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        persona = db.get_persona()
        text = (
            "🧠 **Menga moslashish (Shaxsiyat va Uslub):**\n\n"
            f"👤 **Ism:** {persona.get('owner_name')}\n"
            f"ℹ️ **Siz haqingizda:** {persona.get('about_me')}\n"
            f"🎭 **Muloqot uslubi:** {persona.get('communication_style')}\n"
            f"📜 **Qoidalar:** {persona.get('custom_rules')}\n\n"
            "💡 **Moslashtirish uchun yozing:**\n"
            "`/adapt Men dasturchiman, rasmiy emas do'stona va qisqa gapir`"
        )
        await message.answer(text, parse_mode="Markdown")
        return

    adaptation_text = parts[1].strip()
    db.set_full_adaptation(about=adaptation_text, rules="Suhbatdosh bilan har bir xabarda qayta salomlashmang!")
    await message.answer(
        "✅ **Muvaffaqiyatli saqlandi!**\n\n"
        "AI endi sizning yangi shaxsiyatingiz va ko'rsatmalaringizga to'liq moslashgan holda muloqot qiladi.",
        parse_mode="Markdown"
    )

@router.message(Command("persona"))
@router.message(F.text == "🧠 Menga moslashish")
async def handle_persona_btn(message: Message):
    persona = db.get_persona()
    text = (
        "🧠 **AI Shaxsiyati va Sizga moslashuv holati:**\n\n"
        f"👤 **Egasi ismi:** {persona.get('owner_name')}\n"
        f"ℹ️ **Siz haqingizda ma'lumot:**\n_{persona.get('about_me')}_\n\n"
        f"🎭 **Muloqot uslubi:**\n_{persona.get('communication_style')}_\n\n"
        f"📜 **Maxsus qoidalar:**\n_{persona.get('custom_rules')}_\n\n"
        "Yangilash uchun: `/adapt <o'zingiz haqingizda va muloqot uslubingiz haqida matn>`"
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✏️ Ismni o'zgartirish", callback_data="persona_name")],
        [InlineKeyboardButton(text="🔙 Admin Panel", callback_data="admin_main")]
    ])
    await message.answer(text, reply_markup=kb, parse_mode="Markdown")

# ----------------- QORA RO'YXAT (BLACKLIST) BOSHQARUVI -----------------

@router.message(Command("blacklist"))
@router.message(Command("blocked"))
@router.message(F.text == "🚫 Qora ro'yxat")
async def handle_blacklist_view(message: Message):
    blocked_list = db.get_blacklist_detailed()
    if not blocked_list:
        text = "🚫 **Qora ro'yxat bo'sh.** Hozircha hech kim bloklanmagan.\n\nFoydalanuvchini bloklash uchun: `/block <user_id>`"
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔙 Admin Panel", callback_data="admin_main")]
        ])
        await message.answer(text, reply_markup=kb, parse_mode="Markdown")
        return

    text = f"🚫 **Qora ro'yxatdagi foydalanuvchilar ({len(blocked_list)} ta):**\n\n"
    keyboard_rows = []
    for item in blocked_list[:15]:
        uid = item["id"]
        name = item["name"]
        uname = f"(@{item['username']})" if item.get("username") else ""
        date = f"[{item.get('date')}]" if item.get("date") else ""
        text += f"• **{name}** {uname} — ID: `{uid}` {date}\n"
        keyboard_rows.append([
            InlineKeyboardButton(text=f"🗑 Chiqarish: {name[:12]} ({uid})", callback_data=f"agent_unblock_{uid}")
        ])

    keyboard_rows.append([InlineKeyboardButton(text="🔙 Admin Panel", callback_data="admin_main")])
    kb = InlineKeyboardMarkup(inline_keyboard=keyboard_rows)
    await message.answer(text, reply_markup=kb, parse_mode="Markdown")

@router.message(Command("block"))
async def handle_block_user(message: Message):
    parts = message.text.split(maxsplit=2)
    if len(parts) < 2 or not parts[1].lstrip("-").isdigit():
        await message.reply("Format: `/block <user_id> [izoh]`\nMisol: `/block 1234567 Reklamachi`", parse_mode="Markdown")
        return
    uid = int(parts[1])
    note = parts[2].strip() if len(parts) > 2 else "Qo'lda bloklangan"
    db.add_to_blacklist(uid, name=note)
    await message.reply(f"🚫 `{uid}` ID li foydalanuvchi qora ro'yxatga kiritildi. AI unga javob bermaydi.", parse_mode="Markdown")

@router.message(Command("unblock"))
async def handle_unblock_user(message: Message):
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2 or not parts[1].lstrip("-").isdigit():
        await message.reply("Format: `/unblock <user_id>`", parse_mode="Markdown")
        return
    uid = int(parts[1])
    removed = db.remove_from_blacklist(uid)
    if removed:
        await message.reply(f"✅ `{uid}` qora ro'yxatdan chiqarildi.", parse_mode="Markdown")
    else:
        await message.reply(f"`{uid}` qora ro'yxatda topilmadi.", parse_mode="Markdown")

# ----------------- KENGAYTIRILGAN ADMIN PANEL -----------------

def build_admin_main_kb():
    status = userbot.get_status()
    agent_status_emoji = "🟢" if status["agent_enabled"] else "🔴"
    smart_filter_emoji = "🛡" if status["stats"]["smart_filter"] else "⚪️"

    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text=f"🤖 AI Kotib: {agent_status_emoji}", callback_data="admin_agent_menu"),
            InlineKeyboardButton(text=f"Aqlli filtr: {smart_filter_emoji}", callback_data="admin_toggle_filter")
        ],
        [
            InlineKeyboardButton(text="🧠 Menga moslashish", callback_data="admin_persona"),
            InlineKeyboardButton(text="🚫 Qora ro'yxat", callback_data="admin_blacklist")
        ],
        [
            InlineKeyboardButton(text="📱 Chatlarim (Userbot)", callback_data="admin_mychats"),
            InlineKeyboardButton(text="🤖 Boshqa botlar", callback_data="admin_botcall_help")
        ],
        [
            InlineKeyboardButton(text="✉️ Chatlarga xabar yozish", callback_data="admin_sendmsg_help"),
            InlineKeyboardButton(text="📢 E'lon tarqatish", callback_data="admin_broadcast_help")
        ],
        [
            InlineKeyboardButton(text="📊 To'liq statistika", callback_data="admin_stats"),
            InlineKeyboardButton(text="🔄 Yangilash", callback_data="admin_main")
        ]
    ])

@router.message(Command("admin"))
@router.message(F.text == "👑 Admin Panel")
async def handle_admin(message: Message):
    stats = db.get_stats()
    status = userbot.get_status()
    ub_conn = "🟢 Faol" if status.get("connected") else "🔴 Ulanmagan"
    agent_enabled_label = "🟢 Yoqilgan" if status.get("agent_enabled") else "🔴 O'chirilgan"
    mode_label = "👤 Sizning nomingizdan" if db.get_agent_mode() == "as_me" else "🤖 AI Kotib"

    text = (
        "👑 **Boshqaruv Paneli**\n\n"
        f"📱 **Telegram Userbot:** {ub_conn}\n"
        f"🤖 **AI Kotib (Auto-reply):** {agent_enabled_label}\n"
        f"🎭 **Uslub:** {mode_label}\n"
        f"👥 **Bot foydalanuvchilari:** {stats['total_users']} ta\n"
        f"📢 **Guruh va kanallar:** {stats['total_chats']} ta\n"
        f"🚫 **Bloklanganlar:** {len(db.get_agent_blacklist())} ta\n\n"
        "Quyidagi tugmalar orqali kerakli bo'limni tanlang:"
    )
    await message.answer(text, reply_markup=build_admin_main_kb(), parse_mode="Markdown")

@router.callback_query(F.data.startswith("admin_"))
async def handle_admin_callbacks(callback: CallbackQuery):
    data = callback.data
    
    if data == "admin_main":
        stats = db.get_stats()
        status = userbot.get_status()
        ub_conn = "🟢 Faol" if status.get("connected") else "🔴 Ulanmagan"
        agent_enabled_label = "🟢 Yoqilgan" if status.get("agent_enabled") else "🔴 O'chirilgan"
        mode_label = "👤 Sizning nomingizdan" if db.get_agent_mode() == "as_me" else "🤖 AI Kotib"
        text = (
            "👑 **Boshqaruv Paneli**\n\n"
            f"📱 **Telegram Userbot:** {ub_conn}\n"
            f"🤖 **AI Kotib (Auto-reply):** {agent_enabled_label}\n"
            f"🎭 **Uslub:** {mode_label}\n"
            f"👥 **Bot foydalanuvchilari:** {stats['total_users']} ta\n"
            f"📢 **Guruh va kanallar:** {stats['total_chats']} ta\n"
            f"🚫 **Bloklanganlar:** {len(db.get_agent_blacklist())} ta"
        )
        await callback.message.edit_text(text, reply_markup=build_admin_main_kb(), parse_mode="Markdown")
        await callback.answer()

    elif data == "admin_toggle_filter":
        new_state = not db.is_smart_filter_enabled()
        db.set_smart_filter(new_state)
        await callback.answer(f"Aqlli filtr: {'Yoqildi' if new_state else 'O‘chirildi'}")
        await callback.message.edit_reply_markup(reply_markup=build_admin_main_kb())

    elif data == "admin_agent_menu":
        text, kb = build_agent_dashboard()
        await callback.message.edit_text(text, reply_markup=kb, parse_mode="Markdown")
        await callback.answer()

    elif data == "admin_persona":
        persona = db.get_persona()
        text = (
            "🧠 **AI Shaxsiyati va Moslashuvi:**\n\n"
            f"👤 **Egasi:** {persona.get('owner_name')}\n"
            f"ℹ️ **Ma'lumot:** {persona.get('about_me')}\n"
            f"🎭 **Uslub:** {persona.get('communication_style')}\n\n"
            "O'zgartirish uchun: `/adapt <matn>`"
        )
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔙 Asosiy Menyu", callback_data="admin_main")]
        ])
        await callback.message.edit_text(text, reply_markup=kb, parse_mode="Markdown")
        await callback.answer()

    elif data == "admin_blacklist":
        blocked_list = db.get_blacklist_detailed()
        rows = []
        if not blocked_list:
            text = "🚫 **Qora ro'yxat bo'sh.**\n\nFoydalanuvchini qo'shish: `/block <user_id>`"
        else:
            text = f"🚫 **Qora ro'yxatdagi foydalanuvchilar ({len(blocked_list)} ta):**\n\n"
            for item in blocked_list[:10]:
                uid = item["id"]
                name = item["name"]
                text += f"• **{name}** (`{uid}`)\n"
                rows.append([InlineKeyboardButton(text=f"🗑 Chiqarish: {name[:12]} ({uid})", callback_data=f"agent_unblock_{uid}")])
        rows.append([InlineKeyboardButton(text="🔙 Asosiy Menyu", callback_data="admin_main")])
        await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=rows), parse_mode="Markdown")
        await callback.answer()

    elif data == "admin_mychats":
        await callback.answer("Yuklanmoqda...")
        dialogs = await userbot.get_dialogs_list(limit=15)
        if not dialogs:
            text = "Chatlar ro'yxatini olib bo'lmadi. Userbot ulanganligini tekshiring."
        else:
            text = "📋 **Siz a'zo bo'lgan chatlar (Userbot):**\n\n"
            for d in dialogs:
                icon = "📢" if d["type"] == "channel" else ("👥" if d["type"] == "group" else ("🤖" if d["type"] == "bot" else "👤"))
                uname = f"(@{d['username']})" if d.get("username") else ""
                text += f"{icon} **{d['title']}** {uname}\n  ID: `{d['id']}`\n"
            text += "\nXabarlarni o'qish uchun: `/read <id yoki @username>`"
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔙 Asosiy Menyu", callback_data="admin_main")]
        ])
        await callback.message.edit_text(text, reply_markup=kb, parse_mode="Markdown")

    elif data == "admin_botcall_help":
        text = (
            "🤖 **Boshqa botlardan foydalanish (Userbot orqali):**\n\n"
            "Siz o'z shaxsiy akkauntingiz nomidan istalgan Telegram botiga buyruq yuborishingiz va uning javobini shu botda ko'rishingiz mumkin!\n\n"
            "Format: `/botcall <@bot_username> <buyruq>`\n"
            "Misol: `/botcall @vkmusic_bot /start` yoki `/botcall @ChatGPT_bot Salom`"
        )
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔙 Asosiy Menyu", callback_data="admin_main")]
        ])
        await callback.message.edit_text(text, reply_markup=kb, parse_mode="Markdown")
        await callback.answer()

    elif data == "admin_broadcast_help":
        text = (
            "📢 **E'lon tarqatish (Broadcast):**\n\n"
            "Bot barcha a'zolari va ulangan guruhlariga e'lon yuborish uchun quyidagi buyruqdan foydalaning:\n\n"
            "`/broadcast <xabar matni>`"
        )
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔙 Asosiy Menyu", callback_data="admin_main")]
        ])
        await callback.message.edit_text(text, reply_markup=kb, parse_mode="Markdown")
        await callback.answer()

    elif data == "admin_sendmsg_help":
        text = (
            "✉️ **Chatlarga xabar yozish va Telegram Premium imkoniyatlari:**\n\n"
            "Siz botga shunchaki tabiiy tilda aytishingiz mumkin:\n"
            "• *\"Aliga 'Bugun 17:00 da uchrashamiz' deb yoz\"*\n"
            "• *\"Daryo kanaliga yangi post chiqar: ...\"*\n"
            "• *\"Guruhga xabar tashla: Ertaga majlis bo'ladi\"*\n\n"
            "Yoki to'g'ridan-to'g'ri maxsus buyruqlardan foydalaning:\n"
            "• `/sendmsg <chat, @username yoki ism> <matn>` — bitta chatga xabar yozish\n"
            "• `/multisend <chat1,chat2,...> <matn>` — bir vaqtning o'zida bir nechta chatga tarqatish\n"
            "• `/react <chat> <msg_id> <emoji>` — istalgan emoji / Premium emoji reaksiyasi\n"
            "• `/silentmsg <chat> <matn>` — ovozsiz bildirishnoma bilan yuborish\n"
            "• `/findchat <nom>` — chatlarni ismi bo'yicha topish\n"
            "• `/read <chat> [soni]` — chatdagi xabarlarni o'qib AI xulosasini olish"
        )
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔙 Asosiy Menyu", callback_data="admin_main")]
        ])
        await callback.message.edit_text(text, reply_markup=kb, parse_mode="Markdown")
        await callback.answer()

    elif data == "admin_stats":
        stats = db.get_stats()
        agent_st = userbot.get_status()
        text = (
            "📊 **Tizim va Foydalanish Statistikasi:**\n\n"
            f"👥 **Jami foydalanuvchilar:** {stats['total_users']}\n"
            f"👥 **Guruhlar:** {stats['total_groups']}\n"
            f"📢 **Kanallar:** {stats['total_channels']}\n"
            f"💬 **AI Kotib javob bergan xabarlar:** {agent_st['stats']['replied_count']} ta\n"
            f"🚫 **Qora ro'yxatdagilar:** {agent_st['stats']['blacklist_count']} ta\n"
            f"⚡ **AI Modeli:** {gemini.model_name}"
        )
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔙 Asosiy Menyu", callback_data="admin_main")]
        ])
        await callback.message.edit_text(text, reply_markup=kb, parse_mode="Markdown")
        await callback.answer()

# ----------------- SHAXSIY AI KOTIB (USERBOT) MENYUSI -----------------

def build_agent_dashboard():
    try:
        status = userbot.get_status()
    except Exception:
        status = {
            "configured": False,
            "connected": False,
            "user_name": "Aniqlanmagan",
            "username": "",
            "agent_enabled": db.is_agent_enabled(),
            "stats": db.get_agent_stats()
        }

    conn_text = "🟢 Ulangan (Faol)" if status.get("connected") else "🔴 Ulanmagan"
    agent_switch = "🟢 Yoqilgan" if status.get("agent_enabled") else "🔴 O'chirilgan"
    mode_text = "👤 Sizning nomingizdan" if db.get_agent_mode() == "as_me" else "🤖 AI Kotib sifatida"
    
    uname = status.get("username") or ""
    uname_str = f" (@{uname})" if uname else ""
    user_name = status.get("user_name") or "Aniqlanmagan"
    user_info = f"{user_name}{uname_str}".replace("_", "\\_")

    stats_dict = status.get("stats", {})
    replied = stats_dict.get("replied_count", 0)
    bl_count = stats_dict.get("blacklist_count", 0)
    filter_st = "🟢 Yoqilgan" if stats_dict.get("smart_filter", True) else "🔴 O'chirilgan"

    text = (
        "🤖 **Telegram AI Agent (Shaxsiy Kotib) Paneli**\n\n"
        f"📱 **Shaxsiy akkaunt:** {user_info}\n"
        f"🔌 **Ulanish holati:** {conn_text}\n"
        f"⚡ **Avto-javob:** {agent_switch}\n"
        f"🛡 **Aqlli filtr:** {filter_st}\n"
        f"🎭 **Javob berish uslubi:** {mode_text}\n"
        f"💬 **Javob berilgan:** {replied} ta\n"
        f"🚫 **Qora ro'yxat:** {bl_count} ta\n\n"
        "💡 *Quyidagi tugmalar yoki buyruqlar orqali boshqarishingiz mumkin:*\n"
        "• `/agent on` yoki `/agent off` — Yoqish / O'chirish\n"
        "• `/agent mode as_me` (Mening nomimdan) / `assistant` (Kotib)\n"
        "• `/agent prompt <matn>` — AI xarakteri va ko'rsatmasi\n"
        "• `/agent ignore <id>` — Bloklash"
    )

    mode_btn = "🔄 Uslub: Kotibga o'tish" if db.get_agent_mode() == "as_me" else "🔄 Uslub: Mening nomimga o'tish"
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🟢 Yoqish" if not status.get("agent_enabled") else "🔴 O'chirish", callback_data="agent_toggle"),
            InlineKeyboardButton(text=mode_btn, callback_data="agent_toggle_mode")
        ],
        [
            InlineKeyboardButton(text="🛡 Aqlli filtrni o'zgartirish", callback_data="agent_toggle_filter"),
            InlineKeyboardButton(text="🧠 Moslashish", callback_data="admin_persona")
        ],
        [
            InlineKeyboardButton(text="🚫 Qora ro'yxat", callback_data="admin_blacklist"),
            InlineKeyboardButton(text="🔙 Admin Panel", callback_data="admin_main")
        ]
    ])
    return text, kb

async def send_agent_dashboard(message_or_callback):
    text, kb = build_agent_dashboard()
    if isinstance(message_or_callback, Message):
        try:
            await message_or_callback.answer(text, reply_markup=kb, parse_mode="Markdown")
        except Exception:
            clean_text = text.replace("*", "").replace("_", "").replace("`", "")
            await message_or_callback.answer(clean_text, reply_markup=kb, parse_mode=None)
    elif isinstance(message_or_callback, CallbackQuery):
        try:
            await message_or_callback.message.edit_text(text, reply_markup=kb, parse_mode="Markdown")
        except Exception:
            clean_text = text.replace("*", "").replace("_", "").replace("`", "")
            try:
                await message_or_callback.message.edit_text(clean_text, reply_markup=kb, parse_mode=None)
            except Exception:
                pass

@router.message(Command("agent"))
@router.message(F.text == "🤖 AI Kotib (Userbot)")
async def handle_agent_command(message: Message):
    args = message.text.split(maxsplit=2) if message.text else []

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
            mode_desc = "👤 Sizning nomingizdan" if current_mode == "as_me" else "🤖 AI Kotib sifatida"
            await message.reply(f"🎭 **Hozirgi uslub:** {mode_desc}\n\nO'zgartirish: `/agent mode as_me` yoki `/agent mode assistant`", parse_mode="Markdown")
            return
        new_mode = args[2].lower()
        if new_mode in ["as_me", "me", "men"]:
            db.set_agent_mode("as_me")
            await message.reply("✅ **Uslub:** 👤 Sizning nomingizdan!", parse_mode="Markdown")
        elif new_mode in ["assistant", "kotib", "bot"]:
            db.set_agent_mode("assistant")
            await message.reply("✅ **Uslub:** 🤖 AI Kotib sifatida!", parse_mode="Markdown")
        else:
            await message.reply("Tanlang: `/agent mode as_me` yoki `/agent mode assistant`", parse_mode="Markdown")
        return

    # 4. /agent prompt <matn>
    if len(args) > 1 and args[1].lower() == "prompt":
        if len(args) < 3:
            cur = db.get_agent_prompt()
            await message.reply(f"📝 **Hozirgi ko'rsatma:**\n_{cur}_\n\nO'zgartirish: `/agent prompt <yangi_matn>`", parse_mode="Markdown")
            return
        db.set_agent_prompt(args[2].strip())
        await message.reply("✅ **AI Agent ko'rsatmasi yangilandi!**", parse_mode="Markdown")
        return

    # 5. /agent myinfo <matn>
    if len(args) > 1 and args[1].lower() == "myinfo":
        if len(args) < 3:
            info = db.get_owner_info()
            await message.reply(f"ℹ️ **Siz haqingizda:**\n_{info}_\n\nO'zgartirish: `/agent myinfo <matn>`", parse_mode="Markdown")
            return
        db.set_owner_info(args[2].strip())
        await message.reply("✅ **Shaxsiy ma'lumotlaringiz yangilandi!**", parse_mode="Markdown")
        return

    # 6. /agent ignore <id> yoki block <id>
    if len(args) > 1 and args[1].lower() in ["ignore", "block"]:
        if len(args) < 3 or not args[2].lstrip("-").isdigit():
            await message.reply("Format: `/agent ignore <user_id>`", parse_mode="Markdown")
            return
        uid = int(args[2])
        db.add_to_blacklist(uid)
        await message.reply(f"🚫 `{uid}` qora ro'yxatga kiritildi.", parse_mode="Markdown")
        return

    # 7. /agent unignore <id> yoki unblock <id>
    if len(args) > 1 and args[1].lower() in ["unignore", "unblock"]:
        if len(args) < 3 or not args[2].lstrip("-").isdigit():
            await message.reply("Format: `/agent unignore <user_id>`", parse_mode="Markdown")
            return
        uid = int(args[2])
        db.remove_from_blacklist(uid)
        await message.reply(f"✅ `{uid}` qora ro'yxatdan chiqarildi.", parse_mode="Markdown")
        return

    # 8. Asosiy panelni chiqarish
    await send_agent_dashboard(message)

@router.callback_query(F.data.startswith("agent_"))
async def handle_agent_callback(callback: CallbackQuery):
    data = callback.data
    
    if data == "agent_toggle":
        new_state = not db.is_agent_enabled()
        db.set_agent_enabled(new_state)
        await callback.answer(f"AI Agent {'yoqildi' if new_state else 'o‘chirildi'}!")
        await send_agent_dashboard(callback)

    elif data == "agent_toggle_mode":
        current = db.get_agent_mode()
        new_mode = "assistant" if current == "as_me" else "as_me"
        db.set_agent_mode(new_mode)
        mode_desc = "Sizning nomingizdan" if new_mode == "as_me" else "AI Kotib sifatida"
        await callback.answer(f"Uslub o'zgardi: {mode_desc}!")
        await send_agent_dashboard(callback)

    elif data == "agent_toggle_filter":
        new_state = not db.is_smart_filter_enabled()
        db.set_smart_filter(new_state)
        await callback.answer(f"Aqlli filtr {'yoqildi' if new_state else 'o‘chirildi'}!")
        await send_agent_dashboard(callback)

    elif data.startswith("agent_block_"):
        uid = int(data.split("_")[2])
        db.add_to_blacklist(uid)
        await callback.answer(f"Foydalanuvchi {uid} bloklandi!", show_alert=True)
        try:
            await callback.message.edit_reply_markup(reply_markup=None)
        except Exception:
            pass

    elif data.startswith("agent_unblock_"):
        uid = int(data.split("_")[2])
        db.remove_from_blacklist(uid)
        await callback.answer(f"Foydalanuvchi {uid} qora ro'yxatdan chiqarildi!", show_alert=True)
        # Qora ro'yxat menyusini yangilash
        blocked_list = db.get_blacklist_detailed()
        rows = []
        if not blocked_list:
            text = "🚫 **Qora ro'yxat bo'sh.**\n\nFoydalanuvchini qo'shish: `/block <user_id>`"
        else:
            text = f"🚫 **Qora ro'yxatdagi foydalanuvchilar ({len(blocked_list)} ta):**\n\n"
            for item in blocked_list[:10]:
                u = item["id"]
                name = item["name"]
                text += f"• **{name}** (`{u}`)\n"
                rows.append([InlineKeyboardButton(text=f"🗑 Chiqarish: {name[:12]} ({u})", callback_data=f"agent_unblock_{u}")])
        rows.append([InlineKeyboardButton(text="🔙 Asosiy Menyu", callback_data="admin_main")])
        try:
            await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=rows), parse_mode="Markdown")
        except Exception:
            pass

# ----------------- AKKAUNTNI BOSHQARISH BUYRUQLARI -----------------

@router.message(Command("mychats"))
async def handle_mychats(message: Message):
    """Userbot qo'shilgan chatlarni ko'rish"""
    dialogs = await userbot.get_dialogs_list(limit=25)
    if not dialogs:
        await message.reply("Chatlar ro'yxatini olib bo'lmadi. Userbot ulanganligini tekshiring.")
        return

    lines = ["📋 **Siz a'zo bo'lgan chatlar (Userbot):**\n"]
    for d in dialogs:
        icon = "📢" if d["type"] == "channel" else ("👥" if d["type"] == "group" else ("🤖" if d["type"] == "bot" else "👤"))
        uname = f"(@{d['username']})" if d.get("username") else ""
        lines.append(f"{icon} **{d['title']}** {uname}\n  ID: `{d['id']}`")

    lines.append("\n💡 Xabarlarni o'qish uchun: `/read <chat_id> [soni]`")
    await safe_reply(message, "\n".join(lines))

@router.message(Command("read"))
async def handle_read_chat(message: Message):
    """Istalgan kanal yoki guruhdagi so'nggi xabarlarni o'qish va AI konspektini olish"""
    parts = message.text.split(maxsplit=2)
    if len(parts) < 2:
        await message.reply("Format: `/read <chat_id yoki @username> [xabarlar_soni]`\nMisol: `/read @daryo 10`", parse_mode="Markdown")
        return

    target = parts[1].strip()
    target_id = int(target) if (target.isdigit() or target.startswith("-")) else target
    limit = int(parts[2]) if (len(parts) > 2 and parts[2].isdigit()) else 12

    status_msg = await message.reply("⏳ Xabarlar o'qilmoqda va AI tahlil qilmoqda...")
    raw_history = await userbot.get_chat_history_text(target_id, limit=limit)

    if "Xatolik" in raw_history or "topilmadi" in raw_history:
        await status_msg.edit_text(f"❌ {raw_history}")
        return

    # Gemini orqali qisqacha xulosa
    summary = await gemini.summarize_chat_messages(chat_title=str(target), messages_text=raw_history)
    await status_msg.edit_text(
        f"📖 **{target} — So'nggi {limit} ta xabar konspekti:**\n\n{summary}",
        parse_mode="Markdown"
    )

@router.message(Command("botcall"))
async def handle_botcall(message: Message):
    """Boshqa Telegram botga buyruq jo'natish"""
    parts = message.text.split(maxsplit=2)
    if len(parts) < 3:
        await message.reply("Format: `/botcall <@bot_username> <buyruq>`\nMisol: `/botcall @vkmusic_bot /start`", parse_mode="Markdown")
        return

    bot_username = parts[1].strip().lstrip("@")
    command = parts[2].strip()

    status_msg = await message.reply(f"⏳ `@{bot_username}` ga '{command}' yuborilmoqda...")
    bot_reply = await userbot.interact_with_bot(bot_username, command)
    await status_msg.edit_text(
        f"🤖 **@{bot_username} javobi:**\n\n{bot_reply}",
        parse_mode=None
    )

@router.message(Command("reply"))
async def handle_direct_reply(message: Message):
    """Shaxsiy akkaunt nomidan belgilangan chat/shaxsga xabar yuborish"""
    args = message.text.split(maxsplit=2)
    if len(args) < 3:
        await message.reply("Format: `/reply <user_id yoki @username> <xabar matni>`", parse_mode="Markdown")
        return

    target = args[1].strip()
    reply_text = args[2].strip()
    target_id = int(target) if (target.isdigit() or target.startswith("-")) else target

    success = await userbot.send_direct_message(target_id, reply_text)
    if success:
        await message.reply(f"✅ Shaxsiy Telegram akkauntingiz nomidan `{target}` ga xabar yuborildi!", parse_mode="Markdown")
    else:
        await message.reply("❌ Xabar yuborishda xatolik yuz berdi.")

@router.message(F.reply_to_message)
async def handle_reply_to_notification(message: Message):
    """Bot yuborgan xabarnomaga javob (Reply) yozilganda, uni shaxsiy akkauntdan yetkazish"""
    replied_msg = message.reply_to_message
    target_sender_id = userbot.get_sender_for_notification(replied_msg.message_id)
    if target_sender_id:
        reply_text = message.text.strip() if message.text else ""
        if not reply_text:
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
            await message.reply("❌ Xabar jo'natishda xatolik yuz berdi.")

@router.message(Command("broadcast"))
async def handle_broadcast(message: Message, bot: Bot):
    """Barcha a'zolarga va guruhlarga e'lon tarqatish"""
    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        await message.reply("Format: `/broadcast <xabar matni>`", parse_mode="Markdown")
        return

    broadcast_text = args[1].strip()
    users = db.get_users()
    chats = db.get_chats()
    sent_count, fail_count = 0, 0
    status_msg = await message.reply("⏳ Xabar tarqatilmoqda...")

    for uid in users.keys():
        try:
            await bot.send_message(chat_id=int(uid), text=broadcast_text)
            sent_count += 1
        except Exception:
            fail_count += 1

    for cid in chats.keys():
        try:
            await bot.send_message(chat_id=int(cid), text=broadcast_text)
            sent_count += 1
        except Exception:
            fail_count += 1

    await status_msg.edit_text(
        f"📢 **E'lon yakunlandi!**\n\n✅ Yuborildi: {sent_count}\n❌ Yetib bormadi: {fail_count}",
        parse_mode="Markdown"
    )

@router.message(Command("post"))
async def handle_post_to_channel(message: Message, bot: Bot):
    """Kanalga post joylash"""
    args = message.text.split(maxsplit=2)
    if len(args) < 3:
        await message.reply("Format: `/post <kanal_id yoki @username> <matn>`", parse_mode="Markdown")
        return
    target = args[1].strip()
    content = args[2].strip()
    try:
        chat_target = int(target) if (target.isdigit() or target.startswith("-")) else target
        await bot.send_message(chat_id=chat_target, text=content, parse_mode="Markdown")
        await message.reply(f"✅ Kanalga post joylandi: `{target}`", parse_mode="Markdown")
    except Exception as e:
        await message.reply(f"❌ Kanalga post joylashda xatolik: {e}")

@router.message(Command("pin"))
async def handle_pin_message(message: Message, bot: Bot):
    """Xabarni qadash"""
    if not message.reply_to_message:
        await message.reply("Xabarni qadash uchun o'sha xabarga reply qilib /pin yozing.")
        return
    try:
        await bot.pin_chat_message(chat_id=message.chat.id, message_id=message.reply_to_message.message_id)
        await message.reply("📌 Xabar qadab qo'yildi!")
    except Exception as e:
        await message.reply(f"❌ Xatolik: {e}")

# ----------------- CHATLARGA XABAR YUBORISH VA TELEGRAM AMALLARI -----------------

_last_failed_send_action: Dict[int, Dict[str, Any]] = {}

async def execute_ai_action_if_any(ai_reply: str, message: Message) -> bool:
    """AI javobidagi maxsus amallarni (Action) bajarish"""
    import re
    
    # 1. SEND_MESSAGE (bitta chatga xabar yuborish)
    send_match = re.search(r"\[ACTION:SEND_MESSAGE\|TARGET:(.*?)\|TEXT:(.*?)\]", ai_reply, re.DOTALL)
    if send_match:
        target = send_match.group(1).strip()
        text_to_send = send_match.group(2).strip()
        status_msg = await message.reply(f"⏳ `{target}` ga xabar yuborilmoqda...")
        res = await userbot.send_to_target(target, text_to_send)
        if res["success"]:
            _last_failed_send_action.pop(message.from_user.id, None)
            await status_msg.edit_text(
                f"✅ **Xabar muvaffaqiyatli yuborildi!**\n\n"
                f"🎯 **Qayerga:** {res['chat_title']}\n"
                f"💬 **Xabar:** {text_to_send}",
                parse_mode="Markdown"
            )
        else:
            _last_failed_send_action[message.from_user.id] = {
                "target": target,
                "text": text_to_send,
                "time": time.time()
            }
            await status_msg.edit_text(
                f"❌ **Xabar yuborishda xatolik:**\n{res['error']}\n\n"
                f"💡 *Agar bu shaxsning Telegram ID si yoki @username ini bilsangiz, shunchaki yuboring (masalan: `8927070806` yoki `@username`), bot uni o'zi yetkazadi.*",
                parse_mode="Markdown"
            )
        return True

    # 2. SEND_MULTIPLE (bir nechta chatlarga xabar yuborish)
    multi_match = re.search(r"\[ACTION:SEND_MULTIPLE\|TARGETS:(.*?)\|TEXT:(.*?)\]", ai_reply, re.DOTALL)
    if multi_match:
        targets = [t.strip() for t in multi_match.group(1).split(",") if t.strip()]
        text_to_send = multi_match.group(2).strip()
        status_msg = await message.reply(f"⏳ {len(targets)} ta chatga xabar yuborilmoqda...")
        res = await userbot.send_to_multiple_targets(targets, text_to_send)
        succ = "\n".join([f"• ✅ {c}" for c in res["success"]]) if res["success"] else "Hech biri"
        fail = "\n".join([f"• ❌ {c}" for c in res["failed"]]) if res["failed"] else "Yo'q"
        await status_msg.edit_text(
            f"📢 **Xabar bir nechta chatga yuborildi:**\n\n"
            f"**Muvaffaqiyatli:**\n{succ}\n\n"
            f"**Yetib bormadi:**\n{fail}\n\n"
            f"💬 **Matn:** {text_to_send}",
            parse_mode="Markdown"
        )
        return True

    # 3. REACT (xabarga reaksiya qoldirish)
    react_match = re.search(r"\[ACTION:REACT\|TARGET:(.*?)\|MSG_ID:(\d+)\|EMOJI:(.*?)\]", ai_reply)
    if react_match:
        target = react_match.group(1).strip()
        msg_id = int(react_match.group(2).strip())
        emoji = react_match.group(3).strip()
        res = await userbot.react_to_message(target, msg_id, emoji)
        if res["success"]:
            await message.reply(f"✨ `{target}` dagi #{msg_id} xabarga {emoji} reaksiyasi qoldirildi!")
        else:
            await message.reply(f"❌ Reaksiya bildirishda xatolik: {res['error']}")
        return True

    return False

@router.message(Command("sendmsg"))
@router.message(Command("msg"))
async def handle_sendmsg_command(message: Message):
    """Shaxsiy akkauntdan istalgan chat, shaxs yoki kanalga xabar yuborish"""
    parts = message.text.split(maxsplit=2)
    if len(parts) < 3:
        await message.reply(
            "Format: `/sendmsg <chat_id, @username yoki ism> <xabar matni>`\n\n"
            "Misollar:\n"
            "• `/sendmsg @ali Salom, qalaysan?`\n"
            "• `/sendmsg -100123456789 Yangi post!`\n"
            "• `/sendmsg Doston Akam Bugun uchrashamiz`",
            parse_mode="Markdown"
        )
        return

    target = parts[1].strip()
    text = parts[2].strip()

    status_msg = await message.reply(f"⏳ `{target}` ga xabar yuborilmoqda...")
    res = await userbot.send_to_target(target, text)
    if res["success"]:
        await status_msg.edit_text(
            f"✅ **Xabar muvaffaqiyatli yuborildi!**\n\n"
            f"🎯 **Qayerga:** {res['chat_title']}\n"
            f"💬 **Xabar:** {text}",
            parse_mode="Markdown"
        )
    else:
        await status_msg.edit_text(f"❌ Xatolik yuz berdi: {res['error']}", parse_mode="Markdown")

@router.message(Command("multisend"))
async def handle_multisend_command(message: Message):
    """Bir nechta chatlarga bir vaqtda xabar tarqatish"""
    parts = message.text.split(maxsplit=2)
    if len(parts) < 3:
        await message.reply(
            "Format: `/multisend <chat1,chat2,...> <xabar matni>`\n\n"
            "Misol: `/multisend @daryo,@mychannel,-100123456 Hammaga xayrli kun!`",
            parse_mode="Markdown"
        )
        return

    targets = [t.strip() for t in parts[1].split(",") if t.strip()]
    text = parts[2].strip()

    status_msg = await message.reply(f"⏳ {len(targets)} ta chatga xabar tarqatilmoqda...")
    res = await userbot.send_to_multiple_targets(targets, text)
    
    succ_lines = "\n".join([f"• ✅ {c}" for c in res["success"]]) if res["success"] else "Hech biri"
    fail_lines = "\n".join([f"• ❌ {c}" for c in res["failed"]]) if res["failed"] else "Yo'q"

    await status_msg.edit_text(
        f"📢 **Natija:**\n\n"
        f"**Muvaffaqiyatli ({len(res['success'])} ta):**\n{succ_lines}\n\n"
        f"**Yuborilmadi ({len(res['failed'])} ta):**\n{fail_lines}\n\n"
        f"💬 **Xabar:** {text}",
        parse_mode="Markdown"
    )

@router.message(Command("react"))
async def handle_react_command(message: Message):
    """Xabarga reaksiya bildirish (Telegram Premium / Standart emojilar)"""
    parts = message.text.split(maxsplit=3)
    if len(parts) < 3:
        await message.reply(
            "Format: `/react <chat_id yoki @username> <xabar_id> [emoji]`\n\n"
            "Misol: `/react @mychannel 125 🔥` (standart: 🔥)",
            parse_mode="Markdown"
        )
        return

    target = parts[1].strip()
    if not parts[2].isdigit():
        await message.reply("Xabar ID si faqat raqam bo'lishi kerak!")
        return
    msg_id = int(parts[2])
    emoji = parts[3].strip() if len(parts) > 3 else "🔥"

    res = await userbot.react_to_message(target, msg_id, emoji)
    if res["success"]:
        await message.reply(f"✨ `{target}` dagi #{msg_id} xabarga {emoji} reaksiyasi qoldirildi!")
    else:
        await message.reply(f"❌ Reaksiya qoldirib bo'lmadi: {res['error']}")

@router.message(Command("silentmsg"))
async def handle_silentmsg_command(message: Message):
    """Ovoz bildirishnomasisiz (Silent) xabar yuborish"""
    parts = message.text.split(maxsplit=2)
    if len(parts) < 3:
        await message.reply("Format: `/silentmsg <chat> <matn>`", parse_mode="Markdown")
        return
    target, text = parts[1].strip(), parts[2].strip()
    res = await userbot.send_to_target(target, text, silent=True)
    if res["success"]:
        await message.reply(f"🔕 **Ovozsiz (Silent) xabar yuborildi:** `{res['chat_title']}`", parse_mode="Markdown")
    else:
        await message.reply(f"❌ Xatolik: {res['error']}")

@router.message(Command("findchat"))
async def handle_findchat_command(message: Message):
    """Chatlarni nomi bo'yicha qidirish"""
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        await message.reply("Format: `/findchat <qidiruv_so'zi>`", parse_mode="Markdown")
        return
    q = parts[1].strip().lower()
    dialogs = await userbot.get_dialogs_list(limit=80)
    matched = [d for d in dialogs if q in d["title"].lower() or q in d["username"].lower()]
    if not matched:
        await message.reply(f"'{q}' bo'yicha hech qanday chat topilmadi.")
        return
    lines = [f"🔍 **'{q}' bo'yicha topilgan chatlar:**\n"]
    for d in matched[:10]:
        icon = "📢" if d["type"] == "channel" else ("👥" if d["type"] == "group" else "👤")
        uname = f"(@{d['username']})" if d.get("username") else ""
        lines.append(f"{icon} **{d['title']}** {uname}\n  ID: `{d['id']}`")
    await safe_reply(message, "\n".join(lines))

# ----------------- GURUHLARDA ISHLASH VA /ai BUYRUG'I -----------------

@router.message(Command("ai"))
@router.message(Command("ask"))
async def handle_ai_command(message: Message):
    """Guruhda yoki shaxsiy chatda AI ga to'g'ridan-to'g'ri savol berish"""
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        await message.reply("Savolingizni yozing: `/ai O'zbekiston poytaxti qaysi?`", parse_mode="Markdown")
        return

    question = parts[1].strip()
    await message.bot.send_chat_action(chat_id=message.chat.id, action=ChatAction.TYPING)
    ai_reply = await gemini.generate_response(user_id=message.chat.id, user_message=question)
    await safe_reply(message, ai_reply)

# ----------------- OVOZLI VA MEDIA XABARLAR -----------------

@router.message(F.voice | F.audio)
async def handle_voice(message: Message):
    """Foydalanuvchi yuborgan ovozli xabarni qabul qilish va ovoz bilan javob qaytarish"""
    user_id = message.from_user.id
    db.register_user(user_id, message.from_user.full_name, message.from_user.username)

    await message.bot.send_chat_action(chat_id=message.chat.id, action=ChatAction.RECORD_VOICE)

    voice_obj = message.voice if message.voice else message.audio
    file_io = io.BytesIO()
    await message.bot.download(voice_obj, destination=file_io)
    audio_bytes = file_io.getvalue()
    mime_type = "audio/ogg" if message.voice else "audio/mp3"

    ai_reply = await gemini.process_audio(user_id=user_id, audio_bytes=audio_bytes, mime_type=mime_type)

    try:
        voice_bytes = await synthesize_voice(ai_reply)
        voice_file = BufferedInputFile(voice_bytes, filename="reply.ogg")
        caption = ai_reply if len(ai_reply) <= 1000 else ai_reply[:1000] + "..."
        await message.reply_voice(voice=voice_file, caption=caption)
    except Exception as e:
        logger.error(f"Ovoz jo'natishda xatolik: {e}")
        await safe_reply(message, f"🗣 {ai_reply}")

@router.message(F.photo)
async def handle_photo(message: Message):
    """Foydalanuvchi yuborgan rasmni tahlil qilish"""
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
async def handle_text(message: Message, bot: Bot):
    """Foydalanuvchi matnli xabarlarini qayta ishlash"""
    user_text = message.text.strip()
    is_private = (message.chat.type == "private")

    # Agar guruh yoki kanal bo'lsa
    if not is_private:
        db.register_chat(
            chat_id=message.chat.id,
            title=message.chat.title or "Guruh",
            chat_type=message.chat.type,
            username=message.chat.username
        )
        
        bot_info = await bot.get_me()
        bot_username = f"@{bot_info.username}".lower()
        
        is_reply_to_bot = (message.reply_to_message and message.reply_to_message.from_user and message.reply_to_message.from_user.id == bot_info.id)
        is_mentioned = bot_username in user_text.lower()

        if is_reply_to_bot or is_mentioned:
            clean_text = user_text.lower().replace(bot_username, "").strip()
            if not clean_text:
                clean_text = "Salom, qanday yordam bera olaman?"
            await bot.send_chat_action(chat_id=message.chat.id, action=ChatAction.TYPING)
            ai_reply = await gemini.generate_response(user_id=message.chat.id, user_message=clean_text)
            await safe_reply(message, ai_reply)
        return

    # Shaxsiy chat (Private)
    db.register_user(message.from_user.id, message.from_user.full_name, message.from_user.username)

    if user_text.startswith("/"):
        await message.reply("Noma'lum buyruq. Yordam uchun /help deb yozing.")
        return

    # Agar avvalgi xabar yuborish muvaffaqiyatsiz bo'lgan bo'lsa va foydalanuvchi yangi xabarda ID yoki username kiritgan bo'lsa:
    last_failed = _last_failed_send_action.get(message.from_user.id)
    if last_failed and (time.time() - last_failed.get("time", 0) < 300):
        import re
        id_match = re.search(r"(\b-?\d{6,14}\b)", user_text)
        username_match = re.search(r"(@[a-zA-Z0-9_]{4,32})", user_text)
        new_target = None
        if id_match:
            new_target = id_match.group(1)
        elif username_match:
            new_target = username_match.group(1)

        if new_target:
            text_to_retry = last_failed["text"]
            status_msg = await message.reply(f"⏳ `{new_target}` ga xabar yuborilmoqda...")
            res = await userbot.send_to_target(new_target, text_to_retry)
            if res["success"]:
                _last_failed_send_action.pop(message.from_user.id, None)
                await status_msg.edit_text(
                    f"✅ **Xabar muvaffaqiyatli yuborildi!**\n\n"
                    f"🎯 **Qayerga:** {res['chat_title']}\n"
                    f"💬 **Xabar:** {text_to_retry}",
                    parse_mode="Markdown"
                )
                return
            else:
                await status_msg.edit_text(
                    f"❌ **Xabar yuborishda xatolik:**\n{res['error']}",
                    parse_mode="Markdown"
                )
                return

    await bot.send_chat_action(chat_id=message.chat.id, action=ChatAction.TYPING)
    ai_reply = await gemini.generate_response(user_id=message.from_user.id, user_message=user_text)

    # 1. AI javobida amaliy topshiriq (Action) bormi?
    action_handled = await execute_ai_action_if_any(ai_reply, message)
    if not action_handled:
        await safe_reply(message, ai_reply)
