import time
import os
from typing import Dict, Any, Optional
from app.ai.models.base import ModelProvider


class GroqModel(ModelProvider):
    """Mô hình inference gọi qua Groq API."""

    def __init__(
        self,
        model_name: Optional[str] = None,
        api_key: Optional[str] = None,
        system_prompt: Optional[str] = None,
        temperature: float = 0.0
    ):
        name = model_name or "openai/gpt-oss-120b"
        super().__init__(model_name=name, system_prompt=system_prompt)

        from groq import Groq

        self.api_key = api_key or os.getenv("GROQ_API_KEY")
        if not self.api_key:
            raise ValueError("GROQ_API_KEY không được tìm thấy trong biến môi trường.")

        self.client = Groq(api_key=self.api_key)
        self.temperature = temperature

    def predict(
        self,
        text: str,
        business_type: str = "PRODUCER",
        knowledge: str = ""
    ) -> Dict[str, Any]:
        """Gọi Groq Chat Completions API với response_format JSON."""
        user_prompt = f"USER INPUT:\n{text.strip()}"

        if knowledge and knowledge.strip():
            user_prompt += f"\n\nRELEVANT KNOWLEDGE:\n{knowledge.strip()}\n(Áp dụng kiến thức trên để chuẩn hóa từ lóng, phương ngữ hoặc quy cách đóng gói nếu có trong câu nói)."

        start_time = time.perf_counter()
        error_msg = None
        prediction = {"intent": "khac", "entities": {}}
        input_tokens = None
        output_tokens = None

        try:
            response = self.client.chat.completions.create(
                model=self.model_name,
                temperature=self.temperature,
                response_format={"type": "json_object"},
                messages=[
                    {"role": "system", "content": self.system_prompt},
                    {"role": "user", "content": user_prompt}
                ]
            )

            latency_ms = (time.perf_counter() - start_time) * 1000.0

            if response.usage:
                input_tokens = response.usage.prompt_tokens
                output_tokens = response.usage.completion_tokens

            raw_content = response.choices[0].message.content or ""
            prediction = self.extract_json(raw_content)

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
