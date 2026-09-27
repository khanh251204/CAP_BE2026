from decimal import Decimal
from typing import Optional
from datetime import datetime
from sqlalchemy.orm import Session

from app.models.supplier_model import Supplier
from app.models.customer_model import Customer
from app.models.product_model import Product


class InventoryLookupRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_supplier_by_name(self, user_id: int, name: str) -> Optional[Supplier]:
        if not name:
            return None
        clean_name = name.strip()
        supplier = (
            self.db.query(Supplier)
            .filter(
                Supplier.user_id == user_id,
                Supplier.supplier_name == clean_name,
            )
            .first()
        )
        if not supplier:
            supplier = (
                self.db.query(Supplier)
                .filter(
                    Supplier.user_id == user_id,
                    Supplier.supplier_name.ilike(f"%{clean_name}%"),
                )
                .first()
            )
        return supplier

    def create_supplier(
        self,
        user_id: int,
        supplier_name: str,
        note: Optional[str] = None
    ) -> Supplier:
        now = datetime.now()
        supplier = Supplier(
            user_id=user_id,
            supplier_name=supplier_name.strip(),
            note=note,
            created_at=now,
            updated_at=now,
        )
        self.db.add(supplier)
        self.db.flush()
        return supplier

    def get_customer_by_name(self, user_id: int, name: str) -> Optional[Customer]:
        if not name:
            return None
        clean_name = name.strip()
        customer = (
            self.db.query(Customer)
            .filter(
                Customer.user_id == user_id,
                Customer.customer_name == clean_name,
            )
            .first()
        )
        if not customer:
            customer = (
                self.db.query(Customer)
                .filter(
                    Customer.user_id == user_id,
                    Customer.customer_name.ilike(f"%{clean_name}%"),
                )
                .first()
            )
        return customer

    def get_product_id_by_name(self, user_id: int, name: str) -> Optional[int]:
        if not name:
            return None
        clean_name = name.strip()
        product = (
            self.db.query(Product)
            .filter(
                Product.user_id == user_id,
                Product.product_name == clean_name,
            )
            .first()
        )
        if not product:
            product = (
                self.db.query(Product)
                .filter(
                    Product.user_id == user_id,
                    Product.product_name.ilike(f"%{clean_name}%"),
                )
                .first()
            )
        return product.product_id if product else None

    def get_product_by_id(self, user_id: int, product_id: int) -> Optional[Product]:
        return (
            self.db.query(Product)
            .filter(
                Product.user_id == user_id,
                Product.product_id == product_id,
            )
            .first()
        )

    def get_product_price(self, user_id: int, product_id: int) -> Optional[Decimal]:
        product = self.get_product_by_id(user_id=user_id, product_id=product_id)
        if product and product.unit_price is not None and float(product.unit_price) > 0:
            return Decimal(str(product.unit_price))
        return None

    def get_product_by_name_and_unit(self, user_id: int, name: str, unit: str):
        query = (
            self.db.query(Product)
            .filter(
                Product.user_id == user_id,
                Product.product_name.ilike(f"%{name}%"),
            )
        )
        if unit:
            query = query.filter(Product.default_unit.ilike(unit))
        return query.first()

    # Compatibility alias
    get_product = get_product_by_id
