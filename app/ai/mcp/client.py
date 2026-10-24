import json
import logging
from typing import Any

logger = logging.getLogger(__name__)

from app.ai.mcp.product.server import server as product_server
from app.ai.mcp.inventory.server import server as inventory_server
from app.ai.mcp.debt.server import server as debt_server
from app.ai.mcp.expense.server import server as expense_server
from app.ai.mcp.report.server import server as report_server


# ============================================================
# MCP SERVERS
# ============================================================

MCP_SERVERS = {
    "product": product_server,
    "inventory": inventory_server,
    "debt": debt_server,
    "expense": expense_server,
    "report": report_server,
}

# tool_name -> server. Danh sách tool cố định lúc khởi động nên chỉ cần dựng 1 lần,
# tránh gọi list_tools() của mọi server ở mỗi lần gọi tool.
_TOOL_INDEX: dict[str, Any] | None = None


async def _build_tool_index() -> tuple[dict[str, Any], bool]:
    """Trả về (index, complete). complete=False nếu có server lỗi -> không cache để lần sau thử lại."""
    index: dict[str, Any] = {}
    complete = True
    for server_name, server in MCP_SERVERS.items():
        try:
            for tool in await server.list_tools():
                name = getattr(tool, "name", None)
                if not name:
                    continue
                if name in index:
                    logger.warning(f"[MCP] Tool '{name}' bị trùng tên ở server {server_name}")
                    continue
                index[name] = server
        except Exception as e:
            logger.warning(f"[MCP] Không lấy được tools từ {server_name}: {e}")
            complete = False
    return index, complete


# ============================================================
# FIND SERVER
# ============================================================

async def find_mcp_server(tool_name: str):
    """
    Tìm MCP server chứa tool cần gọi.
    """
    global _TOOL_INDEX
    if _TOOL_INDEX is not None:
        return _TOOL_INDEX.get(tool_name)

    index, complete = await _build_tool_index()
    if complete:
        _TOOL_INDEX = index
    return index.get(tool_name)


# ============================================================
# CALL MCP TOOL
# ============================================================

async def call_mcp_tool(
    tool_name: str,
    arguments: dict[str, Any]
):
    """
    Tìm đúng MCP server và gọi tool.
    """

    try:

        # ----------------------------------------------------
        # 1. Tìm server
        # ----------------------------------------------------

        server = await find_mcp_server(
            tool_name
        )

        if server is None:

            return {
                "success": False,
                "error": f"Unknown tool: {tool_name}"
            }

        # ----------------------------------------------------
        # 2. Gọi tool
        # ----------------------------------------------------

        result = await server.call_tool(
            tool_name,
            arguments
        )

        # ----------------------------------------------------
        # 3. MCP error
        # ----------------------------------------------------

        if hasattr(result, "is_error") and result.is_error:

            return {
                "success": False,
                "error": getattr(
                    result,
                    "content",
                    str(result)
                )
            }

        return result

    except Exception as e:

        return {
            "success": False,
            "error": str(e)
        }


# ============================================================
# NORMALIZE RESULT
# ============================================================

def normalize_mcp_result(
    result: Any
) -> dict | list | str:

    if result is None:
        return {}

    # ========================================================
    # Tuple
    # ========================================================

    if isinstance(result, tuple) and len(result) > 0:

        first_item = result[0]

        # [TextContent(...)]
        if (
            isinstance(first_item, list)
            and len(first_item) > 0
        ):

            text_data = getattr(
                first_item[0],
                "text",
                str(first_item[0])
            )

            try:
                return json.loads(text_data)

            except Exception:
                return {
                    "raw": text_data
                }

        # Tuple thứ 2
        if (
            len(result) > 1
            and isinstance(result[1], dict)
        ):

            raw_res = result[1].get("result")

            if isinstance(raw_res, str):

                try:
                    return json.loads(raw_res)

                except Exception:
                    return {
                        "raw": raw_res
                    }

            if isinstance(raw_res, dict):
                return raw_res

    # ========================================================
    # String
    # ========================================================

    if isinstance(result, str):

        try:
            return json.loads(result)

        except Exception:
            return {
                "raw": result
            }

    # ========================================================
    # List
    # ========================================================

    if isinstance(result, list):

        parsed_items = []

        for item in result:

            text_data = getattr(
                item,
                "text",
                str(item)
            )

            try:

                parsed_items.append(
                    json.loads(text_data)
                )

            except Exception:

                parsed_items.append(
                    text_data
                )

        if len(parsed_items) == 1:
            return parsed_items[0]

        return parsed_items

    # ========================================================
    # Dict
    # ========================================================

    if isinstance(result, dict):
        return result

    # ========================================================
    # Other
    # ========================================================

    return {
        "result": str(result)
    }

