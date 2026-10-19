import asyncio
import io
import logging
from typing import Dict, Optional
from PIL import Image
from google import genai
from google.genai import types

import config

logger = logging.getLogger(__name__)

class GeminiService:
    def __init__(self):
        self.model_name = config.get_gemini_model()
        self.system_prompt = config.SYSTEM_PROMPT
        self._client: Optional[genai.Client] = None
        # Har bir foydalanuvchi uchun alohida chat sessiyasi
        self._user_chats: Dict[int, any] = {}

    @property
    def client(self) -> genai.Client:
        if self._client is None:
            api_key = config.get_gemini_api_key()
            if not api_key:
                raise ValueError("GEMINI_API_KEY sozlanmagan. Iltimos, .env faylini tekshiring.")
            self._client = genai.Client(api_key=api_key)
        return self._client

    def _get_or_create_chat(self, user_id: int):
        """Foydalanuvchining avvalgi suhbat tarixini saqlaydigan chat obyektini olish yoki yangi yaratish"""
        if user_id not in self._user_chats:
            try:
                # Yangi chat sessiyasi yaratish
                chat = self.client.chats.create(
                    model=self.model_name,
                    config=types.GenerateContentConfig(
                        system_instruction=self.system_prompt,
                        temperature=0.7,
                    )
                )
                self._user_chats[user_id] = chat
            except Exception as e:
                logger.error(f"Chat yaratishda xatolik: {e}")
                raise e
        return self._user_chats[user_id]

    def reset_chat(self, user_id: int) -> bool:
        """Foydalanuvchi suhbat tarixini tozalash (yangi suhbat boshlash)"""
        if user_id in self._user_chats:
            del self._user_chats[user_id]
            return True
        return False

    async def generate_response(self, user_id: int, user_message: str) -> str:
        """Foydalanuvchi matnli xabariga AI javobini olish (non-blocking)"""
        try:
            chat = self._get_or_create_chat(user_id)
            # Event loop bloklanmasligi uchun alohida oqimda ishlatamiz
            response = await asyncio.to_thread(chat.send_message, user_message)
            if response and response.text:
                return response.text
            return "Kechirasiz, javob matni bo'sh qaytdi. Boshqattan urinib ko'ring."
        except Exception as e:
            logger.error(f"Xabar yuborishda xatolik: {e}")
            err_msg = str(e)
            if "API_KEY_INVALID" in err_msg or "invalid api key" in err_msg.lower():
                return "⚠️ Xatolik: Gemini API kaliti noto'g'ri ko'rsatilgan. Iltimos, .env faylini tekshiring."
            elif "RESOURCE_EXHAUSTED" in err_msg or "quota" in err_msg.lower():
                return "⚠️ Xatolik: API so'rovlar limiti (kvota) tugadi. Birozdan so'ng qayta urinib ko'ring."
            else:
                return f"⚠️ Xatolik yuz berdi: {err_msg[:200]}"

    async def analyze_image(self, user_id: int, image_bytes: bytes, caption: Optional[str] = None) -> str:
        """Foydalanuvchi yuborgan rasmni tahlil qilish (Multimodal, non-blocking)"""
        try:
            image = Image.open(io.BytesIO(image_bytes))
            prompt = caption if caption else "Ushbu rasmni batafsil tasvirlab bering va undagi muhim ma'lumotlarni tahlil qiling."
            
            def _call_gemini_image():
                return self.client.models.generate_content(
                    model=self.model_name,
                    contents=[prompt, image],
                    config=types.GenerateContentConfig(
                        system_instruction=self.system_prompt,
                        temperature=0.6,
                    )
                )

            response = await asyncio.to_thread(_call_gemini_image)
            if response and response.text:
                return response.text
            return "Kechirasiz, rasmni tahlil qilishda javob olib bo'lmadi."
        except Exception as e:
            logger.error(f"Rasm tahlilida xatolik: {e}")
            return f"⚠️ Rasmni tahlil qilishda xatolik yuz berdi: {str(e)[:200]}"

    async def process_audio(self, user_id: int, audio_bytes: bytes, mime_type: str = "audio/ogg") -> str:
        """Foydalanuvchi yuborgan ovozli xabarni eshitib, tushunib javob qaytarish (Multimodal Audio)"""
        try:
            audio_part = types.Part.from_bytes(data=audio_bytes, mime_type=mime_type)
            prompt = (
                "Foydalanuvchi sizga ovozli xabar (audio) yubordi. "
                "Ovozni diqqat bilan tinglang, nima deyilganini to'liq tushuning va unga foydalanuvchi tilida (asosan o'zbek tilida) "
                "aniq, to'liq, do'stona va ravon javob bering."
            )

            def _call_gemini_audio():
                return self.client.models.generate_content(
                    model=self.model_name,
                    contents=[audio_part, prompt],
                    config=types.GenerateContentConfig(
                        system_instruction=self.system_prompt,
                        temperature=0.7,
                    )
                )

            response = await asyncio.to_thread(_call_gemini_audio)
            if response and response.text:
                return response.text
            return "Kechirasiz, ovozli xabarni tahlil qilishda javob olib bo'lmadi."
        except Exception as e:
            logger.error(f"Ovozli xabarni tahlil qilishda xatolik: {e}")
            return f"⚠️ Ovozli xabarni eshitishda xatolik yuz berdi: {str(e)[:200]}"

    async def generate_agent_reply(self, sender_name: str, message_text: str, custom_prompt: str) -> str:
        """Shaxsiy Telegram akkaunti (Userbot AI Agent) nomidan kelgan xabarlarga aqlli javob qaytarish"""
        try:
            instruction = (
                f"{custom_prompt}\n\n"
                f"Siz hozir Telegram akkaunt egasining shaxsiy AI Kotibisiz (Agentisiz).\n"
                f"Suhbatdosh: {sender_name}.\n"
                f"Asosiy vazifangiz:\n"
                f"- Foydalanuvchi bilan o'ta samimiy, xushmuomala va insoniy muloqot qiling.\n"
                f"- Egasi hozir bandligi yoki tez orada ko'rib chiqishini bildiring.\n"
                f"- Ortiqcha cho'zmasdan, lo'nda va tabiiy javob bering (1-3 jumla)."
            )

            def _call():
                return self.client.models.generate_content(
                    model=self.model_name,
                    contents=message_text,
                    config=types.GenerateContentConfig(
                        system_instruction=instruction,
                        temperature=0.6,
                    )
                )

            response = await asyncio.to_thread(_call)
            if response and response.text:
                return response.text.strip()
            return "Salom! Xabaringizni qabul qildim, tez orada o'zim ko'rib chiqib javob yozaman."
        except Exception as e:
            logger.error(f"AI Agent javob yaratishda xatolik: {e}")
            return "Salom! Xabaringizni qabul qildim, bo'shashim bilanoq o'zim yozaman."


