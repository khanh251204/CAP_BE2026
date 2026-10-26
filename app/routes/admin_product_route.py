"""
Admin Product Management — Router

Endpoints:
  GET /admin/products               — Danh sách sản phẩm (phân trang, search, filter, sort)
  GET /admin/products/{product_id}  — Chi tiết sản phẩm
  PATCH /admin/products/{product_id}/status — Cập nhật trạng thái sản phẩm (kích hoạt / ngừng kinh doanh)

Authorization: JWT + quyền admin_* (require_admin_area + require_permission)
"""
from typing import Optional

from fastapi import APIRouter, Depends, Query, Path
from sqlalchemy.orm import Session

from app.configs.database import get_db
from app.configs.jwt import require_permission, require_admin_area
from app.schemas.admin_product_schema import (
    AdminProductListResponse,
    AdminProductDetailResponse,
    AdminProductStatusUpdateRequest,
    AdminProductStatusUpdateResponse,
)
from app.services.admin_product_service import AdminProductService


router = APIRouter(
    prefix="/admin/products",
    tags=["Admin - Product Management"],
    dependencies=[Depends(require_admin_area)]
)


@router.get(
    "",
    response_model=AdminProductListResponse,
    summary="Xem danh sách sản phẩm (Admin)",
    description=(
        "Truy vấn danh sách sản phẩm toàn hệ thống với phân trang, "
        "tìm kiếm (theo tên sản phẩm, tên/email/cửa hàng User), "
        "bộ lọc (product_type, is_active, user_id), "
        "và sắp xếp."
    ),
    dependencies=[Depends(require_permission("admin_product:read"))],
)
def list_products(
    page: int = Query(1, ge=1, description="Trang hiện tại (bắt đầu từ 1)"),
    limit: int = Query(20, ge=1, le=100, description="Số bản ghi trên một trang"),
    search: Optional[str] = Query(
        None,
        description="Tìm theo tên sản phẩm, tên/email/tên cửa hàng User"
    ),
    user_id: Optional[int] = Query(None, description="Lọc theo ID người dùng sở hữu"),
    product_type: Optional[str] = Query(
        None,
        description="Lọc theo loại sản phẩm (RESALE, RAW_MATERIAL, FINISHED_GOOD)"
    ),
    is_active: Optional[bool] = Query(
        None,
        description="Lọc theo trạng thái kinh doanh (true = Hoạt động, false = Ngừng kinh doanh)"
    ),
    sort_by: Optional[str] = Query(
        "created_at",
        description="Sắp xếp theo: created_at, product_name, unit_price, product_id, owner_name, user_name, store_name"
    ),
    sort_order: Optional[str] = Query(
        "desc",
        description="Thứ tự sắp xếp: asc hoặc desc"
    ),
    db: Session = Depends(get_db),
):
    return AdminProductService.list_products(
        db=db,
        page=page,
        limit=limit,
        search=search,
        product_type=product_type,
        is_active=is_active,
        user_id=user_id,
        sort_by=sort_by or "created_at",
        sort_order=sort_order or "desc",
    )


@router.get(
    "/{product_id}",
    response_model=AdminProductDetailResponse,
    summary="Xem chi tiết sản phẩm (Admin)",
    description="Truy xuất thông tin chi tiết của một sản phẩm kèm thông tin người dùng sở hữu, tồn kho và số liệu liên quan.",
    dependencies=[Depends(require_permission("admin_product:read"))],
)
def get_product_detail(
    product_id: int = Path(..., description="ID sản phẩm"),
    db: Session = Depends(get_db),
):
    return AdminProductService.get_product_detail(
        db=db,
        product_id=product_id,
    )


@router.patch(
    "/{product_id}",
    response_model=AdminProductStatusUpdateResponse,
    summary="Cập nhật trạng thái sản phẩm (Admin)",
    description="Cập nhật trạng thái kích hoạt/ngừng kinh doanh (is_active) cho sản phẩm.",
    dependencies=[Depends(require_permission("admin_product:manage"))],
)
def update_product_status(
    product_id: int = Path(..., description="ID sản phẩm"),
    request: AdminProductStatusUpdateRequest = ...,
    db: Session = Depends(get_db),
):
    return AdminProductService.update_product_status(
        db=db,
        product_id=product_id,
        is_active=request.is_active,
    )
