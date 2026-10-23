# 🤖 Telegram AI Bot (Google Gemini + Voice + Admin Panel)

Telegram uchun zamonaviy, ovozli muloqot va yaratuvchi (admin) boshqaruviga ega **Aqlli AI Bot**.

- **Bot username:** [@MAX_3AI_BOT](https://t.me/MAX_3AI_BOT)
- **AI Modeli:** `Google Gemini 3.8 Flash`
- **Ovoz moduli:** `Microsoft Edge Neural TTS (O'zbekcha: Sardor)`
- **Kutubxona:** `aiogram 3` (Python 3.11 asinxron)
- **Yaratuvchi (Creator ID):** `5772939710`

---

## ✨ Asosiy imkoniyatlar

### 1. 🎙 Ovozli muloqot (Voice In, Voice Out)
- Foydalanuvchi botga Telegram orqali oddiy **ovozli xabar (Voice message)** yuborishi mumkin.
- Gemini 3.8 Flash audio faylni eshitib, gapirilgan so'zlarni va ma'nosini to'liq tushunadi.
- Bot javobni o'zbek tilida **tabiiy ovozda (audio ovozli xabar)** hamda matn ko'rinishida qaytaradi.

### 2. 👑 Yaratuvchi (Admin) Boshqaruv Paneli
Faqat sizning Telegram hisobingiz (`ID: 5772939710`) uchun maxsus imkoniyatlar:
- `/admin` — Boshqaruv paneli va statistikani ko'rish (a'zolar soni, ulanishlar).
- `/send <ID/@username> <matn>` — Bot orqali istalgan shaxsga yoki guruhga xabar yuborish.
- `/broadcast <matn>` — Botdan foydalangan barcha a'zolar va guruhlarga umumiy e'lon tarqatish.
- `/chats` — Bot qo'shilgan barcha guruh va kanallar ro'yxati (ID va nomlari bilan).
- `/post <kanal_id> <matn>` — Bot admin bo'lgan kanallarga avtomatik post chiqarish.
- `/pin` — Guruhda reply qilingan xabarni darhol qadab qo'yish (pin).

### 3. 👥 Guruhlar va Kanallarni nazorat qilish
- Botni o'zingizning guruh yoki kanalingizga **Admin** qilib qo'shing.
- Bot ulangan chatlarni avtomatik ro'yxatga oladi va sizga boshqaruv imkonini beradi.

### 4. 🖼 Multimodal (Rasm tahlili) va Matn
- Istalgan matnli savolga o'zbek tilida batafsil javob.
- Rasmlarni tahlil qilish, masalalarni yechish va tasvirlash.

### 5. 🤖 Shaxsiy Telegram AI Agent (Userbot / Shaxsiy Kotib)
Bot sizning shaxsiy Telegram akkauntingizga ulanib, sizning shaxsiy AI Kotibingiz sifatida ishlaydi:
- **Shaxsiy lichkaga avto-javob:** Siz band bo'lganingizda, shaxsiy lichkangizga kelgan xabarlarga AI sizning nomingizdan samimiy va aqlli javob qaytaradi.
- **Botga xabarnoma:** Lichkaga kim nima yozgani va AI unga nima deb javob bergani darhol botingizga bildirishnoma sifatida keladi.
- **Shaxsiy akkauntdan xabar yozish:** `/reply <user_id> <matn>` orqali shaxsiy Telegramingiz nomidan istalgan odamga bot orqali javob yozish mumkin.
- **Moslashuvchan boshqaruv:** `/agent` buyrug'i orqali AI ni yoqish/o'chirish (`/agent on`, `/agent off`), AI xarakterini o'zgartirish (`/agent prompt <matn>`) va qora ro'yxatni boshqarish.

---

## 🛠 Buyruqlar ro'yxati

### Oddiy foydalanuvchilar uchun:
- `/start` — Botni ishga tushirish
- `/reset` yoki `/clear` — Suhbat tarixini tozalash
- `/help` — Qo'llanma
- `/about` — Bot haqida ma'lumot

### Yaratuvchi (Creator) uchun:
- `🔒 /lock` — Botni darhol qulflash (keyingi murojaatda maxfiy kod so'raladi)
- `🔑 /setcode <kod>` — Maxfiy kirish kodini o'zgartirish
- `/agent` — Shaxsiy AI Agent boshqaruv paneli (Holat, Yoqish/O'chirish, Statistika)
- `/agent on` / `/agent off` — Shaxsiy lichkaga AI avto-javobni yoqish / o'chirish
- `/agent prompt <matn>` — AI Agent xarakteri va ko'rsatmalarini o'zgartirish
- `/reply <user_id> <matn>` — Shaxsiy akkauntingiz nomidan belgilangan kishiga xabar jo'natish
- `/agent ignore <user_id>` — AI javob bermasligi uchun qora ro'yxatga kiritish
- `/admin` — Umumiy boshqaruv paneli va statistika
- `/send <target> <matn>` — Bot nomidan xabar yuborish
- `/broadcast <matn>` — Umumiy e'lon tarqatish
- `/chats` — Guruh va kanallar ro'yxati
- `/post <kanal> <matn>` — Kanalga post
- `/pin` — Xabarni qadash

---

## 📲 Shaxsiy Telegram akkauntini ulash tartibi:
1. Terminalda quyidagi buyruqni bering:
   ```bash
   python generate_session.py
   ```
2. Telefon raqamingizni kiriting (`+998...`) va Telegramingizga kelgan kodni yozing.
3. Dastur avtomatik ravishda `.env` fayliga `TELEGRAM_STRING_SESSION` ni saqlaydi.
4. Render.com ga deploy qilganda ham Environment Variables bo'limiga `TELEGRAM_API_ID`, `TELEGRAM_API_HASH` va `TELEGRAM_STRING_SESSION` qiymatlarini kiritasiz.

## 🚀 Render.com serveriga joylash (Deploy qilish) bo'yicha qo'llanma

Bot Render.com da bepul (Free tier) rejimida uzluksiz ishlashga to'liq moslashtirilgan. Render talab qiladigan ichki Web-server (`aiohttp` health-check) `main.py` ga integratsiya qilingan.

### 1-qadam: Render.com ga kirish
1. [dashboard.render.com](https://dashboard.render.com/) saytiga kiring.
2. **New +** tugmasini bosing va **Web Service** ni tanlang (yoki **Blueprint** orqali `render.yaml` bilan).

### 2-qadam: Repositoriyani ulash
1. GitHub hisobingizdagi ushbu repositoriyani tanlang (`Connect`).

### 3-qadam: Sozlamalar (Settings)
- **Name:** `max-3ai-telegram-bot` (yoki ixtiyoriy nom)
- **Region:** `Frankfurt (EU Central)`
- **Branch:** `main`
- **Runtime:** `Python 3`
- **Build Command:** `pip install -r requirements.txt`
- **Start Command:** `python main.py`
- **Plan:** `Free`

### 4-qadam: Muhit o'zgaruvchilari (Environment Variables)
**Environment** bo'limida quyidagi o'zgaruvchilarni qo'shing:
- `BOT_TOKEN` = Sizning Telegram bot tokeningiz (@BotFather dan)
- `GEMINI_API_KEY` (yoki `GEMINI_API_KEYS`) = Google Gemini API kalit(lar)ingiz. Kvota tugamasligi uchun bir nechta kalitni vergul bilan yozish mumkin: `kalit1,kalit2,kalit3`
- `GEMINI_MODEL` = `gemini-2.5-flash` (tavsiya etiladi; server band bo'lsa bot avtomatik zaxira modellarga o'tadi)
- `CREATOR_ID` = `5772939710`
- `PYTHON_VERSION` = `3.11.4`

### 5-qadam: Bepul 24/7 rejimda ushlab turish (Uxlashini oldini olish)
Render.com Free Web Service 15 daqiqa murojaat bo'lmasa uxlab qoladi (spin down). Buni oldini olish va botni tunu-kun faol ushlab turish uchun:
1. Render sizga bergan manzilni oling (masalan: `https://max-3ai-telegram-bot.onrender.com/health`).
2. [UptimeRobot.com](https://uptimerobot.com) yoki [cron-job.org](https://cron-job.org) bepul saytiga kiring.
3. Yangi monitor (HTTP GET) ochib, ushbu `/health` havolasini har **5 daqiqada** tekshirib turadigan qilib qo'ying.
4. Natijada bot Render serverida **24/7 mutlaqo bepul va uzluksiz** ishlaydi! 🚀
