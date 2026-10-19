import io
import re
import logging
import edge_tts

logger = logging.getLogger(__name__)

# O'zbek ovozlari: 'uz-UZ-SardorNeural' (erkak), 'uz-UZ-MadinaNeural' (ayol)
DEFAULT_VOICE = "uz-UZ-SardorNeural"

def clean_text_for_speech(text: str) -> str:
    """Markdown belgilari va keraksiz simvollarni tozalash"""
    # Markdown kod bloklari va teglarni tozalash
    text = re.sub(r"```[\s\S]*?```", " Kod bloki. ", text)
    text = re.sub(r"`.*?`", "", text)
    # * va _ larni olib tashlash
    text = re.sub(r"[\*\_~#]", "", text)
    # Ko'p bo'shliqlarni bittaga keltirish
    text = re.sub(r"\s+", " ", text).strip()
    return text

async def synthesize_voice(text: str, voice: str = DEFAULT_VOICE) -> bytes:
    """Matnni tabiiy ovozga (TTS) aylantirib baytlarni qaytarish"""
    cleaned = clean_text_for_speech(text)
    # Agar matn juda uzun bo'lsa, dastlabki 1000 belgisini ovozga aylantiramiz
    if len(cleaned) > 1000:
        cleaned = cleaned[:1000] + "... Davomi matnda yozilgan."
    
    if not cleaned:
        cleaned = "Javob tayyor."

    try:
        communicate = edge_tts.Communicate(cleaned, voice=voice)
        audio_stream = io.BytesIO()
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                audio_stream.write(chunk["data"])
        return audio_stream.getvalue()
    except Exception as e:
        logger.error(f"TTS ovoz yaratishda xatolik: {e}")
        raise e
