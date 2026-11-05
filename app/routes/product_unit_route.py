from typing import List, Optional

from fastapi import APIRouter, Depends, Path
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.configs.database import get_db
from app.configs.jwt import get_current_user_id, require_permission
from app.services.product_unit_service import ProductUnitService

product_unit_router = APIRouter(tags=["Product Unit"])


class ProductUnitInput(BaseModel):
    unit_name: str = Field(..., description="Tên đơn vị quy đổi, vd 'gói', 'thùng'")
    factor: float = Field(..., gt=0, description="Số đơn vị tính kho trong 1 đơn vị này (1 gói = 1000 g -> 1000)")


class ProductUnitReplaceRequest(BaseModel):
    """Ghi đè toàn bộ đơn vị quy đổi. Danh sách rỗng = xóa hết."""
    units: List[ProductUnitInput] = Field(default_factory=list)


class ProductUnitItem(BaseModel):
    unit_name: str
    factor: float


class ProductUnitResponse(BaseModel):
    product_id: int
    product_name: str
    default_unit: Optional[str] = None
    units: List[ProductUnitItem]


@product_unit_router.get(
    "/products/{product_id}/units",
    response_model=ProductUnitResponse,
    summary="Xem đơn vị quy đổi của sản phẩm (1 gói = 1000 g...)",
    dependencies=[Depends(require_permission("product:read"))],
)
def get_product_units(
    product_id: int = Path(..., ge=1),
    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user_id),
):
    return ProductUnitService(db).get_units(user_id, product_id)


@product_unit_router.put(
    "/products/{product_id}/units",
    response_model=ProductUnitResponse,
    summary="Ghi đè đơn vị quy đổi của sản phẩm (danh sách rỗng = xóa)",
    dependencies=[Depends(require_permission("product:update"))],
)
def replace_product_units(
    request: ProductUnitReplaceRequest,
    product_id: int = Path(..., ge=1),
    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user_id),
):
    units = [u.model_dump() for u in request.units]
    return ProductUnitService(db).replace_units(user_id, product_id, units)
