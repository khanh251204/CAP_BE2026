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
        # Đọc cấu hình từ .env, mặc định là qwen_27b nếu không set
        self.active_ai_model = os.getenv("ACTIVE_AI_MODEL", "qwen_27b").strip()
        custom_llm_model = os.getenv("AI_LLM_MODEL", "").strip()

        from app.ai.models import get_model_provider

        if custom_llm_model:
            self.provider = get_model_provider(provider_name="groq", model_name=custom_llm_model)
            self.analysis_model = custom_llm_model

        elif self.active_ai_model in ("qwen_27b", "groq_qwen_27b", "qwen/qwen3.8-27b", "Qwen/Qwen3.5-27B"):
            qwen_27b_id = os.getenv("QWEN_27B_MODEL_ID", "qwen/qwen3.8-27b").strip()
            self.provider = get_model_provider(provider_name="groq", model_name=qwen_27b_id)
            self.analysis_model = qwen_27b_id

        elif self.active_ai_model in ("qwen_27b_local", "Qwen/Qwen3.5-27B-local"):
            self.provider = get_model_provider(provider_name="llama_local", model_name="Qwen/Qwen3.5-27B")
            self.analysis_model = "Qwen/Qwen3.5-27B"

        elif self.active_ai_model == "groq_20b":
            self.provider = get_model_provider(provider_name="groq", model_name="openai/gpt-oss-20b")
            self.analysis_model = "openai/gpt-oss-20b"

        elif self.active_ai_model == "groq_120b":
            self.provider = get_model_provider(provider_name="groq", model_name="openai/gpt-oss-120b")
            self.analysis_model = "openai/gpt-oss-120b"

        elif self.active_ai_model == "qwen_local":
            # Qwen2.5 không có bản 2.5B; dùng 1.5B (khớp mặc định của LlamaLocalModel)
            self.provider = get_model_provider(provider_name="llama_local", model_name="Qwen/Qwen2.5-1.5B-Instruct")
            self.analysis_model = "Qwen/Qwen2.5-1.5B-Instruct"

        elif "/" in self.active_ai_model:
            # Cho phép truyền trực tiếp model_id bất kỳ qua ACTIVE_AI_MODEL trong .env
            self.provider = get_model_provider(provider_name="groq", model_name=self.active_ai_model)
            self.analysis_model = self.active_ai_model

        else:
            # Fallback về Qwen 27B trên Groq
            self.provider = get_model_provider(provider_name="groq", model_name="qwen/qwen3.8-27b")
            self.analysis_model = "qwen/qwen3.8-27b"

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
