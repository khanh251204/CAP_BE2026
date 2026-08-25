from sqlalchemy.orm import Session

from app.models.debt_model import Debt
from app.models.customer_model import Customer
from app.models.supplier_model import Supplier
from app.repositories.debt_repository import DebtRepository


class DebtService:

    # ==========================================
    # FORMAT DATA
    # ==========================================

    @staticmethod
    def format_debt(result):

        debt, customer_name, supplier_name = result

        return {
    "debt_id": debt.debt_id,
    "transaction_id": debt.transaction_id,
    "user_id": debt.user_id,

    "customer_id": debt.customer_id,
    "customer_name": customer_name,

    "supplier_id": debt.supplier_id,
    "supplier_name": supplier_name,

    "direction": debt.direction,

    "original_amount": debt.original_amount,
    "remaining_amount": debt.remaining_amount,
    "status": debt.status,
    "created_at": debt.created_at,
    "updated_at": debt.updated_at,
}
    # ==========================================
    # GET ALL
    # ==========================================

    @staticmethod
    def get_all_debts(
        user_id: int,
        db: Session
    ):

        results = DebtRepository.get_all_by_user(
            user_id,
            db
        )

        return [
            DebtService.format_debt(item)
            for item in results
        ]

    # ==========================================
    # GET BY ID
    # ==========================================

    @staticmethod
    def get_debt_by_id(
        debt_id: int,
        db: Session
    ):

        result = DebtRepository.get_by_id(
            debt_id,
            db
        )

        if not result:
            return None

        return DebtService.format_debt(result)

    # ==========================================
    # GET BY USER
    # ==========================================

    @staticmethod
    def get_debts_by_user_id(
        user_id: int,
        db: Session
    ):

        results = DebtRepository.get_by_user_id(
            user_id,
            db
        )

        return [
            DebtService.format_debt(item)
            for item in results
        ]

    # ==========================================
    # SEARCH NAME
    # ==========================================

    @staticmethod
    def search_by_name(
        name: str,
        db: Session
    ):

        results = DebtRepository.search_by_name(
            name,
            db
        )

        return [
            DebtService.format_debt(item)
            for item in results
        ]

    # ==========================================
    # GET CUSTOMER
    # ==========================================

    @staticmethod
    def get_customer_name(
        customer_id: int,
        db: Session
    ):

        customer = DebtRepository.get_customer_by_id(
            customer_id,
            db
        )

        if not customer:
            return None

        return {
            "customer_id": customer.customer_id,
            "name": customer.name
        }

    # ==========================================
    # GET SUPPLIER
    # ==========================================

    @staticmethod
    def get_supplier_name(
        supplier_id: int,
        db: Session
    ):

        supplier = DebtRepository.get_supplier_by_id(
            supplier_id,
            db
        )

        if not supplier:
            return None

        return {
            "supplier_id": supplier.supplier_id,
            "name": supplier.name
        }

    # ==========================================
    # CREATE DEBT
    # ==========================================

    @staticmethod
    def create_debt(
        data: dict,
        db: Session
    ):

        user_id = data.get("user_id")

        if not user_id:
            raise ValueError(
                "User ID không được để trống"
            )

        customer_id = data.get("customer_id")
        supplier_id = data.get("supplier_id")

        # ======================================
        # PHẢI CÓ CUSTOMER HOẶC SUPPLIER
        # ======================================

        if not customer_id and not supplier_id:
            raise ValueError(
                "Phải có Customer ID hoặc Supplier ID"
            )

        # ======================================
        # CUSTOMER
        # ======================================

        if customer_id:

            customer = DebtRepository.get_customer_by_id(
                customer_id,
                db
            )

            if not customer:

                customer = Customer(
                    customer_id=customer_id,
                    user_id=user_id,
                    name=data.get(
                        "customer_name",
                        f"Khách hàng {customer_id}"
                    ),
                    phone_number=data.get(
                        "phone_number",
                        ""
                    ),
                    note=data.get(
                        "note",
                        ""
                    )
                )

                db.add(customer)
                db.flush()

        # ======================================
        # SUPPLIER
        # ======================================

        if supplier_id:

            supplier = DebtRepository.get_supplier_by_id(
                supplier_id,
                db
            )

            if not supplier:

                supplier = Supplier(
                    supplier_id=supplier_id,
                    user_id=user_id,
                    name=data.get(
                        "supplier_name",
                        f"Nhà cung cấp {supplier_id}"
                    ),
                    phone_number=data.get(
                        "phone_number",
                        ""
                    ),
                    note=data.get(
                        "note",
                        ""
                    )
                )

                db.add(supplier)
                db.flush()

        # ======================================
        # CREATE DEBT
        # ======================================

        debt = Debt(

            transaction_id=data.get(
                "transaction_id"
            ),

            user_id=user_id,

            customer_id=customer_id,

            supplier_id=supplier_id,

            direction=data["direction"],

            original_amount=data["original_amount"],

            remaining_amount=data.get(
                "remaining_amount",
                data["original_amount"]
            ),

            status=data.get(
                "status",
                "UNPAID"
            )
        )

        return DebtRepository.create(
            debt,
            db
        )

    # ==========================================
    # UPDATE
    # ==========================================

    @staticmethod
    def update_debt(
        debt_id: int,
        data: dict,
        db: Session
    ):

        result = DebtRepository.get_by_id(
            debt_id,
            db
        )

        if not result:
            return None

        debt, customer_name, supplier_name = result

        # ======================================
        # CUSTOMER
        # ======================================

        if "customer_id" in data:

            customer_id = data["customer_id"]

            if customer_id:

                customer = DebtRepository.get_customer_by_id(
                    customer_id,
                    db
                )

                if not customer:
                    return None

        # ======================================
        # SUPPLIER
        # ======================================

        if "supplier_id" in data:

            supplier_id = data["supplier_id"]

            if supplier_id:

                supplier = DebtRepository.get_supplier_by_id(
                    supplier_id,
                    db
                )

                if not supplier:
                    return None

        # ======================================
        # UPDATE
        # ======================================

        for key, value in data.items():

            if hasattr(debt, key):

                setattr(
                    debt,
                    key,
                    value
                )

        db.commit()
        db.refresh(debt)

        # ======================================
        # GET AGAIN
        # ======================================

        result = DebtRepository.get_by_id(
            debt_id,
            db
        )

        if not result:
            return None

        return DebtService.format_debt(
            result
        )

    # ==========================================
    # DELETE
    # ==========================================

    @staticmethod
    def delete_debt(
        debt_id: int,
        db: Session
    ):

        result = DebtRepository.get_by_id(
            debt_id,
            db
        )

        if not result:
            return None

        debt, customer_name, supplier_name = result

        return DebtRepository.delete(
            debt,
            db
        )