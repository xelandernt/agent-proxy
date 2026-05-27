from collections.abc import Iterator

from fastapi import FastAPI, Header, HTTPException, Request, Response, status
from fastapi.testclient import TestClient
import pytest

from proxy.app.auth import (
    AuthenticatedPrincipal,
    ProtectedResourceAuthMetadata,
)
from proxy.app.main import create_app
from proxy.settings import (
    Config,
    ConfigDisabledAuthProvider,
    ConfigEntraIdAuthProvider,
    ConfigMcp,
    ConfigMcpGroup,
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
        if authorization == "Bearer token-alice":
            subject = "alice"
        elif authorization == "Bearer token-bob":
            subject = "bob"
        else:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token.",
            )

        return AuthenticatedPrincipal(
            subject=subject,
            issuer="https://login.microsoftonline.com/test-tenant/v2.0",
            audiences=(str(server.resource),),
            granted_scopes=frozenset(group.required_scopes_for_server(server)),
            client_id="test-client",
            token_id=None,
        )


@pytest.fixture()
def backend_app() -> FastAPI:
    app = FastAPI()
    sessions: set[str] = set()
    last_request: dict[str, str | None] = {"authorization": None, "session_id": None}
    app.state.last_request = last_request

    @app.post("/mcp", response_model=None)
    async def handle_mcp(
        request: Request,
        response: Response,
        authorization: str | None = Header(default=None, alias="Authorization"),
        mcp_session_id: str | None = Header(default=None, alias="MCP-Session-Id"),
    ) -> Response | dict:
        last_request["authorization"] = authorization
        last_request["session_id"] = mcp_session_id
        payload = await request.json()

        if payload["method"] == "initialize":
            session_id = "session-1"
            sessions.add(session_id)
            response.headers["MCP-Session-Id"] = session_id
            return {
                "jsonrpc": "2.0",
                "id": payload["id"],
                "result": {
                    "protocolVersion": "2025-03-26",
                    "capabilities": {"tools": {}},
                    "serverInfo": {"name": "demo-backend", "version": "0.1.0"},
                },
            }

        if mcp_session_id not in sessions:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Unknown session."
            )

        return {
            "jsonrpc": "2.0",
            "id": payload["id"],
            "result": {"tools": []},
        }

    return app


@pytest.fixture()
def config() -> Config:
    return Config(
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
            ]
        )
    )


@pytest.fixture()
def client(config: Config, backend_app: FastAPI) -> Iterator[TestClient]:
    app = create_app(config)
    app.state.auth_providers["secure"] = StaticAuthProvider()
    app.state.upstream_asgi_app = backend_app
    with TestClient(app) as test_client:
        yield test_client


def test_missing_token_returns_mcp_auth_challenge(
    config: Config, backend_app: FastAPI
) -> None:
    app = create_app(config)
    app.state.upstream_asgi_app = backend_app

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


def test_disabled_group_forwards_initialize_without_auth(
    client: TestClient,
    backend_app: FastAPI,
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
    assert backend_app.state.last_request["authorization"] is None


def test_secure_group_forwards_after_authentication(
    client: TestClient,
    backend_app: FastAPI,
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
        },
        json={"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
    )

    assert tools_response.status_code == 200
    assert tools_response.json()["result"]["tools"] == []
    assert backend_app.state.last_request["authorization"] is None
    assert backend_app.state.last_request["session_id"] == session_id


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


def test_malformed_secure_token_returns_auth_challenge(
    config: Config,
    backend_app: FastAPI,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app = create_app(config)
    app.state.upstream_asgi_app = backend_app

    secure_provider = app.state.auth_providers["secure"]
    monkeypatch.setattr(
        secure_provider,
        "_get_metadata",
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
