from fastapi import APIRouter, HTTPException, Request, Response, status

from proxy.app.dependencies import (
    AuthProviderDep,
    PrincipalDep,
    ServerDep,
)
from proxy.app.mcp.schemas import OAuthProtectedResourceMetadata
from proxy.app.mcp.service import McpServiceDep

router = APIRouter(tags=["mcp"])


@router.get(
    "/.well-known/oauth-protected-resource/mcp/{name}",
    name="get_protected_resource_metadata",
)
async def get_protected_resource_metadata(
    server: ServerDep,
    auth_provider: AuthProviderDep,
) -> OAuthProtectedResourceMetadata:
    """Get OAuth protected resource metadata for an MCP server.

    Returns the resource metadata (resource URI, authorization servers, and
    supported scopes) for the named MCP server. Used by OAuth clients to
    discover how to obtain tokens for this protected resource.

    Args:
        server: The resolved MCP server configuration from the path parameter.
        auth_provider: The auth provider for the server's group.

    Returns:
        OAuth protected resource metadata including resource URI,
        authorization server URLs, and supported scopes.

    Raises:
        HTTPException 404: If the server is not configured as a protected
            resource.
    """
    metadata = auth_provider.describe_resource(
        group=server.group,
        server=server.server,
    )
    if metadata is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"MCP server '{server.server.name}' is not a protected resource.",
        )
    return OAuthProtectedResourceMetadata(
        resource=metadata.resource,
        authorization_servers=list(metadata.authorization_servers),
        scopes_supported=list(metadata.scopes_supported),
        resource_name=server.server.name,
    )


@router.post("/mcp/{name}", name="proxy_mcp_backend")
async def post_mcp_backend(
    request: Request,
    server: ServerDep,
    principal: PrincipalDep,
    mcp_service: McpServiceDep,
) -> Response:
    """Proxy a POST request to the upstream MCP server.

    Forwards the incoming POST request (including body, query parameters, and
    headers) to the configured MCP server endpoint and returns the upstream
    response to the client. Supports both regular and streaming (SSE)
    responses.

    Args:
        request: The incoming HTTP request.
        server: The resolved MCP server configuration from the path parameter.
        principal: The authenticated principal extracted from the request.
        mcp_service: The MCP proxy service handling forwarding logic.

    Returns:
        Response from the upstream MCP server, with headers filtered per
        configuration.
    """
    result = await mcp_service.post(
        body=await request.body(),
        query=request.url.query,
        request_headers=request.headers,
        server=server,
        principal=principal,
    )
    return result.to_response()


@router.get("/mcp/{name}", name="proxy_mcp_backend_get")
async def get_mcp_backend(
    request: Request,
    server: ServerDep,
    principal: PrincipalDep,
    mcp_service: McpServiceDep,
) -> Response:
    """Proxy a GET request to the upstream MCP server.

    Forwards the incoming GET request to the configured MCP server endpoint
    and returns the upstream response.

    Args:
        request: The incoming HTTP request.
        server: The resolved MCP server configuration from the path parameter.
        principal: The authenticated principal extracted from the request.
        mcp_service: The MCP proxy service handling forwarding logic.

    Returns:
        Response from the upstream MCP server.
    """
    result = await mcp_service.get(
        body=await request.body(),
        query=request.url.query,
        request_headers=request.headers,
        server=server,
        principal=principal,
    )
    return result.to_response()


@router.delete("/mcp/{name}", name="proxy_mcp_backend_delete")
async def delete_mcp_backend(
    request: Request,
    server: ServerDep,
    principal: PrincipalDep,
    mcp_service: McpServiceDep,
) -> Response:
    """Proxy a DELETE request to the upstream MCP server.

    Forwards the incoming DELETE request to the configured MCP server endpoint
    and returns the upstream response.

    Args:
        request: The incoming HTTP request.
        server: The resolved MCP server configuration from the path parameter.
        principal: The authenticated principal extracted from the request.
        mcp_service: The MCP proxy service handling forwarding logic.

    Returns:
        Response from the upstream MCP server.
    """
    result = await mcp_service.delete(
        body=await request.body(),
        query=request.url.query,
        request_headers=request.headers,
        server=server,
        principal=principal,
    )
    return result.to_response()
