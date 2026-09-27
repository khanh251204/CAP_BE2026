from fastapi import APIRouter, Depends, Query, HTTPException, status
from sqlalchemy.orm import Session
from typing import Optional

from app.configs.database import get_db
from app.configs.jwt import get_current_user_id
from app.controllers.transaction_controller import TransactionController
from app.schemas.transaction_schema import (
    TransactionCreateRequest,
    TransactionListResponse,
    TransactionResponseItem,
)


transaction_router = APIRouter(tags=["Transactions"])


@transaction_router.get(
    "/transactions",
    response_model=TransactionListResponse,
    summary="Lấy danh sách giao dịch (Transaction) có phân trang và bộ lọc intent_type"
)
def get_transactions(
    page: int = Query(
        default=1,
        ge=1,
        description="Số trang (bắt đầu từ 1)"
    ),
    limit: int = Query(
        default=10,
        ge=1,
        le=100,
        description="Số lượng bản ghi trên một trang"
    ),
    intent_type: Optional[str] = Query(
        default=None,
        description="Lọc theo loại intent (INCOME, EXPENSE, DEBT, TRANFER, REFUND, NONE theo docs/erd.md)"
    ),
    intent: Optional[str] = Query(
        default=None,
        description="Lọc theo tên intent cụ thể (ban_hang, mua_hang, chi_tien, ghi_no_khach_hang...)"
    ),
    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user_id),
):
    """
    Lấy danh sách giao dịch của người dùng hiện tại theo đúng cấu trúc model Transaction và docs/erd.md:
    Bao gồm thông tin Transaction, Transaction_Detail, Product, Customer, Supplier, Account, Intent (kèm intent_type).
    """
    return TransactionController.get_transactions(
        db=db,
        user_id=user_id,
        page=page,
        limit=limit,
        intent_type=intent_type,
        intent=intent,
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
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Dữ liệu không hợp lệ: {str(ve)}"
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Lưu database thất bại: {str(e)}"
        )