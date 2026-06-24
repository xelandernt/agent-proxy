from typing import Annotated

from fastapi import Depends
from loguru import logger

from proxy.auth.models import AuthenticatedPrincipal
from proxy.sessions.repository import SessionRegistry, SessionRegistryDep
from proxy.sessions.types import SessionOwner, SessionOwnershipConflictError
from proxy.settings import DisabledAuthProviderConfig, ResolvedMcpServer


class SessionService:
    def __init__(self, registry: SessionRegistry) -> None:
        self._registry = registry

    def requires_binding(self, server: ResolvedMcpServer) -> bool:
        return not isinstance(server.group.auth, DisabledAuthProviderConfig)

    def owner_from_principal(self, principal: AuthenticatedPrincipal) -> SessionOwner:
        return SessionOwner(
            issuer=principal.issuer,
            subject=principal.subject,
        )

    async def verify_owner(
        self, *, server_name: str, session_id: str, owner: SessionOwner
    ) -> bool:
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
    return SessionService(registry)


SessionServiceDep = Annotated[SessionService, Depends(get_session_service)]
