import os
import logging
from typing import Optional
# pyrefly: ignore [missing-import]
from dotenv import load_dotenv

# pyrefly: ignore [missing-import]
from google import genai
# pyrefly: ignore [missing-import]
# pyrefly: ignore [missing-import]
from google.genai import types
from app.services.audio.hallucination import is_speech_hallucination

load_dotenv()

logger = logging.getLogger(__name__)

MIME_TYPE_MAP = {
    ".wav": "audio/wav",
    ".mp3": "audio/mp3",
    ".m4a": "audio/m4a",
    ".aac": "audio/aac",
    ".ogg": "audio/ogg",
    ".flac": "audio/flac",
    ".webm": "audio/webm",
}


class GeminiService:
    """
    Service xử lý:
    Speech-to-Text bằng Google Gemini API (Multimodal Audio Transcription).
    """

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("GEMINI_API_KEY")
        if not self.api_key:
            raise ValueError("GEMINI_API_KEY chưa được cấu hình trong .env")

        self.client = genai.Client(api_key=self.api_key)
        self.transcription_model = os.getenv("GEMINI_STT_MODEL", "gemini-3.6-flash")

    def transcribe(self, file_path: str) -> str:
        """
        Chuyển file âm thanh thành văn bản tiếng Việt bằng Gemini API.
        
        Args:
            file_path: Đường dẫn tới file âm thanh (.wav, .m4a, .mp3, ...)
            
        Returns:
            Văn bản tiếng Việt được phiên âm.
        """
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"Không tìm thấy file: {file_path}")

        ext = os.path.splitext(file_path)[1].lower()
        mime_type = MIME_TYPE_MAP.get(ext, "audio/wav")

        with open(file_path, "rb") as f:
            audio_bytes = f.read()

        if not audio_bytes:
            return ""

        prompt = (
            "Bạn là một hệ thống chuyển đổi giọng nói thành văn bản (Speech-to-Text) tiếng Việt chính xác và trung thực.\n"
            "Hãy nghe đoạn âm thanh này và phiên âm lại chính xác từng từ tiếng Việt được nói trong đoạn băng.\n"
            "Quy tắc bắt buộc:\n"
            "- Chỉ trả về duy nhất nội dung văn bản được nói trong âm thanh, không thêm bất kỳ lời dẫn, giải thích hay định dạng markdown nào.\n"
            "- Nếu trong âm thanh chỉ là tiếng ồn, tiếng bíp hoặc không có tiếng người nói, hãy trả về chuỗi rỗng."
        )

        try:
            response = self.client.models.generate_content(
                model=self.transcription_model,
                contents=[
                    types.Part.from_bytes(data=audio_bytes, mime_type=mime_type),
                    prompt
                ],
                config=types.GenerateContentConfig(
                    temperature=0.0
                )
            )

            text = (response.text or "").strip()
            if is_speech_hallucination(text):
                return ""
            return text

        except Exception as e:
            logger.error(f"Gemini transcription error: {e}", exc_info=True)
            raise e
