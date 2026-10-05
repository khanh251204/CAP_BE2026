import time
import requests
import json
from typing import Dict, Any, Optional
from ai_benchmark.config import BenchmarkConfig
from ai_benchmark.models.base import ModelProvider


class OllamaModel(ModelProvider):
    """
    Mô hình Llama chạy local thông qua Ollama (tối ưu CPU & RAM cho Windows).
    Không yêu cầu card NVIDIA CUDA, chạy trực tiếp bản 4-bit GGUF (4.7 GB).
    """

    def __init__(
        self,
        model_name: Optional[str] = None,
        base_url: str = "http://localhost:11434",
        prompt_path: Optional[str] = None
    ):
        name = model_name or "llama3.1:latest"
        super().__init__(model_name=name, prompt_path=prompt_path)
        self.base_url = base_url.rstrip("/")
        self._check_ollama_alive()

    def _check_ollama_alive(self):
        """Kiểm tra xem Ollama service đang chạy hay không."""
        try:
            resp = requests.get(f"{self.base_url}/api/tags", timeout=3)
            if resp.status_code == 200:
                print(f"[✓] Kết nối thành công tới Ollama tại {self.base_url} (Model: {self.model_name})")
        except Exception:
            print(f"[!] Cảnh báo: Không thể kết nối tới Ollama tại {self.base_url}.")
            print("    Hãy chắc chắn ứng dụng Ollama đã được cài và đang chạy (ollama serve).")

    def predict(
        self,
        text: str,
        business_type: str = "PRODUCER",
        knowledge: str = ""
    ) -> Dict[str, Any]:
        """Gửi prompt tới Ollama chat API với định dạng JSON."""
        user_prompt = f"USER INPUT:\n{text.strip()}"

        if knowledge and knowledge.strip():
            user_prompt += f"\n\nRELEVANT KNOWLEDGE:\n{knowledge.strip()}\n(Áp dụng kiến thức trên để chuẩn hóa từ lóng, phương ngữ hoặc quy cách đóng gói nếu có trong câu nói)."

        start_time = time.perf_counter()
        error_msg = None
        prediction = {"intent": "khac", "entities": {}}
        input_tokens = None
        output_tokens = None

        payload = {
            "model": self.model_name,
            "messages": [
                {"role": "system", "content": self.system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            "stream": False,
            "format": "json",
            "options": {
                "temperature": BenchmarkConfig.TEMPERATURE
            }
        }

        try:
            resp = requests.post(f"{self.base_url}/api/chat", json=payload, timeout=120)
            latency_ms = (time.perf_counter() - start_time) * 1000.0

            if resp.status_code == 200:
                data = resp.json()
                raw_content = data.get("message", {}).get("content", "")
                input_tokens = data.get("prompt_eval_count")
                output_tokens = data.get("eval_count")
                prediction = self.extract_json(raw_content)
            else:
                error_msg = f"Ollama HTTP {resp.status_code}: {resp.text}"
        except Exception as e:
            latency_ms = (time.perf_counter() - start_time) * 1000.0
            error_msg = str(e)

        return {
            "prediction": prediction,
            "latency_ms": round(latency_ms, 2),
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "error": error_msg
        }
