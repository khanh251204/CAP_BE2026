"""
Engine OCR dự phòng bằng Gemini (đọc ảnh -> văn bản), dùng khi máy chủ không có GPU cho Vintern
hoặc Vintern lỗi. Cùng đầu ra với VinternEngine nên các bước sau (thêm dấu, tách dòng, đối chiếu) giữ nguyên.

Lưu ý: ảnh hóa đơn được gửi tới dịch vụ Google và tính phí token.
"""
import logging
import os
import time
from io import BytesIO
from typing import Dict

from app.ai.ocr.engine import OCR_PROMPT, OcrUnavailableError
from app.ai.ocr.preprocess import resize_long_side
from app.ai.ocr.text_utils import collapse_repeats

logger = logging.getLogger(__name__)

_PROMPT = OCR_PROMPT.replace("<image>\n", "")
_GEMINI_MAX_SIDE = 1280


class GeminiOcrEngine:
    name = "gemini"

    def __init__(self, model: str):
        self.model = model
        self._client = None

    def _get_client(self):
        if self._client is None:
            from app.configs.settings import settings
            api_key = settings.GEMINI_API_KEY or os.getenv("GEMINI_API_KEY")
            if not api_key:
                raise OcrUnavailableError("GEMINI_API_KEY chưa được cấu hình")
            from google import genai
            from google.genai import types
            self._client = genai.Client(api_key=api_key, http_options=types.HttpOptions(timeout=45000))
        return self._client

    def extract_text(self, image) -> Dict:
        from google.genai import types
        resized = resize_long_side(image, _GEMINI_MAX_SIDE)
        buf = BytesIO()
        resized.convert("RGB").save(buf, format="JPEG", quality=82)
        image_part = types.Part.from_bytes(data=buf.getvalue(), mime_type="image/jpeg")
        start = time.perf_counter()
        try:
            config_kwargs: Dict = {"temperature": 0.0}
            if hasattr(types, "ThinkingConfig"):
                config_kwargs["thinking_config"] = types.ThinkingConfig(thinking_budget=0)
            try:
                response = self._get_client().models.generate_content(
                    model=self.model,
                    contents=[image_part, _PROMPT],
                    config=types.GenerateContentConfig(**config_kwargs),
                )
            except Exception as cfg_err:
                if "thinking_config" not in config_kwargs:
                    raise
                logger.debug("[OCR] Model %s không hỗ trợ thinking_budget=0 (%s), thử lại mặc định", self.model, cfg_err)
                response = self._get_client().models.generate_content(
                    model=self.model,
                    contents=[image_part, _PROMPT],
                    config=types.GenerateContentConfig(temperature=0.0),
                )
        except OcrUnavailableError:
            raise
        except Exception as e:  # noqa: BLE001
            raise OcrUnavailableError(f"Gemini lỗi: {str(e)[:200]}") from e
        return {"text": collapse_repeats(response.text or ""), "n_tiles": None,
                "latency_ms": round((time.perf_counter() - start) * 1000, 1)}
