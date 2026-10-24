from typing import Optional
from fastapi import APIRouter, Depends, Path, Query, status
from sqlalchemy.orm import Session

from app.configs.database import get_db
from app.configs.jwt import get_current_user_id, require_permission
from app.services.supplier_service import SupplierService
from app.services.debt_service import DebtService
from app.schemas.supplier_schema import (
    SupplierCreateRequest,
    SupplierUpdateRequest,
    SupplierResponse,
    SupplierDetailResponse,
    SupplierDebtListResponse,
    PaginatedSupplierListResponse,
)
from app.schemas.debt_schema import (
    FIFODebtPaymentRequest,
    SupplierFIFOPaymentResponse,
)

supplier_router = APIRouter(tags=["Supplier Management"])


@supplier_router.post(
    "/suppliers",
    response_model=SupplierResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Tạo mới nhà cung cấp (Mục 18)",
    dependencies=[Depends(require_permission("supplier:manage"))],
)
def create_supplier(
    request: SupplierCreateRequest,
    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user_id),
):
    return SupplierService.create_supplier(user_id=user_id, request=request, db=db)


@supplier_router.get(
    "/suppliers",
    response_model=PaginatedSupplierListResponse,
    summary="Lấy danh sách nhà cung cấp (Mục 18)",
    dependencies=[Depends(require_permission("supplier:read"))],
)
def get_suppliers(
    search: Optional[str] = Query(None, description="Tìm kiếm theo tên hoặc số điện thoại"),
    page: int = Query(1, ge=1, description="Số trang"),
    limit: int = Query(20, ge=1, le=100, description="Số lượng bản ghi mỗi trang"),
    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user_id),
):
    return SupplierService.get_suppliers(
        user_id=user_id,
        db=db,
        search=search,
        page=page,
        limit=limit,
    )


@supplier_router.get(
    "/suppliers/{supplier_id}",
    response_model=SupplierDetailResponse,
    summary="Chi tiết nhà cung cấp kèm tổng quan công nợ (Mục 19)",
    dependencies=[Depends(require_permission("supplier:read"))],
)
def get_supplier_detail(
    supplier_id: int = Path(..., ge=1, description="ID nhà cung cấp"),
    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user_id),
):
    return SupplierService.get_supplier_detail(
        supplier_id=supplier_id,
        user_id=user_id,
        db=db,
    )


@supplier_router.patch(
    "/suppliers/{supplier_id}",
    response_model=SupplierResponse,
    summary="Cập nhật thông tin nhà cung cấp (PATCH - Mục 18)",
    dependencies=[Depends(require_permission("supplier:manage"))],
)
@supplier_router.put(
    "/suppliers/{supplier_id}",
    response_model=SupplierResponse,
    summary="Cập nhật thông tin nhà cung cấp (PUT)",
    dependencies=[Depends(require_permission("supplier:manage"))],
)
def update_supplier(
    supplier_id: int = Path(..., ge=1, description="ID nhà cung cấp"),
    request: SupplierUpdateRequest = ...,
    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user_id),
):
    return SupplierService.update_supplier(
        supplier_id=supplier_id,
        user_id=user_id,
        request=request,
        db=db,
    )


@supplier_router.delete(
    "/suppliers/{supplier_id}",
    summary="Xóa nhà cung cấp (Mục 18)",
    dependencies=[Depends(require_permission("supplier:manage"))],
)
def delete_supplier(
    supplier_id: int = Path(..., ge=1, description="ID nhà cung cấp"),
    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user_id),
):
    return SupplierService.delete_supplier(
        supplier_id=supplier_id,
        user_id=user_id,
        db=db,
    )


@supplier_router.get(
    "/suppliers/{supplier_id}/debts",
    response_model=SupplierDebtListResponse,
    summary="Danh sách công nợ chi tiết của nhà cung cấp kèm sản phẩm (Mục 18)",
    dependencies=[Depends(require_permission("debt:read"))],
)
def get_supplier_debts(
    supplier_id: int = Path(..., ge=1, description="ID nhà cung cấp"),
    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user_id),
):
    return SupplierService.get_supplier_debts(
        supplier_id=supplier_id,
        user_id=user_id,
        db=db,
    )


@supplier_router.post(
    "/suppliers/{supplier_id}/debt-payments",
    response_model=SupplierFIFOPaymentResponse,
    summary="Thanh toán tổng công nợ nhà cung cấp theo thuật toán FIFO (Mục 14)",
    dependencies=[Depends(require_permission("debt:manage"))],
)
def pay_supplier_debt_fifo(
    supplier_id: int = Path(..., ge=1, description="ID nhà cung cấp"),
    request: FIFODebtPaymentRequest = ...,
    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user_id),
):
    return DebtService.pay_supplier_debts_fifo(
        supplier_id=supplier_id,
        account_id=request.account_id,
        amount=request.amount,
        payment_date=request.payment_date,
        note=request.note,
        user_id=user_id,
        db=db,
    )
