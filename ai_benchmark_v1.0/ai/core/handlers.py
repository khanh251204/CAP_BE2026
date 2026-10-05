# app/ai/core/handlers.py
# Backward-compatibility adapter delegating to modular intent handlers in app/ai/intents/

from typing import Any, Optional
from app.ai.mcp.client import call_mcp_tool, normalize_mcp_result
from app.ai.intents.ban_hang.handler import BanHangHandler
from app.ai.intents.nhap_hang.handler import NhapHangHandler
from app.ai.intents.khach_ghi_no.handler import KhachGhiNoHandler
from app.ai.intents.thu_no_khach.handler import ThuNoKhachHandler
from app.ai.intents.ghi_no_nha_cung_cap.handler import GhiNoNhaCungCapHandler
from app.ai.intents.tra_no_nha_cung_cap.handler import TraNoNhaCungCapHandler

_ban_hang_handler = BanHangHandler()
_nhap_hang_handler = NhapHangHandler()
_khach_ghi_no_handler = KhachGhiNoHandler()
_thu_no_khach_handler = ThuNoKhachHandler()
_ghi_no_ncc_handler = GhiNoNhaCungCapHandler()
_tra_no_ncc_handler = TraNoNhaCungCapHandler()

REQUIRED_FIELDS = {
    "ban_hang": ["product", "quantity"],
    "nhap_hang": ["product", "quantity", "price"],
    "mua_hang": ["product", "quantity", "price"],
    "ghi_no_khach_hang": ["customer", "amount"],
    "thu_no_khach_hang": ["customer", "amount"],
    "ghi_no_nha_cung_cap": ["supplier", "amount"],
    "thu_no_nha_cung_cap": ["supplier", "amount"],
}


def validate(intent: str, entities: dict[str, Any]) -> list[str]:
    required = REQUIRED_FIELDS.get(intent, [])
    missing = []
    for field in required:
        val = entities.get(field)
        if val is None or val == "":
            missing.append(field)
    return missing


def build_payload(intent: str, entities: dict[str, Any], text: str = "") -> dict:
    from app.ai.core.router import HANDLERS
    handler = HANDLERS.get(intent)
    if handler and hasattr(handler, "build_payload"):
        return handler.build_payload(entities, text)
    return entities


async def search_product(product_name: str, user_id: int) -> dict:
    call = await call_mcp_tool(
        "search_products",
        {"payload": {"query": product_name}, "user_id": user_id}
    )
    return normalize_mcp_result(call)


async def get_stock(product_name: str, user_id: int) -> dict:
    call = await call_mcp_tool(
        "check_stock",
        {"payload": {"product_name": product_name}, "user_id": user_id}
    )
    return normalize_mcp_result(call)


async def handle_sell(
    intent: str,
    user_id: int,
    entities: dict[str, Any],
    text: str,
    business_type: Optional[str] = None
) -> dict:
    return await _ban_hang_handler.handle(
        user_id=user_id,
        entities=entities,
        text=text,
        intent=intent,
        business_type=business_type
    )


async def handle_import(
    intent: str,
    user_id: int,
    entities: dict[str, Any],
    text: str,
    business_type: Optional[str] = None
) -> dict:
    return await _nhap_hang_handler.handle(
        user_id=user_id,
        entities=entities,
        text=text,
        intent=intent,
        business_type=business_type
    )


async def handle_ghi_no_khach_hang(
    intent: str,
    user_id: int,
    entities: dict[str, Any],
    text: str
) -> dict:
    return await _khach_ghi_no_handler.handle(
        user_id=user_id,
        entities=entities,
        text=text,
        intent=intent
    )


async def handle_thu_no_khach_hang(
    intent: str,
    user_id: int,
    entities: dict[str, Any],
    text: str
) -> dict:
    return await _thu_no_khach_handler.handle(
        user_id=user_id,
        entities=entities,
        text=text,
        intent=intent
    )


async def handle_ghi_no_nha_cung_cap(
    intent: str,
    user_id: int,
    entities: dict[str, Any],
    text: str
) -> dict:
    return await _ghi_no_ncc_handler.handle(
        user_id=user_id,
        entities=entities,
        text=text,
        intent=intent
    )


async def handle_thu_no_nha_cung_cap(
    intent: str,
    user_id: int,
    entities: dict[str, Any],
    text: str
) -> dict:
    return await _tra_no_ncc_handler.handle(
        user_id=user_id,
        entities=entities,
        text=text,
        intent=intent
    )


__all__ = [
    "validate",
    "build_payload",
    "search_product",
    "get_stock",
    "handle_sell",
    "handle_import",
    "handle_ghi_no_khach_hang",
    "handle_thu_no_khach_hang",
    "handle_ghi_no_nha_cung_cap",
    "handle_thu_no_nha_cung_cap",
]
