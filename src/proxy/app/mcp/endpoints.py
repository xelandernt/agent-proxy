import json
from collections.abc import Generator, Mapping
from dataclasses import dataclass
from typing import Annotated
from urllib.parse import SplitResult, parse_qsl, urlencode, urlsplit, urlunsplit

import niquests
from fastapi import APIRouter, Depends, Header, HTTPException, Request, Response, status
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from starlette.types import ASGIApp

from proxy.app.auth import (
    AUTHORIZATION_HEADER,
    AuthProvider,
    AuthenticatedPrincipal,
    ProtectedResourceAuthMetadata,
)
from proxy.app.mcp.sessions import SessionOwner, SessionRegistry
from proxy.settings import Config, ConfigDisabledAuthProvider, ResolvedMcpServer

router = APIRouter(tags=["mcp"])

_HOP_BY_HOP_HEADERS = {
    "connection",
    "keep-alive",
    "proxy-authenticate",
    "proxy-authorization",
    "te",
    "trailer",
    "transfer-encoding",
    "upgrade",
}
_FORWARDED_REQUEST_HEADERS = {
    "accept",
    "content-type",
    "last-event-id",
    "mcp-protocol-version",
    "mcp-session-id",
}
_FORWARDED_RESPONSE_HEADERS = {
    "cache-control",
    "content-type",
    "last-event-id",
    "mcp-session-id",
}


class OAuthProtectedResourceMetadata(BaseModel):
    resource: str
    authorization_servers: list[str]
    scopes_supported: list[str] = Field(default_factory=list)
    bearer_methods_supported: list[str] = Field(default_factory=lambda: ["header"])
    resource_name: str


@dataclass(frozen=True)
class UpstreamResponseHandle:
    session: niquests.Session
    response: niquests.Response


async def get_config(request: Request) -> Config:
    return request.app.state.config


ConfigDep = Annotated[Config, Depends(get_config)]


async def get_server(name: str, config: ConfigDep) -> ResolvedMcpServer:
    resolved_server = config.get_server(name)
    if resolved_server is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Unknown MCP server '{name}'.",
        )
    return resolved_server


ServerDep = Annotated[ResolvedMcpServer, Depends(get_server)]


async def get_auth_provider(request: Request, server: ServerDep) -> AuthProvider:
    return request.app.state.auth_providers[server.group.name]


AuthProviderDep = Annotated[AuthProvider, Depends(get_auth_provider)]


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
    return _build_protected_resource_metadata(metadata=metadata, server=server)


@router.api_route(
    "/mcp/{name}",
    methods=["GET", "POST", "DELETE"],
    name="proxy_mcp_backend",
)
async def proxy_mcp_backend(
    request: Request,
    server: ServerDep,
    principal: PrincipalDep,
) -> Response:
    body = await request.body()
    forwarded_headers = _filter_request_headers(request.headers)
    upstream_app = getattr(request.app.state, "upstream_asgi_app", None)
    session_id = _optional_header_value(request.headers.get("mcp-session-id"))
    jsonrpc_method = _extract_jsonrpc_method(request.method, body)

    if _requires_session_binding(server) and session_id is not None:
        _require_session_owner(
            registry=_session_registry(request),
            server=server,
            session_id=session_id,
            owner=_session_owner(principal),
        )

    try:
        upstream_handle = await run_in_threadpool(
            _send_upstream_request,
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

    _synchronize_session_binding(
        request=request,
        server=server,
        principal=principal,
        request_session_id=session_id,
        jsonrpc_method=jsonrpc_method,
        response=upstream_handle.response,
    )

    response_headers = _filter_response_headers(upstream_handle.response.headers)
    if _is_event_stream(upstream_handle.response):
        return StreamingResponse(
            _stream_upstream_response(upstream_handle),
            status_code=_response_status_code(upstream_handle.response),
            headers=response_headers,
        )

    payload = await run_in_threadpool(_read_response_payload, upstream_handle)
    return Response(
        content=payload,
        status_code=_response_status_code(upstream_handle.response),
        headers=response_headers,
    )


def _build_protected_resource_metadata(
    *,
    server: ResolvedMcpServer,
    metadata: ProtectedResourceAuthMetadata,
) -> OAuthProtectedResourceMetadata:
    return OAuthProtectedResourceMetadata(
        resource=metadata.resource,
        authorization_servers=list(metadata.authorization_servers),
        scopes_supported=list(metadata.scopes_supported),
        resource_name=server.server.name,
    )


def _filter_request_headers(headers: Mapping[str, str]) -> dict[str, str]:
    filtered: dict[str, str] = {}
    for header_name, header_value in headers.items():
        normalized_name = header_name.lower()
        if normalized_name in _HOP_BY_HOP_HEADERS:
            continue
        if normalized_name == "authorization":
            continue
        if normalized_name in _FORWARDED_REQUEST_HEADERS:
            filtered[header_name] = header_value
    return filtered


def _filter_response_headers(headers: Mapping[str, str]) -> dict[str, str]:
    filtered: dict[str, str] = {}
    for header_name, header_value in headers.items():
        normalized_name = header_name.lower()
        if normalized_name in _HOP_BY_HOP_HEADERS:
            continue
        if normalized_name in _FORWARDED_RESPONSE_HEADERS:
            filtered[header_name] = header_value
    return filtered


def _send_upstream_request(
    *,
    url: str,
    method: str,
    body: bytes,
    headers: dict[str, str],
    query: str,
    upstream_app: ASGIApp | None,
) -> UpstreamResponseHandle:
    target_url = _build_target_url(url, query, use_asgi_app=upstream_app is not None)

    if upstream_app is not None:
        session = niquests.Session(
            app=upstream_app,
            base_url="asgi://default",
            timeout=(10.0, 3600.0),
        )
    else:
        session = niquests.Session(timeout=(10.0, 3600.0))

    try:
        response = session.request(
            method=method,
            url=target_url,
            data=body,
            headers=headers,
            allow_redirects=False,
            stream=upstream_app is None,
        )
    except niquests.exceptions.RequestException:
        session.close()
        raise

    return UpstreamResponseHandle(session=session, response=response)


def _build_target_url(url: str, query: str, *, use_asgi_app: bool) -> str:
    parsed = urlsplit(url)
    merged_query = urlencode(
        parse_qsl(parsed.query, keep_blank_values=True), doseq=True
    )
    request_query = urlencode(parse_qsl(query, keep_blank_values=True), doseq=True)
    combined_query = "&".join(part for part in [merged_query, request_query] if part)

    if use_asgi_app:
        path = parsed.path or "/"
        return path if not combined_query else f"{path}?{combined_query}"

    rebuilt = SplitResult(
        scheme=parsed.scheme,
        netloc=parsed.netloc,
        path=parsed.path,
        query=combined_query,
        fragment=parsed.fragment,
    )
    return urlunsplit(rebuilt)


def _read_response_payload(handle: UpstreamResponseHandle) -> bytes:
    try:
        return handle.response.content or b""
    finally:
        handle.response.close()
        handle.session.close()


def _is_event_stream(response: niquests.Response) -> bool:
    content_type = response.headers.get("content-type", "")
    normalized_content_type = (
        content_type.decode() if isinstance(content_type, bytes) else str(content_type)
    )
    return normalized_content_type.startswith("text/event-stream")


def _response_status_code(response: niquests.Response) -> int:
    return int(response.status_code or status.HTTP_502_BAD_GATEWAY)


def _stream_upstream_response(
    handle: UpstreamResponseHandle,
) -> Generator[bytes, None, None]:
    try:
        for chunk in handle.response.iter_content(chunk_size=64 * 1024):
            if isinstance(chunk, str):
                yield chunk.encode()
            elif chunk:
                yield chunk
    finally:
        handle.response.close()
        handle.session.close()


def _extract_jsonrpc_method(method: str, body: bytes) -> str | None:
    if method != "POST" or not body:
        return None

    try:
        payload = json.loads(body)
    except (UnicodeDecodeError, json.JSONDecodeError):
        return None

    if not isinstance(payload, dict):
        return None

    candidate = payload.get("method")
    if isinstance(candidate, str):
        return candidate
    return None


def _optional_header_value(value: str | bytes | None) -> str | None:
    if value is None:
        return None
    if isinstance(value, bytes):
        value = value.decode()
    stripped_value = value.strip()
    return stripped_value or None


def _requires_session_binding(server: ResolvedMcpServer) -> bool:
    return not isinstance(server.group.auth, ConfigDisabledAuthProvider)


def _session_owner(principal: AuthenticatedPrincipal) -> SessionOwner:
    return SessionOwner(
        issuer=principal.issuer,
        subject=principal.subject,
        client_id=principal.client_id,
    )


def _session_registry(request: Request) -> SessionRegistry:
    return request.app.state.mcp_session_registry


def _require_session_owner(
    *,
    registry: SessionRegistry,
    server: ResolvedMcpServer,
    session_id: str,
    owner: SessionOwner,
) -> None:
    bound_owner = registry.get(server_name=server.server.name, session_id=session_id)
    if bound_owner != owner:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Unknown session.",
        )


def _synchronize_session_binding(
    *,
    request: Request,
    server: ResolvedMcpServer,
    principal: AuthenticatedPrincipal,
    request_session_id: str | None,
    jsonrpc_method: str | None,
    response: niquests.Response,
) -> None:
    if not _requires_session_binding(server):
        return

    registry = _session_registry(request)
    response_status = _response_status_code(response)
    owner = _session_owner(principal)

    if request_session_id is not None and response_status == status.HTTP_404_NOT_FOUND:
        registry.remove(server_name=server.server.name, session_id=request_session_id)
        return

    if (
        request.method == "DELETE"
        and request_session_id is not None
        and 200 <= response_status < 300
    ):
        registry.remove(server_name=server.server.name, session_id=request_session_id)
        return

    response_session_id = _optional_header_value(response.headers.get("mcp-session-id"))
    if (
        jsonrpc_method == "initialize"
        and response_session_id is not None
        and 200 <= response_status < 300
    ):
        registry.bind(
            server_name=server.server.name,
            session_id=response_session_id,
            owner=owner,
        )
