from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel

from proxy.settings import GatewayConfig, McpServerConfig


class McpServerListing(BaseModel):
    """One publicly discoverable MCP server mounted by the gateway."""

    name: str
    description: str
    url: str
    auth: Literal["oauth2", "none"]


class McpServersDocument(BaseModel):
    """The ``/.well-known/mcp-servers`` discovery document."""

    servers: list[McpServerListing]


def get_config(request: Request) -> GatewayConfig:
    """Return the validated gateway configuration stored on app state."""

    return request.app.state.config


def mcp_endpoint_url(config: GatewayConfig, server: McpServerConfig) -> str:
    """Return the public URL of a server's MCP endpoint."""

    return f"{config.server_base_url(server)}/mcp"


def _listing(config: GatewayConfig, server: McpServerConfig) -> McpServerListing:
    return McpServerListing(
        name=server.name,
        description=server.description,
        url=mcp_endpoint_url(config, server),
        auth="oauth2",
    )


router = APIRouter()


@router.get("/.well-known/mcp-servers", response_model=McpServersDocument)
def mcp_servers(config: GatewayConfig = Depends(get_config)) -> McpServersDocument:
    """Publish the gateway's mounted MCP servers for discovery."""

    return McpServersDocument(
        servers=[_listing(config, server) for server in config.servers]
    )
