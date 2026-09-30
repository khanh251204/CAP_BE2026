"""
AI Pipeline and Model Versioning Configuration for Capstone 1.
Cung cấp định danh phiên bản rõ ràng cho mô hình, prompt và pipeline xử lý AI.
"""
from typing import Dict, Any

AI_PIPELINE_VERSION = "1.0.0"

STT_PROVIDER = "Groq"
STT_MODEL = "whisper-large-v3-turbo"
STT_MODEL_VERSION = "2024-v3-turbo"

LLM_PROVIDER = "Groq"
LLM_MODEL = "openai/gpt-oss-120b"
LLM_MODEL_VERSION = "llama-3.3-70b-v1"
PROMPT_VERSION = "1.2.0"


def get_ai_metadata() -> Dict[str, Any]:
    """Trả về metadata phiên bản chuẩn hóa cho quá trình suy luận AI."""
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
            "model": LLM_MODEL,
            "version": LLM_MODEL_VERSION,
            "prompt_version": PROMPT_VERSION,
        }
    }
