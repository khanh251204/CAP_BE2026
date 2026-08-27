from typing import Optional

from fastapi import (
    HTTPException,
    status
)

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.repositories.supplier_repository import (
    count_suppliers,
    create_supplier,
    delete_supplier,
    get_supplier_by_id,
    get_suppliers_by_user,
    update_supplier
)

from app.schemas.supplier_schema import (
    CreateSupplierRequest,
    UpdateSupplierRequest
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


# SUPPLIER TO DICT
def supplier_to_dict(
    supplier
) -> dict:
    return {
        "supplierId": supplier.supplier_id,
        "name": supplier.name,
        "phoneNumber": supplier.phone_number,
        "email": supplier.email,
        "address": supplier.address,
        "productGroup": supplier.product_group,
        "taxCode": supplier.tax_code,
        "note": supplier.note,
        "createdAt": (
            supplier.created_at.isoformat()
            if supplier.created_at
            else None
        ),
        "updatedAt": (
            supplier.updated_at.isoformat()
            if supplier.updated_at
            else None
        )
    }


# SUPPLIER LIST ITEM
def supplier_to_list_item(
    supplier
) -> dict:
    return {
        "supplierId": supplier.supplier_id,
        "name": supplier.name,
        "phoneNumber": supplier.phone_number,
        "productGroup": supplier.product_group,

        # TODO: tính từ giao dịch nhập hàng
        "purchaseCount": 0,

        # TODO: tính từ Debt
        "totalDebt": 0
    }


# CREATE SUPPLIER
def create_supplier_service(
    db: Session,
    payload: dict,
    data: CreateSupplierRequest
):
    try:
        user_id = get_current_user_id(
            payload
        )

        supplier = create_supplier(
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
            product_group=data.productGroup,
            tax_code=data.taxCode,
            note=data.note
        )

        db.commit()

        db.refresh(
            supplier
        )

        return {
            "success": True,
            "message": "Thêm nhà cung cấp thành công",
            "supplier": supplier_to_dict(
                supplier
            )
        }

    except HTTPException:
        db.rollback()
        raise

    except IntegrityError:
        db.rollback()

        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Không thể thêm nhà cung cấp"
        )

    except Exception:
        db.rollback()

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Không thể thêm nhà cung cấp"
        )


# GET SUPPLIERS
def get_suppliers_service(
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

    suppliers = get_suppliers_by_user(
        db=db,
        user_id=user_id,
        search=search,
        offset=offset,
        limit=limit
    )

    total = count_suppliers(
        db=db,
        user_id=user_id,
        search=search
    )

    return {
        "success": True,
        "items": [
            supplier_to_list_item(
                supplier
            )
            for supplier in suppliers
        ],
        "pagination": {
            "page": page,
            "limit": limit,
            "total": total
        }
    }


# SUPPLIER SUMMARY
def get_supplier_summary_service(
    db: Session,
    payload: dict
):
    user_id = get_current_user_id(
        payload
    )

    total_suppliers = count_suppliers(
        db=db,
        user_id=user_id
    )

    return {
        "totalSuppliers": total_suppliers,

        # TODO: tính từ Debt
        "suppliersWithDebt": 0,

        # TODO: tính từ Debt
        "totalDebt": 0
    }


# GET SUPPLIER DETAIL
def get_supplier_detail_service(
    db: Session,
    payload: dict,
    supplier_id: int
):
    user_id = get_current_user_id(
        payload
    )

    supplier = get_supplier_by_id(
        db=db,
        supplier_id=supplier_id,
        user_id=user_id
    )

    if not supplier:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Không tìm thấy nhà cung cấp"
        )

    result = supplier_to_dict(
        supplier
    )

    result["stats"] = {
        # TODO: tính từ giao dịch nhập hàng
        "purchaseCount": 0,

        # TODO: tính từ giao dịch nhập hàng
        "totalPurchase": 0,

        # TODO: tính từ Debt
        "totalDebt": 0
    }

    result["recentPurchases"] = []

    return result


# UPDATE SUPPLIER
def update_supplier_service(
    db: Session,
    payload: dict,
    supplier_id: int,
    data: UpdateSupplierRequest
):
    try:
        user_id = get_current_user_id(
            payload
        )

        supplier = get_supplier_by_id(
            db=db,
            supplier_id=supplier_id,
            user_id=user_id
        )

        if not supplier:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Không tìm thấy nhà cung cấp"
            )

        request_data = data.model_dump(
            exclude_unset=True
        )

        field_map = {
            "name": "name",
            "phoneNumber": "phone_number",
            "email": "email",
            "address": "address",
            "productGroup": "product_group",
            "taxCode": "tax_code",
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

        update_supplier(
            supplier=supplier,
            updates=updates
        )

        db.commit()

        db.refresh(
            supplier
        )

        return {
            "success": True,
            "message": "Cập nhật nhà cung cấp thành công",
            "supplier": supplier_to_dict(
                supplier
            )
        }

    except HTTPException:
        db.rollback()
        raise

    except IntegrityError:
        db.rollback()

        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Không thể cập nhật nhà cung cấp"
        )

    except Exception:
        db.rollback()

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Không thể cập nhật nhà cung cấp"
        )


# DELETE SUPPLIER
def delete_supplier_service(
    db: Session,
    payload: dict,
    supplier_id: int
):
    try:
        user_id = get_current_user_id(
            payload
        )

        supplier = get_supplier_by_id(
            db=db,
            supplier_id=supplier_id,
            user_id=user_id
        )

        if not supplier:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Không tìm thấy nhà cung cấp"
            )

        delete_supplier(
            db=db,
            supplier=supplier
        )

        db.commit()

        return {
            "success": True,
            "message": "Xóa nhà cung cấp thành công"
        }

    except HTTPException:
        db.rollback()
        raise

    except IntegrityError:
        db.rollback()

        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "Không thể xóa nhà cung cấp "
                "vì đang có dữ liệu liên quan"
            )
        )

    except Exception:
        db.rollback()

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Không thể xóa nhà cung cấp"
        )