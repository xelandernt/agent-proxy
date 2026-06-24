from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from typing import Annotated

import niquests
from fastapi import Depends
from starlette.responses import Response, StreamingResponse
from loguru import logger

from proxy.app.dependencies import ConfigDep
from proxy.auth.models import AuthenticatedPrincipal
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
from proxy.sessions.service import SessionService, SessionServiceDep
from proxy.settings import ProxyConfig, ResolvedMcpServer


class UpstreamConnectionError(Exception):
    pass


@dataclass
class ForwardResult:
    status_code: int
    headers: dict[str, str]
    body: bytes | None = None
    stream: Iterable[bytes] | None = None

    def to_response(self) -> Response:
        if self.stream is not None:
            return StreamingResponse(
                content=self.stream,
                status_code=self.status_code,
                headers=self.headers,
            )
        return Response(
            content=self.body,
            status_code=self.status_code,
            headers=self.headers,
        )


class McpProxyService:
    def __init__(self, config: ProxyConfig, sessions: SessionService) -> None:
        self._config = config
        self._sessions = sessions

    async def post(
        self,
        *,
        body: bytes,
        query: str,
        request_headers: Mapping[str, str],
        server: ResolvedMcpServer,
        principal: AuthenticatedPrincipal,
    ) -> ForwardResult:
        return await self._forward(
            body=body,
            query=query,
            request_headers=request_headers,
            server=server,
            principal=principal,
            http_method="POST",
        )

    async def get(
        self,
        *,
        body: bytes,
        query: str,
        request_headers: Mapping[str, str],
        server: ResolvedMcpServer,
        principal: AuthenticatedPrincipal,
    ) -> ForwardResult:
        return await self._forward(
            body=body,
            query=query,
            request_headers=request_headers,
            server=server,
            principal=principal,
            http_method="GET",
        )

    async def delete(
        self,
        *,
        body: bytes,
        query: str,
        request_headers: Mapping[str, str],
        server: ResolvedMcpServer,
        principal: AuthenticatedPrincipal,
    ) -> ForwardResult:
        return await self._forward(
            body=body,
            query=query,
            request_headers=request_headers,
            server=server,
            principal=principal,
            http_method="DELETE",
        )

    async def _forward(
        self,
        *,
        body: bytes,
        query: str,
        request_headers: Mapping[str, str],
        server: ResolvedMcpServer,
        principal: AuthenticatedPrincipal,
        http_method: str,
    ) -> ForwardResult:
        forwarded_headers = filter_request_headers(
            request_headers, self._config.strip_headers
        )
        session_id = optional_header_value(request_headers.get("mcp-session-id"))
        jsonrpc_method = extract_jsonrpc_method(http_method, body)
        owner = self._sessions.owner_from_principal(principal)

        logger.debug(
            "Proxying MCP request server={server_name} http_method={http_method} "
            "jsonrpc_method={jsonrpc_method} issuer={issuer} subject={subject} "
            "client_id={client_id} has_session={has_session}",
            server_name=server.server.name,
            http_method=http_method,
            jsonrpc_method=jsonrpc_method,
            issuer=owner.issuer,
            subject=owner.subject,
            client_id=principal.client_id,
            has_session=session_id is not None,
        )

        request_session_bound = False
        if self._sessions.requires_binding(server) and session_id is not None:
            request_session_bound = await self._sessions.verify_owner(
                server_name=server.server.name,
                session_id=session_id,
                owner=owner,
            )

        try:
            upstream_handle = send_upstream_request(
                url=str(server.server.endpoint),
                method=http_method,
                body=body,
                headers=forwarded_headers,
                query=query,
            )
        except niquests.exceptions.RequestException as exc:
            raise UpstreamConnectionError(
                f"Failed to reach upstream MCP server '{server.server.name}'."
            ) from exc

        if self._sessions.requires_binding(server):
            await self._sessions.synchronize_binding(
                server_name=server.server.name,
                request_method=http_method,
                principal=principal,
                request_session_id=session_id,
                request_session_bound=request_session_bound,
                jsonrpc_method=jsonrpc_method,
                response_status=response_status_code(upstream_handle.response),
                response_session_id=optional_header_value(
                    upstream_handle.response.headers.get("mcp-session-id")
                ),
            )

        response_headers = filter_response_headers(
            upstream_handle.response.headers, self._config.strip_headers
        )
        status_code = response_status_code(upstream_handle.response)

        if is_event_stream(upstream_handle.response):
            return ForwardResult(
                status_code=status_code,
                headers=response_headers,
                stream=stream_upstream_response(upstream_handle),
            )

        payload = read_response_payload(upstream_handle)
        return ForwardResult(
            status_code=status_code,
            headers=response_headers,
            body=payload,
        )


async def get_mcp_service(
    config: ConfigDep, sessions: SessionServiceDep
) -> McpProxyService:
    return McpProxyService(config=config, sessions=sessions)


McpServiceDep = Annotated[McpProxyService, Depends(get_mcp_service)]
