from typing import Optional

from fastapi import (
    APIRouter,
    Depends,
    Query,
    status
)

from sqlalchemy.orm import Session

from app.configs.database import (
    get_db
)

from app.configs.jwt import (
    authenticate_user
)

from app.schemas.supplier_schema import (
    CreateSupplierRequest,
    UpdateSupplierRequest
)

from app.controllers.supplier_controller import (
    create_supplier_controller,
    get_suppliers_controller,
    get_supplier_summary_controller,
    get_supplier_detail_controller,
    update_supplier_controller,
    delete_supplier_controller
)


router = APIRouter(
    prefix="/api/suppliers",
    tags=["Suppliers"]
)


# CREATE SUPPLIER
@router.post(
    "",
    status_code=status.HTTP_201_CREATED
)
def create_supplier(
    request: CreateSupplierRequest,
    payload: dict = Depends(
        authenticate_user
    ),
    db: Session = Depends(
        get_db
    )
):
    return create_supplier_controller(
        request=request,
        payload=payload,
        db=db
    )


# GET SUPPLIERS
@router.get("")
def get_suppliers(
    search: Optional[str] = Query(
        default=None
    ),
    page: int = Query(
        default=1,
        ge=1
    ),
    limit: int = Query(
        default=20,
        ge=1,
        le=100
    ),
    payload: dict = Depends(
        authenticate_user
    ),
    db: Session = Depends(
        get_db
    )
):
    return get_suppliers_controller(
        payload=payload,
        db=db,
        search=search,
        page=page,
        limit=limit
    )


# SUPPLIER SUMMARY
@router.get("/summary")
def get_supplier_summary(
    payload: dict = Depends(
        authenticate_user
    ),
    db: Session = Depends(
        get_db
    )
):
    return get_supplier_summary_controller(
        payload=payload,
        db=db
    )


# SUPPLIER DETAIL
@router.get("/{supplier_id}")
def get_supplier_detail(
    supplier_id: int,
    payload: dict = Depends(
        authenticate_user
    ),
    db: Session = Depends(
        get_db
    )
):
    return get_supplier_detail_controller(
        supplier_id=supplier_id,
        payload=payload,
        db=db
    )


# UPDATE SUPPLIER
@router.patch("/{supplier_id}")
def update_supplier(
    supplier_id: int,
    request: UpdateSupplierRequest,
    payload: dict = Depends(
        authenticate_user
    ),
    db: Session = Depends(
        get_db
    )
):
    return update_supplier_controller(
        supplier_id=supplier_id,
        request=request,
        payload=payload,
        db=db
    )


# DELETE SUPPLIER
@router.delete("/{supplier_id}")
def delete_supplier(
    supplier_id: int,
    payload: dict = Depends(
        authenticate_user
    ),
    db: Session = Depends(
        get_db
    )
):
    return delete_supplier_controller(
        supplier_id=supplier_id,
        payload=payload,
        db=db
    )