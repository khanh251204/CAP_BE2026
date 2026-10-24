from mcp.server.fastmcp import FastMCP

from .tools import ReportTools


server = FastMCP(
    name="Report MCP"
)


server.tool()(ReportTools.get_summary_report)


if __name__ == "__main__":
    server.run(
        transport="streamable-http"
    )
