import pytest

from proxy.auth.models import AuthenticatedPrincipal
from proxy.sessions.types import SessionOwner, SessionOwnershipConflictError
from proxy.sessions.service import SessionService
from proxy.settings import (
    DisabledAuthProviderConfig,
    McpGroupConfig,
    McpServerConfig,
    OidcAuthProviderConfig,
    ResolvedMcpServer,
)


def _disabled_server(name: str = "test") -> ResolvedMcpServer:
    return ResolvedMcpServer(
        group=McpGroupConfig(
            name="test-group",
            auth=DisabledAuthProviderConfig(),
            servers=[McpServerConfig(name=name, endpoint="http://localhost:1/mcp")],
        ),
        server=McpServerConfig(name=name, endpoint="http://localhost:1/mcp"),
    )


def _protected_server(name: str = "test") -> ResolvedMcpServer:
    return ResolvedMcpServer(
        group=McpGroupConfig(
            name="test-group",
            auth=OidcAuthProviderConfig(issuer="http://localhost:8080/realms/test"),
            servers=[
                McpServerConfig(
                    name=name,
                    endpoint="http://localhost:1/mcp",
                    resource="http://localhost:8008/mcp/test",
                )
            ],
        ),
        server=McpServerConfig(
            name=name,
            endpoint="http://localhost:1/mcp",
            resource="http://localhost:8008/mcp/test",
        ),
    )


def _principal(
    subject: str = "user",
    issuer: str = "http://example.com",
    client_id: str | None = "client-1",
) -> AuthenticatedPrincipal:
    return AuthenticatedPrincipal(
        subject=subject,
        issuer=issuer,
        audiences=("api://default",),
        granted_scopes=frozenset({"read"}),
        client_id=client_id,
        token_id="token-1",
    )


class MockSessionRegistry:
    def __init__(self) -> None:
        self.bindings: dict[tuple[str, str], SessionOwner] = {}
        self.bound_calls: list[dict] = []
        self.removed_calls: list[dict] = []

    async def bind(
        self,
        *,
        server_name: str,
        session_id: str,
        owner: SessionOwner,
        client_id: str | None,
    ) -> None:
        key = (server_name, session_id)
        if key in self.bindings and self.bindings[key] != owner:
            raise SessionOwnershipConflictError(
                f"Protected session for server '{server_name}' is already bound to a different principal."
            )
        self.bindings[key] = owner
        self.bound_calls.append(
            {
                "server_name": server_name,
                "session_id": session_id,
                "owner": owner,
                "client_id": client_id,
            }
        )

    async def get(self, *, server_name: str, session_id: str) -> SessionOwner | None:
        return self.bindings.get((server_name, session_id))

    async def remove(self, *, server_name: str, session_id: str) -> None:
        self.bindings.pop((server_name, session_id), None)
        self.removed_calls.append(
            {"server_name": server_name, "session_id": session_id}
        )


class TestRequiresSessionBinding:
    def test_disabled_auth_returns_false(self):
        service = SessionService(MockSessionRegistry())
        assert not service.requires_binding(_disabled_server())

    def test_oidc_auth_returns_true(self):
        service = SessionService(MockSessionRegistry())
        assert service.requires_binding(_protected_server())


class TestSessionOwner:
    def test_owner_from_principal(self):
        service = SessionService(MockSessionRegistry())
        principal = _principal(subject="user-1", issuer="issuer-1")
        owner = service.owner_from_principal(principal)
        assert owner.subject == "user-1"
        assert owner.issuer == "issuer-1"


class TestVerifySessionOwner:
    async def test_no_binding_returns_false(self):
        service = SessionService(MockSessionRegistry())
        owner = SessionOwner(issuer="issuer", subject="user")
        result = await service.verify_owner(
            server_name="test",
            session_id="session-1",
            owner=owner,
        )
        assert result is False

    async def test_matching_owner_returns_true(self):
        registry = MockSessionRegistry()
        service = SessionService(registry)
        owner = SessionOwner(issuer="issuer", subject="user")
        await registry.bind(
            server_name="test",
            session_id="session-1",
            owner=owner,
            client_id="client-1",
        )
        result = await service.verify_owner(
            server_name="test",
            session_id="session-1",
            owner=owner,
        )
        assert result is True

    async def test_different_owner_raises(self):
        registry = MockSessionRegistry()
        service = SessionService(registry)
        existing = SessionOwner(issuer="issuer", subject="user-a")
        await registry.bind(
            server_name="test",
            session_id="session-1",
            owner=existing,
            client_id="client-1",
        )
        requester = SessionOwner(issuer="issuer", subject="user-b")
        with pytest.raises(SessionOwnershipConflictError):
            await service.verify_owner(
                server_name="test",
                session_id="session-1",
                owner=requester,
            )


class TestSynchronizeSessionBinding:
    async def test_delete_removes_binding(self):
        registry = MockSessionRegistry()
        service = SessionService(registry)
        owner = SessionOwner(issuer="http://example.com", subject="user")
        await registry.bind(
            server_name="test",
            session_id="session-1",
            owner=owner,
            client_id="client-1",
        )
        await service.synchronize_binding(
            server_name="test",
            request_method="DELETE",
            principal=_principal(),
            request_session_id="session-1",
            request_session_bound=True,
            jsonrpc_method=None,
            response_status=200,
            response_session_id=None,
        )
        assert len(registry.removed_calls) == 1

    async def test_not_found_response_removes_binding(self):
        registry = MockSessionRegistry()
        service = SessionService(registry)
        owner = SessionOwner(issuer="http://example.com", subject="user")
        await registry.bind(
            server_name="test",
            session_id="session-1",
            owner=owner,
            client_id="client-1",
        )
        await service.synchronize_binding(
            server_name="test",
            request_method="POST",
            principal=_principal(),
            request_session_id="session-1",
            request_session_bound=True,
            jsonrpc_method="tools/list",
            response_status=404,
            response_session_id=None,
        )
        assert len(registry.removed_calls) == 1

    async def test_successful_request_without_binding_binds(self):
        registry = MockSessionRegistry()
        service = SessionService(registry)
        await service.synchronize_binding(
            server_name="test",
            request_method="POST",
            principal=_principal(subject="user"),
            request_session_id="session-1",
            request_session_bound=False,
            jsonrpc_method="tools/list",
            response_status=200,
            response_session_id=None,
        )
        assert len(registry.bound_calls) == 1
        assert registry.bound_calls[0]["session_id"] == "session-1"

    async def test_initialize_with_response_session_binds(self):
        registry = MockSessionRegistry()
        service = SessionService(registry)
        await service.synchronize_binding(
            server_name="test",
            request_method="POST",
            principal=_principal(subject="user"),
            request_session_id=None,
            request_session_bound=False,
            jsonrpc_method="initialize",
            response_status=200,
            response_session_id="session-new",
        )
        assert len(registry.bound_calls) == 1
        assert registry.bound_calls[0]["session_id"] == "session-new"

    async def test_initialize_without_response_session_does_not_bind(self):
        registry = MockSessionRegistry()
        service = SessionService(registry)
        await service.synchronize_binding(
            server_name="test",
            request_method="POST",
            principal=_principal(subject="user"),
            request_session_id=None,
            request_session_bound=False,
            jsonrpc_method="initialize",
            response_status=200,
            response_session_id=None,
        )
        assert len(registry.bound_calls) == 0
