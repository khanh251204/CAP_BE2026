import abc
import json
import re
import time
from typing import Dict, Any, List, Optional
from ai_benchmark.config import BenchmarkConfig


class ModelProvider(abc.ABC):
    """Lớp cơ sở trừu tượng cho tất cả các mô hình inference."""

    def __init__(self, model_name: str, prompt_path: Optional[str] = None):
        self.model_name = model_name
        self.prompt_path = prompt_path or BenchmarkConfig.PROMPT_PATH
        self.system_prompt = self._load_system_prompt()

    def _load_system_prompt(self) -> str:
        """Đọc nội dung file prompt chuẩn hóa của ai_benchmark."""
        try:
            with open(self.prompt_path, "r", encoding="utf-8") as f:
                content = f.read().strip()
                if "{{USER_INPUT}}" in content:
                    content = content.split("{{USER_INPUT}}")[0]
                    content = re.sub(r"=+\s*USER UTTERANCE\s*=+\s*$", "", content, flags=re.MULTILINE).strip()
                return content
        except Exception as e:
            print(f"[Warning] Không thể đọc prompt từ {self.prompt_path}: {e}")
            return "You are an AI for Vietnamese transaction logging. Parse Speech-to-Text inputs into JSON."

    def extract_json(self, raw_text: str) -> Dict[str, Any]:
        """
        Trích xuất an toàn JSON object từ output thô của LLM,
        hỗ trợ trường hợp LLM bọc trong ```json ... ``` hoặc có ký tự thừa.
        """
        if not raw_text:
            return {"intent": "khac", "entities": {}}

        text = raw_text.strip()

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
        """Trả về thông tin phần cứng (GPU/CPU/RAM)."""
        info = {
            "device": "cpu",
            "gpu_name": None,
            "vram_used_mb": None,
            "vram_total_mb": None
        }
        try:
            # pyrefly: ignore [missing-import]
            import torch
            if torch.cuda.is_available():
                info["device"] = "cuda"
                info["gpu_name"] = torch.cuda.get_device_name(0)
                info["vram_used_mb"] = round(torch.cuda.memory_allocated(0) / 1024**2, 2)
                info["vram_total_mb"] = round(torch.cuda.get_device_properties(0).total_memory / 1024**2, 2)
        except Exception:
            pass
        return info
