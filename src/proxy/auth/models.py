from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any
from urllib.parse import SplitResult, urlsplit, urlunsplit

from proxy.settings import McpServerConfig


@dataclass(frozen=True)
class AuthenticatedPrincipal:
    subject: str
    issuer: str
    audiences: tuple[str, ...]
    granted_scopes: frozenset[str]
    client_id: str | None
    token_id: str | None


@dataclass(frozen=True)
class ProtectedResourceAuthMetadata:
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
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def extract_scopes(claims: dict[str, Any]) -> set[str]:
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
    audience_claim = claims.get("aud")
    if isinstance(audience_claim, list):
        return tuple(str(audience) for audience in audience_claim)
    return (str(audience_claim),)


def principal_subject(claims: dict[str, Any]) -> str:
    return claims.get("oid", None) or str(claims["sub"])


def normalize_resource_uri(value: str) -> str | None:
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
    if server.resource is None:
        raise TokenValidationError(
            f"MCP server '{server.name}' is missing a configured canonical resource URL."
        )
    return str(server.resource)


def server_accepted_audiences(server: McpServerConfig) -> tuple[str, ...]:
    return (server_resource(server), *server.accepted_audiences)


def find_jwk(jwks: dict[str, Any], key_id: str) -> dict[str, Any] | None:
    for key in jwks["keys"]:
        if key.get("kid") == key_id:
            return key
    return None
