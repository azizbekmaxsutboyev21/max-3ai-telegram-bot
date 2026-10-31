# 🤖 Telegram AI Bot & Shaxsiy AI Kotib (Google Gemini + Userbot + Voice)

Telegram uchun yaratilgan zamonaviy, ovozli muloqot, to'liq shaxsiy akkaunt nazorati (Userbot) va interaktiv Admin paneliga ega universal **Aqlli AI Bot**.

- **Bot username:** [@MAX_3AI_BOT](https://t.me/MAX_3AI_BOT)
- **AI Modeli:** `Google Gemini 3.8 Flash / 3.5 Flash Lite`
- **Ovoz moduli:** `Microsoft Edge Neural TTS (O'zbekcha: Sardor)`
- **Kutubxonalar:** `aiogram 3`, `telethon 1.38`, `google-genai`
- **Platforma:** Oracle Cloud (VPS systemd), Render.com, Linux/Windows

---

## ✨ Asosiy Imkoniyatlar va Yangiliklar

### 1. 🎙 Ovozli va Multimodal muloqot
- Foydalanuvchi oddiy **ovozli xabar (Voice)** yuborishi mumkin. AI uni tinglab, o'zbek tilida **tabiiy ovozda** javob qaytaradi.
- Rasm yuborilganda undagi ma'lumotlarni tahlil qiladi va savollarga javob beradi.

### 2. 🤖 Shaxsiy AI Kotib (Userbot) va Anti-Spam
- **Takroriy salomlashish yo'qotildi:** AI bir suhbatdosh bilan har bir xabarda qayta-qayta "Salom" deb yozmaydi, to'g'ridan-to'g'ri mavzu bo'yicha tabiiy insondek gaplashadi.
- **Xabarlarni birlashtirish (Debouncing):** Bir vaqtning o'zida kelgan ketma-ket xabarlarni bitta qilib jamlaydi va bitta umumiy mantiqiy javob qaytaradi.
- **Aqlli filtr:** Keraksiz stikerlar, yagona emojilar, "ok", "+" kabi xabarlarga javob qaytarib spam qilmaydi.
- **Egasi yozganda to'xtash:** Agar siz (Azizbek) shaxsan o'zingiz lichkada yozishayotgan bo'lsangiz, AI suhbatga xalaqit bermaydi.

### 3. 🧠 Menga moslashish (Persona & Adaptation)
- AI o'z-o'zidan sizning fe'l-atvoringiz, kasbingiz, muloqot uslubingiz va qoidalaringizga moslashadi.
- `/adapt <matn>` orqali AI ga o'zingiz haqingizda yangi ma'lumotlar berishingiz mumkin.

### 4. 🚫 Qora ro'yxat (Blacklist) boshqaruvi
- Keraksiz kishilar yoki spamerlarni qora ro'yxatga kiritish va chiqarish.
- `/blacklist` — barcha bloklanganlarni ko'rish va bitta tugma bilan ro'yxatdan chiqarish.
- `/block <user_id>` va `/unblock <user_id>` buyruqlari.

### 5. 📱 Butun boshli Telegram akkauntini boshqarish
- `/mychats` — Siz a'zo bo'lgan barcha guruhlar, kanallar va botlar ro'yxatini ko'rish.
- `/read <chat_id> [soni]` — Istalgan kanal yoki guruhdagi so'nggi xabarlarni o'qish va AI orqali konspekt (xulosa) olish.
- `/botcall <@bot> <buyruq>` — Siz ishlatadigan boshqa Telegram botlariga o'z nomingizdan buyruq berish va javobini olish.
- `/reply <id> <matn>` — Shaxsiy akkauntingiz nomidan xabar yozish.

### 6. 🔐 Istalgan akkauntdan xavfsiz kirish (Passcode)
- Siz botga istalgan ikkinchi yoki uchinchi Telegram akkauntingizdan kirishingiz mumkin.
- Shaxsiy chatda bot sizdan **maxfiy kirish kodini** so'raydi. Kodni to'g'ri kiritishingiz bilanoq to'liq Admin huquqiga ega bo'lasiz.
- `/lock` — Botni darhol qulflash.
- `/setcode <kod>` — Maxfiy kodni o'zgartirish.

### 7. 👥 Guruhlar va Kanallarda ishlash
- Botni istalgan guruhga qo'shing: `@bot_username` deb murojaat qilinsa yoki `/ai <savol>` deb yozilsa, bot guruh a'zolariga professional javob beradi.
- Kanallarga `/post <kanal_id> <matn>` orqali post joylash.

---

## 🛠 Buyruqlar ro'yxati

| Buyruq | Tavsif |
|---|---|
| `/start` | Botni ishga tushirish |
| `/admin` | Kengaytirilgan boshqaruv paneli |
| `/agent` | Shaxsiy AI Kotib (Userbot) paneli |
| `/adapt <matn>` | Botni o'zingizga moslashtirish |
| `/persona` | Hozirgi moslashuv profilini ko'rish |
| `/blacklist` | Bloklanganlar ro'yxati va boshqarish |
| `/block <id>` | Foydalanuvchini bloklash |
| `/unblock <id>` | Blokdan chiqarish |
| `/mychats` | Userbot ulangan chatlar va kanallar |
| `/read <chat> [n]` | Kanal/guruh xabarlarini o'qish va AI xulosasi |
| `/botcall <@bot> <cmd>` | Boshqa botlarga buyruq berish |
| `/reply <id> <matn>` | O'z nomingizdan xabar jo'natish |
| `/ai <savol>` | Guruhda AI ga savol berish |
| `/broadcast <matn>` | Barcha a'zolarga e'lon tarqatish |
| `/lock` | Botni qulflash |
| `/setcode <kod>` | Kirish kodini o'zgartirish |
| `/reset` | Suhbat tarixini tozalash |

---

## 🚀 Oracle Cloud (VPS Always Free) serveriga o'rnatish

Bot Oracle Cloud Ubuntu VPS da **24/7 uzluksiz** ishlashga to'liq moslashtirilgan.

### 1. Server paketlarini o'rnatish:
```bash
sudo apt update && sudo apt upgrade -y
sudo apt install -y python3-pip python3-venv git
```

### 2. Loyihani yuklab olish:
```bash
git clone https://github.com/azizbekmaxsutboyev21/max-3ai-telegram-bot.git
cd max-3ai-telegram-bot
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 3. `.env` faylini sozlash:
```bash
cp .env.example .env
nano .env
```
Kerakli kalitlarni to'ldiring (`BOT_TOKEN`, `GEMINI_API_KEY`, `CREATOR_ID`, `ACCESS_CODE`, `TELEGRAM_STRING_SESSION` va h.k.).

### 4. `systemd` orqali 24/7 rejimda ishga tushirish:
```bash
sudo nano /etc/systemd/system/telegram-bot.service
```
Quyidagi konfiguratsiyani qo'ying:
```ini
[Unit]
Description=Telegram AI Bot (max-3ai-telegram-bot)
After=network.target

[Service]
Type=simple
User=ubuntu
WorkingDirectory=/home/ubuntu/max-3ai-telegram-bot
ExecStart=/home/ubuntu/max-3ai-telegram-bot/venv/bin/python main.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Servisni yoqish:
```bash
sudo systemctl daemon-reload
sudo systemctl enable telegram-bot
sudo systemctl start telegram-bot
```

Holatini tekshirish:
```bash
sudo systemctl status telegram-bot
```
Loglarni kuzatish:
```bash
journalctl -u telegram-bot -f
```
