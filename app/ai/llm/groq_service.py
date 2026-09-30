import os
import json

from dotenv import load_dotenv
from groq import Groq

from app.ai.prompts.main import get_system_prompt
from app.services.audio.hallucination import is_speech_hallucination



load_dotenv()


class GroqService:
    """
    Service xử lý:
    1. Speech-to-Text bằng Groq Whisper
    2. Phân tích transaction bằng LLM
    """

    def __init__(self):
        # ========================================================
        # API KEY
        # ========================================================

        api_key = os.getenv("GROQ_API_KEY")

        if not api_key:
            raise ValueError(
                "GROQ_API_KEY chưa được cấu hình trong .env"
            )

        # ========================================================
        # GROQ CLIENT
        # ========================================================

        self.client = Groq(
            api_key=api_key
        )

        # ========================================================
        # MODEL
        # ========================================================

        self.transcription_model = (
            "whisper-large-v3-turbo"
        )

        self.analysis_model = (
            # "llama-3.3-70b-versatile" 
            "openai/gpt-oss-120b"
        )

    # ============================================================
    # SPEECH TO TEXT
    # ============================================================

    def transcribe(
        self,
        file_path: str
    ) -> str:
        """
        Chuyển file âm thanh thành văn bản
        bằng Groq Whisper API.
        """

        if not os.path.exists(file_path):
            raise FileNotFoundError(
                f"Không tìm thấy file: {file_path}"
            )

        with open(file_path, "rb") as file:
            transcription = (
                self.client.audio.transcriptions.create(
                    file=(
                        os.path.basename(file_path),
                        file.read()
                    ),

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


    
    
    
    def analyze_transaction(
        self,
        text: str,
        knowledge: str = ""
    ) -> dict:
        """
        Phân tích câu giao dịch bằng LLM
        và trả về JSON.
        """

        if not text or not text.strip():
            raise ValueError(
                "Text giao dịch không được để trống."
            )

        # ========================================================
        # SYSTEM PROMPT
        # ========================================================

        system_prompt = get_system_prompt()

        # ========================================================
        # USER PROMPT
        # ========================================================

        user_prompt = f"USER INPUT:\n{text.strip()}"

        if knowledge and knowledge.strip():
            user_prompt += f"\n\nRELEVANT KNOWLEDGE:\n{knowledge.strip()}\n(Áp dụng kiến thức trên để chuẩn hóa từ lóng, phương ngữ hoặc quy cách đóng gói nếu có trong câu nói)."

        # ========================================================
        # CALL GROQ
        # ========================================================

        try:
            response = (
                self.client.chat.completions.create(
                    model=self.analysis_model,
                    temperature=0,
                    response_format={
                        "type": "json_object"
                    },
                    messages=[
                        {
                            "role": "system",
                            "content": system_prompt
                        },
                        {
                            "role": "user",
                            "content": user_prompt
                        }
                    ]
                )
            )

            result = (
                response
                .choices[0]
                .message
                .content
                .strip()
            )
        except Exception as api_err:
            from app.services.system_log_service import log_event
            log_event(
                level="ERROR",
                step="LLM",
                message=f"Groq API chat completion failed: {str(api_err)}",
                detail={"model": self.analysis_model, "error": str(api_err)},
                api_path="/ai/analyze"
            )
            raise api_err

        # ========================================================
        # PARSE JSON
        # ========================================================

        try:
            parsed = json.loads(result)
            if isinstance(parsed, dict):
                from app.ai.version import get_ai_metadata, PROMPT_VERSION, AI_PIPELINE_VERSION
                parsed.setdefault("provider", "Groq")
                parsed.setdefault("model", self.analysis_model)
                parsed.setdefault("prompt_version", PROMPT_VERSION)
                parsed.setdefault("pipeline_version", AI_PIPELINE_VERSION)
                parsed.setdefault("_ai_metadata", get_ai_metadata())
            return parsed

        except json.JSONDecodeError as error:
            from app.services.system_log_service import log_event
            log_event(
                level="ERROR",
                step="LLM",
                message=f"Groq trả về JSON không hợp lệ: {result[:200]}",
                detail={"model": self.analysis_model, "raw_result": result[:500], "error": str(error)},
                api_path="/ai/analyze"
            )
            raise ValueError(
                f"Groq trả về JSON không hợp lệ: {result}"
            ) from error