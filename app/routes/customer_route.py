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

from app.schemas.customer_schema import (
    CreateCustomerRequest,
    UpdateCustomerRequest
)

from app.controllers.customer_controller import (
    create_customer_controller,
    get_customers_controller,
    get_customer_summary_controller,
    get_customer_detail_controller,
    update_customer_controller,
    delete_customer_controller
)


router = APIRouter(
    prefix="/api/customers",
    tags=["Customers"]
)


# CREATE CUSTOMER
@router.post(
    "",
    status_code=status.HTTP_201_CREATED
)
def create_customer(
    request: CreateCustomerRequest,
    payload: dict = Depends(
        authenticate_user
    ),
    db: Session = Depends(
        get_db
    )
):
    return create_customer_controller(
        request=request,
        payload=payload,
        db=db
    )


# GET CUSTOMERS
@router.get("")
def get_customers(
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
    return get_customers_controller(
        payload=payload,
        db=db,
        search=search,
        page=page,
        limit=limit
    )


# CUSTOMER SUMMARY
@router.get("/summary")
def get_customer_summary(
    payload: dict = Depends(
        authenticate_user
    ),
    db: Session = Depends(
        get_db
    )
):
    return get_customer_summary_controller(
        payload=payload,
        db=db
    )


# CUSTOMER DETAIL
@router.get("/{customer_id}")
def get_customer_detail(
    customer_id: int,
    payload: dict = Depends(
        authenticate_user
    ),
    db: Session = Depends(
        get_db
    )
):
    return get_customer_detail_controller(
        customer_id=customer_id,
        payload=payload,
        db=db
    )


# UPDATE CUSTOMER
@router.patch("/{customer_id}")
def update_customer(
    customer_id: int,
    request: UpdateCustomerRequest,
    payload: dict = Depends(
        authenticate_user
    ),
    db: Session = Depends(
        get_db
    )
):
    return update_customer_controller(
        customer_id=customer_id,
        request=request,
        payload=payload,
        db=db
    )


# DELETE CUSTOMER
@router.delete("/{customer_id}")
def delete_customer(
    customer_id: int,
    payload: dict = Depends(
        authenticate_user
    ),
    db: Session = Depends(
        get_db
    )
):
    return delete_customer_controller(
        customer_id=customer_id,
        payload=payload,
        db=db
    )
