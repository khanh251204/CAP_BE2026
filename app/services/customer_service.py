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

    @staticmethod
    def get_customer_for_sale(
        db: Session,
        user_id: int,
        customer_name: str | None,
    ):
        """
        Customer của intent ban_hang.

        - Không có customer -> None
        - Có customer -> phải tìm thấy trong DB
        - Không được tạo customer mới
        """

        if not customer_name:
            return None

        customer_name = str(customer_name).strip()

        if not customer_name:
            return None

        customer = CustomerRepository.get_by_name(
            db=db,
            user_id=user_id,
            customer_name=customer_name
        )

        if not customer:
            raise ValueError(
                f"Khách hàng '{customer_name}' không tồn tại "
            )

        return customer