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
                # Bloklanmaslik uchun alohida thread'da bajaramiz
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

                if is_invalid:
                    logger.error(f"API kalit yaroqsiz! Kalitni almashtiramiz...")
                    self._rotate_key()
                    await asyncio.sleep(0.5)
                    continue

                if is_quota:
                    # Kvota tugaganda: keyingi API kalitga o'tamiz
                    self._rotate_key()
                    # Agar bir nechta kalit bo'lmasa, zaxira modelga o'tamiz (har modelning o'z kvotasi bor)
                    if len(self.api_keys) <= 1:
                        self._rotate_model()
                    await asyncio.sleep(1.0)
                    continue

                if is_503:
                    # 503 UNAVAILABLE (High demand) holatida zaxira modelga o'tamiz va biroz kutamiz
                    self._rotate_model()
                    delay = 1.0 * attempt
                    await asyncio.sleep(delay)
                    continue

                # Boshqa kutilmagan xatolik bo'lsa biroz kutib qayta urinish
                await asyncio.sleep(1.0)

        # Barcha urinishlar tugaganda ham xatolik yuz bersa, foydalanuvchiga madaniyatli javob berish
        logger.error(f"Gemini {operation_name} barcha urinishlardan so'ng ishlamadi. Oxirgi xato: {last_error}")
        if "503" in last_error or "UNAVAILABLE" in last_error:
            return "⚠️ AI serverlarida ayni paytda juda yuqori yuklanish kuzatilmoqda. Iltimos, 1-2 daqiqadan so'ng qayta yozib ko'ring."
        elif "429" in last_error or "quota" in last_error.lower() or "RESOURCE_EXHAUSTED" in last_error:
            return "⚠️ API so'rovlar limiti (kvotasi) vaqtinchalik to'ldi. Iltimos, bir necha daqiqadan so'ng qayta urinib ko'ring."
        else:
            return "⚠️ Server bilan ulanishda vaqtinchalik xatolik yuz berdi. Iltimos, birozdan so'ng qayta urinib ko'ring."

    async def generate_response(self, user_id: int, user_message: str) -> str:
        """Foydalanuvchi matnli xabariga AI javobini olish (non-blocking, sliding window chat history)"""
        try:
            history = self._user_histories.get(user_id, [])
            # Tokenlar va limitlarni tejash uchun oxirgi 12 ta xabarni olamiz
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

            # Agar javob muvaffaqiyatli olingan bo'lsa, uni suhbat tarixiga yozamiz
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
        """Foydalanuvchi yuborgan rasmni tahlil qilish (Multimodal, non-blocking)"""
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
            return "⚠️ Rasmni tahlil qilishda xatolik yuz berdi. Iltimos, qayta urinib ko'ring."

    async def process_audio(self, user_id: int, audio_bytes: bytes, mime_type: str = "audio/ogg") -> str:
        """Foydalanuvchi yuborgan ovozli xabarni eshitib, tushunib javob qaytarish (Multimodal Audio)"""
        try:
            audio_part = types.Part.from_bytes(data=audio_bytes, mime_type=mime_type)
            prompt = (
                "Foydalanuvchi sizga ovozli xabar (audio) yubordi. "
                "Ovozni diqqat bilan tinglang, nima deyilganini to'liq tushuning va unga foydalanuvchi tilida (asosan o'zbek tilida) "
                "aniq, to'liq, do'stona va ravon javob bering."
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
            return "⚠️ Ovozli xabarni eshitishda xatolik yuz berdi. Iltimos, qayta urinib ko'ring."

    async def generate_agent_reply(
        self,
        sender_name: str,
        message_text: str,
        custom_prompt: str,
        mode: str = "as_me",
        owner_info: str = ""
    ) -> str:
        """Shaxsiy Telegram akkaunti (Userbot AI Agent) nomidan kelgan xabarlarga aqlli javob qaytarish"""
        try:
            if mode == "as_me":
                instruction = (
                    "Siz to'g'ridan-to'g'ri Telegram akkaunt egasisiz (Ismingiz: Azizbek). Siz o'zingiz nomingizdan gapirasiz!\n"
                    f"Akkaunt egasi (siz) haqingizda ma'lumotlar:\n{owner_info}\n\n"
                    f"Hozirgi holat va ko'rsatmalar:\n{custom_prompt}\n\n"
                    f"Suhbatdosh ismi: {sender_name}.\n"
                    "MUHIM QOIDALAR:\n"
                    "- Birinchi shaxsda ('men', 'hozir bandman', 'ko'rib chiqaman', 'salom') gapiring.\n"
                    "- Aslo o'zingizni bot, sun'iy intellekt yoki dastur deb atamang! Oddiy inson kabi tabiiy, do'stona va xushmuomala yozing.\n"
                    "- Qisqa, lo'nda va insoniy yozing (1-2 jumla kifoya)."
                )
            else:
                instruction = (
                    "Siz Telegram akkaunt egasining (Azizbekning) shaxsiy AI Kotibisiz (Agentisiz).\n"
                    f"Egasi haqida ma'lumotlar:\n{owner_info}\n\n"
                    f"Hozirgi ko'rsatmalar:\n{custom_prompt}\n\n"
                    f"Suhbatdosh ismi: {sender_name}.\n"
                    "MUHIM QOIDALAR:\n"
                    "- Egasi hozir biroz bandligini va xabarni unga yetkazib qo'yishingizni ayting.\n"
                    "- O'ta samimiy, xushmuomala va insoniy muloqot qiling.\n"
                    "- Qisqa va lo'nda javob bering (1-2 jumla)."
                )

            def _call(client: genai.Client, model: str):
                return client.models.generate_content(
                    model=model,
                    contents=message_text,
                    config=types.GenerateContentConfig(
                        system_instruction=instruction,
                        temperature=0.6,
                    )
                )

            reply = await self._execute_with_resilience("Userbot agent javobi", _call)
            if reply.startswith("⚠️"):
                return "Salom! Xabaringizni ko'rdim, bo'shashim bilanoq o'zim yozaman."
            return reply
        except Exception as e:
            logger.error(f"AI Agent javob yaratishda xatolik: {e}")
            return "Salom! Xabaringizni oldim, tez orada o'zim bog'lanaman."
