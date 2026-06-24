from abc import ABC, abstractmethod
from collections.abc import Iterable
from typing import Protocol

from proxy.auth.models import (
    AuthenticatedPrincipal,
    InsufficientScopeError,
    InvalidTokenError,
    MissingTokenError,
    ProtectedResourceAuthMetadata,
    TokenValidationError,
    server_resource,
)
from proxy.settings import (
    AuthProviderConfig,
    DisabledAuthProviderConfig,
    EntraIdAuthProviderConfig,
    McpGroupConfig,
    McpServerConfig,
    OidcAuthProviderConfig,
)


class AuthProvider(Protocol):
    def describe_resource(
        self,
        *,
        group: McpGroupConfig,
        server: McpServerConfig,
    ) -> ProtectedResourceAuthMetadata | None: ...

    def authenticate_request(
        self,
        *,
        authorization: str | None,
        group: McpGroupConfig,
        server: McpServerConfig,
    ) -> AuthenticatedPrincipal: ...


class DisabledAuthProvider:
    def describe_resource(
        self,
        *,
        group: McpGroupConfig,
        server: McpServerConfig,
    ) -> ProtectedResourceAuthMetadata | None:
        return None

    def authenticate_request(
        self,
        *,
        authorization: str | None,
        group: McpGroupConfig,
        server: McpServerConfig,
    ) -> AuthenticatedPrincipal:
        return AuthenticatedPrincipal(
            subject="anonymous",
            issuer="agent-proxy",
            audiences=(),
            granted_scopes=frozenset(),
            client_id=None,
            token_id=None,
        )


class OAuthBearerAuthProvider(ABC):
    def describe_resource(
        self,
        *,
        group: McpGroupConfig,
        server: McpServerConfig,
    ) -> ProtectedResourceAuthMetadata:
        return ProtectedResourceAuthMetadata(
            resource=server_resource(server),
            authorization_servers=self.authorization_servers(),
            scopes_supported=group.authorization_scopes_for_server(server),
        )

    def authenticate_request(
        self,
        *,
        authorization: str | None,
        group: McpGroupConfig,
        server: McpServerConfig,
    ) -> AuthenticatedPrincipal:
        if authorization is None:
            raise MissingTokenError("Missing bearer token.")

        scheme, _, token = authorization.partition(" ")
        if scheme.lower() != "bearer" or not token:
            raise InvalidTokenError("Invalid authorization header.")

        try:
            principal = self.authenticate_token(token.strip(), server=server)
        except TokenValidationError as exc:
            raise InvalidTokenError(str(exc)) from exc

        required_scopes = group.required_scopes_for_server(server)
        if required_scopes and not set(required_scopes).issubset(
            principal.granted_scopes
        ):
            raise InsufficientScopeError("Access token is missing required scopes.")

        return principal

    @abstractmethod
    def authorization_servers(self) -> tuple[str, ...]:
        raise NotImplementedError

    @abstractmethod
    def authenticate_token(
        self, token: str, *, server: McpServerConfig
    ) -> AuthenticatedPrincipal:
        raise NotImplementedError


def build_auth_provider(config: AuthProviderConfig) -> AuthProvider:
    if isinstance(config, DisabledAuthProviderConfig):
        return DisabledAuthProvider()
    if isinstance(config, OidcAuthProviderConfig | EntraIdAuthProviderConfig):
        from proxy.auth.oidc import OidcAuthProvider

        return OidcAuthProvider(config)
    raise ValueError(f"Unsupported auth provider configuration: {type(config)!r}")


def build_auth_provider_registry(
    groups: Iterable[McpGroupConfig],
) -> dict[str, AuthProvider]:
    return {group.name: build_auth_provider(group.auth) for group in groups}
