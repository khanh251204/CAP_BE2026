import os
import json

from dotenv import load_dotenv
from app.ai.llm.groq_client_pool import get_groq_pool

from app.services.audio.hallucination import is_speech_hallucination

load_dotenv()


class GroqService:
    """
    Service xử lý:
    1. Speech-to-Text bằng Groq Whisper
    2. Phân tích transaction bằng AI Benchmark Model Provider (Pluggable)
    """

    def __init__(self):
        # ========================================================
        # GROQ CLIENT cho Whisper STT
        # Dùng pool nhiều key: GROQ_API_KEY lỗi thì tự chuyển sang GROQ_API_KEY_2
        # ========================================================
        self.groq = get_groq_pool()
        self.transcription_model = "whisper-large-v3-turbo"

        # ========================================================
        # PLUGGABLE AI MODEL INITIALIZATION
        # ========================================================
        # Đọc cấu hình từ .env (ACTIVE_AI_MODEL), mặc định là qwen_27b (qwen/qwen3.8-27b)
        self.active_ai_model = (os.getenv("ACTIVE_AI_MODEL") or "qwen_27b").strip()

        from app.ai.models import get_model_provider

        _GROQ_ALIASES = {
            "qwen_27b": "qwen/qwen3.8-27b",
            "groq_qwen_27b": "qwen/qwen3.8-27b",
            "qwen": "qwen/qwen3.8-27b",
            "groq_120b": "openai/gpt-oss-120b",
            "groq_20b": "openai/gpt-oss-20b",
        }

        key_lower = self.active_ai_model.lower()
        if key_lower in _GROQ_ALIASES:
            self.analysis_model = _GROQ_ALIASES[key_lower]
            self.provider = get_model_provider(provider_name="groq", model_name=self.analysis_model)

        elif key_lower == "qwen_local":
            # Qwen2.5 không có bản 2.5B; dùng 1.5B (khớp mặc định của LlamaLocalModel)
            self.analysis_model = "Qwen/Qwen2.5-1.5B-Instruct"
            self.provider = get_model_provider(provider_name="llama_local", model_name=self.analysis_model)

        elif key_lower.startswith("local:"):
            self.analysis_model = self.active_ai_model.split(":", 1)[1].strip()
            self.provider = get_model_provider(provider_name="llama_local", model_name=self.analysis_model)

        else:
            # Cho phép điền thẳng tên model Groq trong .env (vd: ACTIVE_AI_MODEL=qwen/qwen3.8-27b)
            self.analysis_model = self.active_ai_model
            self.provider = get_model_provider(provider_name="groq", model_name=self.analysis_model)

    # ============================================================
    # SPEECH TO TEXT
    # ============================================================

    def transcribe(self, file_path: str) -> str:
        """
        Chuyển file âm thanh thành văn bản
        bằng Groq Whisper API.
        """
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"Không tìm thấy file: {file_path}")

        with open(file_path, "rb") as file:
            audio_bytes = file.read()

        transcription = self.groq.call(
            lambda client: client.audio.transcriptions.create(
                file=(os.path.basename(file_path), audio_bytes),
                model=self.transcription_model,
                language="vi",
                prompt="Giao dịch bán hàng, mua hàng, nhập kho, xuất kho, kiểm kho, ghi nợ, chi tiền, giá tiền, số lượng sản phẩm.",
                temperature=0.0
            )
        )

        text = transcription.text.strip()
        if is_speech_hallucination(text):
            return ""

        return text

    # ============================================================
    # ANALYZE TRANSACTION
    # ============================================================

    def analyze_transaction(
        self,
        text: str,
        knowledge: str = ""
    ) -> dict:
        """
        Phân tích câu giao dịch bằng LLM thông qua Model Provider (Pluggable).
        """
        if not text or not text.strip():
            raise ValueError("Text giao dịch không được để trống.")

        try:
            # Sử dụng Model Provider từ app.ai.models
            # (Hàm predict sẽ tự động ghép system prompt và format JSON)
            # business_type không được dùng trong prompt: LLM chỉ trích xuất intent/entity,
            # quy tắc theo loại hình kinh doanh do backend áp dụng (AGENTS.md 2.1)
            benchmark_result = self.provider.predict(
                text=text,
                knowledge=knowledge
            )

            if benchmark_result.get("error"):
                raise ValueError(f"AI Provider Error: {benchmark_result['error']}")

            parsed = benchmark_result.get("prediction", {})

            # Gắn thêm metadata để tương thích với codebase cũ
            from app.ai.version import get_ai_metadata, PROMPT_VERSION, AI_PIPELINE_VERSION
            parsed.setdefault("provider", self.provider.__class__.__name__)
            parsed.setdefault("model", self.analysis_model)
            parsed.setdefault("prompt_version", PROMPT_VERSION)
            parsed.setdefault("pipeline_version", AI_PIPELINE_VERSION)
            parsed.setdefault("_ai_metadata", get_ai_metadata(self.analysis_model))

            return parsed

        except Exception as error:
            from app.services.system_log_service import log_event
            log_event(
                level="ERROR",
                step="LLM",
                message=f"Lỗi khi chạy Pluggable AI Model: {str(error)}",
                detail={"model": self.analysis_model, "text": text, "error": str(error)},
                api_path="/ai/analyze"
            )
            raise error
