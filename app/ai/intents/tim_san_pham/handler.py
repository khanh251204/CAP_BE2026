import asyncio
from typing import Any

from app.ai.mcp.client import call_mcp_tool, normalize_mcp_result
from app.configs.database import get_db_session
from app.models.product_model import Product
from app.repositories.inventory.inventory_stock_repo import InventoryStockRepository
from app.services.stock_status import resolve_min_quantity, stock_status_of
from .validator import validate
from .payload import build_payload

# Câu nói thường chỉ cần vài kết quả đầu; giới hạn để không phải đọc tồn kho quá nhiều sản phẩm
MAX_RESULTS = 10


def _attach_stock(user_id: int, products: list[dict]) -> list[dict]:
    """Thêm tồn kho, mức tối thiểu, trạng thái tồn cho từng sản phẩm tìm được."""
    if not products:
        return products
    db = get_db_session()
    try:
        ids = [p["product_id"] for p in products if p.get("product_id")]
        min_by_id = {
            pid: mq
            for pid, mq in db.query(Product.product_id, Product.min_quantity).filter(Product.product_id.in_(ids)).all()
        }
        stock_repo = InventoryStockRepository(db)
        enriched = []
        for p in products:
            pid = p.get("product_id")
            qty = float(stock_repo.get_latest_stock(user_id, pid)) if pid else 0.0
            min_qty = resolve_min_quantity(min_by_id.get(pid))
            price = p.get("unit_price")
            enriched.append({
                **p,
                "unit_price": float(price) if price is not None else 0.0,
                "quantity": qty,
                "min_quantity": min_qty,
                "stock_status": stock_status_of(qty, min_qty),
            })
        return enriched
    finally:
        db.close()


class TimSanPhamHandler:
    """
    Business workflow cho intent: tim_san_pham (xem_san_pham)
    Xử lý:
    - Validate bắt buộc có trường 'product'.
    - Gọi MCP search_products.
    - Gắn tồn kho / trạng thái tồn cho từng sản phẩm để app hiển thị danh sách.
    """

    async def handle(
        self,
        user_id: int,
        entities: dict[str, Any],
        text: str,
        intent: str = "tim_san_pham"
    ) -> dict:
        val_result = validate(entities)
        if not val_result["success"]:
            return {
                "success": False,
                "status": "need_information",
                "intent": intent,
                "missing_fields": val_result["missing_fields"],
                "message": val_result["message"]
            }

        payload = build_payload(entities=entities, text=text)
        result = normalize_mcp_result(await call_mcp_tool(
            "search_products",
            {
                "name": payload["name"],
                "user_id": user_id
            }
        ))
        if not isinstance(result, dict) or not result.get("success"):
            return result

        keyword = payload["name"]
        found = result.get("products") or []
        if not found:
            return {
                "success": False,
                "status": "product_not_found",
                "intent": intent,
                "product_name": keyword,
                "message": f"Không tìm thấy sản phẩm nào có tên '{keyword}'.",
            }

        products = await asyncio.to_thread(_attach_stock, user_id, found[:MAX_RESULTS])
        more = len(found) - len(products)
        return {
            "success": True,
            "status": "success",
            "intent": intent,
            "keyword": keyword,
            "total": len(found),
            "products": products,
            "message": (
                f"Tìm thấy {len(found)} sản phẩm khớp '{keyword}'."
                + (f" Đang hiện {len(products)} sản phẩm đầu." if more > 0 else "")
            ),
        }
