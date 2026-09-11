from typing import Any


def build_payload(
    entities: dict[str, Any],
    text: str = ""
) -> dict:
    """
    Mapping dữ liệu entities của them_san_pham thành payload chuẩn.
    """
    prod_name = entities.get("product") or entities.get("product_name") or entities.get("name") or ""
    unit_val = entities.get("unit") or entities.get("default_unit") or "cái"
    price_val = entities.get("price") or entities.get("unit_price") or 0

    return {
        "product_name": prod_name,
        "name": prod_name,
        "default_unit": unit_val,
        "unit": unit_val,
        "unit_price": price_val,
        "price": price_val
    }
