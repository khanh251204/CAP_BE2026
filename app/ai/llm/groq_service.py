import os
import json

from dotenv import load_dotenv
from groq import Groq

from app.ai.prompts.main import get_system_prompt


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

                    temperature=0.0
                )
            )

        return transcription.text.strip()

    
    
    
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
        # USER PROMPT & EXTRA GUIDANCE FOR KIỂM KHO / PRODUCTS
        # ========================================================

        intent_guidance = """
        HƯỚNG DẪN BỔ SUNG CHO INTENT VÀ ENTITY:
        - Nếu người dùng muốn kiểm tra tồn kho, xem hàng tồn (ví dụ: "kiểm kho", "check kho", "mặt hàng X còn không"), hãy gán intent là "kiem_kho".
        - Bắt buộc trích xuất tên sản phẩm/mặt hàng vào entity có key là "product".
        """

        user_prompt = f"""
        {intent_guidance.strip()}

        USER INPUT:
        {text}
        """

        if knowledge and knowledge.strip():
            user_prompt += f"""

        RELEVANT KNOWLEDGE:
        {knowledge}

        Use the retrieved knowledge above when interpreting
        Vietnamese dialects, slang, units, currency and
        product packaging.

        If a dialect/slang expression appears in the user input,
        normalize it according to the retrieved knowledge.

        Do not invent information that is not present
        in the retrieved knowledge.
        """

        # ========================================================
        # CALL GROQ
        # ========================================================

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

        # ========================================================
        # GET RESULT
        # ========================================================

        result = (
            response
            .choices[0]
            .message
            .content
            .strip()
        )

        # ========================================================
        # PARSE JSON
        # ========================================================

        try:
            return json.loads(result)

        except json.JSONDecodeError as error:
            raise ValueError(
                f"Groq trả về JSON không hợp lệ: {result}"
            ) from error