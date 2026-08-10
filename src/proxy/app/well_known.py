from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Request
from pydantic import BaseModel

from proxy.servers.manager import ServerManager
from proxy.servers.models import McpServerConfig, server_base_url


class McpServerListing(BaseModel):
    """One publicly discoverable MCP server mounted by the gateway."""

    name: str
    description: str
    url: str
    auth: Literal["oauth2", "none"]


class McpServersDocument(BaseModel):
    """The ``/.well-known/mcp-servers`` discovery document."""

    servers: list[McpServerListing]


def get_server_manager(request: Request) -> ServerManager:
    """Return the runtime server manager stored on app state."""

    return request.app.state.server_manager


def mcp_endpoint_url(public_base_url: str, server: McpServerConfig) -> str:
    """Return the public URL of a server's MCP endpoint."""

    return f"{server_base_url(public_base_url, server.name)}/mcp"


def _listing(
    public_base_url: str,
    server: McpServerConfig,
) -> McpServerListing:
    return McpServerListing(
        name=server.name,
        description=server.description,
        url=mcp_endpoint_url(public_base_url, server),
        auth="oauth2",
    )


router = APIRouter()


@router.get("/.well-known/mcp-servers", response_model=McpServersDocument)
def mcp_servers(request: Request) -> McpServersDocument:
    """Publish the gateway's mounted MCP servers for discovery."""

    manager = get_server_manager(request)
    public_base_url = str(request.app.state.config.public_base_url)
    return McpServersDocument(
        servers=[_listing(public_base_url, server) for server in manager.snapshot()]
    )
