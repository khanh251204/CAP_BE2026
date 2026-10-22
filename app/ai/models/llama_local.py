import os
import time
from typing import Dict, Any, Optional
from app.ai.models.base import ModelProvider


class LlamaLocalModel(ModelProvider):
    """
    Mô hình chạy local qua Hugging Face Transformers.
    Hỗ trợ 4-bit quantization (BitsAndBytes) khi có GPU NVIDIA.
    """

    def __init__(
        self,
        model_name: Optional[str] = None,
        hf_token: Optional[str] = None,
        load_in_4bit: Optional[bool] = None,
        device: Optional[str] = None,
        system_prompt: Optional[str] = None,
        temperature: float = 0.0,
        max_new_tokens: int = 512
    ):
        name = model_name or "Qwen/Qwen2.5-1.5B-Instruct"
        super().__init__(model_name=name, system_prompt=system_prompt)

        self.hf_token = hf_token or os.getenv("HF_TOKEN") or os.getenv("HUGGINGFACE_HUB_TOKEN")
        self.load_in_4bit = load_in_4bit if load_in_4bit is not None else (os.getenv("LOAD_IN_4BIT", "true").lower() in ("true", "1", "yes"))
        self.device_pref = device or os.getenv("DEVICE", "auto")
        self.temperature = temperature
        self.max_new_tokens = max_new_tokens

        self.tokenizer = None
        self.model = None

        self._init_model()

    def _init_model(self):
        """Khởi tạo tokenizer và model với cấu hình phù hợp."""
        import torch
        from transformers import AutoTokenizer, AutoModelForCausalLM

        has_cuda = torch.cuda.is_available()

        self.tokenizer = AutoTokenizer.from_pretrained(
            self.model_name,
            token=self.hf_token,
            trust_remote_code=True
        )

        if self.tokenizer.pad_token is None:
            self.tokenizer.pad_token = self.tokenizer.eos_token

        model_kwargs: Dict[str, Any] = {
            "token": self.hf_token,
            "trust_remote_code": True,
        }

        if has_cuda and self.load_in_4bit:
            try:
                from transformers import BitsAndBytesConfig
                compute_dtype = torch.bfloat16 if torch.cuda.is_bf16_supported() else torch.float16
                bnb_config = BitsAndBytesConfig(
                    load_in_4bit=True,
                    bnb_4bit_quant_type="nf4",
                    bnb_4bit_compute_dtype=compute_dtype,
                    bnb_4bit_use_double_quant=True,
                )
                model_kwargs["quantization_config"] = bnb_config
                model_kwargs["device_map"] = "auto"
            except Exception:
                model_kwargs["torch_dtype"] = torch.float16
                model_kwargs["device_map"] = "auto"
        elif has_cuda:
            model_kwargs["torch_dtype"] = torch.float16
            model_kwargs["device_map"] = "auto"
        else:
            model_kwargs["torch_dtype"] = torch.float32
            model_kwargs["device_map"] = "cpu"

        self.model = AutoModelForCausalLM.from_pretrained(
            self.model_name,
            **model_kwargs
        )
        self.model.eval()

    def predict(
        self,
        text: str,
        business_type: str = "PRODUCER",
        knowledge: str = ""
    ) -> Dict[str, Any]:
        """Chạy dự đoán trên mô hình qua Transformers."""
        import torch

        user_prompt = f"USER INPUT:\n{text.strip()}"

        if knowledge and knowledge.strip():
            user_prompt += f"\n\nRELEVANT KNOWLEDGE:\n{knowledge.strip()}\n(Áp dụng kiến thức trên để chuẩn hóa từ lóng, phương ngữ hoặc quy cách đóng gói nếu có trong câu nói)."

        messages = [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": user_prompt}
        ]

        start_time = time.perf_counter()
        error_msg = None
        prediction = {"intent": "khac", "entities": {}}
        input_tokens = None
        output_tokens = None

        try:
            prompt_formatted = self.tokenizer.apply_chat_template(
                messages,
                tokenize=False,
                add_generation_prompt=True
            )

            inputs = self.tokenizer(
                prompt_formatted,
                return_tensors="pt"
            )

            input_tokens = inputs["input_ids"].shape[1]

            device = next(self.model.parameters()).device
            inputs = {k: v.to(device) for k, v in inputs.items()}

            gen_kwargs = {
                "max_new_tokens": self.max_new_tokens,
                "pad_token_id": self.tokenizer.pad_token_id,
                "eos_token_id": self.tokenizer.eos_token_id,
            }

            if self.temperature <= 0.0:
                gen_kwargs["do_sample"] = False
            else:
                gen_kwargs["do_sample"] = True
                gen_kwargs["temperature"] = self.temperature

            with torch.no_grad():
                generated_ids = self.model.generate(
                    **inputs,
                    **gen_kwargs
                )

            new_tokens = generated_ids[0][input_tokens:]
            output_tokens = len(new_tokens)

            raw_output = self.tokenizer.decode(new_tokens, skip_special_tokens=True).strip()
            latency_ms = (time.perf_counter() - start_time) * 1000.0

            prediction = self.extract_json(raw_output)

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
