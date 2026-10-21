import os
import json

from dotenv import load_dotenv
from groq import Groq

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
        # GROQ CLIENT (Vẫn giữ cho Whisper STT)
        # ========================================================
        api_key = os.getenv("GROQ_API_KEY")
        if not api_key:
            raise ValueError("GROQ_API_KEY chưa được cấu hình trong .env")

        self.client = Groq(api_key=api_key)
        self.transcription_model = "whisper-large-v3-turbo"

        # ========================================================
        # PLUGGABLE AI MODEL INITIALIZATION
        # ========================================================
        # Đọc cấu hình từ .env, mặc định là groq_120b nếu không set
        self.active_ai_model = os.getenv("ACTIVE_AI_MODEL", "groq_120b")
        
        # pyrefly: ignore [missing-import]
        from ai_benchmark_qwen.models import get_model_provider
        
        if self.active_ai_model == "groq_20b":
            self.provider = get_model_provider(provider_name="groq", model_name="openai/gpt-oss-20b")
            self.analysis_model = "openai/gpt-oss-20b"
            
        elif self.active_ai_model == "groq_120b":
            self.provider = get_model_provider(provider_name="groq", model_name="openai/gpt-oss-120b")
            self.analysis_model = "openai/gpt-oss-120b"
            
        elif self.active_ai_model == "qwen_local":
            self.provider = get_model_provider(provider_name="llama_local", model_name="Qwen/Qwen2.5-2.5B-Instruct")
            self.analysis_model = "Qwen/Qwen2.5-2.5B-Instruct"

            
        else:
            # Fallback về Groq 20B
            self.provider = get_model_provider(provider_name="groq", model_name="openai/gpt-oss-20b")
            self.analysis_model = "openai/gpt-oss-20b"

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
            transcription = (
                self.client.audio.transcriptions.create(
                    file=(os.path.basename(file_path), file.read()),
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
        Phân tích câu giao dịch bằng LLM thông qua Plug-in của ai_benchmark.
        """
        if not text or not text.strip():
            raise ValueError("Text giao dịch không được để trống.")

        try:
            # Sử dụng Model Provider từ ai_benchmark
            # (Hàm predict sẽ tự động ghép system prompt và format JSON)
            benchmark_result = self.provider.predict(
                text=text, 
                business_type="PRODUCER", # Mặc định hoặc truyền động nếu cần
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
            parsed.setdefault("_ai_metadata", get_ai_metadata())
            
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