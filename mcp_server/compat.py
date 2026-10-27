"""Work with both MCP Python SDK lines."""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import Any

try:  # MCP SDK 2.x
    from mcp.server import MCPServer as _Server  # type: ignore[attr-defined]
    from mcp.server.mcpserver.exceptions import ToolError  # type: ignore[no-redef]
    MCP_V2 = True
except ImportError:  # MCP SDK 1.x (what Agent Framework installs)
    from mcp.server.fastmcp import FastMCP as _Server  # type: ignore[no-redef]
    from mcp.server.fastmcp.exceptions import ToolError  # type: ignore[no-redef]
    MCP_V2 = False

__all__ = ["MCP_V2", "ToolError", "make_server", "run_server", "connect", "is_error"]


def make_server(name: str, instructions: str) -> Any:
    if MCP_V2:
        return _Server(name, instructions=instructions)
    return _Server(name, instructions=instructions, log_level="WARNING")  # keep stderr quiet for agents


def run_server(server: Any, http: bool, host: str = "0.0.0.0", port: int = 8000) -> None:
    if not http:
        server.run(transport="stdio")
    elif MCP_V2:
        server.run(transport="streamable-http", host=host, port=port, json_response=True, stateless_http=True)
    else:
        server.settings.host = host
        server.settings.port = port
        server.settings.json_response = True
        server.settings.stateless_http = True
        server.run(transport="streamable-http")


@asynccontextmanager
async def connect(server: Any):
    """In-memory client session for tests (same call_tool / list_tools API on both lines)."""
    if MCP_V2:
        from mcp import Client  # type: ignore[attr-defined]
        async with Client(server, raise_exceptions=False) as client:
            yield client
    else:
        from mcp.shared.memory import create_connected_server_and_client_session
        async with create_connected_server_and_client_session(server._mcp_server) as session:
            yield session


def is_error(result: Any) -> bool:
    return bool(getattr(result, "is_error", None) or getattr(result, "isError", None))
