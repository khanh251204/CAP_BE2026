from sqlalchemy.orm import Session

from app.services.supplier_service import SupplierService


class SupplierController:

    @staticmethod
    def get_suppliers(
        db: Session,
        user_id
    ):

        suppliers = SupplierService.get_all_suppliers(
            db=db,
            user_id=user_id
        )

        return suppliers