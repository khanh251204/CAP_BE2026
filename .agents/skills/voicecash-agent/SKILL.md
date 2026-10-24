---
name: voicecash-agent
description: >-
  Standard development workflows, conventions, and runbooks for developing,
  extending, and testing AI Agent features (Intents, Handlers, Validators, MCP Tools,
  RAG Normalization, LLM Prompts) in the VoiceCashBook backend.
---

# VoiceCashBook AI Agent Development Skill

This skill provides step-by-step procedures, architectural patterns, and code conventions for engineers and AI agents working on the AI subsystem of **VoiceCashBook**.

---

## 1. System Flow Overview

The VoiceCashBook AI Agent follows a strict **Two-Phase Architecture**:

```
[Voice / Text Input]
       │
       ▼
[Audio Pipeline (FFmpeg + WebRTC VAD)] -> [Groq Whisper STT]
       │
       ▼
[Normalization-RAG Layer] (Regex in-memory: units, currency, dialects)
       │
       ▼
[LLM Inference (openai/gpt-oss-120b)] -> [Strict JSON Extraction: intent + entities]
       │
       ▼
[Agent Orchestrator (app/ai/core/agent.py)]
       │
       ▼
[IntentRouter (app/ai/core/router.py)]
       │
       ▼
[IntentHandler (app/ai/intents/<intent>/handler.py)]
  ├── 1. validator.py: deterministic entity check
  ├── 2. MCP call (e.g. check_stock): check availability
  ├── 3. Business rule verification (RESELLER / PRODUCER / SERVICE)
  └── 4. payload.py: build draft payload
       │
       ▼
[Status: waiting_confirmation] (Stored in SessionStoreService)
       │
       ▼ (User confirms or edits via /api/v1/agent/confirm)
[AgentConfirmService]
       │
       ▼
[MCP Execution / DB Atomic Transaction (Transaction + Detail + Inventory + Debt)]
       │
       ▼
[Async Data Lake Service] (Logs voice, AI result, correction diff for MLOps)
```

> **CORE PRINCIPLE**: The LLM ONLY classifies intent and extracts entities. All business rules, stock validations, and calculations MUST be executed by backend services.

---

## 2. Standard Workflow: Implementing a New Intent

Follow these 8 steps whenever you add a new business intent:

### Step 1: Create Intent Package Directory
Create folder: `app/ai/intents/<intent_name>/`
- `__init__.py`
- `validator.py`: Entity format validation
- `payload.py`: Draft payload constructor
- `handler.py`: Handler implementation orchestrating checks

### Step 2: Implement `validator.py`
```python
# app/ai/intents/<intent_name>/validator.py
from typing import Dict, Any, List

REQUIRED_FIELDS = ["product", "quantity"]

def validate(entities: Dict[str, Any]) -> Dict[str, Any]:
    missing_fields: List[str] = []
    for field in REQUIRED_FIELDS:
        val = entities.get(field)
        if val is None or str(val).strip() == "":
            missing_fields.append(field)

    if missing_fields:
        return {
            "success": False,
            "missing_fields": missing_fields,
            "message": f"Thiếu thông tin bắt buộc: {', '.join(missing_fields)}"
        }

    return {"success": True, "missing_fields": []}
```

### Step 3: Implement `payload.py`
```python
# app/ai/intents/<intent_name>/payload.py
from typing import Dict, Any
from decimal import Decimal

def build_payload(entities: Dict[str, Any], extra_data: Dict[str, Any] = None) -> Dict[str, Any]:
    extra = extra_data or {}
    quantity = Decimal(str(entities.get("quantity") or 0))
    unit_price = Decimal(str(entities.get("price") or extra.get("unit_price") or 0))
    total_amount = quantity * unit_price

    return {
        "product_name": entities.get("product"),
        "quantity": float(quantity),
        "unit": entities.get("unit") or extra.get("default_unit", "cái"),
        "unit_price": float(unit_price),
        "total_amount": float(total_amount),
        "note": entities.get("note", "")
    }
```

### Step 4: Implement `handler.py`
```python
# app/ai/intents/<intent_name>/handler.py
from typing import Dict, Any
from app.ai.mcp.client import call_mcp_tool, normalize_mcp_result
from .validator import validate
from .payload import build_payload

class ExampleIntentHandler:
    async def handle(
        self,
        user_id: int,
        entities: Dict[str, Any],
        text: str,
        intent: str = "example_intent",
        business_type: str | None = None
    ) -> Dict[str, Any]:
        # 1. Validate
        val_res = validate(entities)
        if not val_res["success"]:
            return {
                "success": False,
                "status": "need_information",
                "intent": intent,
                "missing_fields": val_res["missing_fields"],
                "message": val_res["message"]
            }

        # 2. Query MCP / DB if needed
        # stock_call = await call_mcp_tool("check_stock", {"payload": {...}, "user_id": user_id})

        # 3. Construct draft payload
        payload = build_payload(entities)

        # 4. Return waiting_confirmation state
        return {
            "success": True,
            "status": "waiting_confirmation",
            "intent": intent,
            "message": "Vui lòng xác nhận giao dịch",
            "payload": payload
        }
```

### Step 5: Register Handler in `app/ai/core/router.py`
```python
from app.ai.intents.<intent_name>.handler import ExampleIntentHandler

_example_intent = ExampleIntentHandler()
HANDLERS = {
    ...
    "<intent_name>": _example_intent,
    "<alias_intent>": _example_intent,
}
```

### Step 6: Handle Confirmation Execution
In `app/routes/groq_route.py` under `@router.post("/agent/confirm")`:
1. Add validation hook in `AgentConfirmService.validate_and_prepare_payload()`
2. Add branch in execution block:
```python
elif intent == "<intent_name>":
    res = await call_mcp_tool("<mcp_tool_name>", {"payload": payload, "user_id": current_user_id})
    result = normalize_mcp_result(res)
```

### Step 7: Update Prompts if Necessary
If the intent requires new entity extraction or special instructions:
- Update `app/ai/prompts/intent.py`
- Update `app/ai/prompts/entity.py`
- Verify JSON schema in `app/ai/llm/groq_service.py`

### Step 8: Update Normalization Dictionary
If users use dialect/slang for this intent:
- Add rules to `app/ai/rag/knowledge/normalization_data.json`

---

## 3. Business Rule Validation Standard (RESELLER / PRODUCER / SERVICE)

When handling sales (`ban_hang`) or inventory movements, strictly enforce:

| Business Type | Product Type | Stock Checking Rule | Error Handling |
| :--- | :--- | :--- | :--- |
| **RESELLER** | `RESALE` | Mandatory: `quantity <= current_stock` | Return `INSUFFICIENT_STOCK` / `out_of_stock`. Do NOT commit or create negative stock. |
| **PRODUCER** | `FINISHED_GOOD` | **Bypass stock check**: Allowed to sell even when `stock == 0` (on-demand production). | Allow sale. Do NOT generate negative inventory transaction if BOM is not configured. |
| **PRODUCER** | `RAW_MATERIAL` | Raw materials cannot be sold directly as finished goods. | Return `cannot_sell_raw_material`. |
| **SERVICE** | Any / None | **Bypass stock check entirely**. | No inventory movement (`Inventory_Transaction` is not created). |

---

## 4. MCP Server & Tool Conventions (Capstone 1 vs Capstone 2)

### Capstone 1 Core Scope (7 Intents):
1. **`ban_hang`**: `check_stock`, `export_inventory` (Inventory MCP)
2. **`mua_hang` / `nhap_hang`**: `import_inventory` (Inventory MCP)
3. **`chi_tien` / `chi_phi`**: `create_expense` (Expense MCP)
4. **`ghi_no_khach_hang` / `khach_ghi_no`**: `ghi_no_khach_hang` (Debt MCP)
5. **`thu_no_khach_hang` / `thu_no_khach`**: `thu_no_khach_hang` (Debt MCP)
6. **`ghi_no_nha_cung_cap` / `ghi_no_ncc`**: `ghi_no_nha_cung_cap` (Debt MCP)
7. **`tra_no_nha_cung_cap` / `tra_no_ncc`**: `thu_no_nha_cung_cap` (Debt MCP)

### Capstone 2 Extended Scope:
- Voice CRUD Sản phẩm (`them_san_pham`, `sua_san_pham`, `xoa_san_pham`, `tim_san_pham` - Product MCP).
- Quản trị kho nội bộ & kiểm kê (`nhap_kho`, `xuat_kho`, `hang_hong`, `kiem_kho`).
- Báo cáo định kỳ & chốt sổ (`bao_cao`, `chot_so` - Report MCP).
- BOM & Trích xuất đa sản phẩm (Multi-item).

### Invoking MCP Tools in Handlers:
```python
from app.ai.mcp.client import call_mcp_tool, normalize_mcp_result

raw_res = await call_mcp_tool(
    tool_name="check_stock",
    arguments={
        "payload": {"product_name": product_name},
        "user_id": user_id
    }
)
result = normalize_mcp_result(raw_res)
if not result.get("success"):
    # handle failure
    pass
```

---

## 5. Testing & Verification Runbook

Run the following test suite to ensure no regressions:

```bash
# 1. Run unit tests for AI core and intents
pytest tests/ -k "ai or intent or mcp" -v

# 2. Test business rules specifically
pytest tests/test_business_rules_reseller_producer.py -v

# 3. Test multi-tenancy and inventory isolation
pytest tests/test_inventory_tenant.py -v
```

### Manual Testing via API:
1. **Analyze input**: `POST /api/v1/analyze/groq` with `{"text": "Bán 5 lon Coca giá 10k"}`
   - Ensure response has `status == "waiting_confirmation"`
2. **Confirm draft**: `POST /api/v1/agent/confirm`
   - Ensure DB records are committed atomically.
