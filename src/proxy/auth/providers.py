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
    """Protocol for authentication providers.

    Implementations must provide OAuth-protected resource metadata and
    authenticate incoming requests by validating bearer tokens.
    """

    def describe_resource(
        self,
        *,
        group: McpGroupConfig,
        server: McpServerConfig,
    ) -> ProtectedResourceAuthMetadata | None:
        """Describe the OAuth protected resource for a server.

        Args:
            group: The MCP group configuration.
            server: The MCP server configuration.

        Returns:
            Protected resource metadata, or None if auth is disabled.
        """
        ...

    def authenticate_request(
        self,
        *,
        authorization: str | None,
        group: McpGroupConfig,
        server: McpServerConfig,
    ) -> AuthenticatedPrincipal:
        """Authenticate an incoming request.

        Validates the bearer token and returns an authenticated principal.

        Args:
            authorization: The raw Authorization header value.
            group: The MCP group configuration.
            server: The MCP server configuration.

        Returns:
            The authenticated principal.

        Raises:
            MissingTokenError: If no token is provided.
            InvalidTokenError: If the token is invalid.
            InsufficientScopeError: If the token lacks required scopes.
        """
        ...


class DisabledAuthProvider:
    """Auth provider used when authentication is disabled.

    Returns anonymous principal and no resource metadata.
    """

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
    """Abstract base for OAuth Bearer token authentication providers.

    Implements the common describe_resource and authenticate_request flow,
    delegating token-specific validation to subclasses.
    """

    def describe_resource(
        self,
        *,
        group: McpGroupConfig,
        server: McpServerConfig,
    ) -> ProtectedResourceAuthMetadata:
        """Describe the OAuth protected resource for a server.

        Args:
            group: The MCP group configuration.
            server: The MCP server configuration.

        Returns:
            Protected resource metadata with server URI, auth servers, and
            supported scopes.
        """
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
        """Authenticate an incoming request using a Bearer token.

        Parses the Authorization header, delegates token validation to
        ``authenticate_token``, and checks required scopes.

        Args:
            authorization: The raw Authorization header value.
            group: The MCP group configuration.
            server: The MCP server configuration.

        Returns:
            The authenticated principal.

        Raises:
            MissingTokenError: If no Authorization header is present.
            InvalidTokenError: If the scheme is not Bearer or token
                validation fails.
            InsufficientScopeError: If the token lacks required scopes.
        """
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
        """Return the URLs of the authorization servers for this provider.

        Returns:
            A tuple of authorization server URLs.
        """
        raise NotImplementedError

    @abstractmethod
    def authenticate_token(
        self, token: str, *, server: McpServerConfig
    ) -> AuthenticatedPrincipal:
        """Validate an access token and return the authenticated principal.

        Args:
            token: The raw bearer token string.
            server: The MCP server configuration for audience/scope checks.

        Returns:
            The authenticated principal extracted from the token.

        Raises:
            TokenValidationError: If the token is invalid.
        """
        raise NotImplementedError


def build_auth_provider(config: AuthProviderConfig) -> AuthProvider:
    """Build an auth provider from its configuration.

    Args:
        config: The auth provider configuration, discriminated by provider
            type.

    Returns:
        An AuthProvider instance matching the configuration.

    Raises:
        ValueError: If the provider type is not recognised.
    """
    if isinstance(config, DisabledAuthProviderConfig):
        return DisabledAuthProvider()
    if isinstance(config, OidcAuthProviderConfig | EntraIdAuthProviderConfig):
        from proxy.auth.oidc import OidcAuthProvider

        return OidcAuthProvider(config)
    raise ValueError(f"Unsupported auth provider configuration: {type(config)!r}")


def build_auth_provider_registry(
    groups: Iterable[McpGroupConfig],
) -> dict[str, AuthProvider]:
    """Build a registry mapping group names to auth providers.

    Args:
        groups: Iterable of MCP group configurations.

    Returns:
        Dictionary keyed by group name with the corresponding auth provider.
    """
    return {group.name: build_auth_provider(group.auth) for group in groups}
