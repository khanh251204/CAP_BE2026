from decimal import Decimal
from typing import Optional, List
from datetime import datetime
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.supplier_model import Supplier
from app.models.customer_model import Customer
from app.models.product_model import Product


class AmbiguousMatchError(ValueError):
    """Tên tìm kiếm khớp nhiều bản ghi: phải hỏi lại người dùng, không tự chọn bừa."""

    def __init__(self, kind: str, query: str, candidates: List[str]):
        self.kind = kind
        self.query = query
        self.candidates = candidates
        shown = ", ".join(f"'{c}'" for c in candidates[:5])
        super().__init__(
            f"Có nhiều {kind} khớp với '{query}': {shown}. Vui lòng nói rõ tên hơn."
        )


MAX_FUZZY_CANDIDATES = 6


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
        # Dùng lại nhà cung cấp đã có (so khớp đã chuẩn hóa) thay vì tạo trùng
        from app.services.duplicate_guard import get_or_create_supplier_by_name
        return get_or_create_supplier_by_name(self.db, user_id, supplier_name, note=note)

    def get_customer_by_name(self, user_id: int, name: str) -> Optional[Customer]:
        """
        Tìm khách hàng: khớp chính xác (không phân biệt hoa thường) trước,
        sau đó khớp gần đúng. Nếu gần đúng ra nhiều kết quả -> AmbiguousMatchError.
        """
        if not name:
            return None
        clean_name = name.strip()
        exact = (
            self.db.query(Customer)
            .filter(
                Customer.user_id == user_id,
                func.lower(Customer.customer_name) == clean_name.lower(),
            )
            .first()
        )
        if exact:
            return exact

        matches = (
            self.db.query(Customer)
            .filter(
                Customer.user_id == user_id,
                Customer.customer_name.ilike(f"%{clean_name}%"),
            )
            .limit(MAX_FUZZY_CANDIDATES)
            .all()
        )
        if len(matches) > 1:
            raise AmbiguousMatchError("khách hàng", clean_name, [c.customer_name for c in matches])
        return matches[0] if matches else None

    def get_product_id_by_name(self, user_id: int, name: str) -> Optional[int]:
        """
        Tìm sản phẩm đang kinh doanh (is_active) theo tên: khớp chính xác trước,
        sau đó khớp gần đúng. Nếu gần đúng ra nhiều kết quả -> AmbiguousMatchError.
        """
        if not name:
            return None
        clean_name = name.strip()
        active = Product.is_active == True  # noqa: E712
        exact = (
            self.db.query(Product)
            .filter(
                Product.user_id == user_id,
                active,
                func.lower(Product.product_name) == clean_name.lower(),
            )
            .first()
        )
        if exact:
            return exact.product_id

        matches = (
            self.db.query(Product)
            .filter(
                Product.user_id == user_id,
                active,
                Product.product_name.ilike(f"%{clean_name}%"),
            )
            .limit(MAX_FUZZY_CANDIDATES)
            .all()
        )
        if len(matches) > 1:
            raise AmbiguousMatchError("sản phẩm", clean_name, [p.product_name for p in matches])
        return matches[0].product_id if matches else None

    def get_product_by_id(self, user_id: int, product_id: int) -> Optional[Product]:
        return (
            self.db.query(Product)
            .filter(
                Product.user_id == user_id,
                Product.product_id == product_id,
            )
            .first()
        )

    def lock_product(self, user_id: int, product_id: int) -> Optional[Product]:
        """
        Khóa dòng Product (SELECT ... FOR UPDATE) trước khi đọc/ghi tồn kho.
        Các giao dịch đồng thời trên cùng sản phẩm sẽ phải xếp hàng chờ,
        nên tồn kho đọc ra luôn là giá trị mới nhất (chống race condition).
        """
        return (
            self.db.query(Product)
            .filter(
                Product.user_id == user_id,
                Product.product_id == product_id,
            )
            .with_for_update()
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
