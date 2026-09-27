from mcp.server.fastmcp import FastMCP

from .tools import ProductTools


server = FastMCP(
    name="Product MCP"
)


server.tool()(ProductTools.search_products)
server.tool()(ProductTools.get_product_by_id)
server.tool()(ProductTools.get_all_products)
server.tool()(ProductTools.get_products_with_stock)
server.tool()(ProductTools.create_product)
server.tool()(ProductTools.update_product)
server.tool()(ProductTools.delete_product)


if __name__ == "__main__":
    server.run(
        transport="streamable-http"
    )