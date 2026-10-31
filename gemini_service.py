import asyncio
import io
import logging
from typing import Dict, List, Optional, Callable, Any
from PIL import Image
from google import genai
from google.genai import types

import config

logger = logging.getLogger(__name__)

class GeminiService:
    def __init__(self):
        self.system_prompt = config.SYSTEM_PROMPT
        self.api_keys: List[str] = config.get_gemini_api_keys()
        self.fallback_models: List[str] = config.get_gemini_fallback_models()
        self._current_key_idx = 0
        self._current_model_idx = 0
        self._clients: Dict[str, genai.Client] = {}
        # Har bir foydalanuvchi uchun xabarlar tarixi (oxirgi 12 ta xabar saqlanadi, token tejash uchun)
        self._user_histories: Dict[int, List[types.Content]] = {}

    @property
    def model_name(self) -> str:
        return self.fallback_models[self._current_model_idx % len(self.fallback_models)]

    def _get_client_for_key(self, api_key: str) -> genai.Client:
        """Har bir API kalit uchun alohida genai.Client obyektini keshlab qaytarish"""
        if api_key not in self._clients:
            self._clients[api_key] = genai.Client(api_key=api_key)
        return self._clients[api_key]

    def _get_active_client(self) -> tuple[genai.Client, str]:
        """Aktiv API kalit va unga bog'langan Clientni olish"""
        self.api_keys = config.get_gemini_api_keys()
        if not self.api_keys:
            raise ValueError("GEMINI_API_KEY sozlanmagan. Iltimos, .env faylini tekshiring.")
        
        idx = self._current_key_idx % len(self.api_keys)
        key = self.api_keys[idx]
        return self._get_client_for_key(key), key

    def _rotate_key(self):
        """Kvota (429) yoki xatolik yuz berganda keyingi API kalitga o'tish"""
        if len(self.api_keys) > 1:
            self._current_key_idx = (self._current_key_idx + 1) % len(self.api_keys)
            logger.info(f"API kalit almashtirildi. Yangi kalit indeksi: {self._current_key_idx + 1}/{len(self.api_keys)}")

    def _rotate_model(self):
        """Model band bo'lsa (503 UNAVAILABLE), keyingi zaxira modelga o'tish"""
        if len(self.fallback_models) > 1:
            self._current_model_idx = (self._current_model_idx + 1) % len(self.fallback_models)
            logger.info(f"Zaxira modelga o'tildi: {self.fallback_models[self._current_model_idx]}")

    def reset_chat(self, user_id: int) -> bool:
        """Foydalanuvchi suhbat tarixini tozalash (yangi suhbat boshlash)"""
        if user_id in self._user_histories:
            del self._user_histories[user_id]
            return True
        return False

    async def _execute_with_resilience(
        self,
        operation_name: str,
        call_factory: Callable[[genai.Client, str], Any],
        max_retries: int = 4
    ) -> str:
        """
        503 UNAVAILABLE (yuqori yuklanish) va 429 RESOURCE_EXHAUSTED (kvota) xatoliklariga qarshi:
        - Exponential Backoff (kutib qayta urinish)
        - Multi-API Key Rotation (boshqa kalitga o'tish)
        - Fallback Model switching (boshqa zaxira modelga o'tish)
        """
        last_error = ""
        for attempt in range(1, max_retries + 1):
            client, key_str = self._get_active_client()
            model_name = self.fallback_models[self._current_model_idx % len(self.fallback_models)]

            try:
                response = await asyncio.to_thread(call_factory, client, model_name)
                if response and response.text:
                    return response.text.strip()
                return "Kechirasiz, javob matni bo'sh qaytdi. Boshqattan urinib ko'ring."

            except Exception as e:
                err_msg = str(e)
                last_error = err_msg
                logger.warning(
                    f"Gemini {operation_name} urinish #{attempt}/{max_retries} muvaffaqiyatsiz bo'ldi "
                    f"(Model: {model_name}): {err_msg[:120]}"
                )

                is_503 = "503" in err_msg or "UNAVAILABLE" in err_msg or "high demand" in err_msg.lower()
                is_quota = "429" in err_msg or "RESOURCE_EXHAUSTED" in err_msg or "quota" in err_msg.lower()
                is_invalid = "API_KEY_INVALID" in err_msg or "invalid api key" in err_msg.lower()
                is_not_found = "404" in err_msg or "not found" in err_msg.lower()

                if is_invalid:
                    logger.error("API kalit yaroqsiz! Kalitni almashtiramiz...")
                    self._rotate_key()
                    await asyncio.sleep(0.2)
                    continue

                if is_not_found:
                    logger.warning(f"Model '{model_name}' topilmadi (404). Zaxira modelga o'tamiz...")
                    self._rotate_model()
                    continue

                if is_quota:
                    self._rotate_key()
                    if len(self.api_keys) <= 1:
                        self._rotate_model()
                    await asyncio.sleep(0.4)
                    continue

                if is_503:
                    self._rotate_model()
                    delay = 0.5 * attempt
                    await asyncio.sleep(delay)
                    continue

                await asyncio.sleep(0.4)

        logger.error(f"Gemini {operation_name} barcha urinishlardan so'ng ishlamadi. Oxirgi xato: {last_error}")
        if "503" in last_error or "UNAVAILABLE" in last_error:
            return "⚠️ AI serverlarida ayni paytda yuqori yuklanish kuzatilmoqda. 1-2 daqiqadan so'ng qayta yozing."
        elif "429" in last_error or "quota" in last_error.lower() or "RESOURCE_EXHAUSTED" in last_error:
            return "⚠️ API so'rovlar limiti vaqtinchalik to'ldi. Birozdan so'ng qayta urinib ko'ring."
        else:
            return "⚠️ Server bilan ulanishda vaqtinchalik xatolik yuz berdi."

    async def generate_response(self, user_id: int, user_message: str) -> str:
        """Foydalanuvchi matnli xabariga AI javobini olish"""
        try:
            history = self._user_histories.get(user_id, [])
            trimmed_history = history[-12:]

            new_turn = types.Content(
                role="user",
                parts=[types.Part.from_text(text=user_message)]
            )
            request_contents = trimmed_history + [new_turn]

            def _call(client: genai.Client, model: str):
                return client.models.generate_content(
                    model=model,
                    contents=request_contents,
                    config=types.GenerateContentConfig(
                        system_instruction=self.system_prompt,
                        temperature=0.7,
                    )
                )

            reply = await self._execute_with_resilience("Chat so'rovi", _call)

            if not reply.startswith("⚠️"):
                trimmed_history.append(new_turn)
                trimmed_history.append(types.Content(
                    role="model",
                    parts=[types.Part.from_text(text=reply)]
                ))
                self._user_histories[user_id] = trimmed_history[-12:]

            return reply
        except Exception as e:
            logger.error(f"Xabar yuborishda umumiy xatolik: {e}")
            return "⚠️ Xatolik yuz berdi. Iltimos, birozdan so'ng qayta urinib ko'ring."

    async def analyze_image(self, user_id: int, image_bytes: bytes, caption: Optional[str] = None) -> str:
        """Foydalanuvchi yuborgan rasmni tahlil qilish"""
        try:
            image = Image.open(io.BytesIO(image_bytes))
            prompt = caption if caption else "Ushbu rasmni batafsil tasvirlab bering va undagi muhim ma'lumotlarni tahlil qiling."

            def _call(client: genai.Client, model: str):
                return client.models.generate_content(
                    model=model,
                    contents=[prompt, image],
                    config=types.GenerateContentConfig(
                        system_instruction=self.system_prompt,
                        temperature=0.6,
                    )
                )

            return await self._execute_with_resilience("Rasm tahlili", _call)
        except Exception as e:
            logger.error(f"Rasm tahlilida xatolik: {e}")
            return "⚠️ Rasmni tahlil qilishda xatolik yuz berdi."

    async def process_audio(self, user_id: int, audio_bytes: bytes, mime_type: str = "audio/ogg") -> str:
        """Foydalanuvchi yuborgan ovozli xabarni eshitib javob berish"""
        try:
            audio_part = types.Part.from_bytes(data=audio_bytes, mime_type=mime_type)
            prompt = (
                "Foydalanuvchi sizga ovozli xabar (audio) yubordi. "
                "Ovozni tinglab, unga o'zbek tilida aniq, to'liq, do'stona va ravon javob bering."
            )

            def _call(client: genai.Client, model: str):
                return client.models.generate_content(
                    model=model,
                    contents=[audio_part, prompt],
                    config=types.GenerateContentConfig(
                        system_instruction=self.system_prompt,
                        temperature=0.7,
                    )
                )

            return await self._execute_with_resilience("Ovoz tahlili", _call)
        except Exception as e:
            logger.error(f"Ovozli xabarni tahlil qilishda xatolik: {e}")
            return "⚠️ Ovozli xabarni eshitishda xatolik yuz berdi."

    async def generate_agent_reply(
        self,
        sender_name: str,
        message_text: str,
        custom_prompt: str,
        mode: str = "as_me",
        owner_info: str = "",
        chat_history: Optional[List[Dict[str, str]]] = None,
        already_greeted: bool = False,
        persona: Optional[Dict[str, str]] = None
    ) -> str:
        """
        Shaxsiy Telegram akkaunti (Userbot AI Kotib / Agent) nomidan kelgan xabarlarga aqlli javob qaytarish.
        - Takroriy 'Salom' deyishning oldi olingan.
        - Suhbat konteksti (tarixi) inobatga olinadi.
        - Egasi shaxsiyatiga (persona) to'liq moslashadi.
        """
        try:
            persona = persona or {}
            owner_name = persona.get("owner_name", "Azizbek")
            about_me = persona.get("about_me", owner_info)
            comm_style = persona.get("communication_style", "Samimiy, do'stona, madaniyatli va lo'nda.")
            custom_rules = persona.get("custom_rules", "")

            # Salomlashish cheklovi
            greeting_rule = (
                "🛑 QAT'IY QOIDA: Ushbu suhbatdosh bilan allaqachon salomlashilgan yoki suhbat davom etmoqda. "
                "HECH QACHON 'Salom', 'Assalomu alaykum' yoki shunga o'xshash salom so'zlarini qayta ishlatmang! "
                "To'g'ridan-to'g'ri masalaning o'ziga, savolga yoki mavzuga javob bering."
            ) if already_greeted else (
                "Agar bu yangi suhbatning eng birinchi xabari bo'lsa, qisqa xushmuomala salomlashishingiz mumkin. "
                "Lekin agar salomlashish shart bo'lmasa, darhol javobga o'ting."
            )

            if mode == "as_me":
                instruction = (
                    f"Siz to'g'ridan-to'g'ri Telegram akkaunt egasisiz (Ismingiz: {owner_name}). Siz o'z nomingizdan yozasiz!\n"
                    f"Siz haqingizda ma'lumotlar:\n{about_me}\n"
                    f"Muloqot uslubingiz: {comm_style}\n"
                    f"Qo'shimcha ko'rsatmalar:\n{custom_rules}\n"
                    f"Vaziyat / Holatingiz: {custom_prompt}\n"
                    f"Suhbatdosh: {sender_name}.\n\n"
                    f"{greeting_rule}\n\n"
                    "MUHIM TALABLAR:\n"
                    "1. Birinchi shaxsda ('men', 'hali ko'rib chiqaman', 'bo'shagach yozaman') gapiring.\n"
                    "2. Aslo o'zingizni sun'iy intellekt, bot yoki kotib deb aytmang! Oddiy inson kabi tabiiy va jonli yozing.\n"
                    "3. Xabarlarga 1-3 ta qisqa jumla bilan, Telegram chat uslubida javob bering (juda uzun bo'lmasin)."
                )
            else:
                instruction = (
                    f"Siz Telegram akkaunt egasining ({owner_name}ning) shaxsiy AI Kotibisiz (Yordamchisisiz).\n"
                    f"Egasi haqida ma'lumotlar:\n{about_me}\n"
                    f"Uslub: {comm_style}\n"
                    f"Ko'rsatmalar: {custom_rules}\n"
                    f"Hozirgi holat: {custom_prompt}\n"
                    f"Suhbatdosh: {sender_name}.\n\n"
                    f"{greeting_rule}\n\n"
                    "MUHIM TALABLAR:\n"
                    "1. Egasi hozir biroz bandligini va xabarni unga yetkazib qo'yishingizni ayting.\n"
                    "2. O'ta xushmuomala, madaniyatli va professional yordamchi sifatida muloqot qiling.\n"
                    "3. Qisqa va aniq javob bering (1-2 jumla)."
                )

            # Tarixni Google GenAI Content formatiga keltirish
            contents_list = []
            if chat_history:
                for item in chat_history[-6:]:
                    role = "user" if item.get("role") == "user" else "model"
                    contents_list.append(types.Content(
                        role=role,
                        parts=[types.Part.from_text(text=item.get("text", ""))]
                    ))

            # Hozirgi xabarni qo'shish
            contents_list.append(types.Content(
                role="user",
                parts=[types.Part.from_text(text=message_text)]
            ))

            def _call(client: genai.Client, model: str):
                return client.models.generate_content(
                    model=model,
                    contents=contents_list,
                    config=types.GenerateContentConfig(
                        system_instruction=instruction,
                        temperature=0.6,
                    )
                )

            reply = await self._execute_with_resilience("Userbot agent javobi", _call)
            if reply.startswith("⚠️"):
                return "Xabaringizni ko'rdim, bo'shashim bilanoq o'zim yozaman."
            return reply
        except Exception as e:
            logger.error(f"AI Agent javob yaratishda xatolik: {e}")
            return "Xabaringizni oldim, tez orada o'zim bog'lanaman."

    async def summarize_chat_messages(self, chat_title: str, messages_text: str) -> str:
        """Guruh, kanal yoki botdagi so'nggi xabarlarni tahlil qilish va konspektini berish"""
        try:
            prompt = (
                f"Quyida '{chat_title}' Telegram chat/kanalidagi so'nggi xabarlar berilgan. "
                "Ularni diqqat bilan o'rganib chiqib, o'zbek tilida eng muhim mavzular, yangiliklar va xulosalarni "
                "chiroyli punktlar ko'rinishida qisqacha xulosa (konspekt) qilib bering:\n\n"
                f"{messages_text}"
            )

            def _call(client: genai.Client, model: str):
                return client.models.generate_content(
                    model=model,
                    contents=prompt,
                    config=types.GenerateContentConfig(
                        temperature=0.4,
                    )
                )

            return await self._execute_with_resilience("Chat konspekti", _call)
        except Exception as e:
            logger.error(f"Konspekt yaratishda xatolik: {e}")
            return "Xabarlarni konspekt qilishda xatolik yuz berdi."
