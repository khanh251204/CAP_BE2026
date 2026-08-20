from typing import Optional

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.models.supplier_model import Supplier


# CREATE SUPPLIER
def create_supplier(
    db: Session,
    user_id: int,
    name: str,
    phone_number: Optional[str] = None,
    email: Optional[str] = None,
    address: Optional[str] = None,
    product_group: Optional[str] = None,
    tax_code: Optional[str] = None,
    note: Optional[str] = None
) -> Supplier:
    supplier = Supplier(
        user_id=user_id,
        name=name,
        phone_number=phone_number,
        email=email,
        address=address,
        product_group=product_group,
        tax_code=tax_code,
        note=note
    )

    db.add(
        supplier
    )

    db.flush()

    return supplier


# GET SUPPLIER BY ID
def get_supplier_by_id(
    db: Session,
    supplier_id: int,
    user_id: int
) -> Optional[Supplier]:
    return (
        db.query(Supplier)
        .filter(
            Supplier.supplier_id == supplier_id,
            Supplier.user_id == user_id
        )
        .first()
    )


# GET SUPPLIERS
def get_suppliers_by_user(
    db: Session,
    user_id: int,
    search: Optional[str] = None,
    offset: int = 0,
    limit: int = 20
) -> list[Supplier]:
    query = (
        db.query(Supplier)
        .filter(
            Supplier.user_id == user_id
        )
    )

    if search:
        search = search.strip()

        if search:
            search_value = (
                f"%{search}%"
            )

            query = query.filter(
                or_(
                    Supplier.name.ilike(
                        search_value
                    ),
                    Supplier.phone_number.ilike(
                        search_value
                    )
                )
            )

    return (
        query
        .order_by(
            Supplier.created_at.desc(),
            Supplier.supplier_id.desc()
        )
        .offset(
            offset
        )
        .limit(
            limit
        )
        .all()
    )


# COUNT SUPPLIERS
def count_suppliers(
    db: Session,
    user_id: int,
    search: Optional[str] = None
) -> int:
    query = (
        db.query(Supplier)
        .filter(
            Supplier.user_id == user_id
        )
    )

    if search:
        search = search.strip()

        if search:
            search_value = (
                f"%{search}%"
            )

            query = query.filter(
                or_(
                    Supplier.name.ilike(
                        search_value
                    ),
                    Supplier.phone_number.ilike(
                        search_value
                    )
                )
            )

    return query.count()


# UPDATE SUPPLIER
def update_supplier(
    supplier: Supplier,
    updates: dict
) -> Supplier:
    for field, value in updates.items():
        setattr(
            supplier,
            field,
            value
        )

    return supplier


# DELETE SUPPLIER
def delete_supplier(
    db: Session,
    supplier: Supplier
):
    db.delete(
        supplier
    )