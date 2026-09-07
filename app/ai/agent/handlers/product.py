from typing import Any

from app.ai.mcp.client import call_mcp_tool, normalize_mcp_result
from app.ai.agent.payload_builder import build_payload
from app.ai.agent.routes import REQUIRED_FIELDS


# ============================================================
# VALIDATE HELPER
# ============================================================

def validate(intent: str, entities: dict[str, Any]) -> list[str]:

    required = REQUIRED_FIELDS.get(intent, [])
    missing = []

    for field in required:
        value = entities.get(field)
        if value is None or value == "":
            missing.append(field)

    return missing


# ============================================================
# SEARCH PRODUCT HELPER
# ============================================================

async def search_product(product_name: str, user_id: int) -> dict:

    result = await call_mcp_tool(
        "search_products",
        {
            "name": product_name,
            "user_id": user_id
        }
    )

    return normalize_mcp_result(result)


# ============================================================
# THÊM SẢN PHẨM
# ============================================================

async def handle_create_product(
    intent: str,
    user_id: int,
    entities: dict[str, Any],
    text: str
) -> dict:

    missing_fields = validate(intent=intent, entities=entities)

    if missing_fields:

        return {
            "success": False,
            "status": "need_information",
            "intent": intent,
            "missing_fields": missing_fields,
            "message": "Thiếu thông tin bắt buộc"
        }

    product_name = entities.get("product")

    # --------------------------------------------------------
    # Kiểm tra sản phẩm đã tồn tại chưa
    # --------------------------------------------------------

    search_result = await search_product(
        product_name=product_name,
        user_id=user_id
    )

    if not search_result.get("success"):
        return search_result

    existing_products = search_result.get("products", [])

    if existing_products:

        existing = existing_products[0]

        unit_price = existing.get("unit_price")

        try:
            price_text = f"{float(unit_price):,.0f}đ/{existing.get('default_unit', '')}"
        except (TypeError, ValueError):
            price_text = "chưa có giá"

        return {
            "success": False,
            "status": "product_already_exists",
            "intent": intent,
            "existing_product": existing,
            "message": (
                f"Sản phẩm '{existing['product_name']}' đã tồn tại "
                f"(giá: {price_text}). "
                f"Bạn có muốn sửa thông tin sản phẩm này không?"
            )
        }

    # --------------------------------------------------------
    # Chưa tồn tại → chờ xác nhận thêm mới
    # --------------------------------------------------------

    payload = build_payload(intent=intent, entities=entities, text=text)

    return {
        "success": True,
        "status": "waiting_confirmation",
        "intent": intent,
        "action": "create_product",
        "payload": payload,
        "message": (
            f"Bạn có muốn thêm sản phẩm "
            f"{payload['name']} "
            f"giá {payload['unit_price']:,}đ/"
            f"{payload['default_unit']} không?"
        )
    }



# ============================================================
# XÓA SẢN PHẨM
# ============================================================

async def handle_delete_product(
    intent: str,
    user_id: int,
    entities: dict[str, Any],
    text: str
) -> dict:

    product_name = entities.get("product")

    if not product_name:

        return {
            "success": False,
            "status": "need_information",
            "intent": intent,
            "missing_fields": ["product"],
            "message": "Bạn muốn xóa sản phẩm nào?"
        }

    result = await search_product(
        product_name=product_name,
        user_id=user_id
    )

    if not result.get("success"):
        return result

    products = result.get("products", [])

    if not products:

        return {
            "success": False,
            "status": "not_found",
            "intent": intent,
            "message": (
                f"Không tìm thấy sản phẩm "
                f"'{product_name}'"
            )
        }

    product = products[0]
    product_id = product["product_id"]

    return {
        "success": True,
        "status": "waiting_confirmation",
        "intent": intent,
        "action": "delete_product",
        "payload": {
            "product_id": product_id,
            "product_name": product["product_name"]
        },
        "message": (
            f"Bạn có chắc muốn xóa "
            f"sản phẩm '{product['product_name']}' không?"
        )
    }


# ============================================================
# SỬA SẢN PHẨM
# ============================================================

async def handle_update_product(
    intent: str,
    user_id: int,
    entities: dict[str, Any],
    text: str
) -> dict:

    product_name = entities.get("product")

    if not product_name:

        return {
            "success": False,
            "status": "need_information",
            "intent": intent,
            "missing_fields": ["product"],
            "message": "Bạn muốn sửa sản phẩm nào?"
        }

    result = await search_product(
        product_name=product_name,
        user_id=user_id
    )

    if not result.get("success"):
        return result

    products = result.get("products", [])

    if not products:

        return {
            "success": False,
            "status": "not_found",
            "intent": intent,
            "message": (
                f"Không tìm thấy sản phẩm "
                f"'{product_name}'"
            )
        }

    product = products[0]
    product_id = product["product_id"]

    update_data = {}

    new_product_name = entities.get("new_product_name")

    if new_product_name:
        update_data["product_name"] = new_product_name

    if entities.get("price") is not None:
        update_data["unit_price"] = entities["price"]

    if entities.get("unit") is not None:
        update_data["default_unit"] = entities["unit"]

    if not update_data:

        return {
            "success": False,
            "status": "need_information",
            "intent": intent,
            "message": (
                "Bạn muốn sửa thông tin nào "
                "của sản phẩm?"
            )
        }

    changes = []

    if "product_name" in update_data:
        changes.append(
            f"tên thành '{update_data['product_name']}'"
        )

    if "unit_price" in update_data:
        changes.append(
            f"giá thành {update_data['unit_price']:,}đ"
        )

    if "default_unit" in update_data:
        changes.append(
            f"đơn vị thành '{update_data['default_unit']}'"
        )

    change_text = ", ".join(changes)

    return {
        "success": True,
        "status": "waiting_confirmation",
        "intent": intent,
        "action": "update_product",
        "payload": {
            "product_id": product_id,
            "product_name": product["product_name"],
            "data": update_data
        },
        "message": (
            f"Bạn có muốn sửa sản phẩm "
            f"'{product['product_name']}' "
            f"{change_text} không?"
        )
    }
