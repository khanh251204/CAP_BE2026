from sqlalchemy.orm import Session
from app.models.supplier_model import Supplier


class SupplierRepository:

    @staticmethod
    def get_all_by_user(
        db: Session,
        user_id: int
    ):
        return (
            db.query(Supplier)
            .filter(
                Supplier.user_id == user_id
            )
            .order_by(Supplier.supplier_id.desc())
            .all()
        )