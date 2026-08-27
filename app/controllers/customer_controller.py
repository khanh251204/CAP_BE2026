from typing import Optional

from sqlalchemy.orm import Session

from app.schemas.customer_schema import (
    CreateCustomerRequest,
    UpdateCustomerRequest
)

from app.services.customer_service import (
    create_customer_service,
    get_customers_service,
    get_customer_summary_service,
    get_customer_detail_service,
    update_customer_service,
    delete_customer_service
)


# CREATE CUSTOMER
def create_customer_controller(
    request: CreateCustomerRequest,
    payload: dict,
    db: Session
):
    return create_customer_service(
        db=db,
        payload=payload,
        data=request
    )


# GET CUSTOMERS
def get_customers_controller(
    payload: dict,
    db: Session,
    search: Optional[str] = None,
    page: int = 1,
    limit: int = 20
):
    return get_customers_service(
        db=db,
        payload=payload,
        search=search,
        page=page,
        limit=limit
    )


# CUSTOMER SUMMARY
def get_customer_summary_controller(
    payload: dict,
    db: Session
):
    return get_customer_summary_service(
        db=db,
        payload=payload
    )


# CUSTOMER DETAIL
def get_customer_detail_controller(
    customer_id: int,
    payload: dict,
    db: Session
):
    return get_customer_detail_service(
        db=db,
        payload=payload,
        customer_id=customer_id
    )


# UPDATE CUSTOMER
def update_customer_controller(
    customer_id: int,
    request: UpdateCustomerRequest,
    payload: dict,
    db: Session
):
    return update_customer_service(
        db=db,
        payload=payload,
        customer_id=customer_id,
        data=request
    )


# DELETE CUSTOMER
def delete_customer_controller(
    customer_id: int,
    payload: dict,
    db: Session
):
    return delete_customer_service(
        db=db,
        payload=payload,
        customer_id=customer_id
    )
