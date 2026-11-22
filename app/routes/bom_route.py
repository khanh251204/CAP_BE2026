from typing import List

from fastapi import APIRouter, Depends, Path
from sqlalchemy.orm import Session

from app.configs.database import get_db
from app.configs.jwt import get_current_user_id, require_permission
from app.schemas.bom_schema import BomReplaceRequest, BomResponse, BomSummaryItem
from app.services.bom_service import BomService

bom_router = APIRouter(tags=["Bill Of Material"])


@bom_router.get(
    "/boms",
    response_model=List[BomSummaryItem],
    summary="Danh sách thành phẩm kèm định mức nguyên vật liệu (màn Công thức món)",
    dependencies=[Depends(require_permission("product:read"))],
)
def list_boms(
    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user_id),
):
    return BomService(db).list_boms(user_id)


@bom_router.get(
    "/products/{product_id}/bom",
    response_model=BomResponse,
    summary="Xem định mức nguyên vật liệu của thành phẩm",
    dependencies=[Depends(require_permission("product:read"))],
)
def get_bom(
    product_id: int = Path(..., ge=1),
    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user_id),
):
    return BomService(db).get_bom(user_id, product_id)


@bom_router.put(
    "/products/{product_id}/bom",
    response_model=BomResponse,
    summary="Ghi đè định mức nguyên vật liệu của thành phẩm (danh sách rỗng = xóa)",
    dependencies=[Depends(require_permission("product:update"))],
)
def replace_bom(
    request: BomReplaceRequest,
    product_id: int = Path(..., ge=1),
    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user_id),
):
    materials = [m.model_dump() for m in request.materials]
    return BomService(db).replace_bom(user_id, product_id, materials)


@bom_router.delete(
    "/products/{product_id}/bom",
    summary="Xóa toàn bộ định mức nguyên vật liệu của thành phẩm",
    dependencies=[Depends(require_permission("product:update"))],
)
def delete_bom(
    product_id: int = Path(..., ge=1),
    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user_id),
):
    return BomService(db).delete_bom(user_id, product_id)
