from typing import Any

from app.ai.mcp.client import call_mcp_tool, normalize_mcp_result
from app.ai.agent.routes import ROUTES, REQUIRED_FIELDS
from app.ai.agent.payload_builder import build_payload
from app.ai.agent.handlers.transaction import (
    handle_sell,
    handle_import,
    handle_ghi_no_khach_hang,
    handle_thu_no_khach_hang,
    handle_ghi_no_nha_cung_cap,
    handle_thu_no_nha_cung_cap,
)
from app.ai.agent.handlers.product import (
    handle_create_product,
    handle_delete_product,
    handle_update_product
)


class AgentRouter:

    # ========================================================
    # GET MCP TOOL
    # ========================================================

    @staticmethod
    def get_tool(intent: str) -> str | None:
        return ROUTES.get(intent)

    # ========================================================
    # VALIDATE
    # ========================================================

    @staticmethod
    def validate(
        intent: str,
        entities: dict[str, Any]
    ) -> list[str]:

        required_fields = REQUIRED_FIELDS.get(intent, [])
        missing_fields = []

        for field in required_fields:
            value = entities.get(field)
            if value is None or value == "":
                missing_fields.append(field)

        return missing_fields

    # ========================================================
    # BUILD PAYLOAD
    # ========================================================

    @staticmethod
    def build_payload(
        intent: str,
        entities: dict[str, Any],
        text: str
    ) -> dict:
        return build_payload(intent=intent, entities=entities, text=text)

    # ========================================================
    # SEARCH PRODUCT
    # ========================================================

    @staticmethod
    async def search_product(
        product_name: str,
        user_id: int
    ) -> dict:

        result = await call_mcp_tool(
            "search_products",
            {
                "name": product_name,
                "user_id": user_id
            }
        )

        return normalize_mcp_result(result)

    # ========================================================
    # EXECUTE
    # ========================================================

    @staticmethod
    async def execute(
        intent: str,
        user_id: int,
        entities: dict[str, Any],
        text: str
    ) -> dict:

        # ====================================================
        # GIAO DỊCH
        # ====================================================

        if intent == "ban_hang":
            return await handle_sell(
                intent=intent,
                user_id=user_id,
                entities=entities,
                text=text
            )

        if intent == "nhap_hang":
            return await handle_import(
                intent=intent,
                user_id=user_id,
                entities=entities,
                text=text
            )

        # ====================================================
        # SẢN PHẨM
        # ====================================================

        if intent == "them_san_pham":
            return await handle_create_product(
                intent=intent,
                user_id=user_id,
                entities=entities,
                text=text
            )

        if intent == "xoa_san_pham":
            return await handle_delete_product(
                intent=intent,
                user_id=user_id,
                entities=entities,
                text=text
            )

        if intent == "sua_san_pham":
            return await handle_update_product(
                intent=intent,
                user_id=user_id,
                entities=entities,
                text=text
            )

        # ====================================================
        # CÔNG NỢ KHÁCH HÀNG
        # ====================================================

        if intent in ("ghi_no_khach_hang", "khach_ghi_no"):
            return await handle_ghi_no_khach_hang(
                intent=intent,
                user_id=user_id,
                entities=entities,
                text=text
            )

        if intent in ("thu_no_khach_hang", "thu_no_khach"):
            return await handle_thu_no_khach_hang(
                intent=intent,
                user_id=user_id,
                entities=entities,
                text=text
            )

        # ====================================================
        # CÔNG NỢ NHÀ CUNG CẤP
        # ====================================================

        if intent in ("ghi_no_nha_cung_cap", "ncc_ghi_no"):
            return await handle_ghi_no_nha_cung_cap(
                intent=intent,
                user_id=user_id,
                entities=entities,
                text=text
            )

        if intent in ("thu_no_nha_cung_cap", "tra_no_nha_cung_cap", "tra_no_ncc"):
            return await handle_thu_no_nha_cung_cap(
                intent=intent,
                user_id=user_id,
                entities=entities,
                text=text
            )

        # ====================================================
        # CÁC INTENT KHÁC (kiem_kho, cong_no, chi_phi, bao_cao...)
        # ====================================================

        tool_name = AgentRouter.get_tool(intent)

        if not tool_name:

            return {
                "success": False,
                "status": "error",
                "intent": intent,
                "message": f"Intent chưa được hỗ trợ: {intent}"
            }

        missing_fields = AgentRouter.validate(
            intent=intent,
            entities=entities
        )

        if missing_fields:

            return {
                "success": False,
                "status": "error",
                "intent": intent,
                "missing_fields": missing_fields,
                "message": "Thiếu thông tin bắt buộc"
            }

        payload = build_payload(
            intent=intent,
            entities=entities,
            text=text
        )

        if intent in ("tim_san_pham", "xem_san_pham"):

            arguments = {
                "name": payload["name"],
                "user_id": user_id
            }

        elif tool_name in (
            "ghi_no_khach_hang",
            "thu_no_khach_hang",
            "ghi_no_nha_cung_cap",
            "thu_no_nha_cung_cap",
        ):

            arguments = {
                "input": payload,
                "user_id": user_id
            }

        else:

            arguments = {
                "payload": payload,
                "user_id": user_id
            }

        result = await call_mcp_tool(tool_name, arguments)

        return normalize_mcp_result(result)