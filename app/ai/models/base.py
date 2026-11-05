import abc
import json
import re
import time
from typing import Dict, Any, List, Optional
from app.ai.prompts.main import get_system_prompt


class ModelProvider(abc.ABC):
    """Lớp cơ sở trừu tượng cho tất cả các mô hình LLM inference trong app/ai."""

    def __init__(self, model_name: str, system_prompt: Optional[str] = None):
        self.model_name = model_name
        self.system_prompt = system_prompt or get_system_prompt()

    def extract_json(self, raw_text: str) -> Dict[str, Any]:
        """
        Trích xuất an toàn JSON object từ output thô của LLM,
        hỗ trợ trường hợp LLM bọc trong ```json ... ``` hoặc có thẻ <think>...</think>.
        """
        if not raw_text:
            return {"intent": "khac", "entities": {}}

        text = raw_text.strip()
        # Loại bỏ khối <think>...</think> nếu model thuộc dòng Qwen3
        text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()

        # 1. Thử parse trực tiếp
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass

        # 2. Tìm khối markdown ```json ... ```
        json_block_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
        if json_block_match:
            try:
                return json.loads(json_block_match.group(1))
            except json.JSONDecodeError:
                pass

        # 3. Tìm cặp ngoặc nhọn ngoài cùng { ... }
        brace_match = re.search(r"(\{.*\})", text, re.DOTALL)
        if brace_match:
            try:
                return json.loads(brace_match.group(1))
            except json.JSONDecodeError:
                pass

        # Fallback nếu không parse được
        return {
            "intent": "khac",
            "type": "none",
            "entities": {},
            "missing_fields": [],
            "message": None,
            "raw_output": raw_text,
            "error": "JSONDecodeError"
        }

    @abc.abstractmethod
    def predict(
        self,
        text: str,
        business_type: str = "PRODUCER",
        knowledge: str = ""
    ) -> Dict[str, Any]:
        """
        Chạy dự đoán cho 1 câu văn bản (kèm ngữ cảnh tri thức RAG nếu có).
        Trả về dict có cấu trúc:
        {
            "prediction": {"intent": "...", "entities": {...}},
            "latency_ms": 123.4,
            "input_tokens": 100,
            "output_tokens": 50,
            "error": None
        }
        """
        pass

    def predict_batch(
        self,
        texts: List[str],
        business_type: str = "PRODUCER",
        knowledge_list: Optional[List[str]] = None
    ) -> List[Dict[str, Any]]:
        """Dự đoán cho một danh sách các câu văn bản."""
        if knowledge_list:
            return [self.predict(t, business_type=business_type, knowledge=k) for t, k in zip(texts, knowledge_list)]
        return [self.predict(t, business_type=business_type) for t in texts]

    def get_hardware_info(self) -> Dict[str, Any]:
        """Trả về thông tin phần cứng nơi model đang chạy."""
        return {
            "provider": self.__class__.__name__,
            "model_name": self.model_name
        }
