# app/routes/groq_route.py

import os
import asyncio
import tempfile
import traceback

# pyrefly: ignore [missing-import]
from fastapi import (
    APIRouter,
    UploadFile,
    File,
    Depends
)
from requests import Session

from app.ai.llm.groq_service import GroqService
from app.ai.core.agent import Agent as TransactionAgent

from app.schemas.analysis_schema import AnalysisRequest
from app.configs.jwt import get_current_user_id

from app.ai.rag.rag_service import RAGService
from app.ai.rag.vector_store import VectorStore


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

from app.api.stt import stt_groq
router.add_api_route("/stt/groq", stt_groq, methods=["POST"], tags=["Speech to Text"])


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


@router.post("/agent/confirm")
async def confirm_action(
    current_user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db)
):
    pending = pending_confirmations.get(current_user_id)

    if not pending:
        return {
            "success": False,
            "message": "Không có thao tác nào đang chờ xác nhận"
        }

    intent = pending["intent"]
    payload = pending["payload"]

    # ========================================================
    # THÊM SẢN PHẨM
    # ========================================================

    if intent == "them_san_pham":

        result = ProductController.create_product(
            data=payload,
            user_id=current_user_id,
            db=db
        )

    # ========================================================
    # SỬA SẢN PHẨM
    # ========================================================

    elif intent == "sua_san_pham":

        result = ProductController.update_product(
            product_id=payload["product_id"],
            data=payload["data"],
            user_id=current_user_id,
            db=db
        )

    # ========================================================
    # XÓA SẢN PHẨM
    # ========================================================

    elif intent == "xoa_san_pham":

        result = ProductController.delete_product(
            product_id=payload["product_id"],
            user_id=current_user_id,
            db=db
        )

    # ========================================================
    # BÁN HÀNG
    # ========================================================

    elif intent == "ban_hang":

        result = await call_mcp_tool(
            "export_inventory",
            {
                "payload": payload,
                "user_id": current_user_id
            }
        )

        result = normalize_mcp_result(result)

    # ========================================================
    # MUA HÀNG / NHẬP HÀNG
    # ========================================================

    elif intent in ("mua_hang", "nhap_hang"):

        result = await call_mcp_tool(
            "import_inventory",
            {
                "payload": payload,
                "user_id": current_user_id
            }
        )

        result = normalize_mcp_result(result)

    # ========================================================
    # NHẬP KHO
    # ========================================================

    elif intent == "nhap_kho":

        result = await call_mcp_tool(
            "nhap_kho",
            {
                "payload": payload,
                "user_id": current_user_id
            }
        )

        result = normalize_mcp_result(result)

    # ========================================================
    # XUẤT KHO
    # ========================================================

    elif intent == "xuat_kho":

        result = await call_mcp_tool(
            "xuat_kho",
            {
                "payload": payload,
                "user_id": current_user_id
            }
        )

        result = normalize_mcp_result(result)

    # ========================================================
    # GHI NỢ KHÁCH HÀNG
    # ========================================================

    elif intent in ("ghi_no_khach_hang", "khach_ghi_no"):

        result = await call_mcp_tool(
            "ghi_no_khach_hang",
            {
                "input": {
                    "customer_id": payload["customer_id"],
                    "original_amount": payload["original_amount"],
                    "transaction_id": payload.get("transaction_id"),
                },
                "user_id": current_user_id
            }
        )

        result = normalize_mcp_result(result)

    # ========================================================
    # THU NỢ KHÁCH HÀNG
    # ========================================================

    elif intent in ("thu_no_khach_hang", "thu_no_khach"):

        input_data = {
            "account_id": payload.get("account_id") or 1,
            "amount": payload.get("amount") or payload.get("original_amount"),
        }
        if payload.get("debt_id"):
            input_data["debt_id"] = payload["debt_id"]
        elif payload.get("customer_id"):
            input_data["customer_id"] = payload["customer_id"]

        result = await call_mcp_tool(
            "thu_no_khach_hang",
            {
                "input": input_data,
                "user_id": current_user_id
            }
        )

        result = normalize_mcp_result(result)

    # ========================================================
    # CHI PHÍ (EXPENSE)
    # ========================================================

    elif intent in ("chi_phi", "chi_tien"):

        result = await call_mcp_tool(
            "create_expense",
            {
                "payload": payload,
                "user_id": current_user_id
            }
        )

        result = normalize_mcp_result(result)

    # ========================================================
    # CHƯA HỖ TRỢ
    # ========================================================

    else:

        return {
            "success": False,
            "message": (
                f"Chưa hỗ trợ xác nhận intent: {intent}"
            )
        }

    # ========================================================
    # XÓA PENDING SAU KHI XỬ LÝ & TRIGGER REALTIME SOCKET
    # ========================================================

    pending_confirmations.pop(
        current_user_id,
        None
    )

    try:
        from app.services.websocket_manager import trigger_report_update
        trigger_report_update(
            user_id=current_user_id,
            affected=["sales", "purchase", "expense", "debt", "inventory", "profit"]
        )
    except Exception:
        pass

    return result
