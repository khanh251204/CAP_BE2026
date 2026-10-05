from typing import Dict, Any, Optional, List
from pydantic import BaseModel, Field


class EntitySchema(BaseModel):
    """Schema 9 thực thể chuẩn của VoiceCash."""
    product: Optional[str] = None
    new_product_name: Optional[str] = None
    price: Optional[float] = None
    quantity: Optional[float] = None
    unit: Optional[str] = None
    customer: Optional[str] = None
    supplier: Optional[str] = None
    date: Optional[str] = None
    payment: Optional[str] = None


class ExtractedOutput(BaseModel):
    """Output của LLM sau khi parse JSON theo chuẩn app/ai."""
    status: Optional[str] = "success"
    text: Optional[str] = None
    intent: str = "khac"
    type: Optional[str] = "none"
    entities: EntitySchema = Field(default_factory=EntitySchema)
    missing_fields: Optional[List[str]] = Field(default_factory=list)
    message: Optional[str] = None


class PredictionRecord(BaseModel):
    """Bản ghi lưu trữ persistence cho từng sample trong predictions.jsonl."""
    id: int | str
    text: str
    raw_text: Optional[str] = None
    normalized_text: Optional[str] = None
    normalization_changes: Optional[Dict[str, str]] = None
    mode: Optional[str] = None
    business_type: Optional[str] = "PRODUCER"
    prediction: Dict[str, Any]
    latency_ms: float
    knowledge: Optional[str] = None
    input_tokens: Optional[int] = None
    output_tokens: Optional[int] = None
    error: Optional[str] = None


class BenchmarkSummary(BaseModel):
    """Bản tóm tắt hiệu năng của phiên benchmark."""
    model_name: str
    provider: str
    total_samples: int
    successful_samples: int
    failed_samples: int
    avg_latency_ms: float
    p50_latency_ms: float
    p95_latency_ms: float
    min_latency_ms: float
    max_latency_ms: float
    throughput_samples_per_sec: float
    total_input_tokens: Optional[int] = None
    total_output_tokens: Optional[int] = None
    gpu_memory_used_mb: Optional[float] = None
    gpu_memory_total_mb: Optional[float] = None
