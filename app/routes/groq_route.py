# app/routes/groq_route.py

import os
import asyncio
import tempfile
import traceback

from typing import Optional
from fastapi import (
    APIRouter,
    UploadFile,
    File,
    Depends,
    Query
)
from requests import Session

from app.ai.llm.groq_service import GroqService
from app.ai.core.agent import Agent as TransactionAgent

from app.schemas.analysis_schema import AnalysisRequest
from app.configs.jwt import get_current_user_id

from app.ai.rag.rag_service import RAGService
from app.ai.rag.vector_store import VectorStore
from app.ai.core.state import pending_confirmations


router = APIRouter()


# ============================================================
# SERVICES
# ============================================================

groq_service = GroqService()

vector_store = VectorStore()

rag_service = RAGService(
    vector_store=vector_store
)


# ============================================================
# AGENT
# ============================================================

transaction_agent = TransactionAgent(
    llm=groq_service,
    rag=rag_service
)


# ============================================================
# STT
# ============================================================

from app.api.stt import stt_groq, stt_gemini
from app.services.gemini_service import gemini_service, gemini_transcribe

router.add_api_route("/stt/groq", stt_groq, methods=["POST"], tags=["Speech to Text"])
# router.add_api_route("/stt/groq", stt_gemini, methods=["POST"], tags=["Speech to Text"])

# ============================================================
# ANALYZE - TEST LLM
# ============================================================

@router.post("/analyze/groq1")
async def analyze_groq(
    request: AnalysisRequest
):

    result = await asyncio.to_thread(
        groq_service.analyze_transaction,
        request.text
    )

    return {
        "success": True,
        "service": "Groq NLP",
        "transaction_analysis": result
    }


# ============================================================
# TRANSACTION - AGENT
# ============================================================

@router.post("/analyze/groq")
async def voice_transaction(
    request: AnalysisRequest,
    current_user_id: int = Depends(
        get_current_user_id
    )
):

    try:

        result = await transaction_agent.run(
            user_id=current_user_id,
            text=request.text
        )

        req_method = getattr(request, "input_method", None)
        is_voice = bool(request.voice_id or (req_method and req_method.upper() == "VOICE"))
        input_method_val = "VOICE" if is_voice else "MANUAL"

        if request.voice_id:
            try:
                from app.models.voice_record_model import VoiceRecord
                from app.configs.database import SessionLocal
                with SessionLocal() as db_session:
                    v_rec = db_session.query(VoiceRecord).filter(VoiceRecord.voice_id == request.voice_id).first()
                    if v_rec:
                        v_rec.intent = result.get("intent")
                        v_rec.llm_output = result.get("analysis")
                        if not v_rec.user_id:
                            v_rec.user_id = current_user_id
                        db_session.commit()
            except Exception:
                pass

        if current_user_id in pending_confirmations:
            pending_confirmations[current_user_id]["voice_id"] = request.voice_id if request.voice_id else None
            pending_confirmations[current_user_id]["input_method"] = input_method_val

        return result

    except Exception as e:

        traceback.print_exc()

        return {
            "success": False,
            "message": "Lỗi xử lý giao dịch",
            "error": str(e)
        }


from app.ai.core.state import pending_confirmations
from app.controllers.product_controller import ProductController
from app.configs.database import get_db
# pyrefly: ignore [missing-import]
from sqlalchemy.orm import Session
from app.ai.mcp.client import (
    call_mcp_tool,
    normalize_mcp_result
)
from app.schemas.agent_schema import AgentConfirmRequest
from app.services.agent_confirm_service import AgentConfirmService
from app.services.data_lake_service import DataLakeService
import copy


@router.post("/agent/confirm")
async def confirm_action(
    body: Optional[AgentConfirmRequest] = None,
    session_id: Optional[str] = Query(None),
    current_user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db)
):
    session_key = (body.session_id if body and body.session_id else None) or session_id or current_user_id
    pending = pending_confirmations.get(session_key) or pending_confirmations.get(current_user_id)

    if not pending:
        return {
            "success": False,
            "message": "Không có thao tác nào đang chờ xác nhận"
        }

    intent = pending["intent"]
    ai_result = copy.deepcopy(pending["payload"])
    payload = pending["payload"]
    correction_diff = None
    correction_type = "CONFIRM_WITHOUT_CHANGE"

    # ========================================================
    # XỬ LÝ BẢN HIỆU CHỈNH CỦA NGƯỜI DÙNG (NẾU CÓ)
    # ========================================================
    if body and body.corrected_transaction:
        payload, correction_diff, correction_type = AgentConfirmService.validate_and_prepare_payload(
            pending_payload=pending["payload"],
            intent=intent,
            corrected=body.corrected_transaction,
            user_id=current_user_id
        )

    body_voice_id = getattr(body, "voice_id", None) if body else None
    body_input_method = getattr(body, "input_method", None) if body else None

    voice_id = body_voice_id or pending.get("voice_id")
    is_voice = bool(
        voice_id or 
        (body_input_method and body_input_method.upper() == "VOICE") or 
        pending.get("input_method") == "VOICE"
    )
    payload["input_method"] = "VOICE" if is_voice else "MANUAL"
    if voice_id:
        payload["voice_id"] = voice_id

    if intent == "them_san_pham":
        result = ProductController.create_product(data=payload, user_id=current_user_id, db=db)
    elif intent == "sua_san_pham":
        result = ProductController.update_product(product_id=payload["product_id"], data=payload["data"], user_id=current_user_id, db=db)
    elif intent == "xoa_san_pham":
        result = ProductController.delete_product(product_id=payload["product_id"], user_id=current_user_id, db=db)
    elif intent == "ban_hang":
        res = await call_mcp_tool("export_inventory", {"payload": payload, "user_id": current_user_id})
        result = normalize_mcp_result(res)
    elif intent in ("mua_hang", "nhap_hang"):
        res = await call_mcp_tool("import_inventory", {"payload": payload, "user_id": current_user_id})
        result = normalize_mcp_result(res)
    elif intent == "nhap_kho":
        res = await call_mcp_tool("nhap_kho", {"payload": payload, "user_id": current_user_id})
        result = normalize_mcp_result(res)
    elif intent == "xuat_kho":
        res = await call_mcp_tool("xuat_kho", {"payload": payload, "user_id": current_user_id})
        result = normalize_mcp_result(res)
    elif intent in ("ghi_no_khach_hang", "khach_ghi_no"):
        res = await call_mcp_tool("ghi_no_khach_hang", {
            "input": {
                "customer_id": payload["customer_id"],
                "original_amount": payload["original_amount"],
                "transaction_id": payload.get("transaction_id"),
                "input_method": payload.get("input_method", "MANUAL"),
            },
            "user_id": current_user_id
        })
        result = normalize_mcp_result(res)
    elif intent in ("thu_no_khach_hang", "thu_no_khach"):
        input_data = {
            "account_id": payload.get("account_id") or 1,
            "amount": payload.get("amount") or payload.get("original_amount"),
            "input_method": payload.get("input_method", "MANUAL"),
        }
        if payload.get("debt_id"):
            input_data["debt_id"] = payload["debt_id"]
        elif payload.get("customer_id"):
            input_data["customer_id"] = payload["customer_id"]
        res = await call_mcp_tool("thu_no_khach_hang", {"input": input_data, "user_id": current_user_id})
        result = normalize_mcp_result(res)
    elif intent in ("ghi_no_nha_cung_cap", "ncc_ghi_no"):
        res = await call_mcp_tool("ghi_no_nha_cung_cap", {
            "input": {
                "supplier_id": payload["supplier_id"],
                "original_amount": payload["original_amount"],
                "transaction_id": payload.get("transaction_id"),
                "note": payload.get("note"),
                "input_method": payload.get("input_method", "MANUAL"),
            },
            "user_id": current_user_id
        })
        result = normalize_mcp_result(res)
    elif intent in ("tra_no_nha_cung_cap", "tra_no_ncc"):
        input_data = {
            "account_id": payload.get("account_id") or 1,
            "amount": payload.get("amount") or payload.get("original_amount"),
            "note": payload.get("note"),
            "input_method": payload.get("input_method", "MANUAL"),
        }
        if payload.get("debt_id"):
            input_data["debt_id"] = payload["debt_id"]
        elif payload.get("supplier_id"):
            input_data["supplier_id"] = payload["supplier_id"]
        res = await call_mcp_tool("thu_no_nha_cung_cap", {"input": input_data, "user_id": current_user_id})
        result = normalize_mcp_result(res)
    elif intent in ("chi_phi", "chi_tien"):
        res = await call_mcp_tool("create_expense", {"payload": payload, "user_id": current_user_id})
        result = normalize_mcp_result(res)
    else:
        return {"success": False, "message": f"Chưa hỗ trợ xác nhận intent: {intent}"}

    # Nếu thực thi thất bại, không xóa session để user có thể sửa lại
    is_success = True
    if isinstance(result, dict):
        if result.get("success") is False or result.get("status") == "error":
            is_success = False

    if not is_success:
        return result

    # ========================================================
    # LIÊN KẾT VOICE RECORD VỚI TRANSACTION & GHI DATA LAKE
    # ========================================================
    tx_id = None
    if isinstance(result, dict):
        tx_id = result.get("transaction_id") or result.get("data", {}).get("transaction_id")

    if voice_id and tx_id:
        try:
            from app.services.voice_record_service import link_voice_record_to_transaction
            link_voice_record_to_transaction(
                db=db,
                voice_id=voice_id,
                transaction_id=tx_id,
                user_id=current_user_id
            )
        except Exception:
            pass

    # Ghi nhận User Correction Feedback vào MySQL & Data Lake nếu có thay đổi
    if correction_diff and (correction_diff.get("ai") or correction_diff.get("correction")):
        try:
            from app.services.user_correction_service import UserCorrectionService
            UserCorrectionService.save_user_correction(
                db=db,
                voice_record_id=voice_id,
                transaction_id=tx_id,
                user_id=current_user_id,
                ai_result=ai_result,
                corrected_result=payload,
                diff=correction_diff,
                correction_type=correction_type,
            )
        except Exception as uce:
            logger.warning(f"Lỗi lưu UserCorrection DB: {uce}")

        try:
            DataLakeService.save_correction_feedback(
                voice_record_id=voice_id,
                ai_result=ai_result,
                final_transaction=payload,
                diff=correction_diff,
                correction_type=correction_type,
                transaction_id=tx_id,
                user_id=current_user_id
            )
        except Exception as dle:
            logger.warning(f"Lỗi lưu Data Lake correction: {dle}")

    pending_confirmations.pop(session_key, None)
    pending_confirmations.pop(current_user_id, None)

    try:
        from app.services.websocket_manager import trigger_report_update
        trigger_report_update(
            user_id=current_user_id,
            affected=["sales", "purchase", "expense", "debt", "inventory", "profit"]
        )
    except Exception:
        pass

    return result


confirm_agent_endpoint = confirm_action
