from __future__ import annotations

from collections.abc import AsyncIterator, Iterator

import pytest
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker

from proxy.auth_providers.models import AuthProviderDefinition
from proxy.auth_providers.repository import AuthProvidersRepository
from proxy.database import Base, create_engine, create_session_factory
from proxy.providers import (
    Auth0AuthProviderConfig,
    AuthKitAuthProviderConfig,
    AwsCognitoAuthProviderConfig,
    AzureAuthProviderConfig,
    DescopeAuthProviderConfig,
    DiscordAuthProviderConfig,
    GitHubAuthProviderConfig,
    GoogleAuthProviderConfig,
    HuggingFaceAuthProviderConfig,
    JwtAuthProviderConfig,
    KeycloakAuthProviderConfig,
    ManagedAuthProviderConfig,
    OciAuthProviderConfig,
    PropelAuthProviderConfig,
    ScalekitAuthProviderConfig,
    SupabaseAuthProviderConfig,
    WorkOsAuthProviderConfig,
)
from proxy.servers.models import McpServerConfig
from proxy.servers.repository import (
    ServerAuthProviderNotFound,
    ServerNameTaken,
    ServersRepository,
)


@pytest.fixture()
async def session_factory(
    postgresql_url: str,
) -> AsyncIterator[async_sessionmaker]:
    engine: AsyncEngine = create_engine(postgresql_url)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    try:
        yield create_session_factory(engine)
    finally:
        await engine.dispose()


def provider_configs() -> Iterator[ManagedAuthProviderConfig]:
    yield Auth0AuthProviderConfig(
        provider="auth0",
        config_url="https://tenant.auth0.com/.well-known/openid-configuration",
        client_id="client-id",
        client_secret="client-secret",
        audience="https://api.example",
    )
    yield AuthKitAuthProviderConfig(
        provider="authkit", authkit_domain="https://example.authkit.app"
    )
    yield AwsCognitoAuthProviderConfig(
        provider="aws-cognito",
        user_pool_id="eu-central-1_example",
        client_id="client-id",
        client_secret="client-secret",
    )
    yield AzureAuthProviderConfig(
        provider="azure",
        client_id="client-id",
        client_secret="client-secret",
        tenant_id="tenant-id",
        required_scopes=["mcp"],
    )
    yield DescopeAuthProviderConfig(
        provider="descope",
        config_url="https://api.descope.com/v1/apps/P123/.well-known/openid-configuration",
    )
    yield DiscordAuthProviderConfig(
        provider="discord", client_id="client-id", client_secret="client-secret"
    )
    yield GitHubAuthProviderConfig(
        provider="github", client_id="client-id", client_secret="client-secret"
    )
    yield GoogleAuthProviderConfig(
        provider="google", client_id="client-id", client_secret="client-secret"
    )
    yield HuggingFaceAuthProviderConfig(
        provider="huggingface", client_id="client-id", client_secret="client-secret"
    )
    yield JwtAuthProviderConfig(
        provider="jwt", public_key="test-public-key", algorithm="RS256"
    )
    yield KeycloakAuthProviderConfig(
        provider="keycloak", realm_url="https://identity.example/realms/agents"
    )
    yield OciAuthProviderConfig(
        provider="oci",
        config_url="https://identity.example/.well-known/openid-configuration",
        client_id="client-id",
        client_secret="client-secret",
    )
    yield PropelAuthProviderConfig(
        provider="propelauth",
        auth_url="https://auth.example.com",
        introspection_client_id="client-id",
        introspection_client_secret="client-secret",
    )
    yield ScalekitAuthProviderConfig(
        provider="scalekit",
        environment_url="https://example.scalekit.com",
        resource_id="resource-id",
    )
    yield SupabaseAuthProviderConfig(
        provider="supabase", project_url="https://project.supabase.co"
    )
    yield WorkOsAuthProviderConfig(
        provider="workos",
        client_id="client-id",
        client_secret="client-secret",
        authkit_domain="https://example.authkit.app",
    )


def server_config(index: int, provider_name: str | None = None) -> McpServerConfig:
    return McpServerConfig(
        name=f"server-{index}",
        description=f"Server number {index}",
        upstream_url="http://127.0.0.1:8000/mcp",
        auth_provider=provider_name,
        verify_upstream_tls=False,
    )


@pytest.mark.parametrize("index", range(16), ids=lambda i: str(i))
async def test_server_reference_round_trips(
    session_factory: async_sessionmaker,
    index: int,
) -> None:
    auth = list(provider_configs())[index]
    provider_name = f"provider-{index}"
    await AuthProvidersRepository(session_factory).create(
        AuthProviderDefinition(name=provider_name, auth=auth)
    )
    expected = server_config(index, provider_name)
    repository = ServersRepository(session_factory)

    await repository.create(expected)

    assert await repository.get(expected.name) == expected
    assert await repository.list() == [expected]


async def test_corrupt_provider_payload_fails_loudly(
    session_factory: async_sessionmaker,
) -> None:
    from sqlalchemy import text

    async with session_factory() as session:
        await session.execute(
            text(
                """
                INSERT INTO auth_providers
                    (name, auth, created_at, updated_at)
                VALUES
                    ('broken', :auth, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                """
            ),
            {"auth": '{"provider": "keycloak", "realm_url": "not-a-url"}'},
        )
        await session.commit()

    with pytest.raises(ValidationError, match="realm_url"):
        await AuthProvidersRepository(session_factory).get("broken")


async def test_create_rejects_duplicate_names(
    session_factory: async_sessionmaker,
) -> None:
    repository = ServersRepository(session_factory)
    config = server_config(0)

    await repository.create(config)
    with pytest.raises(ServerNameTaken, match="already exists"):
        await repository.create(config)


async def test_create_rejects_unknown_provider(
    session_factory: async_sessionmaker,
) -> None:
    config = server_config(0).model_copy(update={"auth_provider": "missing"})

    with pytest.raises(ServerAuthProviderNotFound, match="missing"):
        await ServersRepository(session_factory).create(config)


async def test_get_returns_none_for_unknown_names(
    session_factory: async_sessionmaker,
) -> None:
    assert await ServersRepository(session_factory).get("missing") is None


async def test_update_and_delete_round_trip(
    session_factory: async_sessionmaker,
) -> None:
    repository = ServersRepository(session_factory)
    config = server_config(0)
    await repository.create(config)

    updated = config.model_copy(update={"description": "Renamed purpose"})
    await repository.update(config.name, updated)
    assert await repository.get(config.name) == updated

    await repository.delete(config.name)
    assert await repository.get(config.name) is None


async def test_forward_client_credentials_round_trips_without_provider(
    session_factory: async_sessionmaker,
) -> None:
    config = McpServerConfig(
        name="relay",
        upstream_url="http://127.0.0.1:8000/mcp",
        auth_provider=None,
        forward_client_credentials=True,
    )

    await ServersRepository(session_factory).create(config)
    assert await ServersRepository(session_factory).get("relay") == config


async def test_forward_client_credentials_rejected_with_provider() -> None:
    with pytest.raises(ValidationError, match="forward_client_credentials"):
        McpServerConfig(
            name="server-0",
            upstream_url="http://127.0.0.1:8000/mcp",
            auth_provider="keycloak",
            forward_client_credentials=True,
        )
