from typing import Annotated, Protocol

from fastapi import Depends
from loguru import logger
from sqlalchemy import delete
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from proxy.app.runtime import AsyncSessionDep
from proxy.sessions.models import SessionBinding
from proxy.sessions.types import SessionOwner, SessionOwnershipConflictError


class SessionRegistry(Protocol):
    """Protocol for session ownership persistence."""

    async def bind(
        self,
        *,
        server_name: str,
        session_id: str,
        owner: SessionOwner,
        client_id: str | None,
    ) -> None: ...

    async def get(
        self, *, server_name: str, session_id: str
    ) -> SessionOwner | None: ...

    async def remove(self, *, server_name: str, session_id: str) -> None: ...


class SessionRepository(SessionRegistry):
    """SQLAlchemy-backed repository for MCP session ownership bindings.

    Args:
        session: An async SQLAlchemy session for database access.
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def bind(
        self,
        *,
        server_name: str,
        session_id: str,
        owner: SessionOwner,
        client_id: str | None,
    ) -> None:
        """Bind a session to an owner in the database.

        If a binding already exists, verifies the owner matches. If the
        owner matches but the client_id differs, updates the client_id.

        Args:
            server_name: The MCP server name.
            session_id: The session ID to bind.
            owner: The session owner identity.
            client_id: Optional OAuth client ID to associate.

        Raises:
            SessionOwnershipConflictError: If the session is already bound
                to a different principal.
            IntegrityError: If an unexpected database constraint is hit.
        """
        self._session.add(
            SessionBinding(
                server_name=server_name,
                session_id=session_id,
                issuer=owner.issuer,
                subject=owner.subject,
                client_id=client_id,
            )
        )
        try:
            await self._session.commit()
            return
        except IntegrityError:
            await self._session.rollback()

        existing_binding = await self._session.get(
            SessionBinding,
            {"server_name": server_name, "session_id": session_id},
        )
        if existing_binding is None:
            raise

        existing_owner = SessionOwner(
            issuer=existing_binding.issuer,
            subject=existing_binding.subject,
        )
        if existing_owner != owner:
            logger.warning(
                "Protected MCP session ownership conflict server={server_name} "
                "existing_issuer={existing_issuer} existing_subject={existing_subject} "
                "request_issuer={request_issuer} "
                "request_subject={request_subject} existing_client_id={existing_client_id} "
                "request_client_id={request_client_id}",
                server_name=server_name,
                existing_issuer=existing_binding.issuer,
                existing_subject=existing_binding.subject,
                request_issuer=owner.issuer,
                request_subject=owner.subject,
                existing_client_id=existing_binding.client_id,
                request_client_id=client_id,
            )
            raise SessionOwnershipConflictError(
                f"Protected session for server '{server_name}' is already bound to a different principal."
            )
        if existing_binding.client_id != client_id:
            existing_binding.client_id = client_id
            await self._session.commit()

    async def get(self, *, server_name: str, session_id: str) -> SessionOwner | None:
        """Get the owner of a session binding, if one exists.

        Args:
            server_name: The MCP server name.
            session_id: The session ID to look up.

        Returns:
            The session owner, or None if no binding exists.
        """
        binding = await self._session.get(
            SessionBinding,
            {"server_name": server_name, "session_id": session_id},
        )
        if binding is None:
            return None
        return SessionOwner(
            issuer=binding.issuer,
            subject=binding.subject,
        )

    async def remove(self, *, server_name: str, session_id: str) -> None:
        """Remove a session binding from the database.

        Args:
            server_name: The MCP server name.
            session_id: The session ID to remove.
        """
        await self._session.execute(
            delete(SessionBinding).where(
                SessionBinding.server_name == server_name,
                SessionBinding.session_id == session_id,
            )
        )
        await self._session.commit()


async def get_session_repository(session: AsyncSessionDep) -> SessionRegistry:
    """Dependency factory for SessionRepository.

    Args:
        session: An async SQLAlchemy session.

    Returns:
        A new SessionRepository instance.
    """
    return SessionRepository(session)


SessionRegistryDep = Annotated[SessionRegistry, Depends(get_session_repository)]
