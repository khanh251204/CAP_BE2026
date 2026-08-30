from sqlalchemy.orm import Session
from app.models.customer_model import Customer


class CustomerRepository:

    @staticmethod
    def get_all_by_user(
        db: Session,
        user_id: int
    ):
        return (
            db.query(Customer)
            .filter(
                Customer.user_id == user_id
            )
            .order_by(Customer.customer_id.desc())
            .all()
        )

    @staticmethod
    def get_by_name(
        db: Session,
        user_id: int,
        customer_name: str
    ):
        return (
            db.query(Customer)
            .filter(
                Customer.user_id == user_id,
                Customer.name.ilike(customer_name)
            )
            .first()
        )