# app/routes/groq_route.py

import os
import asyncio
import logging
import tempfile
import traceback

from typing import Any, Optional
import re
from app.services.closing.closing_guard import PERIOD_CLOSED_CODE, is_period_closed_message
from fastapi import (
    APIRouter,
    UploadFile,
    File,
    Depends,
    HTTPException,
    Query,
    status,
)

from app.configs.permissions import INTENT_PERMISSIONS
from app.services.permission_service import PermissionService
from app.ai.llm.groq_service import GroqService
from app.ai.core.agent import Agent as TransactionAgent

from app.schemas.analysis_schema import AnalysisRequest
from app.configs.jwt import get_current_user_id, require_permission

from app.ai.rag.normalization_service import NormalizationService
from app.services.session_store_service import SessionStoreService


router = APIRouter()
logger = logging.getLogger(__name__)


# ============================================================
# SERVICES
# ============================================================

groq_service = GroqService()

# Chuẩn hóa từ lóng / đơn vị / tiền tệ bằng regex + từ điển (không cần vector DB)
normalization_service = NormalizationService()


# ============================================================
# AGENT
# ============================================================

transaction_agent = TransactionAgent(
    llm=groq_service,
    rag=normalization_service
)


# ============================================================
# TRANSACTION - AGENT
# ============================================================

@router.post("/agent/messages", dependencies=[Depends(require_permission("voice:use"))])
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
            def _sync_update_vr():
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
                except Exception as ex:
                    logger.warning(f"Lỗi cập nhật VoiceRecord analysis: {ex}")

            await asyncio.to_thread(_sync_update_vr)

        SessionStoreService.update_confirmation(
            current_user_id,
            {
                "voice_id": request.voice_id if request.voice_id else None,
                "input_method": input_method_val
            }
        )

        return result

    except Exception as e:
        logger.error(f"Lỗi xử lý giao dịch giọng nói: {e}", exc_info=True)

        # Chi tiết lỗi đã được log; không trả exception nội bộ (SQL, stacktrace...) ra client
        return {
            "success": False,
            "message": "Lỗi xử lý giao dịch"
        }


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


def _attach_error_message(result: Any) -> None:
    """
    Lỗi từ MCP trả về dạng {"success": False, "error": "Error executing tool x: 409: ..."}
    → luôn có `message` dễ đọc cho app; kỳ đã chốt → thêm `code` = PERIOD_CLOSED để app hỏi người dùng.
    """
    if not isinstance(result, dict):
        return
    raw = result.get("message") or result.get("error") or result.get("detail")
    if isinstance(raw, list):
        raw = " ".join(getattr(x, "text", str(x)) for x in raw)
    msg = re.sub(r"^\s*Error executing tool [\w_]+:\s*", "", str(raw or "")).strip()
    msg = re.sub(r"^\d{3}:\s*", "", msg).strip()
    result["message"] = msg or "Không thể lưu giao dịch. Vui lòng thử lại."
    if is_period_closed_message(msg):
        result["code"] = PERIOD_CLOSED_CODE


def _resolve_account_id(db: Session, user_id: int, payload: dict) -> int:
    """
    Tài khoản nhận/chi tiền cho thu nợ / trả nợ khi xác nhận giao dịch giọng nói.
    Dùng account_id trong payload nếu có (service công nợ sẽ kiểm tra tài khoản thuộc đúng user);
    nếu không có thì lấy tài khoản mặc định CỦA CHÍNH USER (ưu tiên tiền mặt, chưa có thì tạo).
    Trước đây mặc định là account_id = 1 — tài khoản của một user khác.
    """
    if payload.get("account_id"):
        return int(payload["account_id"])
    from app.services.account_service import AccountService

    account = AccountService.get_default_account(db=db, user_id=user_id) or AccountService.get_or_create_account_by_name(
        db=db, user_id=user_id, account_name="Tiền mặt", account_type="CASH"
    )
    return account.account_id


@router.post("/agent/pending-action/confirmation", dependencies=[Depends(require_permission("voice:use"))])
async def confirm_action(
    body: Optional[AgentConfirmRequest] = None,
    session_id: Optional[str] = Query(None),
    current_user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db)
):
    # Phiên chờ xác nhận luôn được lưu theo user_id của người đang đăng nhập.
    # Không dùng session_id do client gửi lên để tránh truy cập phiên của user khác.
    requested_session = (body.session_id if body and body.session_id else None) or session_id
    if requested_session and str(requested_session).strip() != str(current_user_id):
        return {
            "success": False,
            "message": "Phiên xác nhận không hợp lệ"
        }
    session_key = current_user_id
    pending = SessionStoreService.get_confirmation(session_key)

    if not pending:
        return {
            "success": False,
            "message": "Không có thao tác nào đang chờ xác nhận"
        }

    intent = pending["intent"]

    # Thao tác bằng giọng nói phải có cùng quyền như thao tác bằng tay
    required_permission = INTENT_PERMISSIONS.get(intent)
    if required_permission and not PermissionService.has_permission(current_user_id, required_permission):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Bạn không có quyền '{required_permission}' để xác nhận thao tác '{intent}'"
        )
    # Giao dịch kèm thêm sản phẩm mới vào danh mục cần thêm quyền tạo sản phẩm
    if (pending.get("payload") or {}).get("new_product") and not PermissionService.has_permission(current_user_id, "product:create"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Bạn không có quyền 'product:create' để thêm sản phẩm mới vào danh mục"
        )

    # Giao dịch kèm tạo nhà cung cấp mới cần thêm quyền quản lý nhà cung cấp
    if (pending.get("payload") or {}).get("new_supplier") and not PermissionService.has_permission(current_user_id, "supplier:manage"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Bạn không có quyền 'supplier:manage' để tạo nhà cung cấp mới"
        )
    # Giao dịch kèm tạo khách hàng mới cần thêm quyền quản lý khách hàng
    if (pending.get("payload") or {}).get("new_customer") and not PermissionService.has_permission(current_user_id, "customer:manage"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Bạn không có quyền 'customer:manage' để tạo khách hàng mới"
        )

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
        result = await asyncio.to_thread(ProductController.create_product, data=payload, user_id=current_user_id, db=db)
    elif intent == "sua_san_pham":
        result = await asyncio.to_thread(ProductController.update_product, product_id=payload["product_id"], data=payload["data"], user_id=current_user_id, db=db)
    elif intent == "xoa_san_pham":
        result = await asyncio.to_thread(ProductController.delete_product, product_id=payload["product_id"], user_id=current_user_id, db=db)
    elif intent == "ban_hang":
        # Kiểm tra lại giá sau khi người dùng có thể đã sửa
        sale_price = payload.get("unit_price")
        if sale_price is not None:
            try:
                sale_price = float(sale_price)
            except (TypeError, ValueError):
                sale_price = 0.0
            if sale_price <= 0:
                return {"success": False, "message": "Giá bán phải lớn hơn 0đ. Vui lòng nhập lại giá bán."}
        res = await call_mcp_tool("export_inventory", {"payload": payload, "user_id": current_user_id})
        result = normalize_mcp_result(res)
    elif intent in ("mua_hang", "nhap_hang"):
        # Kiểm tra lại sau khi người dùng có thể đã sửa số lượng / giá
        try:
            import_qty = float(payload.get("quantity") or 0)
        except (TypeError, ValueError):
            import_qty = 0.0
        if not payload.get("items") and import_qty <= 0:
            return {"success": False, "message": "Số lượng nhập phải lớn hơn 0. Vui lòng nhập lại số lượng."}
        import_price = payload.get("unit_price")
        if import_price is not None:
            try:
                import_price = float(import_price)
            except (TypeError, ValueError):
                import_price = 0.0
            if import_price <= 0:
                return {"success": False, "message": "Giá nhập phải lớn hơn 0đ. Vui lòng nhập lại giá nhập."}
        res = await call_mcp_tool("import_inventory", {"payload": payload, "user_id": current_user_id})
        result = normalize_mcp_result(res)
    elif intent == "nhap_kho":
        res = await call_mcp_tool("nhap_kho", {"payload": payload, "user_id": current_user_id})
        result = normalize_mcp_result(res)
    elif intent == "xuat_kho":
        res = await call_mcp_tool("xuat_kho", {"payload": payload, "user_id": current_user_id})
        result = normalize_mcp_result(res)
    elif intent == "hang_hong":
        res = await call_mcp_tool("report_damage", {"payload": payload, "user_id": current_user_id})
        result = normalize_mcp_result(res)
    elif intent in ("ghi_no_khach_hang", "khach_ghi_no"):
        # Ưu tiên số tiền người dùng đã sửa (amount), không thì dùng số tiền bản nháp
        debt_amount = payload.get("amount") if payload.get("amount") is not None else payload.get("original_amount")
        try:
            debt_amount = float(debt_amount)
        except (TypeError, ValueError):
            debt_amount = 0.0
        if debt_amount <= 0:
            return {"success": False, "message": "Số tiền ghi nợ phải lớn hơn 0. Vui lòng nhập lại số tiền khách nợ."}
        res = await call_mcp_tool("ghi_no_khach_hang", {
            "input": {
                "customer_id": payload.get("customer_id"),
                "customer_name": payload.get("customer_name"),
                "new_customer": bool(payload.get("new_customer")),
                "original_amount": debt_amount,
                "transaction_id": payload.get("transaction_id"),
                "input_method": payload.get("input_method", "MANUAL"),
            },
            "user_id": current_user_id
        })
        result = normalize_mcp_result(res)
    elif intent in ("thu_no_khach_hang", "thu_no_khach"):
        input_data = {
            "account_id": await asyncio.to_thread(_resolve_account_id, db, current_user_id, payload),
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
        # Ưu tiên số tiền người dùng đã sửa (amount), không thì dùng số tiền bản nháp
        supplier_debt_amount = payload.get("amount") if payload.get("amount") is not None else payload.get("original_amount")
        try:
            supplier_debt_amount = float(supplier_debt_amount)
        except (TypeError, ValueError):
            supplier_debt_amount = 0.0
        if supplier_debt_amount <= 0:
            return {"success": False, "message": "Số tiền ghi nợ phải lớn hơn 0. Vui lòng nhập lại số tiền nợ nhà cung cấp."}
        res = await call_mcp_tool("ghi_no_nha_cung_cap", {
            "input": {
                "supplier_id": payload["supplier_id"],
                "original_amount": supplier_debt_amount,
                "transaction_id": payload.get("transaction_id"),
                "note": payload.get("note"),
                "input_method": payload.get("input_method", "MANUAL"),
            },
            "user_id": current_user_id
        })
        result = normalize_mcp_result(res)
    elif intent in ("tra_no_nha_cung_cap", "tra_no_ncc"):
        input_data = {
            "account_id": await asyncio.to_thread(_resolve_account_id, db, current_user_id, payload),
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
        _attach_error_message(result)
        if voice_id:
            try:
                from app.services.voice_record_service import mark_voice_record_rejected
                await asyncio.to_thread(
                    mark_voice_record_rejected,
                    db=db,
                    voice_id=voice_id,
                    user_id=current_user_id,
                    reason=result.get("message") if isinstance(result, dict) else "Xác nhận giao dịch không thành công"
                )
            except Exception as ex:
                logger.warning(f"Lỗi đánh dấu voice record rejected: {ex}")
        return result

    # ========================================================
    # LIÊN KẾT VOICE RECORD VỚI TRANSACTION & GHI DATA LAKE (CHẠY TRÊN THREADPOOL)
    # ========================================================
    tx_id = None
    if isinstance(result, dict):
        tx_id = result.get("transaction_id") or result.get("data", {}).get("transaction_id")

    def _sync_post_confirm():
        if voice_id:
            try:
                from app.services.voice_record_service import link_voice_record_to_transaction
                link_voice_record_to_transaction(
                    db=db,
                    voice_id=voice_id,
                    transaction_id=tx_id,
                    user_id=current_user_id,
                    status="SUCCESS"
                )
            except Exception as e:
                logger.warning(f"Lỗi liên kết voice record: {e}")

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

        try:
            from app.services.websocket_manager import trigger_report_update
            trigger_report_update(
                user_id=current_user_id,
                affected=["sales", "purchase", "expense", "debt", "inventory", "profit"]
            )
        except Exception as wse:
            logger.warning(f"Lỗi trigger ws update: {wse}")

    await asyncio.to_thread(_sync_post_confirm)

    SessionStoreService.delete_confirmation(session_key)

    return result


@router.delete("/agent/pending-action", dependencies=[Depends(require_permission("voice:use"))])
async def cancel_action(
    session_id: Optional[str] = Query(None),
    current_user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db)
):
    """
    Xử lý khi người dùng KHÔNG ĐỒNG Ý hoặc BẤM HỦY giao dịch.
    Cập nhật VoiceRecord trong DB và Data Lake sang trạng thái FAILED (không thành công).
    """
    # Chỉ được hủy phiên của chính mình (session_id khác user hiện tại bị bỏ qua)
    if session_id and str(session_id).strip() != str(current_user_id):
        return {
            "success": False,
            "message": "Phiên xác nhận không hợp lệ"
        }
    pending = SessionStoreService.pop_confirmation(current_user_id)

    if pending and pending.get("voice_id"):
        try:
            from app.services.voice_record_service import mark_voice_record_rejected
            await asyncio.to_thread(
                mark_voice_record_rejected,
                db=db,
                voice_id=pending["voice_id"],
                user_id=current_user_id,
                reason="Người dùng đã hủy bỏ / không đồng ý xác nhận giao dịch"
            )
        except Exception as e:
            logger.warning(f"Lỗi cập nhật trạng thái hủy bỏ voice record: {e}")

    return {
        "success": True,
        "status": "cancelled",
        "message": "Đã hủy thao tác giao dịch thành công"
    }


confirm_agent_endpoint = confirm_action
