from __future__ import annotations

from fastmcp import FastMCP

mcp = FastMCP(
    name="Example MCP Server",
    version="1.0.0",
    instructions="An unauthenticated backend used by the agent-proxy Compose demo.",
)


@mcp.tool
def echo(message: str) -> str:
    """Return a message unchanged."""

    return message


@mcp.tool
def add(left: int, right: int) -> int:
    """Add two integers."""

    return left + right


if __name__ == "__main__":
    mcp.run(
        transport="http",
        host="0.0.0.0",
        port=8000,
        path="/mcp",
        stateless_http=True,
        show_banner=False,
    )
