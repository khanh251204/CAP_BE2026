"""
Đơn vị quy đổi của sản phẩm: "1 gói = 1000 g", "1 thùng = 24 lon".

Kho luôn ghi theo đơn vị tính kho (Product.default_unit). Đơn vị quy đổi dùng để:
- Nói / nhập theo đơn vị khác ("nhập 3 gói mì chính" -> 3000 g).
- Khai báo định mức theo đơn vị quen dùng.
Các đơn vị đo lường chung (g, kg, lạng, ml, lít...) đã tự quy đổi, không cần khai báo.
"""
from datetime import datetime
from decimal import ROUND_FLOOR, Decimal, InvalidOperation
from typing import Any, Dict, Iterable, List, Optional, Tuple

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.product_model import Product
from app.models.product_unit_model import ProductUnit
from app.services.sales_policy import is_unit_valid, unit_ratio, unit_key

MAX_FACTOR_DECIMALS = 4


def units_by_product(db: Session, user_id: int, product_ids: Iterable[int]) -> Dict[int, List[Dict[str, Any]]]:
    """{product_id: [{"unit_name", "factor"}]} của các sản phẩm (chỉ đơn vị đang dùng)."""
    ids = sorted({int(i) for i in product_ids if i})
    if not ids:
        return {}
    rows = (
        db.query(ProductUnit)
        .filter(
            ProductUnit.user_id == user_id,
            ProductUnit.product_id.in_(ids),
            ProductUnit.is_active.is_(True),
        )
        .order_by(ProductUnit.factor)
        .all()
    )
    result: Dict[int, List[Dict[str, Any]]] = {}
    for r in rows:
        result.setdefault(r.product_id, []).append({"unit_name": r.unit_name, "factor": float(r.factor)})
    return result


def _parse_factor(value: Any, unit_name: str, default_unit: str) -> Decimal:
    try:
        factor = Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"Số quy đổi của '{unit_name}' không hợp lệ")
    if factor <= 0:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"1 {unit_name} phải bằng số {default_unit} lớn hơn 0")
    if -factor.normalize().as_tuple().exponent > MAX_FACTOR_DECIMALS:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"Số quy đổi của '{unit_name}' tối đa {MAX_FACTOR_DECIMALS} chữ số thập phân",
        )
    return factor


class ProductUnitService:
    def __init__(self, db: Session):
        self.db = db

    def _get_product(self, user_id: int, product_id: int) -> Product:
        product = (
            self.db.query(Product)
            .filter(Product.user_id == user_id, Product.product_id == product_id)
            .first()
        )
        if not product:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Không tìm thấy sản phẩm")
        return product

    def _serialize(self, user_id: int, product: Product) -> Dict[str, Any]:
        return {
            "product_id": product.product_id,
            "product_name": product.product_name,
            "default_unit": product.default_unit,
            "units": units_by_product(self.db, user_id, [product.product_id]).get(product.product_id, []),
        }

    def get_units(self, user_id: int, product_id: int) -> Dict[str, Any]:
        return self._serialize(user_id, self._get_product(user_id, product_id))

    def replace_units(self, user_id: int, product_id: int, units: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Ghi đè toàn bộ đơn vị quy đổi của sản phẩm (đơn vị không còn trong danh sách -> xóa mềm)."""
        product = self._get_product(user_id, product_id)
        default_unit = (product.default_unit or "").strip()
        if not default_unit:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Sản phẩm chưa có đơn vị tính kho, hãy đặt đơn vị trước")

        wanted: Dict[str, tuple] = {}  # unit_key -> (tên hiển thị, factor)
        for u in units:
            name = " ".join(str(u.get("unit_name") or "").split())
            if not name:
                raise HTTPException(status.HTTP_400_BAD_REQUEST, "Tên đơn vị quy đổi không được để trống")
            if len(name) > 50:
                raise HTTPException(status.HTTP_400_BAD_REQUEST, f"Tên đơn vị '{name}' quá dài (tối đa 50 ký tự)")
            if is_unit_valid(name, default_unit):
                raise HTTPException(status.HTTP_400_BAD_REQUEST, f"'{name}' đã là đơn vị tính kho của sản phẩm")
            if unit_ratio(name, default_unit) is not None:
                raise HTTPException(
                    status.HTTP_400_BAD_REQUEST,
                    f"'{name}' và '{default_unit}' đã tự quy đổi cho nhau, không cần khai báo",
                )
            key = unit_key(name)
            if key in wanted:
                raise HTTPException(status.HTTP_400_BAD_REQUEST, f"Đơn vị '{name}' bị khai báo nhiều lần")
            wanted[key] = (name, _parse_factor(u.get("factor"), name, default_unit))

        now = datetime.now()
        existing = {
            unit_key(r.unit_name): r
            for r in self.db.query(ProductUnit).filter(
                ProductUnit.user_id == user_id, ProductUnit.product_id == product_id,
            ).all()
        }
        try:
            for key, row in existing.items():
                if key not in wanted and row.is_active:
                    row.is_active = False
                    row.updated_at = now
            for key, (name, factor) in wanted.items():
                row = existing.get(key)
                if row:
                    row.unit_name = name
                    row.factor = factor
                    row.is_active = True
                    row.updated_at = now
                else:
                    self.db.add(ProductUnit(
                        user_id=user_id, product_id=product_id, unit_name=name, factor=factor,
                        is_active=True, created_at=now, updated_at=now,
                    ))
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise
        return self._serialize(user_id, product)


# ======================================================================
# KIỂM KHO THEO ĐƠN VỊ ĐẾM (gói nguyên, bỏ gói đang dùng dở)
# ======================================================================
def pack_unit_of(extra_units: Optional[list], unit: Optional[str]) -> Optional[Dict[str, Any]]:
    """Đơn vị đóng gói đã khai báo (1 gói = 300 g, factor > 1) trùng với `unit`; None nếu không phải."""
    key = unit_key(unit)
    if not key:
        return None
    for u in extra_units or []:
        if unit_key(u.get("unit_name")) == key and Decimal(str(u.get("factor") or 0)) > 1:
            return u
    return None


def whole_packs(book: Any, pack: Dict[str, Any]) -> Tuple[Decimal, Decimal]:
    """Tồn sổ sách quy ra (số gói nguyên, phần lẻ theo đơn vị kho): 2450 g, gói 300 g -> (8, 50)."""
    factor = Decimal(str(pack["factor"]))
    stock = max(Decimal(str(book or 0)), Decimal("0"))
    whole = (stock / factor).to_integral_value(rounding=ROUND_FLOOR)
    return whole, stock - whole * factor


def counted_stock(book: Any, counted: Any, count_unit: Optional[str], stock_unit: Optional[str],
                  extra_units: Optional[list]) -> Optional[Decimal]:
    """
    Tồn thực tế (đơn vị kho) từ số đếm khi kiểm kho.
    - Đếm theo đơn vị kho -> chính số đếm.
    - Đếm theo gói đã khai báo -> so với số gói nguyên trong sổ (làm tròn xuống), chỉ ghi phần gói lệch;
      phần lẻ (gói đang dùng dở) giữ nguyên. Sổ 2450 g (8 gói + 50 g), đếm 7 gói -> 2150 g.
    - Đơn vị đo lường chung (kg khi kho tính g) -> quy đổi chính xác.
    Trả None nếu đơn vị không quy đổi được.
    """
    counted_dec = Decimal(str(counted))
    if not count_unit or is_unit_valid(count_unit, stock_unit):
        return counted_dec
    pack = pack_unit_of(extra_units, count_unit)
    if pack:
        whole, remainder = whole_packs(book, pack)
        return (remainder + counted_dec * Decimal(str(pack["factor"]))).quantize(Decimal("0.01"))
    ratio = unit_ratio(count_unit, stock_unit, extra_units)
    return None if ratio is None else (counted_dec * ratio).quantize(Decimal("0.01"))
