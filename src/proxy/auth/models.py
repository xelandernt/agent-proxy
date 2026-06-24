from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any
from urllib.parse import SplitResult, urlsplit, urlunsplit

from proxy.settings import McpServerConfig


@dataclass(frozen=True)
class AuthenticatedPrincipal:
    """Represents an authenticated principal after token validation.

    Attributes:
        subject: The principal's subject identifier.
        issuer: The OIDC issuer that issued the token.
        audiences: The audience(s) the token was intended for.
        granted_scopes: The set of scopes granted by the token.
        client_id: Optional OAuth client ID (from ``azp`` or ``appid``).
        token_id: Optional token identifier (``jti`` claim).
    """

    subject: str
    issuer: str
    audiences: tuple[str, ...]
    granted_scopes: frozenset[str]
    client_id: str | None
    token_id: str | None


@dataclass(frozen=True)
class ProtectedResourceAuthMetadata:
    """Metadata for an OAuth protected resource.

    Attributes:
        resource: The canonical resource URL of the MCP server.
        authorization_servers: URLs of the authorisation servers.
        scopes_supported: Scopes that the authorisation server supports.
    """

    resource: str
    authorization_servers: tuple[str, ...]
    scopes_supported: tuple[str, ...]


class TokenValidationError(Exception):
    """Raised when an access token cannot be trusted."""


class AuthError(Exception):
    """Base for auth-related errors that translate to HTTP 401/403."""

    def __init__(
        self, message: str, challenge_headers: dict[str, str] | None = None
    ) -> None:
        self.challenge_headers = challenge_headers
        super().__init__(message)


class MissingTokenError(AuthError):
    pass


class InvalidTokenError(AuthError):
    pass


class InsufficientScopeError(AuthError):
    pass


def optional_string(value: Any) -> str | None:
    """Convert a value to an optional stripped string.

    Returns None for None, empty, or whitespace-only values.

    Args:
        value: The value to convert.

    Returns:
        The stripped string or None.
    """
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def extract_scopes(claims: dict[str, Any]) -> set[str]:
    """Extract granted scopes from JWT claims.

    Checks the ``scp``, ``scope``, and ``roles`` claims (commonly used by
    OIDC providers and Microsoft Entra ID).

    Args:
        claims: The decoded JWT claims dictionary.

    Returns:
        A set of scope strings.
    """
    scopes: set[str] = set()

    scope_claim = claims.get("scp")
    if isinstance(scope_claim, str):
        scopes.update(part for part in scope_claim.split(" ") if part)

    oauth_scope_claim = claims.get("scope")
    if isinstance(oauth_scope_claim, str):
        scopes.update(part for part in oauth_scope_claim.split(" ") if part)

    roles_claim = claims.get("roles")
    if isinstance(roles_claim, list):
        scopes.update(str(role) for role in roles_claim if role)

    return scopes


def extract_audiences(claims: dict[str, Any]) -> tuple[str, ...]:
    """Extract audiences from JWT claims.

    Handles both single string and list-of-strings ``aud`` claims.

    Args:
        claims: The decoded JWT claims dictionary.

    Returns:
        A tuple of audience strings.
    """
    audience_claim = claims.get("aud")
    if isinstance(audience_claim, list):
        return tuple(str(audience) for audience in audience_claim)
    return (str(audience_claim),)


def principal_subject(claims: dict[str, Any]) -> str:
    """Extract the principal subject from JWT claims.

    Prefers the ``oid`` claim (Microsoft Entra ID) over ``sub``.

    Args:
        claims: The decoded JWT claims dictionary.

    Returns:
        The subject identifier string.
    """
    return claims.get("oid", None) or str(claims["sub"])


def normalize_resource_uri(value: str) -> str | None:
    """Normalize a URI for comparison purposes.

    Lowercases the scheme and hostname, removes default ports, strips
    trailing slashes from the path, and removes the fragment.

    Args:
        value: The URI to normalize.

    Returns:
        The normalized URI string, or None if the input is empty.
    """
    parsed = urlsplit(value)
    if not parsed.scheme:
        return optional_string(value)
    hostname = parsed.hostname
    if hostname is None:
        return value

    port = parsed.port
    default_port = {"http": 80, "https": 443}.get(parsed.scheme.lower())
    normalized_netloc = hostname.lower()
    if port is not None and port != default_port:
        normalized_netloc = f"{normalized_netloc}:{port}"

    normalized_path = parsed.path or ""
    if normalized_path == "/":
        normalized_path = ""
    elif normalized_path.endswith("/"):
        normalized_path = normalized_path.rstrip("/")

    normalized = SplitResult(
        scheme=parsed.scheme.lower(),
        netloc=normalized_netloc,
        path=normalized_path,
        query=parsed.query,
        fragment="",
    )
    return urlunsplit(normalized)


def audiences_match_resource(
    audiences: tuple[str, ...], configured_resources: Iterable[str]
) -> bool:
    """Check if any audience matches any of the configured resource URIs.

    Performs normalised comparison on both sides.

    Args:
        audiences: Audience values from the token.
        configured_resources: Resource URIs the server accepts.

    Returns:
        True if at least one audience matches a configured resource.
    """
    expected_resources = {
        normalized
        for resource in configured_resources
        if (normalized := normalize_resource_uri(resource)) is not None
    }
    if not expected_resources:
        return False
    return any(
        normalize_resource_uri(audience) in expected_resources for audience in audiences
    )


def server_resource(server: McpServerConfig) -> str:
    """Get the canonical resource URI for a server.

    Args:
        server: The MCP server configuration.

    Returns:
        The configured resource URI.

    Raises:
        TokenValidationError: If the server has no resource configured.
    """
    if server.resource is None:
        raise TokenValidationError(
            f"MCP server '{server.name}' is missing a configured canonical resource URL."
        )
    return str(server.resource)


def server_accepted_audiences(server: McpServerConfig) -> tuple[str, ...]:
    """Return the full list of audiences accepted by a server.

    Includes the server's canonical resource URI followed by any additional
    accepted audiences from the configuration.

    Args:
        server: The MCP server configuration.

    Returns:
        A tuple of accepted audience strings.
    """
    return (server_resource(server), *server.accepted_audiences)


def find_jwk(jwks: dict[str, Any], key_id: str) -> dict[str, Any] | None:
    """Find a JWK by key ID in a JWKS key set.

    Args:
        jwks: The JWKS dictionary containing a ``keys`` array.
        key_id: The key ID (``kid``) to look for.

    Returns:
        The matching JWK dictionary, or None if not found.
    """
    for key in jwks["keys"]:
        if key.get("kid") == key_id:
            return key
    return None
