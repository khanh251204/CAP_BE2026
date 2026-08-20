from typing import Optional

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.models.customer_model import Customer


# CREATE CUSTOMER
def create_customer(
    db: Session,
    user_id: int,
    name: str,
    phone_number: Optional[str] = None,
    email: Optional[str] = None,
    address: Optional[str] = None,
    note: Optional[str] = None
) -> Customer:
    customer = Customer(
        user_id=user_id,
        name=name,
        phone_number=phone_number,
        email=email,
        address=address,
        note=note
    )

    db.add(customer)
    db.flush()

    return customer


# GET CUSTOMER BY ID
def get_customer_by_id(
    db: Session,
    customer_id: int,
    user_id: int
) -> Optional[Customer]:
    return (
        db.query(Customer)
        .filter(
            Customer.customer_id == customer_id,
            Customer.user_id == user_id
        )
        .first()
    )


# GET CUSTOMERS
def get_customers_by_user(
    db: Session,
    user_id: int,
    search: Optional[str] = None,
    offset: int = 0,
    limit: int = 20
) -> list[Customer]:
    query = (
        db.query(Customer)
        .filter(
            Customer.user_id == user_id
        )
    )

    if search:
        search = search.strip()

        if search:
            search_value = f"%{search}%"

            query = query.filter(
                or_(
                    Customer.name.ilike(
                        search_value
                    ),
                    Customer.phone_number.ilike(
                        search_value
                    )
                )
            )

    return (
        query
        .order_by(
            Customer.created_at.desc(),
            Customer.customer_id.desc()
        )
        .offset(offset)
        .limit(limit)
        .all()
    )


# COUNT CUSTOMERS
def count_customers(
    db: Session,
    user_id: int,
    search: Optional[str] = None
) -> int:
    query = (
        db.query(Customer)
        .filter(
            Customer.user_id == user_id
        )
    )

    if search:
        search = search.strip()

        if search:
            search_value = f"%{search}%"

            query = query.filter(
                or_(
                    Customer.name.ilike(
                        search_value
                    ),
                    Customer.phone_number.ilike(
                        search_value
                    )
                )
            )

    return query.count()


# UPDATE CUSTOMER
def update_customer(
    customer: Customer,
    updates: dict
) -> Customer:
    for field, value in updates.items():
        setattr(
            customer,
            field,
            value
        )

    return customer


# DELETE CUSTOMER
def delete_customer(
    db: Session,
    customer: Customer
):
    db.delete(
        customer
    )