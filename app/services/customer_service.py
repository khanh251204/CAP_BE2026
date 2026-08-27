from sqlalchemy.orm import Session

from app.repositories.customer_repositories import CustomerRepository


class CustomerService:

    @staticmethod
    def get_all_customers(
        db: Session,
        user_id: int
    ):
        return CustomerRepository.get_all_by_user(
            db=db,
            user_id=user_id
        )