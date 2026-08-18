from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Request
from pydantic import BaseModel

from proxy.auth_providers.models import AuthProviderDefinition
from proxy.servers.manager import ServerManager
from proxy.servers.models import McpServerConfig, server_base_url


class McpServerListing(BaseModel):
    """One publicly discoverable MCP server mounted by the gateway."""

    name: str
    description: str
    url: str
    auth: Literal["oauth2", "none"]
    auth_provider_type: str | None = None


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
    auth_provider_type: str | None,
) -> McpServerListing:
    return McpServerListing(
        name=server.name,
        description=server.description,
        url=mcp_endpoint_url(public_base_url, server),
        auth="none" if server.auth_provider is None else "oauth2",
        auth_provider_type=auth_provider_type,
    )


def _provider_types(
    definitions: list[AuthProviderDefinition],
) -> dict[str, str]:
    return {definition.name: definition.auth.provider for definition in definitions}


router = APIRouter()


@router.get("/.well-known/mcp-servers", response_model=McpServersDocument)
async def mcp_servers(request: Request) -> McpServersDocument:
    """Publish the gateway's mounted MCP servers for discovery."""

    manager = get_server_manager(request)
    public_base_url = str(request.app.state.config.public_base_url)
    provider_types = _provider_types(await manager.list_auth_providers())
    return McpServersDocument(
        servers=[
            _listing(
                public_base_url,
                server,
                provider_types.get(server.auth_provider)
                if server.auth_provider is not None
                else None,
            )
            for server in manager.snapshot()
        ]
    )
