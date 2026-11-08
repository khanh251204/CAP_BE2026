"""
Định mức nguyên vật liệu (BOM) cho PRODUCER.

Quy tắc khai báo:
- Chỉ user PRODUCER.
- Thành phẩm phải là FINISHED_GOOD, nguyên liệu phải là RAW_MATERIAL, cùng user, đang kinh doanh.
  (Nguyên liệu không thể có BOM nên không có BOM lồng nhiều tầng.)
- Định mức > 0 và tối đa 2 chữ số thập phân: Inventory_Transaction chỉ lưu 2 chữ số lẻ,
  định mức lẻ hơn sẽ bị làm tròn khi trừ kho -> yêu cầu đổi đơn vị nhỏ hơn (kg -> g).
"""
from datetime import datetime
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from typing import Any, Callable, Dict, Iterable, List, Optional, Tuple

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.bom_model import BillOfMaterial
from app.models.product_model import Product
from app.repositories.bom_repository import BomRepository
from app.services.product_unit_service import units_by_product
from app.services.sales_policy import get_user_business_type, is_unit_valid, normalize_product_type, unit_ratio

MAX_DECIMAL_PLACES = 2
ERROR_INSUFFICIENT_MATERIAL = "INSUFFICIENT_MATERIAL"
_CENT = Decimal("0.01")


def fmt_qty(value: Any) -> str:
    """150 -> '150', 0.750 -> '0.75'."""
    text = format(Decimal(str(value)).normalize(), "f")
    return text


def aggregate_material_needs(requirements: Iterable[Tuple[Any, List[Dict[str, Any]]]]) -> List[Dict[str, Any]]:
    """
    Tổng nguyên liệu cần cho các thành phẩm phải làm thêm.
    requirements: [(số thành phẩm phải làm, các dòng định mức của thành phẩm đó)].
    Nhiều món dùng chung một nguyên liệu thì cộng gộp. Kết quả sắp theo material_product_id.
    """
    needs: Dict[int, Dict[str, Any]] = {}
    for produce_qty, lines in requirements:
        produce = Decimal(str(produce_qty or 0))
        if produce <= 0:
            continue
        for line in lines:
            mid = int(line["material_product_id"])
            need = (produce * Decimal(str(line["quantity_per_unit"]))).quantize(_CENT, rounding=ROUND_HALF_UP)
            entry = needs.setdefault(mid, {
                "material_product_id": mid,
                "material_name": line.get("material_name") or "",
                "unit": line.get("unit"),
                "quantity": Decimal("0"),
            })
            entry["quantity"] += need
    return [needs[mid] for mid in sorted(needs)]


def find_shortages(needs: List[Dict[str, Any]], stock_of: Callable[[int], Any]) -> List[Dict[str, Any]]:
    """Ghi tồn hiện tại vào từng dòng (stock_before) và trả về các nguyên liệu không đủ."""
    shortages = []
    for n in needs:
        stock = Decimal(str(stock_of(n["material_product_id"]) or 0))
        n["stock_before"] = stock
        if stock < n["quantity"]:
            shortages.append(n)
    return shortages


def materials_text(needs: List[Dict[str, Any]]) -> str:
    return ", ".join(f"{fmt_qty(n['quantity'])} {n.get('unit') or ''} {n['material_name']}".replace("  ", " ") for n in needs)


def shortage_message(shortages: List[Dict[str, Any]], what: str = "") -> str:
    detail = "; ".join(
        f"'{n['material_name']}' còn {fmt_qty(n['stock_before'])} {n.get('unit') or ''}, cần {fmt_qty(n['quantity'])} {n.get('unit') or ''}".replace("  ", " ").strip()
        for n in shortages
    )
    return f"Không đủ nguyên liệu{(' để làm ' + what) if what else ' theo định mức'}: {detail}."


def needs_to_json(needs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    out = []
    for n in needs:
        item = {
            "material_product_id": n["material_product_id"],
            "material_name": n["material_name"],
            "quantity": float(n["quantity"]),
            "unit": n.get("unit"),
        }
        if "stock_before" in n:
            item["quantity_in_stock"] = float(n["stock_before"])
        out.append(item)
    return out


def product_change_conflict(db: Session, user_id: int, product: Product, data: Dict[str, Any]) -> Optional[str]:
    """
    Lý do không cho sửa sản phẩm (None = được sửa). Chặn các thay đổi làm sai số liệu đã khai báo:
    - Đổi đơn vị tính kho khi đang có đơn vị quy đổi hoặc là nguyên liệu trong định mức
      (1 gói = 1000 g, 150 g/tô sẽ thành sai nếu kho chuyển sang kg).
    - Đổi loại sản phẩm khi đang là nguyên liệu trong định mức / thành phẩm đang có định mức.
    """
    from app.models.product_unit_model import ProductUnit

    pid = product.product_id
    old_unit = product.default_unit or ""
    new_unit = data.get("default_unit")
    old_type = normalize_product_type(product.product_type)
    new_type = data.get("product_type")
    new_type = normalize_product_type(new_type) if new_type else old_type

    def dishes_using() -> List[str]:
        rows = (
            db.query(Product.product_name)
            .join(BillOfMaterial, BillOfMaterial.finished_product_id == Product.product_id)
            .filter(
                BillOfMaterial.user_id == user_id,
                BillOfMaterial.material_product_id == pid,
                BillOfMaterial.is_active.is_(True),
                Product.is_active.is_(True),
            )
            .order_by(Product.product_name)
            .all()
        )
        return [r[0] for r in rows]

    if new_unit is not None and old_unit and not is_unit_valid(new_unit, old_unit):
        units = [
            r.unit_name for r in db.query(ProductUnit.unit_name).filter(
                ProductUnit.user_id == user_id, ProductUnit.product_id == pid, ProductUnit.is_active.is_(True),
            ).all()
        ]
        dishes = dishes_using()
        reasons = []
        if units:
            reasons.append(f"đang có đơn vị quy đổi ({', '.join(units)}) tính theo '{old_unit}'")
        if dishes:
            reasons.append(f"đang dùng trong định mức của {', '.join(dishes)} (tính theo '{old_unit}')")
        if reasons:
            return (
                f"Không đổi được đơn vị tính kho của '{product.product_name}' từ '{old_unit}' sang '{new_unit}': "
                f"{'; '.join(reasons)}. Đổi đơn vị sẽ làm sai các số đã khai báo. "
                f"Hãy xóa đơn vị quy đổi / bỏ nguyên liệu khỏi định mức trước, hoặc giữ đơn vị '{old_unit}'."
            )

    if new_type != old_type:
        if old_type == "RAW_MATERIAL":
            dishes = dishes_using()
            if dishes:
                return (
                    f"'{product.product_name}' đang là nguyên liệu trong định mức của {', '.join(dishes)}. "
                    f"Hãy bỏ nguyên liệu này khỏi định mức trước khi đổi loại sản phẩm."
                )
        if old_type == "FINISHED_GOOD":
            has_bom = db.query(BillOfMaterial.bom_id).filter(
                BillOfMaterial.user_id == user_id,
                BillOfMaterial.finished_product_id == pid,
                BillOfMaterial.is_active.is_(True),
            ).first()
            if has_bom:
                return (
                    f"'{product.product_name}' đang có định mức nguyên liệu. "
                    f"Hãy xóa định mức trước khi đổi loại sản phẩm."
                )
    return None


def _to_quantity(value: Any, material_name: str) -> Decimal:
    try:
        qty = Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"Định mức của '{material_name}' không hợp lệ")
    if qty <= 0:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"Định mức của '{material_name}' phải lớn hơn 0")
    if -qty.normalize().as_tuple().exponent > MAX_DECIMAL_PLACES:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"Định mức {qty.normalize()} cho '{material_name}' quá nhỏ (tối đa {MAX_DECIMAL_PLACES} chữ số thập phân). "
            f"Hãy đổi đơn vị tính của nguyên liệu sang đơn vị nhỏ hơn (ví dụ kg -> g, lít -> ml).",
        )
    return qty


class BomService:
    def __init__(self, db: Session):
        self.db = db
        self.repo = BomRepository(db)

    # ------------------------------------------------------------------
    def _get_finished_product(self, user_id: int, product_id: int) -> Product:
        product = self.repo.get_product(user_id, product_id)
        if not product:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Không tìm thấy sản phẩm")
        return product

    def _serialize(self, user_id: int, product: Product) -> Dict[str, Any]:
        lines = self.repo.get_lines(user_id, product.product_id)
        materials = {
            p.product_id: p
            for p in self.repo.get_products(user_id, [line.material_product_id for line in lines])
        }
        items = []
        for line in lines:
            mat = materials.get(line.material_product_id)
            items.append({
                "bom_id": line.bom_id,
                "material_product_id": line.material_product_id,
                "material_name": mat.product_name if mat else "",
                "quantity_per_unit": float(line.quantity_per_unit),
                "unit": line.unit,
                "material_is_active": bool(mat and mat.is_active),
            })
        return {
            "finished_product_id": product.product_id,
            "product_name": product.product_name,
            "default_unit": product.default_unit,
            "materials": items,
        }

    # ------------------------------------------------------------------
    def get_lines_by_finished(self, user_id: int, finished_ids: Iterable[int]) -> Dict[int, List[Dict[str, Any]]]:
        """Định mức đang dùng của nhiều thành phẩm: {finished_id: [dòng định mức kèm tên nguyên liệu]}."""
        ids = sorted({int(i) for i in finished_ids if i})
        if not ids:
            return {}
        lines = (
            self.db.query(BillOfMaterial, Product.product_name)
            .join(Product, Product.product_id == BillOfMaterial.material_product_id)
            .filter(
                BillOfMaterial.user_id == user_id,
                Product.user_id == user_id,
                BillOfMaterial.finished_product_id.in_(ids),
                BillOfMaterial.is_active.is_(True),
            )
            .order_by(BillOfMaterial.bom_id)
            .all()
        )
        result: Dict[int, List[Dict[str, Any]]] = {}
        for line, material_name in lines:
            result.setdefault(line.finished_product_id, []).append({
                "material_product_id": line.material_product_id,
                "material_name": material_name,
                "quantity_per_unit": float(line.quantity_per_unit),
                "unit": line.unit,
            })
        return result

    def list_boms(self, user_id: int) -> List[Dict[str, Any]]:
        """Mọi thành phẩm đang kinh doanh của user, kèm định mức (rỗng = chưa khai báo)."""
        products = (
            self.db.query(Product)
            .filter(
                Product.user_id == user_id,
                Product.product_type == "FINISHED_GOOD",
                Product.is_active.is_(True),
            )
            .order_by(Product.product_name)
            .all()
        )
        lines = self.get_lines_by_finished(user_id, [p.product_id for p in products])
        return [
            {
                "finished_product_id": p.product_id,
                "product_name": p.product_name,
                "default_unit": p.default_unit,
                "materials": lines.get(p.product_id, []),
            }
            for p in products
        ]

    @staticmethod
    def _to_stock_unit(quantity: Any, unit: Any, material: Product, extra_units: Any) -> Any:
        """Đổi định mức người dùng nhập ("5 g", "0,5 gói") về đơn vị tính kho của nguyên liệu."""
        stock_unit = material.default_unit
        if not unit or not stock_unit or is_unit_valid(unit, stock_unit):
            return quantity
        ratio = unit_ratio(unit, stock_unit, extra_units)
        if ratio is None:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                f"Đơn vị '{unit}' không quy đổi được sang '{stock_unit}' của '{material.product_name}'. "
                f"Hãy khai báo đơn vị quy đổi cho nguyên liệu (vd: 1 {unit} = ... {stock_unit}).",
            )
        try:
            return Decimal(str(quantity)) * ratio
        except (InvalidOperation, ValueError, TypeError):
            return quantity

    def get_bom(self, user_id: int, product_id: int) -> Dict[str, Any]:
        return self._serialize(user_id, self._get_finished_product(user_id, product_id))

    def replace_bom(self, user_id: int, product_id: int, materials: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Ghi đè toàn bộ định mức của thành phẩm (dòng không còn trong danh sách -> xóa mềm)."""
        if get_user_business_type(self.db, user_id) != "PRODUCER":
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                "Chỉ cơ sở sản xuất / chế biến (PRODUCER) mới khai báo định mức nguyên liệu",
            )

        product = self._get_finished_product(user_id, product_id)
        if not product.is_active:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, f"Sản phẩm '{product.product_name}' đã ngừng kinh doanh")
        if normalize_product_type(product.product_type) != "FINISHED_GOOD":
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                f"'{product.product_name}' không phải thành phẩm (FINISHED_GOOD), không khai báo định mức được",
            )

        material_ids = [int(m["material_product_id"]) for m in materials]
        if len(material_ids) != len(set(material_ids)):
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Một nguyên liệu bị khai báo nhiều lần")

        found = {p.product_id: p for p in self.repo.get_products(user_id, material_ids)}
        material_units = units_by_product(self.db, user_id, material_ids)
        wanted: Dict[int, Decimal] = {}
        for m in materials:
            mid = int(m["material_product_id"])
            mat = found.get(mid)
            if not mat:
                raise HTTPException(status.HTTP_404_NOT_FOUND, f"Không tìm thấy nguyên liệu có ID {mid}")
            if not mat.is_active:
                raise HTTPException(status.HTTP_400_BAD_REQUEST, f"Nguyên liệu '{mat.product_name}' đã ngừng kinh doanh")
            if normalize_product_type(mat.product_type) != "RAW_MATERIAL":
                raise HTTPException(
                    status.HTTP_400_BAD_REQUEST,
                    f"'{mat.product_name}' không phải nguyên liệu (RAW_MATERIAL)",
                )
            wanted[mid] = _to_quantity(
                self._to_stock_unit(m.get("quantity_per_unit"), m.get("unit"), mat, material_units.get(mid)),
                mat.product_name,
            )

        now = datetime.now()
        existing = {line.material_product_id: line for line in self.repo.get_lines(user_id, product_id, active_only=False)}
        try:
            for mid, line in existing.items():
                if mid not in wanted and line.is_active:
                    line.is_active = False
                    line.updated_at = now
            for mid, qty in wanted.items():
                unit = found[mid].default_unit
                line = existing.get(mid)
                if line:
                    # Dòng cũ (kể cả đã xóa mềm) dùng lại vì có unique (user, thành phẩm, nguyên liệu)
                    line.quantity_per_unit = qty
                    line.unit = unit
                    line.is_active = True
                    line.updated_at = now
                else:
                    self.db.add(BillOfMaterial(
                        user_id=user_id,
                        finished_product_id=product_id,
                        material_product_id=mid,
                        quantity_per_unit=qty,
                        unit=unit,
                        is_active=True,
                        created_at=now,
                        updated_at=now,
                    ))
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise

        return self._serialize(user_id, product)

    def delete_bom(self, user_id: int, product_id: int) -> Dict[str, Any]:
        """Xóa mềm toàn bộ định mức của thành phẩm."""
        self._get_finished_product(user_id, product_id)
        now = datetime.now()
        lines = self.repo.get_lines(user_id, product_id)
        try:
            for line in lines:
                line.is_active = False
                line.updated_at = now
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise
        return {"success": True, "deactivated": len(lines)}
