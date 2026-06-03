from typing import Annotated

import niquests
from fastapi import APIRouter, Depends, Header, HTTPException, Request, Response, status
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import StreamingResponse
from loguru import logger
from pydantic import BaseModel, Field
from starlette.types import ASGIApp

from proxy.app.auth import (
    AUTHORIZATION_HEADER,
    AuthProvider,
    AuthenticatedPrincipal,
    DisabledAuthProvider,
    get_auth_provider_registry,
)
from proxy.app.mcp.dependencies import ConfigDep
from proxy.app.mcp.ownership import (
    requires_session_binding,
    session_owner,
    synchronize_session_binding,
    verify_session_owner,
)
from proxy.app.mcp.sessions import SessionRegistryDep
from proxy.app.mcp.transport import (
    extract_jsonrpc_method,
    filter_request_headers,
    filter_response_headers,
    is_event_stream,
    optional_header_value,
    read_response_payload,
    response_status_code,
    send_upstream_request,
    stream_upstream_response,
)
from proxy.settings import ResolvedMcpServer

router = APIRouter(tags=["mcp"])


class OAuthProtectedResourceMetadata(BaseModel):
    resource: str
    authorization_servers: list[str]
    scopes_supported: list[str] = Field(default_factory=list)
    bearer_methods_supported: list[str] = Field(default_factory=lambda: ["header"])
    resource_name: str


async def get_server(name: str, config: ConfigDep) -> ResolvedMcpServer:
    resolved_server = config.get_server(name)
    if resolved_server is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Unknown MCP server '{name}'.",
        )
    return resolved_server


ServerDep = Annotated[ResolvedMcpServer, Depends(get_server)]


async def get_auth_provider(server: ServerDep, config: ConfigDep) -> AuthProvider:
    registry = get_auth_provider_registry(config)
    return registry.get(server.group.name, DisabledAuthProvider())


AuthProviderDep = Annotated[AuthProvider, Depends(get_auth_provider)]


def get_upstream_asgi_app() -> ASGIApp | None:
    return None


UpstreamAsgiAppDep = Annotated[ASGIApp | None, Depends(get_upstream_asgi_app)]


async def require_authenticated_principal(
    request: Request,
    server: ServerDep,
    auth_provider: AuthProviderDep,
    authorization: Annotated[str | None, Header(alias=AUTHORIZATION_HEADER)] = None,
) -> AuthenticatedPrincipal:
    resource_metadata_url = str(
        request.url_for("get_protected_resource_metadata", name=server.server.name)
    )
    return await run_in_threadpool(
        auth_provider.authenticate_request,
        request=request,
        authorization=authorization,
        group=server.group,
        server=server.server,
        resource_metadata_url=resource_metadata_url,
    )


PrincipalDep = Annotated[
    AuthenticatedPrincipal, Depends(require_authenticated_principal)
]


@router.get(
    "/.well-known/oauth-protected-resource/mcp/{name}",
    name="get_protected_resource_metadata",
)
async def get_protected_resource_metadata(
    server: ServerDep,
    auth_provider: AuthProviderDep,
) -> OAuthProtectedResourceMetadata:
    metadata = await run_in_threadpool(
        auth_provider.describe_resource,
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


@router.api_route(
    "/mcp/{name}",
    methods=["GET", "POST", "DELETE"],
    name="proxy_mcp_backend",
)
async def proxy_mcp_backend(
    request: Request,
    server: ServerDep,
    principal: PrincipalDep,
    registry: SessionRegistryDep,
    upstream_app: UpstreamAsgiAppDep,
) -> Response:
    body = await request.body()
    forwarded_headers = filter_request_headers(request.headers)
    session_id = optional_header_value(request.headers.get("mcp-session-id"))
    jsonrpc_method = extract_jsonrpc_method(request.method, body)
    owner = session_owner(principal)

    logger.debug(
        "Proxying MCP request server={server_name} http_method={http_method} "
        "jsonrpc_method={jsonrpc_method} issuer={issuer} subject={subject} "
        "client_id={client_id} has_session={has_session}",
        server_name=server.server.name,
        http_method=request.method,
        jsonrpc_method=jsonrpc_method,
        issuer=owner.issuer,
        subject=owner.subject,
        client_id=principal.client_id,
        has_session=session_id is not None,
    )

    request_session_bound = False
    if requires_session_binding(server) and session_id is not None:
        request_session_bound = await verify_session_owner(
            registry=registry,
            server=server,
            session_id=session_id,
            owner=owner,
        )

    if request.method == "DELETE" and not server.server.forward_delete:
        logger.debug(
            "Skipping upstream MCP DELETE server={server_name} issuer={issuer} "
            "subject={subject} client_id={client_id} has_session={has_session}",
            server_name=server.server.name,
            issuer=owner.issuer,
            subject=owner.subject,
            client_id=principal.client_id,
            has_session=session_id is not None,
        )
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    try:
        upstream_handle = await run_in_threadpool(
            send_upstream_request,
            url=str(server.server.endpoint),
            method=request.method,
            body=body,
            headers=forwarded_headers,
            query=request.url.query,
            upstream_app=upstream_app,
        )
    except niquests.exceptions.RequestException as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Failed to reach upstream MCP server '{server.server.name}'.",
        ) from exc

    await synchronize_session_binding(
        registry=registry,
        request_method=request.method,
        server=server,
        principal=principal,
        request_session_id=session_id,
        request_session_bound=request_session_bound,
        jsonrpc_method=jsonrpc_method,
        response=upstream_handle.response,
    )

    response_headers = filter_response_headers(upstream_handle.response.headers)
    if is_event_stream(upstream_handle.response):
        return StreamingResponse(
            stream_upstream_response(upstream_handle),
            status_code=response_status_code(upstream_handle.response),
            headers=response_headers,
        )

    payload = await run_in_threadpool(read_response_payload, upstream_handle)
    return Response(
        content=payload,
        status_code=response_status_code(upstream_handle.response),
        headers=response_headers,
    )
