"""
Số token LLM (input / output) của từng giao dịch giọng nói — lưu trong VoiceRecord.llm_output["token_usage"]
và được Data Lake ghi lại (processed / dataset).

Một giao dịch có thể gọi LLM nhiều lần (phân tích ở bước STT, rồi agent phân tích lại) → cộng dồn.
"""
import json
from datetime import datetime
from typing import Any, Dict, Optional


def _to_int(value: Any) -> Optional[int]:
    try:
        return int(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def build_usage(model: Optional[str], input_tokens: Any, output_tokens: Any, latency_ms: Any = None) -> Dict[str, Any]:
    """token_usage cho MỘT lần gọi LLM."""
    i, o = _to_int(input_tokens), _to_int(output_tokens)
    call = {
        "model": model,
        "input_tokens": i,
        "output_tokens": o,
        "total_tokens": (i or 0) + (o or 0) if (i is not None or o is not None) else None,
        "latency_ms": latency_ms,
        "at": datetime.now().isoformat(timespec="seconds"),
    }
    return {
        "input_tokens": i,
        "output_tokens": o,
        "total_tokens": call["total_tokens"],
        "llm_calls": 1,
        "calls": [call],
    }


def _as_dict(llm_output: Any) -> Dict[str, Any]:
    if isinstance(llm_output, dict):
        return llm_output
    if isinstance(llm_output, str):
        try:
            data = json.loads(llm_output)
            return data if isinstance(data, dict) else {}
        except Exception:
            return {}
    return {}


def get_usage(llm_output: Any) -> Optional[Dict[str, Any]]:
    usage = _as_dict(llm_output).get("token_usage")
    return usage if isinstance(usage, dict) else None


def _sum(a: Optional[int], b: Optional[int]) -> Optional[int]:
    if a is None and b is None:
        return None
    return (a or 0) + (b or 0)


def merge_usage(previous_llm_output: Any, new_llm_output: Any) -> Any:
    """
    Trả về new_llm_output kèm token_usage CỘNG DỒN với lần phân tích trước của cùng bản ghi
    (dùng khi ghi đè VoiceRecord.llm_output). Không đổi gì nếu không có số liệu token.
    """
    prev, new = get_usage(previous_llm_output), get_usage(new_llm_output)
    if not prev:
        return new_llm_output
    data = dict(_as_dict(new_llm_output))
    if not data:
        return new_llm_output
    new = new or {"input_tokens": None, "output_tokens": None, "total_tokens": None, "llm_calls": 0, "calls": []}
    data["token_usage"] = {
        "input_tokens": _sum(_to_int(prev.get("input_tokens")), _to_int(new.get("input_tokens"))),
        "output_tokens": _sum(_to_int(prev.get("output_tokens")), _to_int(new.get("output_tokens"))),
        "total_tokens": _sum(_to_int(prev.get("total_tokens")), _to_int(new.get("total_tokens"))),
        "llm_calls": int(prev.get("llm_calls") or 0) + int(new.get("llm_calls") or 0),
        "calls": list(prev.get("calls") or []) + list(new.get("calls") or []),
    }
    return data


def summary(llm_output: Any) -> Optional[Dict[str, Any]]:
    """Dạng gọn để ghi Data Lake: input / output / total / số lần gọi + chi tiết từng lần."""
    usage = get_usage(llm_output)
    if not usage:
        return None
    return {
        "input_tokens": _to_int(usage.get("input_tokens")),
        "output_tokens": _to_int(usage.get("output_tokens")),
        "total_tokens": _to_int(usage.get("total_tokens")),
        "llm_calls": int(usage.get("llm_calls") or 0),
        "calls": usage.get("calls") or [],
    }
