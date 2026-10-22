from fastapi import APIRouter, Depends, Query, HTTPException, Request, status
from sqlalchemy.orm import Session
from typing import Optional

from app.configs.database import get_db
from app.configs.jwt import get_current_user_id
from app.controllers.transaction_controller import TransactionController
from app.schemas.transaction_schema import (
    TransactionCreateRequest,
    TransactionListResponse,
    TransactionResponseItem,
    IntentTypeEnum,
    IntentNameEnum,
    VALID_INTENT_TYPE_COMBINATIONS,
)


transaction_router = APIRouter(tags=["Transactions"])

ALLOWED_TRANSACTION_QUERY_PARAMS = {"page", "limit", "intent_type", "intent"}
VALID_INTENT_TYPES = {e.value for e in IntentTypeEnum}
VALID_INTENT_NAMES = {e.value for e in IntentNameEnum}


def parse_and_validate_transaction_query(
    request: Request,
    user_id: int = Depends(get_current_user_id),
) -> dict:
    """
    Validate query params cho API GET /transactions:
    - 401: Xác thực người dùng trước qua get_current_user_id.
    - 200: Nếu param không có hoặc để rỗng ("") thì không lọc, coi như None -> trả 200 OK bình thường.
    - 422: Nếu có truyền param nhưng sai giá trị / sai enum / tham số lạ / không khớp tổ hợp -> HTTP 422 Unprocessable Entity.
    """
    errors = []
    query_params = request.query_params

    # 1. Kiểm tra tham số lạ (extra params)
    for key in query_params.keys():
        if key not in ALLOWED_TRANSACTION_QUERY_PARAMS:
            errors.append({
                "loc": ["query", key],
                "msg": f"Tham số '{key}' không được hỗ trợ. Các tham số cho phép: {sorted(list(ALLOWED_TRANSACTION_QUERY_PARAMS))}",
                "type": "extra_forbidden"
            })

    # 2. Kiểm tra page
    page_raw = query_params.get("page")
    page = 1
    if page_raw is not None and page_raw.strip() != "":
        try:
            page = int(page_raw)
            if page < 1:
                errors.append({
                    "loc": ["query", "page"],
                    "msg": "Tham số 'page' phải lớn hơn hoặc bằng 1",
                    "type": "value_error"
                })
        except ValueError:
            errors.append({
                "loc": ["query", "page"],
                "msg": "Tham số 'page' phải là số nguyên hợp lệ",
                "type": "type_error"
            })

    # 3. Kiểm tra limit
    limit_raw = query_params.get("limit")
    limit = 10
    if limit_raw is not None and limit_raw.strip() != "":
        try:
            limit = int(limit_raw)
            if limit < 1 or limit > 100:
                errors.append({
                    "loc": ["query", "limit"],
                    "msg": "Tham số 'limit' phải nằm trong khoảng từ 1 đến 100",
                    "type": "value_error"
                })
        except ValueError:
            errors.append({
                "loc": ["query", "limit"],
                "msg": "Tham số 'limit' phải là số nguyên hợp lệ",
                "type": "type_error"
            })

    # 4. Kiểm tra intent_type (nếu không truyền hoặc để rỗng -> None, ra 200)
    raw_intent_type = query_params.get("intent_type")
    resolved_intent_type = None
    if raw_intent_type is not None:
        if raw_intent_type.strip() == "":
            resolved_intent_type = None
        elif raw_intent_type not in VALID_INTENT_TYPES:
            errors.append({
                "loc": ["query", "intent_type"],
                "msg": f"Loại intent '{raw_intent_type}' không hợp lệ. Chỉ chấp nhận: {', '.join(sorted(list(VALID_INTENT_TYPES)))}",
                "type": "enum"
            })
        else:
            resolved_intent_type = raw_intent_type

    # 5. Kiểm tra intent (nếu không truyền hoặc để rỗng -> None, ra 200)
    raw_intent = query_params.get("intent")
    resolved_intent = None
    if raw_intent is not None:
        if raw_intent.strip() == "":
            resolved_intent = None
        elif raw_intent not in VALID_INTENT_NAMES:
            errors.append({
                "loc": ["query", "intent"],
                "msg": f"Intent '{raw_intent}' không hợp lệ. Chỉ chấp nhận: {', '.join(sorted(list(VALID_INTENT_NAMES)))}",
                "type": "enum"
            })
        else:
            resolved_intent = raw_intent

    # 6. Kiểm tra ràng buộc tổ hợp (nếu cả 2 đều hợp lệ riêng rẽ)
    if resolved_intent and resolved_intent_type:
        allowed = VALID_INTENT_TYPE_COMBINATIONS.get(resolved_intent)
        if allowed and resolved_intent_type not in allowed:
            errors.append({
                "loc": ["query"],
                "msg": f"Intent '{resolved_intent}' không phù hợp với intent_type '{resolved_intent_type}'. Các intent_type hợp lệ: {sorted(list(allowed))}",
                "type": "combination_error"
            })

    if errors:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=errors
        )

    return {
        "user_id": user_id,
        "page": page,
        "limit": limit,
        "intent_type": resolved_intent_type,
        "intent": resolved_intent
    }


@transaction_router.get(
    "/transactions",
    response_model=TransactionListResponse,
    summary="Lấy danh sách giao dịch (Transaction) có phân trang và bộ lọc intent_type"
)
def get_transactions(
    params: dict = Depends(parse_and_validate_transaction_query),
    db: Session = Depends(get_db),
):
    """
    Lấy danh sách giao dịch của người dùng hiện tại theo đúng cấu trúc model Transaction và docs/erd_new.md:
    Bao gồm thông tin Transaction, Transaction_Detail, Product, Customer, Supplier, Account, Intent (kèm intent_type).
    """
    return TransactionController.get_transactions(
        db=db,
        user_id=params["user_id"],
        page=params["page"],
        limit=params["limit"],
        intent_type=params["intent_type"],
        intent=params["intent"],
    )


@transaction_router.get(
    "/transaction/{transaction_id}",
    response_model=TransactionResponseItem,
    summary="Lấy chi tiết giao dịch theo transaction_id"
)
def get_transaction_by_id(
    transaction_id: int,
    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user_id)
):
    """
    Lấy chi tiết một giao dịch cụ thể theo ID đối chiếu theo đúng model trong docs/erd.md.
    """
    result = TransactionController.get_transaction_by_id(
        db=db,
        user_id=user_id,
        transaction_id=transaction_id
    )

    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Không tìm thấy giao dịch với id {transaction_id}"
        )

    return result


@transaction_router.post(
    "/transaction",
    status_code=status.HTTP_201_CREATED,
    summary="Tạo hoặc lưu giao dịch mới"
)
@transaction_router.post(
    "/transactions",
    status_code=status.HTTP_201_CREATED,
    summary="Tạo hoặc lưu giao dịch mới (alias)",
    include_in_schema=False
)
def save_transaction(
    request: TransactionCreateRequest,
    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user_id),
):
    """
    Tạo hoặc lưu giao dịch mới đối chiếu với docs/erd.md:
    
    Hỗ trợ 2 chế độ:
    1. Direct Mode (chuẩn ERD):
       Gửi intent_id, category_id, account_id, customer_id, supplier_id,
       total_amount, payment_status ('PAID', 'PARTIAL', 'PENDING'),
       input_method ('VOICE', 'MANUAL'), input_text, note, transaction_date,
       và danh sách chi tiết dòng hàng `details`.
    
    2. Quick / Flat Mode (tương thích FE voice / NLP parsing):
       Gửi text, intent, product, price, quantity, unit, customer, supplier...
    """
    try:
        saved_transaction = TransactionController.create_transaction(
            db=db,
            user_id=user_id,
            request=request
        )

        return {
            "success": True,
            "message": "Đã lưu giao dịch thành công!",
            "data": saved_transaction
        }

    except ValueError as ve:
        err_msg = str(ve)
        # Gửi thông báo lỗi giao dịch tới người dùng & đẩy Push FCM
        try:
            from app.services.notification_service import NotificationService
            NotificationService.create_notification({
                "userId": str(user_id),
                "title": "Giao dịch không thành công ⚠️",
                "description": f"Không thể lưu giao dịch: {err_msg}",
                "notificationType": "TRANSACTION_FAILED",
                "icon": "alert-circle",
                "iconColor": "#FFFFFF",
                "borderColor": "#EF4444",
                "isRead": False
            })
        except Exception:
            pass

        # Các lỗi về giá trị sai (âm, = 0, vượt tồn kho, sai đơn vị tính, sản phẩm không tồn tại) -> trả 422 UNPROCESSABLE ENTITY theo chuẩn QA testcases
        if any(kw in err_msg.lower() for kw in ["phải lớn hơn", "không đủ tồn kho", "không khớp với đơn vị", "không tồn tại"]):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Dữ liệu không hợp lệ: {err_msg}"
            )
        # Các lỗi thiếu trường dữ liệu bắt buộc (thiếu unit, thiếu product, thiếu quantity...) -> trả 400 BAD REQUEST
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Dữ liệu không hợp lệ: {err_msg}"
        )
    except Exception as e:
        try:
            from app.services.notification_service import NotificationService
            NotificationService.create_notification({
                "userId": str(user_id),
                "title": "Lỗi hệ thống lưu giao dịch ❌",
                "description": f"Hệ thống gặp sự cố khi lưu giao dịch: {str(e)}",
                "notificationType": "TRANSACTION_ERROR",
                "icon": "close-circle",
                "iconColor": "#FFFFFF",
                "borderColor": "#EF4444",
                "isRead": False
            })
        except Exception:
            pass

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Lưu database thất bại: {str(e)}"
        )


@transaction_router.delete(
    "/transaction/{transaction_id}",
    summary="Xóa giao dịch và hoàn lại tồn kho, công nợ liên quan"
)
@transaction_router.delete(
    "/transactions/{transaction_id}",
    summary="Xóa giao dịch (alias)",
    include_in_schema=False
)
def delete_transaction(
    transaction_id: int,
    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user_id)
):
    """
    Xóa giao dịch theo transaction_id:
    - Bắt buộc kiểm tra quyền sở hữu (user_id).
    - Chặn xóa nếu giao dịch thuộc kỳ chốt sổ đã đóng (trả về 409).
    - Hoàn lại toàn bộ biến động kho (Inventory_Transaction), công nợ (Debt, DebtPayment) và số dư tài khoản.
    """
    return TransactionController.delete_transaction(
        db=db,
        user_id=user_id,
        transaction_id=transaction_id
    )