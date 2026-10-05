import os
from pathlib import Path
# pyrefly: ignore [missing-import]
from dotenv import load_dotenv

# Load .env if present
load_dotenv()

BASE_DIR = Path(__file__).resolve().parent

class BenchmarkConfig:
    """Cấu hình cho AI Benchmark Module."""

    # Model Provider: 'llama_local' hoặc 'groq'
    MODEL_PROVIDER: str = os.getenv("MODEL_PROVIDER", "llama_local").lower()

    def _get_default_model() -> str:
        prov = os.getenv("MODEL_PROVIDER", "llama_local").lower()
        if prov == "groq":
            return "openai/gpt-oss-20b"
        if prov == "ollama":
            return "llama3.1:latest"
        token = os.getenv("HF_TOKEN") or os.getenv("HUGGINGFACE_HUB_TOKEN")
        try:
            # pyrefly: ignore [missing-import]
            import torch
            if torch.cuda.is_available() and token:
                return "meta-llama/Llama-3.1-8B-Instruct"
        except Exception:
            pass
        return "Qwen/Qwen2.5-1.5B-Instruct"

    # Model Name
    # Default for local CPU: Qwen/Qwen2.5-0.5B-Instruct (nhẹ, tối ưu VS Code)
    # Default for local GPU: meta-llama/Llama-3.1-8B-Instruct
    # Default for groq: openai/gpt-oss-120b
    MODEL_NAME: str = os.getenv("MODEL_NAME", _get_default_model())

    # Hugging Face Settings
    HF_TOKEN: str | None = os.getenv("HF_TOKEN") or os.getenv("HUGGINGFACE_HUB_TOKEN")
    LOAD_IN_4BIT: bool = os.getenv("LOAD_IN_4BIT", "true").lower() in ("true", "1", "yes")
    DEVICE: str = os.getenv("DEVICE", "auto")
    MAX_NEW_TOKENS: int = int(os.getenv("MAX_NEW_TOKENS", "512"))
    TEMPERATURE: float = float(os.getenv("TEMPERATURE", "0.0"))

    # Groq Settings
    GROQ_API_KEY: str | None = os.getenv("GROQ_API_KEY")

    # RAG Settings
    USE_RAG: bool = os.getenv("USE_RAG", "false").lower() in ("true", "1", "yes")
    BENCHMARK_MODE: str = os.getenv("BENCHMARK_MODE", "no-rag").lower()  # 'no-rag', 'legacy-rag', 'normalization-rag'
    RAG_TOP_K: int = int(os.getenv("RAG_TOP_K", "2"))
    RAG_THRESHOLD: float = float(os.getenv("RAG_THRESHOLD", "0.40"))
    
    _app_knowledge = BASE_DIR.parent / "app" / "ai" / "rag" / "knowledge"
    _local_knowledge = BASE_DIR / "rag" / "knowledge"
    RAG_KNOWLEDGE_PATH: Path = _app_knowledge if _app_knowledge.exists() else _local_knowledge

    _app_chroma = BASE_DIR.parent / "app" / "ai" / "rag" / "chroma_db"
    _local_chroma = BASE_DIR / "rag" / "chroma_db"
    RAG_CHROMA_PATH: Path = _app_chroma if _app_chroma.exists() else _local_chroma



    # Paths
    PROMPT_PATH: Path = BASE_DIR / "prompts" / "intent_entity_prompt.txt"
    
    # Dataset Configuration from .env
    _env_dataset = os.getenv("DATASET_PATH") or os.getenv("DATASET_NAME") or os.getenv("BENCHMARK_DATASET")
    if _env_dataset:
        _p = Path(_env_dataset.strip())
        if _p.is_absolute():
            DEFAULT_DATASET_PATH: Path = _p
        elif (BASE_DIR / _p).exists():
            DEFAULT_DATASET_PATH: Path = BASE_DIR / _p
        elif (BASE_DIR / "datasets" / _p).exists():
            DEFAULT_DATASET_PATH: Path = BASE_DIR / "datasets" / _p
        else:
            DEFAULT_DATASET_PATH: Path = BASE_DIR / "datasets" / _p if not _p.parent.name else BASE_DIR / _p
    else:
        DEFAULT_DATASET_PATH: Path = BASE_DIR / "datasets" / "voicecash_producer_1000.csv"

    PREDICTIONS_DIR: Path = BASE_DIR / "predictions"
    OUTPUT_DIR: Path = BASE_DIR / "evaluation" / "reports"

    @classmethod
    def ensure_dirs(cls):
        cls.PREDICTIONS_DIR.mkdir(parents=True, exist_ok=True)
        cls.OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# Khởi tạo thư mục cần thiết
BenchmarkConfig.ensure_dirs()
