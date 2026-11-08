from typing import List, Optional

from sqlalchemy.orm import Session

from app.models.bom_model import BillOfMaterial
from app.models.product_model import Product


class BomRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_product(self, user_id: int, product_id: int) -> Optional[Product]:
        return (
            self.db.query(Product)
            .filter(Product.user_id == user_id, Product.product_id == product_id)
            .first()
        )

    def get_products(self, user_id: int, product_ids: List[int]) -> List[Product]:
        if not product_ids:
            return []
        return (
            self.db.query(Product)
            .filter(Product.user_id == user_id, Product.product_id.in_(product_ids))
            .all()
        )

    def get_lines(self, user_id: int, finished_product_id: int, active_only: bool = True) -> List[BillOfMaterial]:
        q = self.db.query(BillOfMaterial).filter(
            BillOfMaterial.user_id == user_id,
            BillOfMaterial.finished_product_id == finished_product_id,
        )
        if active_only:
            q = q.filter(BillOfMaterial.is_active.is_(True))
        return q.order_by(BillOfMaterial.bom_id).all()
