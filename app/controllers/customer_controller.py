from sqlalchemy.orm import Session

from app.services.customer_service import CustomerService


class CustomerController:

    @staticmethod
    def get_customers(
        db: Session,
        user_id
    ):

        customers = CustomerService.get_all_customers(
            db=db,
            user_id=user_id
        )

        return customers