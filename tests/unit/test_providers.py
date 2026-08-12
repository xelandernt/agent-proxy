from __future__ import annotations

import pytest
from fastmcp.server.auth import AuthProvider
from fastmcp.server.auth.oidc_proxy import OIDCConfiguration
from fastmcp.server.auth.providers.auth0 import Auth0Provider
from fastmcp.server.auth.providers.aws import AWSCognitoProvider
from fastmcp.server.auth.providers.azure import AzureProvider
from fastmcp.server.auth.providers.descope import DescopeProvider
from fastmcp.server.auth.providers.discord import DiscordProvider
from fastmcp.server.auth.providers.github import GitHubProvider
from fastmcp.server.auth.providers.google import GoogleProvider
from fastmcp.server.auth.providers.huggingface import HuggingFaceProvider
from fastmcp.server.auth.providers.jwt import JWTVerifier
from fastmcp.server.auth.providers.keycloak import KeycloakAuthProvider
from fastmcp.server.auth.providers.oci import OCIProvider
from fastmcp.server.auth.providers.propelauth import PropelAuthProvider
from fastmcp.server.auth.providers.scalekit import ScalekitProvider
from fastmcp.server.auth.providers.supabase import SupabaseProvider
from fastmcp.server.auth.providers.workos import AuthKitProvider, WorkOSProvider
from pydantic import TypeAdapter, ValidationError

from proxy.providers import (
    AdminAuthProviderConfig,
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
    OciAuthProviderConfig,
    PropelAuthProviderConfig,
    ScalekitAuthProviderConfig,
    ServerAuthProviderConfig,
    StaticCredentialsAuthProvider,
    StaticCredentialsAuthProviderConfig,
    SupabaseAuthProviderConfig,
    WorkOsAuthProviderConfig,
    load_auth_provider,
)


@pytest.fixture(autouse=True)
def stub_oidc_discovery(monkeypatch: pytest.MonkeyPatch) -> None:
    def oidc_configuration(
        cls: type[OIDCConfiguration],
        config_url: object,
        *,
        strict: bool | None,
        timeout_seconds: int | None,
    ) -> OIDCConfiguration:
        return cls(
            strict=False,
            issuer="https://identity.example",
            authorization_endpoint="https://identity.example/authorize",
            token_endpoint="https://identity.example/token",
            jwks_uri="https://identity.example/jwks",
        )

    monkeypatch.setattr(
        OIDCConfiguration,
        "get_oidc_configuration",
        classmethod(oidc_configuration),
    )


@pytest.mark.parametrize(
    ("config", "provider_type"),
    [
        (
            Auth0AuthProviderConfig(
                provider="auth0",
                config_url="https://tenant.auth0.com/.well-known/openid-configuration",
                client_id="client-id",
                client_secret="client-secret",
                audience="https://api.example",
            ),
            Auth0Provider,
        ),
        (
            AuthKitAuthProviderConfig(
                provider="authkit",
                authkit_domain="https://example.authkit.app",
            ),
            AuthKitProvider,
        ),
        (
            AwsCognitoAuthProviderConfig(
                provider="aws-cognito",
                user_pool_id="eu-central-1_example",
                client_id="client-id",
                client_secret="client-secret",
            ),
            AWSCognitoProvider,
        ),
        (
            AzureAuthProviderConfig(
                provider="azure",
                client_id="client-id",
                client_secret="client-secret",
                tenant_id="tenant-id",
                required_scopes=["mcp"],
            ),
            AzureProvider,
        ),
        (
            DescopeAuthProviderConfig(
                provider="descope",
                config_url=(
                    "https://api.descope.com/v1/apps/P123/"
                    ".well-known/openid-configuration"
                ),
            ),
            DescopeProvider,
        ),
        (
            DiscordAuthProviderConfig(
                provider="discord",
                client_id="client-id",
                client_secret="client-secret",
            ),
            DiscordProvider,
        ),
        (
            GitHubAuthProviderConfig(
                provider="github",
                client_id="client-id",
                client_secret="client-secret",
            ),
            GitHubProvider,
        ),
        (
            GoogleAuthProviderConfig(
                provider="google",
                client_id="client-id",
                client_secret="client-secret",
            ),
            GoogleProvider,
        ),
        (
            HuggingFaceAuthProviderConfig(
                provider="huggingface",
                client_id="client-id",
                client_secret="client-secret",
            ),
            HuggingFaceProvider,
        ),
        (
            JwtAuthProviderConfig(
                provider="jwt",
                public_key="test-public-key",
                algorithm="RS256",
            ),
            JWTVerifier,
        ),
        (
            KeycloakAuthProviderConfig(
                provider="keycloak",
                realm_url="https://identity.example/realms/agents",
            ),
            KeycloakAuthProvider,
        ),
        (
            OciAuthProviderConfig(
                provider="oci",
                config_url="https://identity.example/.well-known/openid-configuration",
                client_id="client-id",
                client_secret="client-secret",
            ),
            OCIProvider,
        ),
        (
            PropelAuthProviderConfig(
                provider="propelauth",
                auth_url="https://auth.example.com",
                introspection_client_id="client-id",
                introspection_client_secret="client-secret",
            ),
            PropelAuthProvider,
        ),
        (
            ScalekitAuthProviderConfig(
                provider="scalekit",
                environment_url="https://example.scalekit.com",
                resource_id="resource-id",
            ),
            ScalekitProvider,
        ),
        (
            SupabaseAuthProviderConfig(
                provider="supabase",
                project_url="https://project.supabase.co",
            ),
            SupabaseProvider,
        ),
        (
            StaticCredentialsAuthProviderConfig(
                provider="static",
                username="admin",
                password="hunter2",
                jwt_secret="a-very-long-random-secret-at-least-32-bytes",
            ),
            StaticCredentialsAuthProvider,
        ),
        (
            WorkOsAuthProviderConfig(
                provider="workos",
                client_id="client-id",
                client_secret="client-secret",
                authkit_domain="https://example.authkit.app",
            ),
            WorkOSProvider,
        ),
    ],
)
def test_supported_provider_builds(
    config: ServerAuthProviderConfig | AdminAuthProviderConfig,
    provider_type: type[AuthProvider],
) -> None:
    provider = load_auth_provider(
        config,
        base_url="https://gateway.example/calendar",
    )

    assert isinstance(provider, provider_type)


def test_server_auth_schema_exposes_only_server_providers() -> None:
    schema = TypeAdapter(ServerAuthProviderConfig).json_schema()

    assert set(schema["discriminator"]["mapping"]) == {
        "auth0",
        "authkit",
        "aws-cognito",
        "azure",
        "descope",
        "discord",
        "github",
        "google",
        "huggingface",
        "jwt",
        "keycloak",
        "oci",
        "propelauth",
        "scalekit",
        "supabase",
        "workos",
    }


def test_admin_auth_schema_exposes_only_admin_flows() -> None:
    schema = TypeAdapter(AdminAuthProviderConfig).json_schema()

    assert set(schema["discriminator"]["mapping"]) == {
        "jwt",
        "keycloak",
        "static",
    }


def test_provider_rejects_unknown_fields() -> None:
    with pytest.raises(ValidationError, match="extra_forbidden"):
        KeycloakAuthProviderConfig.model_validate(
            {
                "provider": "keycloak",
                "realm_url": "https://identity.example/realms/agents",
                "settings": {},
            }
        )
