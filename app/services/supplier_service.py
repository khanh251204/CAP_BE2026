from sqlalchemy.orm import Session

from app.repositories.supplier_repositories import SupplierRepository


class SupplierService:

    @staticmethod
    def get_all_suppliers(
        db: Session,
        user_id: int
    ):
        return SupplierRepository.get_all_by_user(
            db=db,
            user_id=user_id
        )