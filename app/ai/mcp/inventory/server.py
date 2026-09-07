from mcp.server.fastmcp import FastMCP

from .tool import InventoryTools


server = FastMCP(
    name="Inventory MCP"
)


server.tool()(InventoryTools.export_inventory)
server.tool()(InventoryTools.import_inventory)
server.tool()(InventoryTools.check_stock)


if __name__ == "__main__":
    server.run(
        transport="streamable-http"
    )