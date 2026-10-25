"""
Bước bản nháp khi người dùng nhắc tới sản phẩm CHƯA CÓ trong danh mục.

Dùng chung cho ban_hang, mua_hang, nhap_hang, nhap_kho:
- Quyết định có được tạo sản phẩm mới không (theo luồng & loại hình kinh doanh, quyền product:create).
- Hỏi lại thông tin còn thiếu (giá, đơn vị) thay vì tạo sản phẩm thiếu dữ liệu.
- Trả về spec để handler đính kèm vào payload["new_product"]; sản phẩm chỉ thật sự được tạo khi xác nhận.
"""
from typing import Any, Dict, Optional

from app.services.new_product_service import (
    FLOW_PURCHASE,
    FLOW_SALE,
    FLOW_STOCK_IN,
    build_spec,
    can_create_on_flow,
    default_product_type,
)

PRICE_LABEL = {
    FLOW_PURCHASE: "giá nhập",
    FLOW_SALE: "giá bán",
    FLOW_STOCK_IN: "giá bán",
}


def _positive(value: Any) -> bool:
    try:
        return float(value) > 0
    except (TypeError, ValueError):
        return False


def user_units_hint(user_id: int) -> str:
    """Gợi ý đơn vị tính từ danh mục của user, vd: "lon, thùng, kg". Chưa có thì dùng ví dụ chung."""
    from app.configs.database import get_db_session
    from app.repositories.inventory.inventory_lookup_repo import InventoryLookupRepository

    db = get_db_session()
    try:
        units = InventoryLookupRepository(db).get_user_units(user_id)
    except Exception:
        units = []
    finally:
        db.close()
    return ", ".join(units) if units else "cái, kg, lon, ly..."


def prepare_new_product(
    flow: str,
    intent: str,
    user_id: int,
    product_name: str,
    entities: Dict[str, Any],
    business_type: Optional[str],
) -> Dict[str, Any]:
    """
    Trả về {"spec": {...}} nếu được tạo sản phẩm mới,
    hoặc {"response": {...}} là phản hồi trả thẳng cho người dùng (lỗi / hỏi thêm thông tin).
    """
    if not can_create_on_flow(flow, business_type):
        return {"response": {
            "success": False,
            "status": "product_not_found",
            "intent": intent,
            "product_name": product_name,
            "message": (
                f"Sản phẩm '{product_name}' chưa có trong danh mục và chưa từng nhập kho nên không thể bán. "
                f"Hãy nhập hàng '{product_name}' trước (ví dụ: \"nhập 10 {entities.get('unit') or 'cái'} {product_name} giá ...\")."
            ),
        }}

    from app.services.permission_service import PermissionService
    if not PermissionService.has_permission(user_id, "product:create"):
        return {"response": {
            "success": False,
            "status": "product_not_found",
            "intent": intent,
            "product_name": product_name,
            "message": (
                f"Sản phẩm '{product_name}' chưa có trong danh mục và bạn không có quyền thêm sản phẩm mới. "
                "Hãy nhờ chủ cửa hàng thêm sản phẩm này trước."
            ),
        }}

    price = entities.get("price") if entities.get("price") is not None else entities.get("unit_price")
    unit = entities.get("unit")
    missing = []
    # Nhập hàng / bán hàng cần giá để tính tiền; nhập kho đơn thuần thì giá bán có thể bổ sung sau
    if flow in (FLOW_PURCHASE, FLOW_SALE) and not _positive(price):
        missing.append("price")
    if not unit:
        missing.append("unit")
    if missing:
        asks = []
        if "price" in missing:
            asks.append(PRICE_LABEL[flow])
        if "unit" in missing:
            asks.append(f"đơn vị tính (các đơn vị bạn đang dùng: {user_units_hint(user_id)})")
        return {"response": {
            "success": False,
            "status": "need_information",
            "intent": intent,
            "missing_fields": missing,
            "new_product": True,
            "product_name": product_name,
            "message": f"Sản phẩm '{product_name}' chưa có trong danh mục. Cho mình biết {' và '.join(asks)} để thêm sản phẩm mới.",
        }}

    return {"spec": build_spec(
        product_name,
        unit,
        # Nhập hàng: giá người dùng nói là GIÁ NHẬP, không dùng làm giá bán của sản phẩm
        sale_price=None if flow == FLOW_PURCHASE else price,
        product_type=default_product_type(flow, business_type),
        price_from_item=(flow == FLOW_SALE),
    )}


def new_product_note(spec: Dict[str, Any]) -> str:
    """Câu ghi chú chèn vào câu hỏi xác nhận."""
    from app.services.new_product_service import describe
    note = f" [Sản phẩm mới {describe(spec)} sẽ được thêm vào danh mục]"
    if spec.get("product_type") == "RAW_MATERIAL":
        note = note[:-1] + " — nguyên liệu, không bán trực tiếp]"
    return note
