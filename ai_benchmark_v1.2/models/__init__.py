from typing import Optional
from ai_benchmark.models.base import ModelProvider
from ai_benchmark.models.groq_model import GroqModel


def resolve_model_name(provider: str, model_name: Optional[str]) -> Optional[str]:
    """Chuẩn hóa alias tên mô hình, đặc biệt là Llama 3.2 3B Instruct."""
    if not model_name:
        return model_name
    m = model_name.strip()
    m_lower = m.lower()

    # Nhận diện alias Llama 3.2 3B
    if any(k in m_lower for k in ("llama-3.2-3b", "llama3.2:3b", "llama 3.2 3b", "llama3.2-3b", "llama3.2")):
        if provider == "ollama":
            return "llama3.2:3b"
        elif provider in ("llama_local", "llama", "local", "transformers"):
            return "meta-llama/Llama-3.2-3B-Instruct"

    return m


def get_model_provider(
    provider_name: str,
    model_name: Optional[str] = None,
    **kwargs
) -> ModelProvider:
    """Factory để tạo instance của ModelProvider tương ứng."""
    prov = provider_name.lower().strip()
    resolved_name = resolve_model_name(prov, model_name)

    if prov == "groq":
        return GroqModel(model_name=resolved_name, **kwargs)
    elif prov in ("llama_local", "llama", "local", "transformers"):
        from ai_benchmark.models.llama_local import LlamaLocalModel
        return LlamaLocalModel(model_name=resolved_name, **kwargs)
    elif prov == "ollama":
        from ai_benchmark.models.ollama_model import OllamaModel
        return OllamaModel(model_name=resolved_name, **kwargs)
    else:
        raise ValueError(f"Không hỗ trợ model provider: '{provider_name}'. Chỉ hỗ trợ 'groq', 'llama_local' hoặc 'ollama'.")


__all__ = ["ModelProvider", "GroqModel", "get_model_provider"]
