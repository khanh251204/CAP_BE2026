"""
AI Pipeline and Model Versioning Configuration for Capstone 1.
Cung cấp định danh phiên bản rõ ràng cho mô hình, prompt và pipeline xử lý AI.
"""
from typing import Dict, Any, Optional

AI_PIPELINE_VERSION = "1.0.0"

STT_PROVIDER = "Groq"
STT_MODEL = "whisper-large-v3-turbo"
STT_MODEL_VERSION = "2024-v3-turbo"

LLM_PROVIDER = "Groq"
LLM_MODEL = "qwen/qwen3.8-27b"
LLM_MODEL_VERSION = "qwen3.8-27b"
PROMPT_VERSION = "1.2.0"


def get_ai_metadata(llm_model: Optional[str] = None) -> Dict[str, Any]:
    """
    Trả về metadata phiên bản chuẩn hóa cho quá trình suy luận AI.
    llm_model: model thực tế đang chạy (ACTIVE_AI_MODEL có thể khác mặc định).
    """
    model = llm_model or LLM_MODEL
    model_version = LLM_MODEL_VERSION if model == LLM_MODEL else model.split("/")[-1]
    return {
        "pipeline_version": AI_PIPELINE_VERSION,
        "prompt_version": PROMPT_VERSION,
        "stt": {
            "provider": STT_PROVIDER,
            "model": STT_MODEL,
            "version": STT_MODEL_VERSION,
        },
        "llm": {
            "provider": LLM_PROVIDER,
            "model": model,
            "version": model_version,
            "prompt_version": PROMPT_VERSION,
        }
    }
