from typing import Annotated

from fastapi import Depends
from loguru import logger

from proxy.auth.models import AuthenticatedPrincipal
from proxy.sessions.repository import SessionRegistry, SessionRegistryDep
from proxy.sessions.types import SessionOwner, SessionOwnershipConflictError
from proxy.settings import DisabledAuthProviderConfig, ResolvedMcpServer


class SessionService:
    """Service for managing MCP session ownership bindings.

    Determines whether session binding is required for a server, verifies
    session ownership, and synchronizes bindings based on request/response
    lifecycle events.

    Args:
        registry: The session registry persistence layer.
    """

    def __init__(self, registry: SessionRegistry) -> None:
        self._registry = registry

    def requires_binding(self, server: ResolvedMcpServer) -> bool:
        """Check whether a server requires session ownership binding.

        Binding is required when the server's group has an auth provider
        configured (i.e., it is not a DisabledAuthProvider).

        Args:
            server: The resolved MCP server to check.

        Returns:
            True if session binding is required for this server.
        """
        return not isinstance(server.group.auth, DisabledAuthProviderConfig)

    def owner_from_principal(self, principal: AuthenticatedPrincipal) -> SessionOwner:
        """Derive a session owner identity from an authenticated principal.

        Args:
            principal: The authenticated principal.

        Returns:
            A SessionOwner representing the principal's identity.
        """
        return SessionOwner(
            issuer=principal.issuer,
            subject=principal.subject,
        )

    async def verify_owner(
        self, *, server_name: str, session_id: str, owner: SessionOwner
    ) -> bool:
        """Verify that a session is owned by the given principal.

        If the session is already bound to a different owner, raises a
        SessionOwnershipConflictError.

        Args:
            server_name: The MCP server name.
            session_id: The session ID to verify.
            owner: The expected owner of the session.

        Returns:
            True if the session is bound to the expected owner.

        Raises:
            SessionOwnershipConflictError: If the session is bound to a
                different principal.
        """
        bound_owner = await self._registry.get(
            server_name=server_name, session_id=session_id
        )
        if bound_owner is None:
            return False
        if bound_owner != owner:
            logger.warning(
                "Protected MCP session mismatch server={server_name} "
                "bound_issuer={bound_issuer} bound_subject={bound_subject} "
                "request_issuer={request_issuer} request_subject={request_subject}",
                server_name=server_name,
                bound_issuer=bound_owner.issuer if bound_owner else None,
                bound_subject=bound_owner.subject if bound_owner else None,
                request_issuer=owner.issuer,
                request_subject=owner.subject,
            )
            raise SessionOwnershipConflictError(
                f"Protected session for server '{server_name}' is bound to a different principal."
            )
        return True

    async def synchronize_binding(
        self,
        *,
        server_name: str,
        request_method: str,
        principal: AuthenticatedPrincipal,
        request_session_id: str | None,
        request_session_bound: bool,
        jsonrpc_method: str | None,
        response_status: int,
        response_session_id: str | None,
    ) -> None:
        """Synchronise session ownership bindings based on request/response.

        Implements the session lifecycle:
        - DELETE with success -> remove the binding.
        - Request with session that returns 404 -> remove stale binding.
        - Request with unbound session and success -> bind the session.
        - POST/initialize with response session -> bind the new session.

        Args:
            server_name: The MCP server name.
            request_method: The HTTP method of the request.
            principal: The authenticated principal.
            request_session_id: Session ID from the request, if any.
            request_session_bound: Whether the request session was verified
                as owned by this principal.
            jsonrpc_method: The JSON-RPC method, if extractable.
            response_status: The upstream HTTP response status code.
            response_session_id: Session ID from the upstream response, if any.
        """
        owner = self.owner_from_principal(principal)

        if (
            request_method == "DELETE"
            and request_session_id is not None
            and 200 <= response_status < 300
        ):
            await self._registry.remove(
                server_name=server_name,
                session_id=request_session_id,
            )
            return

        if request_session_id is not None and response_status == 404:
            await self._registry.remove(
                server_name=server_name,
                session_id=request_session_id,
            )
            return

        if (
            request_session_id is not None
            and not request_session_bound
            and 200 <= response_status < 300
        ):
            await self._registry.bind(
                server_name=server_name,
                session_id=request_session_id,
                owner=owner,
                client_id=principal.client_id,
            )
            return

        if (
            request_method == "POST"
            and jsonrpc_method == "initialize"
            and response_session_id is not None
            and 200 <= response_status < 300
        ):
            await self._registry.bind(
                server_name=server_name,
                session_id=response_session_id,
                owner=owner,
                client_id=principal.client_id,
            )


async def get_session_service(registry: SessionRegistryDep) -> SessionService:
    """Dependency factory for SessionService.

    Args:
        registry: The session registry dependency.

    Returns:
        A new SessionService instance.
    """
    return SessionService(registry)


SessionServiceDep = Annotated[SessionService, Depends(get_session_service)]
