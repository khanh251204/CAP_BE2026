from typing import Optional

from sqlalchemy.orm import Session

from app.schemas.supplier_schema import (
    CreateSupplierRequest,
    UpdateSupplierRequest
)

from app.services.supplier_service import (
    create_supplier_service,
    get_suppliers_service,
    get_supplier_summary_service,
    get_supplier_detail_service,
    update_supplier_service,
    delete_supplier_service
)


# CREATE SUPPLIER
def create_supplier_controller(
    request: CreateSupplierRequest,
    payload: dict,
    db: Session
):
    return create_supplier_service(
        db=db,
        payload=payload,
        data=request
    )


# GET SUPPLIERS
def get_suppliers_controller(
    payload: dict,
    db: Session,
    search: Optional[str] = None,
    page: int = 1,
    limit: int = 20
):
    return get_suppliers_service(
        db=db,
        payload=payload,
        search=search,
        page=page,
        limit=limit
    )


# SUPPLIER SUMMARY
def get_supplier_summary_controller(
    payload: dict,
    db: Session
):
    return get_supplier_summary_service(
        db=db,
        payload=payload
    )


# SUPPLIER DETAIL
def get_supplier_detail_controller(
    supplier_id: int,
    payload: dict,
    db: Session
):
    return get_supplier_detail_service(
        db=db,
        payload=payload,
        supplier_id=supplier_id
    )


# UPDATE SUPPLIER
def update_supplier_controller(
    supplier_id: int,
    request: UpdateSupplierRequest,
    payload: dict,
    db: Session
):
    return update_supplier_service(
        db=db,
        payload=payload,
        supplier_id=supplier_id,
        data=request
    )


# DELETE SUPPLIER
def delete_supplier_controller(
    supplier_id: int,
    payload: dict,
    db: Session
):
    return delete_supplier_service(
        db=db,
        payload=payload,
        supplier_id=supplier_id
    )
