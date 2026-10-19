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

---

## 🛠 Buyruqlar ro'yxati

### Oddiy foydalanuvchilar uchun:
- `/start` — Botni ishga tushirish
- `/reset` yoki `/clear` — Suhbat tarixini tozalash
- `/help` — Qo'llanma
- `/about` — Bot haqida ma'lumot

### Yaratuvchi (Creator) uchun:
- `/admin` — Boshqaruv paneli
- `/send <target> <matn>` — Xabar yuborish
- `/broadcast <matn>` — Xabar tarqatish
- `/chats` — Guruh va kanallar ro'yxati
- `/post <kanal> <matn>` — Kanalga post
- `/pin` — Xabarni qadash

---

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
- `GEMINI_API_KEY` = Sizning Google Gemini API kalitingiz
- `GEMINI_MODEL` = `gemini-3.8-flash`
- `CREATOR_ID` = `5772939710`
- `PYTHON_VERSION` = `3.11.4`

### 5-qadam: Bepul 24/7 rejimda ushlab turish (Uxlashini oldini olish)
Render.com Free Web Service 15 daqiqa murojaat bo'lmasa uxlab qoladi (spin down). Buni oldini olish va botni tunu-kun faol ushlab turish uchun:
1. Render sizga bergan manzilni oling (masalan: `https://max-3ai-telegram-bot.onrender.com/health`).
2. [UptimeRobot.com](https://uptimerobot.com) yoki [cron-job.org](https://cron-job.org) bepul saytiga kiring.
3. Yangi monitor (HTTP GET) ochib, ushbu `/health` havolasini har **5 daqiqada** tekshirib turadigan qilib qo'ying.
4. Natijada bot Render serverida **24/7 mutlaqo bepul va uzluksiz** ishlaydi! 🚀
