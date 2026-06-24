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
    result = await mcp_service.delete(
        body=await request.body(),
        query=request.url.query,
        request_headers=request.headers,
        server=server,
        principal=principal,
    )
    return result.to_response()
