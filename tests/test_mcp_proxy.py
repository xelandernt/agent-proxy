import json
from collections.abc import Iterator
from dataclasses import dataclass

from fastapi import FastAPI, Header, HTTPException, Request, Response, status
from fastapi.testclient import TestClient
import pytest
from testcontainers.postgres import PostgresContainer
from uuid import uuid4

from proxy.app.auth import (
    AuthenticatedPrincipal,
    DisabledAuthProvider,
    ProtectedResourceAuthMetadata,
    audiences_match_resource,
    extract_scopes,
    get_auth_provider_registry,
    principal_subject,
    server_accepted_audiences,
)
from proxy.app.mcp.endpoints import ServerDep, get_auth_provider, get_upstream_asgi_app
from proxy.app.mcp.sessions import (
    SessionBinding,
    SessionOwner,
    SessionRegistryDatabase,
    SqlAlchemySessionRegistry,
)
from proxy.app.main import create_app
from proxy.settings import (
    Config,
    ConfigDisabledAuthProvider,
    ConfigEntraIdAuthProvider,
    ConfigMcp,
    ConfigMcpGroup,
    ConfigMcpSessionRegistry,
    ConfigMcpServer,
)


class StaticAuthProvider:
    def describe_resource(
        self,
        *,
        group: ConfigMcpGroup,
        server: ConfigMcpServer,
    ) -> ProtectedResourceAuthMetadata:
        return ProtectedResourceAuthMetadata(
            resource=str(server.resource),
            authorization_servers=(
                "https://login.microsoftonline.com/test-tenant/v2.0",
            ),
            scopes_supported=group.required_scopes_for_server(server),
        )

    def authenticate_request(
        self,
        *,
        request: Request,
        authorization: str | None,
        group: ConfigMcpGroup,
        server: ConfigMcpServer,
        resource_metadata_url: str,
    ) -> AuthenticatedPrincipal:
        token_to_principal = {
            "Bearer token-alice": ("alice", "test-client"),
            "Bearer token-alice-rotated-client": ("alice", "rotated-client"),
            "Bearer token-bob": ("bob", "test-client"),
        }
        principal = (
            None if authorization is None else token_to_principal.get(authorization)
        )
        if principal is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token.",
            )
        subject, client_id = principal

        return AuthenticatedPrincipal(
            subject=subject,
            issuer="https://login.microsoftonline.com/test-tenant/v2.0",
            audiences=(str(server.resource),),
            granted_scopes=frozenset(group.required_scopes_for_server(server)),
            client_id=client_id,
            token_id=None,
        )


@dataclass
class BackendAppFixture:
    app: FastAPI
    last_request: dict[str, str | None]
    last_body: bytes | None
    last_query: str | None
    sessions: set[str]
    keep_session_on_delete: bool = False
    custom_status_code: int | None = None
    custom_headers: dict[str, str] | None = None
    use_event_stream: bool = False


@pytest.fixture()
def backend_app() -> "BackendAppFixture":
    app = FastAPI()
    sessions: set[str] = set()
    last_request: dict[str, str | None] = {
        "authorization": None,
        "session_id": None,
        "method": None,
        "custom_header": None,
    }
    backend = BackendAppFixture(
        app=app,
        last_request=last_request,
        last_body=None,
        last_query=None,
        sessions=sessions,
    )

    @app.api_route("/mcp", methods=["GET", "POST", "DELETE"], response_model=None)
    async def handle_mcp(
        request: Request,
        response: Response,
        authorization: str | None = Header(default=None, alias="Authorization"),
        mcp_session_id: str | None = Header(default=None, alias="MCP-Session-Id"),
        x_custom_trace: str | None = Header(default=None, alias="X-Custom-Trace"),
    ) -> Response | dict:
        last_request["authorization"] = authorization
        last_request["session_id"] = mcp_session_id
        last_request["method"] = request.method
        last_request["custom_header"] = x_custom_trace
        backend.last_query = str(request.url.query) if request.url.query else None

        if request.method == "GET":
            for key, value in (backend.custom_headers or {}).items():
                response.headers[key] = value
            response.status_code = backend.custom_status_code or 200
            return Response(
                content=b"{}",
                status_code=response.status_code,
                headers=response.headers,
            )

        if request.method == "DELETE":
            if mcp_session_id is None or mcp_session_id not in sessions:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND, detail="Unknown session."
                )
            if not backend.keep_session_on_delete:
                sessions.remove(mcp_session_id)
            for key, value in (backend.custom_headers or {}).items():
                response.headers[key] = value
            response.status_code = backend.custom_status_code or 204
            return Response(
                content=b"{}",
                status_code=response.status_code,
                headers=response.headers,
            )

        backend.last_body = await request.body()
        payload = await request.json()

        if payload["method"] == "initialize":
            session_id = "session-1"
            sessions.add(session_id)
            response.headers["MCP-Session-Id"] = session_id
            json_body = {
                "jsonrpc": "2.0",
                "id": payload["id"],
                "result": {
                    "protocolVersion": "2025-03-26",
                    "capabilities": {"tools": {}},
                    "serverInfo": {"name": "demo-backend", "version": "0.1.0"},
                },
            }
        elif mcp_session_id not in sessions:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Unknown session."
            )
        else:
            json_body = {
                "jsonrpc": "2.0",
                "id": payload["id"],
                "result": {"tools": []},
            }

        for key, value in (backend.custom_headers or {}).items():
            response.headers[key] = value
        return Response(
            content=json.dumps(json_body).encode(),
            status_code=backend.custom_status_code or 200,
            headers=dict(response.headers),
            media_type="application/json",
        )

    return backend


@pytest.fixture(scope="session")
def postgres_database_url() -> Iterator[str]:
    with PostgresContainer(
        "postgres:17-alpine",
        username="postgres",
        password="postgres",
        dbname="agent_proxy",
    ) as postgres:
        yield (
            "postgresql+asyncpg://postgres:postgres@"
            f"{postgres.get_container_host_ip()}:{postgres.get_exposed_port(5432)}"
            "/agent_proxy"
        )


@pytest.fixture()
def config(postgres_database_url: str) -> Config:
    return Config(
        session_registry=ConfigMcpSessionRegistry.model_validate(
            {"url": postgres_database_url}
        ),
        mcp=ConfigMcp(
            groups=[
                ConfigMcpGroup(
                    name="secure",
                    auth=ConfigEntraIdAuthProvider(
                        tenant_id="test-tenant",
                    ),
                    default_required_scopes=["mcp.access"],
                    servers=[
                        ConfigMcpServer(
                            name="secure-demo",
                            endpoint="http://backend.test/mcp",
                            resource="https://proxy.example.com/mcp/secure-demo",
                        )
                    ],
                ),
                ConfigMcpGroup(
                    name="public",
                    auth=ConfigDisabledAuthProvider(),
                    servers=[
                        ConfigMcpServer(
                            name="public-demo",
                            endpoint="http://backend.test/mcp",
                        )
                    ],
                ),
            ],
        ),
    )


@pytest.fixture()
def client(
    config: Config,
    backend_app: "BackendAppFixture",
    postgres_database_url: str,
) -> Iterator[TestClient]:
    test_config = config.model_copy(
        update={
            "session_registry": ConfigMcpSessionRegistry.model_validate(
                {"url": postgres_database_url}
            )
        }
    )
    app = create_app(test_config)
    app.dependency_overrides[get_upstream_asgi_app] = lambda: backend_app.app

    async def override_auth_provider(server: ServerDep):
        if server.group.name == "secure":
            return StaticAuthProvider()
        return DisabledAuthProvider()

    app.dependency_overrides[get_auth_provider] = override_auth_provider
    with TestClient(app) as test_client:
        yield test_client


def test_missing_token_returns_mcp_auth_challenge(
    config: Config, backend_app: "BackendAppFixture", postgres_database_url: str
) -> None:
    app = create_app(
        config.model_copy(
            update={
                "session_registry": ConfigMcpSessionRegistry.model_validate(
                    {"url": postgres_database_url}
                )
            }
        )
    )
    app.dependency_overrides[get_upstream_asgi_app] = lambda: backend_app.app

    with TestClient(app) as test_client:
        response = test_client.post(
            "/mcp/secure-demo",
            json={"jsonrpc": "2.0", "id": 1, "method": "initialize"},
        )

    assert response.status_code == 401
    assert "resource_metadata=" in response.headers["www-authenticate"]
    assert 'scope="mcp.access"' in response.headers["www-authenticate"]


def test_protected_resource_metadata_is_group_specific(client: TestClient) -> None:
    secure_response = client.get(
        "/.well-known/oauth-protected-resource/mcp/secure-demo"
    )
    public_response = client.get(
        "/.well-known/oauth-protected-resource/mcp/public-demo"
    )

    assert secure_response.status_code == 200
    assert secure_response.json() == {
        "resource": "https://proxy.example.com/mcp/secure-demo",
        "authorization_servers": ["https://login.microsoftonline.com/test-tenant/v2.0"],
        "scopes_supported": ["mcp.access"],
        "bearer_methods_supported": ["header"],
        "resource_name": "secure-demo",
    }
    assert public_response.status_code == 404


def test_authorization_scopes_can_differ_from_required_scopes() -> None:
    group = ConfigMcpGroup(
        name="secure",
        auth=ConfigEntraIdAuthProvider(tenant_id="test-tenant"),
        default_authorization_scopes=["openid", "profile"],
        servers=[
            ConfigMcpServer(
                name="secure-demo",
                endpoint="http://backend.test/mcp",
                resource="https://proxy.example.com/mcp/secure-demo",
            )
        ],
    )

    assert group.authorization_scopes_for_server(group.servers[0]) == (
        "openid",
        "profile",
    )
    assert group.required_scopes_for_server(group.servers[0]) == ()


def test_server_accepted_audiences_include_resource_and_extra_audiences() -> None:
    server = ConfigMcpServer(
        name="secure-demo",
        endpoint="http://backend.test/mcp",
        resource="http://localhost:8008/mcp/secure-demo",
        accepted_audiences=["api://proxy-api-client-id"],
    )

    assert server_accepted_audiences(server) == (
        "http://localhost:8008/mcp/secure-demo",
        "api://proxy-api-client-id",
    )


def test_audience_match_accepts_api_uri_audience() -> None:
    assert audiences_match_resource(
        ("api://proxy-api-client-id",),
        (
            "http://localhost:8008/mcp/secure-demo",
            "api://proxy-api-client-id",
        ),
    )


def test_disabled_group_forwards_initialize_without_auth(
    client: TestClient,
    backend_app: "BackendAppFixture",
) -> None:
    response = client.post(
        "/mcp/public-demo",
        headers={
            "Accept": "application/json, text/event-stream",
            "Content-Type": "application/json",
        },
        json={
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {"protocolVersion": "2025-03-26", "capabilities": {}},
        },
    )

    assert response.status_code == 200
    assert response.headers["mcp-session-id"] == "session-1"
    assert response.json()["result"]["serverInfo"]["name"] == "demo-backend"
    assert backend_app.last_request["authorization"] is None


def test_secure_group_forwards_after_authentication(
    client: TestClient,
    backend_app: "BackendAppFixture",
) -> None:
    initialize_response = client.post(
        "/mcp/secure-demo",
        headers={
            "Authorization": "Bearer token-alice",
            "Accept": "application/json, text/event-stream",
            "Content-Type": "application/json",
        },
        json={
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {"protocolVersion": "2025-03-26", "capabilities": {}},
        },
    )

    session_id = initialize_response.headers["mcp-session-id"]
    tools_response = client.post(
        "/mcp/secure-demo",
        headers={
            "Authorization": "Bearer token-alice",
            "Accept": "application/json, text/event-stream",
            "Content-Type": "application/json",
            "MCP-Session-Id": session_id,
            "X-Custom-Trace": "trace-123",
        },
        json={"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
    )

    assert tools_response.status_code == 200
    assert tools_response.json()["result"]["tools"] == []
    assert backend_app.last_request["authorization"] is None
    assert backend_app.last_request["session_id"] == session_id
    assert backend_app.last_request["custom_header"] == "trace-123"


def test_secure_group_rejects_session_reuse_by_other_principal(
    client: TestClient,
) -> None:
    initialize_response = client.post(
        "/mcp/secure-demo",
        headers={
            "Authorization": "Bearer token-alice",
            "Accept": "application/json, text/event-stream",
            "Content-Type": "application/json",
        },
        json={
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {"protocolVersion": "2025-03-26", "capabilities": {}},
        },
    )

    session_id = initialize_response.headers["mcp-session-id"]
    tools_response = client.post(
        "/mcp/secure-demo",
        headers={
            "Authorization": "Bearer token-bob",
            "Accept": "application/json, text/event-stream",
            "Content-Type": "application/json",
            "MCP-Session-Id": session_id,
        },
        json={"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
    )

    assert tools_response.status_code == 404
    assert tools_response.json()["detail"] == "Unknown session."


def test_secure_group_allows_session_reuse_by_same_subject_with_new_client_id(
    client: TestClient,
) -> None:
    initialize_response = client.post(
        "/mcp/secure-demo",
        headers={
            "Authorization": "Bearer token-alice",
            "Accept": "application/json, text/event-stream",
            "Content-Type": "application/json",
        },
        json={
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {"protocolVersion": "2025-03-26", "capabilities": {}},
        },
    )

    session_id = initialize_response.headers["mcp-session-id"]
    tools_response = client.post(
        "/mcp/secure-demo",
        headers={
            "Authorization": "Bearer token-alice-rotated-client",
            "Accept": "application/json, text/event-stream",
            "Content-Type": "application/json",
            "MCP-Session-Id": session_id,
        },
        json={"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
    )

    assert tools_response.status_code == 200
    assert tools_response.json()["result"]["tools"] == []


def test_secure_group_keeps_binding_when_upstream_delete_does_not_end_session(
    client: TestClient,
    backend_app: "BackendAppFixture",
) -> None:
    backend_app.keep_session_on_delete = True

    initialize_response = client.post(
        "/mcp/secure-demo",
        headers={
            "Authorization": "Bearer token-alice",
            "Accept": "application/json, text/event-stream",
            "Content-Type": "application/json",
        },
        json={
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {"protocolVersion": "2025-03-26", "capabilities": {}},
        },
    )

    session_id = initialize_response.headers["mcp-session-id"]
    delete_response = client.delete(
        "/mcp/secure-demo",
        headers={
            "Authorization": "Bearer token-alice",
            "Accept": "application/json, text/event-stream",
            "MCP-Session-Id": session_id,
        },
    )
    tools_response = client.post(
        "/mcp/secure-demo",
        headers={
            "Authorization": "Bearer token-alice",
            "Accept": "application/json, text/event-stream",
            "Content-Type": "application/json",
            "MCP-Session-Id": session_id,
        },
        json={"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
    )

    assert delete_response.status_code == 204
    assert tools_response.status_code == 200
    assert tools_response.json()["result"]["tools"] == []


def test_secure_group_recovers_missing_local_binding_from_upstream_session(
    client: TestClient,
    backend_app: "BackendAppFixture",
) -> None:
    backend_app.sessions.add("session-recovered")

    recovered_response = client.post(
        "/mcp/secure-demo",
        headers={
            "Authorization": "Bearer token-alice",
            "Accept": "application/json, text/event-stream",
            "Content-Type": "application/json",
            "MCP-Session-Id": "session-recovered",
        },
        json={"jsonrpc": "2.0", "id": 1, "method": "tools/list"},
    )
    rejected_response = client.post(
        "/mcp/secure-demo",
        headers={
            "Authorization": "Bearer token-bob",
            "Accept": "application/json, text/event-stream",
            "Content-Type": "application/json",
            "MCP-Session-Id": "session-recovered",
        },
        json={"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
    )

    assert recovered_response.status_code == 200
    assert recovered_response.json()["result"]["tools"] == []
    assert rejected_response.status_code == 404
    assert rejected_response.json()["detail"] == "Unknown session."


def test_secure_group_forwards_unbound_unknown_session_to_upstream(
    client: TestClient,
    backend_app: "BackendAppFixture",
) -> None:
    response = client.post(
        "/mcp/secure-demo",
        headers={
            "Authorization": "Bearer token-alice",
            "Accept": "application/json, text/event-stream",
            "Content-Type": "application/json",
            "MCP-Session-Id": "session-missing",
        },
        json={"jsonrpc": "2.0", "id": 1, "method": "tools/list"},
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Unknown session."
    assert backend_app.last_request["session_id"] == "session-missing"


def test_secure_group_rejects_initialize_rebinding_existing_session_to_other_principal(
    client: TestClient,
) -> None:
    first_initialize = client.post(
        "/mcp/secure-demo",
        headers={
            "Authorization": "Bearer token-alice",
            "Accept": "application/json, text/event-stream",
            "Content-Type": "application/json",
        },
        json={
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {"protocolVersion": "2025-03-26", "capabilities": {}},
        },
    )
    second_initialize = client.post(
        "/mcp/secure-demo",
        headers={
            "Authorization": "Bearer token-bob",
            "Accept": "application/json, text/event-stream",
            "Content-Type": "application/json",
        },
        json={
            "jsonrpc": "2.0",
            "id": 2,
            "method": "initialize",
            "params": {"protocolVersion": "2025-03-26", "capabilities": {}},
        },
    )

    assert first_initialize.status_code == 200
    assert second_initialize.status_code == 409
    assert (
        second_initialize.json()["detail"]
        == "Protected session is already bound to another principal."
    )


def test_malformed_secure_token_returns_auth_challenge(
    config: Config,
    backend_app: "BackendAppFixture",
    monkeypatch: pytest.MonkeyPatch,
    postgres_database_url: str,
) -> None:
    test_config = config.model_copy(
        update={
            "session_registry": ConfigMcpSessionRegistry.model_validate(
                {"url": postgres_database_url}
            )
        }
    )
    app = create_app(test_config)
    app.dependency_overrides[get_upstream_asgi_app] = lambda: backend_app.app

    secure_provider = get_auth_provider_registry(test_config)["secure"]
    monkeypatch.setattr(
        secure_provider,
        "discovery_metadata",
        lambda: {
            "issuer": "https://login.microsoftonline.com/test-tenant/v2.0",
            "jwks_uri": "https://login.microsoftonline.com/test-tenant/discovery/v2.0/keys",
        },
    )

    with TestClient(app) as test_client:
        response = test_client.post(
            "/mcp/secure-demo",
            headers={"Authorization": "Bearer not-a-jwt"},
            json={"jsonrpc": "2.0", "id": 1, "method": "initialize"},
        )

    assert response.status_code == 401
    assert "resource_metadata=" in response.headers["www-authenticate"]


def test_extract_scopes_includes_oauth_scope_claim() -> None:
    scopes = extract_scopes({"scope": "openid profile mcp.access"})

    assert scopes == {"openid", "profile", "mcp.access"}


def test_extract_scopes_includes_entra_scp_claim() -> None:
    scopes = extract_scopes({"scp": "Files.Read User.Read"})

    assert scopes == {"Files.Read", "User.Read"}


def test_extract_scopes_includes_entra_roles_claim() -> None:
    scopes = extract_scopes({"roles": ["Admin", "Reader"]})

    assert scopes == {"Admin", "Reader"}


def test_principal_subject_prefers_entra_object_id() -> None:
    subject = principal_subject({"oid": "user-object-id", "sub": "pairwise-subject"})

    assert subject == "user-object-id"


def test_principal_subject_falls_back_to_subject_claim() -> None:
    subject = principal_subject({"sub": "generic-oidc-subject"})

    assert subject == "generic-oidc-subject"


@pytest.mark.asyncio
async def test_sqlalchemy_session_registry_persists_bindings_between_instances(
    postgres_database_url: str,
) -> None:
    server_name = f"secure-demo-{uuid4()}"
    session_id = f"session-{uuid4()}"
    owner = SessionOwner(
        issuer="https://issuer.example.com",
        subject="alice",
    )

    database = SessionRegistryDatabase(database_url=postgres_database_url)
    await database.startup()
    try:
        async with database.session_factory() as first_session:
            first_registry = SqlAlchemySessionRegistry(first_session)
            await first_registry.bind(
                server_name=server_name,
                session_id=session_id,
                owner=owner,
                client_id="test-client",
            )

        async with database.session_factory() as second_session:
            second_registry = SqlAlchemySessionRegistry(second_session)
            assert (
                await second_registry.get(
                    server_name=server_name,
                    session_id=session_id,
                )
                == owner
            )
    finally:
        await database.shutdown()


@pytest.mark.asyncio
async def test_sqlalchemy_session_registry_updates_client_id_for_same_subject(
    postgres_database_url: str,
) -> None:
    server_name = f"secure-demo-{uuid4()}"
    session_id = f"session-{uuid4()}"
    owner = SessionOwner(
        issuer="https://issuer.example.com",
        subject="alice",
    )

    database = SessionRegistryDatabase(database_url=postgres_database_url)
    await database.startup()
    try:
        async with database.session_factory() as session:
            registry = SqlAlchemySessionRegistry(session)
            await registry.bind(
                server_name=server_name,
                session_id=session_id,
                owner=owner,
                client_id="client-a",
            )
            await registry.bind(
                server_name=server_name,
                session_id=session_id,
                owner=owner,
                client_id="client-b",
            )
            binding = await session.get(
                SessionBinding,
                {"server_name": server_name, "session_id": session_id},
            )
            assert binding is not None
            assert binding.client_id == "client-b"
    finally:
        await database.shutdown()


def test_keycloak_realm_contains_static_client() -> None:
    import json
    from pathlib import Path

    realm_path = Path(__file__).parents[1] / "resources" / "keycloak" / "realm.json"
    realm = json.loads(realm_path.read_text())

    client_ids = {c["clientId"] for c in realm["clients"]}
    assert "local-mcp-client" in client_ids, (
        "Realm must contain a static public client named 'local-mcp-client'"
    )

    local_client = next(
        c for c in realm["clients"] if c["clientId"] == "local-mcp-client"
    )
    assert local_client.get("publicClient") is True, (
        "Static local client must be a public client"
    )
    assert "mcp.access" in local_client.get("defaultClientScopes", []), (
        "Static local client must include the mcp.access scope"
    )

    dcr_policies = [
        c
        for c in realm.get("components", {}).get(
            "org.keycloak.services.clientregistration.policy.ClientRegistrationPolicy",
            [],
        )
        if c.get("subType") == "anonymous"
    ]
    assert len(dcr_policies) > 0, "Realm must have anonymous DCR policies"
    trusted_hosts = next(
        (p for p in dcr_policies if p["providerId"] == "trusted-hosts"), None
    )
    assert trusted_hosts is not None, "Realm must have a trusted-hosts DCR policy"
    allowed_hosts = trusted_hosts["config"].get("trusted-hosts", [])
    assert "localhost" in allowed_hosts, "Trusted-hosts policy must allow localhost"
    assert "127.0.0.1" in allowed_hosts, "Trusted-hosts policy must allow 127.0.0.1"

    scope_names = {s["name"] for s in realm.get("clientScopes", [])}
    assert "mcp.access" in scope_names, "Realm must define an mcp.access client scope"

    mcp_scope = next(s for s in realm["clientScopes"] if s["name"] == "mcp.access")
    audience_mappers = [
        m
        for m in mcp_scope.get("protocolMappers", [])
        if m["protocolMapper"] == "oidc-audience-mapper"
    ]
    assert len(audience_mappers) > 0, "mcp.access scope must have an audience mapper"
    assert any(
        m["config"].get("included.custom.audience")
        == "http://localhost:8008/mcp/playwright"
        for m in audience_mappers
    ), "Audience mapper must include http://localhost:8008/mcp/playwright"


def test_secure_group_delete_forwards_and_removes_binding(
    client: TestClient,
    backend_app: "BackendAppFixture",
) -> None:
    initialize_response = client.post(
        "/mcp/secure-demo",
        headers={
            "Authorization": "Bearer token-alice",
            "Accept": "application/json, text/event-stream",
            "Content-Type": "application/json",
        },
        json={
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {"protocolVersion": "2025-03-26", "capabilities": {}},
        },
    )

    session_id = initialize_response.headers["mcp-session-id"]
    delete_response = client.delete(
        "/mcp/secure-demo",
        headers={
            "Authorization": "Bearer token-alice",
            "Accept": "application/json, text/event-stream",
            "MCP-Session-Id": session_id,
        },
    )

    assert delete_response.status_code == 204
    assert backend_app.last_request["method"] == "DELETE"
    assert backend_app.last_request["session_id"] == session_id


def test_public_group_forwards_query_string(
    client: TestClient,
    backend_app: "BackendAppFixture",
) -> None:
    response = client.get(
        "/mcp/public-demo?foo=bar&baz=qux",
        headers={
            "Accept": "application/json",
        },
    )
    assert response.status_code == 200
    assert backend_app.last_query == "foo=bar&baz=qux"


def test_public_group_forwards_post_body_byte_for_byte(
    client: TestClient,
    backend_app: "BackendAppFixture",
) -> None:
    body = b'{"jsonrpc":"2.0","id":1,"method":"initialize","params":{}}'
    response = client.post(
        "/mcp/public-demo",
        content=body,
        headers={
            "Accept": "application/json, text/event-stream",
            "Content-Type": "application/json",
        },
    )
    assert response.status_code == 200
    assert backend_app.last_body == body


def test_public_group_strips_authorization_header(
    client: TestClient,
    backend_app: "BackendAppFixture",
) -> None:
    response = client.post(
        "/mcp/public-demo",
        headers={
            "Authorization": "Bearer some-token",
            "Accept": "application/json, text/event-stream",
            "Content-Type": "application/json",
        },
        json={"jsonrpc": "2.0", "id": 1, "method": "initialize"},
    )
    assert response.status_code == 200
    assert backend_app.last_request["authorization"] is None


def test_public_group_forwards_mcp_headers(
    client: TestClient,
    backend_app: "BackendAppFixture",
) -> None:
    response = client.post(
        "/mcp/public-demo",
        headers={
            "Accept": "application/json, text/event-stream",
            "Content-Type": "application/json",
            "MCP-Session-Id": "test-session",
            "MCP-Protocol-Version": "2025-03-26",
        },
        json={"jsonrpc": "2.0", "id": 1, "method": "initialize"},
    )
    assert response.status_code == 200
    assert backend_app.last_request["session_id"] == "test-session"


def test_public_group_forwards_accept_header_and_returns_json(
    client: TestClient,
    backend_app: "BackendAppFixture",
) -> None:
    response = client.post(
        "/mcp/public-demo",
        headers={
            "Accept": "application/json",
            "Content-Type": "application/json",
        },
        json={"jsonrpc": "2.0", "id": 1, "method": "initialize"},
    )
    assert response.status_code == 200
    assert "application/json" in response.headers.get("content-type", "")


def test_secure_group_forwards_custom_response_headers(
    client: TestClient,
    backend_app: "BackendAppFixture",
) -> None:
    backend_app.custom_headers = {"X-Upstream-Trace": "abc123"}
    response = client.post(
        "/mcp/secure-demo",
        headers={
            "Authorization": "Bearer token-alice",
            "Accept": "application/json, text/event-stream",
            "Content-Type": "application/json",
        },
        json={
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {"protocolVersion": "2025-03-26", "capabilities": {}},
        },
    )
    # Hop-by-hop headers are stripped; custom headers pass through.
    assert response.headers.get("x-upstream-trace") == "abc123"
