from mcp.server.fastmcp import FastMCP

from .tools import ReportTools


server = FastMCP(
    name="Report MCP"
)


server.tool()(ReportTools.get_summary_report)
server.tool()(ReportTools.preview_closing)
server.tool()(ReportTools.close_period)


if __name__ == "__main__":
    server.run(
        transport="streamable-http"
    )
