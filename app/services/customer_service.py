from typing import Optional

from fastapi import (
    HTTPException,
    status
)

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.repositories.customer_repository import (
    count_customers,
    create_customer,
    delete_customer,
    get_customer_by_id,
    get_customers_by_user,
    update_customer
)

from app.schemas.customer_schema import (
    CreateCustomerRequest,
    UpdateCustomerRequest
)


# GET USER ID
def get_current_user_id(
    payload: dict
) -> int:
    user_id = payload.get(
        "sub"
    )

    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Bạn chưa đăng nhập"
        )

    try:
        return int(
            user_id
        )

    except (
        TypeError,
        ValueError
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token không hợp lệ"
        )


# CUSTOMER TO DICT
def customer_to_dict(
    customer
) -> dict:
    return {
        "customerId": customer.customer_id,
        "name": customer.name,
        "phoneNumber": customer.phone_number,
        "email": customer.email,
        "address": customer.address,
        "note": customer.note,
        "createdAt": (
            customer.created_at.isoformat()
            if customer.created_at
            else None
        ),
        "updatedAt": (
            customer.updated_at.isoformat()
            if customer.updated_at
            else None
        )
    }


# CUSTOMER LIST ITEM
def customer_to_list_item(
    customer
) -> dict:
    return {
        "customerId": customer.customer_id,
        "name": customer.name,
        "phoneNumber": customer.phone_number,

        # TODO: lấy từ Transaction
        "transactionCount": 0,

        # TODO: lấy từ Debt
        "totalDebt": 0
    }


# CREATE CUSTOMER
def create_customer_service(
    db: Session,
    payload: dict,
    data: CreateCustomerRequest
):
    try:
        user_id = get_current_user_id(
            payload
        )

        customer = create_customer(
            db=db,
            user_id=user_id,
            name=data.name,
            phone_number=data.phoneNumber,
            email=(
                str(data.email)
                if data.email
                else None
            ),
            address=data.address,
            note=data.note
        )

        db.commit()

        db.refresh(
            customer
        )

        return {
            "success": True,
            "message": "Thêm khách hàng thành công",
            "customer": customer_to_dict(
                customer
            )
        }

    except HTTPException:
        db.rollback()
        raise

    except IntegrityError:
        db.rollback()

        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Không thể thêm khách hàng"
        )

    except Exception:
        db.rollback()

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Không thể thêm khách hàng"
        )


# GET CUSTOMERS
def get_customers_service(
    db: Session,
    payload: dict,
    search: Optional[str] = None,
    page: int = 1,
    limit: int = 20
):
    user_id = get_current_user_id(
        payload
    )

    if page < 1:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="page phải lớn hơn hoặc bằng 1"
        )

    if (
        limit < 1
        or limit > 100
    ):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="limit phải từ 1 đến 100"
        )

    offset = (
        page - 1
    ) * limit

    customers = get_customers_by_user(
        db=db,
        user_id=user_id,
        search=search,
        offset=offset,
        limit=limit
    )

    total = count_customers(
        db=db,
        user_id=user_id,
        search=search
    )

    return {
        "success": True,
        "items": [
            customer_to_list_item(
                customer
            )
            for customer in customers
        ],
        "pagination": {
            "page": page,
            "limit": limit,
            "total": total
        }
    }


# CUSTOMER SUMMARY
def get_customer_summary_service(
    db: Session,
    payload: dict
):
    user_id = get_current_user_id(
        payload
    )

    total_customers = count_customers(
        db=db,
        user_id=user_id
    )

    return {
        "totalCustomers": total_customers,

        # TODO: lấy từ Debt
        "customersWithDebt": 0,

        # TODO: lấy từ Debt
        "totalDebt": 0
    }


# GET CUSTOMER DETAIL
def get_customer_detail_service(
    db: Session,
    payload: dict,
    customer_id: int
):
    user_id = get_current_user_id(
        payload
    )

    customer = get_customer_by_id(
        db=db,
        customer_id=customer_id,
        user_id=user_id
    )

    if not customer:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Không tìm thấy khách hàng"
        )

    result = customer_to_dict(
        customer
    )

    result["stats"] = {
        # TODO: lấy từ Transaction
        "transactionCount": 0,

        # TODO: lấy từ Transaction
        "totalPurchase": 0,

        # TODO: lấy từ Debt
        "totalDebt": 0
    }

    result["recentTransactions"] = []

    return result


# UPDATE CUSTOMER
def update_customer_service(
    db: Session,
    payload: dict,
    customer_id: int,
    data: UpdateCustomerRequest
):
    try:
        user_id = get_current_user_id(
            payload
        )

        customer = get_customer_by_id(
            db=db,
            customer_id=customer_id,
            user_id=user_id
        )

        if not customer:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Không tìm thấy khách hàng"
            )

        request_data = data.model_dump(
            exclude_unset=True
        )

        field_map = {
            "name": "name",
            "phoneNumber": "phone_number",
            "email": "email",
            "address": "address",
            "note": "note"
        }

        updates = {}

        for request_field, db_field in field_map.items():

            if request_field not in request_data:
                continue

            value = request_data[
                request_field
            ]

            if (
                request_field == "email"
                and value is not None
            ):
                value = str(
                    value
                )

            updates[
                db_field
            ] = value

        update_customer(
            customer=customer,
            updates=updates
        )

        db.commit()

        db.refresh(
            customer
        )

        return {
            "success": True,
            "message": "Cập nhật khách hàng thành công",
            "customer": customer_to_dict(
                customer
            )
        }

    except HTTPException:
        db.rollback()
        raise

    except IntegrityError:
        db.rollback()

        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Không thể cập nhật khách hàng"
        )

    except Exception:
        db.rollback()

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Không thể cập nhật khách hàng"
        )


# DELETE CUSTOMER
def delete_customer_service(
    db: Session,
    payload: dict,
    customer_id: int
):
    try:
        user_id = get_current_user_id(
            payload
        )

        customer = get_customer_by_id(
            db=db,
            customer_id=customer_id,
            user_id=user_id
        )

        if not customer:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Không tìm thấy khách hàng"
            )

        delete_customer(
            db=db,
            customer=customer
        )

        db.commit()

        return {
            "success": True,
            "message": "Xóa khách hàng thành công"
        }

    except HTTPException:
        db.rollback()
        raise

    except IntegrityError:
        db.rollback()

        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "Không thể xóa khách hàng "
                "vì đang có dữ liệu liên quan"
            )
        )

    except Exception:
        db.rollback()

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Không thể xóa khách hàng"
        )