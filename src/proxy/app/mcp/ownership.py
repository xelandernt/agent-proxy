import niquests
from fastapi import HTTPException, status
from loguru import logger

from proxy.app.auth import AuthenticatedPrincipal
from proxy.app.mcp.sessions import (
    SessionOwner,
    SessionOwnershipConflictError,
    SessionRegistry,
)
from proxy.app.mcp.transport import optional_header_value, response_status_code
from proxy.settings import ConfigDisabledAuthProvider, ResolvedMcpServer


def requires_session_binding(server: ResolvedMcpServer) -> bool:
    return not isinstance(server.group.auth, ConfigDisabledAuthProvider)


def session_owner(principal: AuthenticatedPrincipal) -> SessionOwner:
    return SessionOwner(
        issuer=principal.issuer,
        subject=principal.subject,
    )


async def verify_session_owner(
    *,
    registry: SessionRegistry,
    server: ResolvedMcpServer,
    session_id: str,
    owner: SessionOwner,
) -> None:
    bound_owner = await registry.get(
        server_name=server.server.name, session_id=session_id
    )
    if bound_owner != owner:
        logger.warning(
            "Protected MCP session mismatch server={server_name} "
            "bound_issuer={bound_issuer} bound_subject={bound_subject} "
            "request_issuer={request_issuer} request_subject={request_subject}",
            server_name=server.server.name,
            bound_issuer=bound_owner.issuer if bound_owner else None,
            bound_subject=bound_owner.subject if bound_owner else None,
            request_issuer=owner.issuer,
            request_subject=owner.subject,
        )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Unknown session.",
        )
    logger.debug(
        "Protected MCP session owner verified server={server_name} issuer={issuer} subject={subject}",
        server_name=server.server.name,
        issuer=owner.issuer,
        subject=owner.subject,
    )


async def synchronize_session_binding(
    *,
    registry: SessionRegistry,
    request_method: str,
    server: ResolvedMcpServer,
    principal: AuthenticatedPrincipal,
    request_session_id: str | None,
    jsonrpc_method: str | None,
    response: niquests.Response,
) -> None:
    if not requires_session_binding(server):
        return

    owner = session_owner(principal)
    response_status = response_status_code(response)

    # Keep the proxy-side binding until the upstream explicitly rejects the
    # session. Some MCP clients issue successful DELETEs without ending the
    # session, and removing the binding early causes proxy-local 404s.
    if request_session_id is not None and response_status == status.HTTP_404_NOT_FOUND:
        logger.debug(
            "Upstream reported unknown MCP session server={server_name}; removing proxy binding",
            server_name=server.server.name,
        )
        await registry.remove(
            server_name=server.server.name,
            session_id=request_session_id,
        )
        return

    response_session_id = optional_header_value(response.headers.get("mcp-session-id"))
    if (
        request_method == "POST"
        and jsonrpc_method == "initialize"
        and response_session_id is not None
        and 200 <= response_status < 300
    ):
        logger.debug(
            "Initialize created MCP session server={server_name} issuer={issuer} "
            "subject={subject} client_id={client_id}",
            server_name=server.server.name,
            issuer=owner.issuer,
            subject=owner.subject,
            client_id=principal.client_id,
        )
        try:
            await registry.bind(
                server_name=server.server.name,
                session_id=response_session_id,
                owner=owner,
                client_id=principal.client_id,
            )
        except SessionOwnershipConflictError as exc:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Protected session is already bound to another principal.",
            ) from exc
