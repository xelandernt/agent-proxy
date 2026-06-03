import json
import threading
import time
from abc import ABC, abstractmethod
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any, Protocol
from urllib.parse import SplitResult, urlsplit, urlunsplit

import jwt
import niquests
from fastapi import HTTPException, Request, status
from jwt.algorithms import RSAAlgorithm
from loguru import logger

from proxy.settings import (
    Config,
    ConfigAuthProvider,
    ConfigDisabledAuthProvider,
    ConfigEntraIdAuthProvider,
    ConfigMcpGroup,
    ConfigMcpServer,
    ConfigOidcAuthProvider,
)

OidcAuthProviderConfig = ConfigOidcAuthProvider | ConfigEntraIdAuthProvider

AUTHORIZATION_HEADER = "Authorization"
_AUTH_PROVIDER_CACHE: tuple[int, dict[str, "AuthProvider"]] | None = None


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


class AuthProvider(Protocol):
    def describe_resource(
        self,
        *,
        group: ConfigMcpGroup,
        server: ConfigMcpServer,
    ) -> ProtectedResourceAuthMetadata | None: ...

    def authenticate_request(
        self,
        *,
        request: Request,
        authorization: str | None,
        group: ConfigMcpGroup,
        server: ConfigMcpServer,
        resource_metadata_url: str,
    ) -> AuthenticatedPrincipal: ...


class DisabledAuthProvider(AuthProvider):
    def describe_resource(
        self,
        *,
        group: ConfigMcpGroup,
        server: ConfigMcpServer,
    ) -> ProtectedResourceAuthMetadata | None:
        return None

    def authenticate_request(
        self,
        *,
        request: Request,
        authorization: str | None,
        group: ConfigMcpGroup,
        server: ConfigMcpServer,
        resource_metadata_url: str,
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
        group: ConfigMcpGroup,
        server: ConfigMcpServer,
    ) -> ProtectedResourceAuthMetadata:
        return ProtectedResourceAuthMetadata(
            resource=server_resource(server),
            authorization_servers=self.authorization_servers(),
            scopes_supported=group.authorization_scopes_for_server(server),
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
        required_scopes = group.required_scopes_for_server(server)
        authorization_scopes = group.authorization_scopes_for_server(server)
        challenge_headers = {
            "WWW-Authenticate": build_auth_challenge(
                resource_metadata_url=resource_metadata_url,
                scopes=authorization_scopes,
            )
        }

        if authorization is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Missing bearer token.",
                headers=challenge_headers,
            )

        scheme, _, token = authorization.partition(" ")
        if scheme.lower() != "bearer" or not token:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid authorization header.",
                headers=challenge_headers,
            )

        try:
            principal = self.authenticate_token(token.strip(), server=server)
        except TokenValidationError as exc:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=str(exc),
                headers=challenge_headers,
            ) from exc

        if required_scopes and not set(required_scopes).issubset(
            principal.granted_scopes
        ):
            forbidden_challenge = build_auth_challenge(
                resource_metadata_url=resource_metadata_url,
                scopes=required_scopes,
                error="insufficient_scope",
                error_description="The token does not grant access to this MCP server.",
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access token is missing required scopes.",
                headers={"WWW-Authenticate": forbidden_challenge},
            )

        return principal

    @abstractmethod
    def authorization_servers(self) -> tuple[str, ...]:
        raise NotImplementedError

    @abstractmethod
    def authenticate_token(
        self, token: str, *, server: ConfigMcpServer
    ) -> AuthenticatedPrincipal:
        raise NotImplementedError


class OidcAuthProvider(OAuthBearerAuthProvider):
    def __init__(self, config: OidcAuthProviderConfig) -> None:
        self._config = config
        self._lock = threading.Lock()
        self._metadata_cache: dict[str, Any] | None = None
        self._metadata_cache_expires_at = 0.0
        self._jwks_cache: dict[str, Any] | None = None
        self._jwks_cache_expires_at = 0.0

    def authorization_servers(self) -> tuple[str, ...]:
        return (self._config.issuer_url,)

    def authenticate_token(
        self, token: str, *, server: ConfigMcpServer
    ) -> AuthenticatedPrincipal:
        metadata = self.discovery_metadata()
        signing_key = self.signing_key(token, str(metadata["jwks_uri"]))

        try:
            claims = jwt.decode(
                token,
                key=signing_key,
                algorithms=self._config.allowed_algorithms,
                issuer=str(metadata["issuer"]),
                leeway=self._config.clock_skew_seconds,
                options={
                    "require": ["exp", "iat", "iss", "aud", "sub"],
                    "verify_signature": True,
                    "verify_aud": False,
                },
            )
        except jwt.PyJWTError as exc:
            raise TokenValidationError("Access token validation failed.") from exc

        granted_scopes = frozenset(extract_scopes(claims))
        audiences = extract_audiences(claims)
        expected_audiences = server_accepted_audiences(server)
        if not audiences_match_resource(audiences, expected_audiences):
            raise TokenValidationError(
                "Access token audience does not match this MCP server."
            )

        subject = principal_subject(claims)
        logger.debug(
            "Authenticated MCP principal server={server_name} issuer={issuer} "
            "subject={subject} client_id={client_id} audiences={audiences}",
            server_name=server.name,
            issuer=str(claims["iss"]),
            subject=subject,
            client_id=optional_string(claims.get("azp"))
            or optional_string(claims.get("appid")),
            audiences=audiences,
        )

        return AuthenticatedPrincipal(
            subject=subject,
            issuer=str(claims["iss"]),
            audiences=audiences,
            granted_scopes=granted_scopes,
            client_id=optional_string(claims.get("azp"))
            or optional_string(claims.get("appid")),
            token_id=optional_string(claims.get("jti")),
        )

    def discovery_metadata(self) -> dict[str, Any]:
        with self._lock:
            if (
                self._metadata_cache is not None
                and time.time() < self._metadata_cache_expires_at
            ):
                return self._metadata_cache

        metadata = self.fetch_json(
            f"{self._config.issuer_url}/.well-known/openid-configuration"
        )

        issuer = optional_string(metadata.get("issuer"))
        jwks_uri = optional_string(metadata.get("jwks_uri"))
        if issuer is None or jwks_uri is None:
            raise TokenValidationError(
                "OIDC discovery metadata is missing required fields."
            )

        with self._lock:
            self._metadata_cache = metadata
            self._metadata_cache_expires_at = (
                time.time() + self._config.discovery_ttl_seconds
            )
            return metadata

    def signing_key(self, token: str, jwks_uri: str) -> Any:
        try:
            unverified_header = jwt.get_unverified_header(token)
        except jwt.PyJWTError as exc:
            raise TokenValidationError("Access token header is malformed.") from exc

        algorithm = optional_string(unverified_header.get("alg"))
        key_id = optional_string(unverified_header.get("kid"))

        if algorithm is None or algorithm not in self._config.allowed_algorithms:
            raise TokenValidationError(
                "Access token uses an unsupported signing algorithm."
            )
        if key_id is None:
            raise TokenValidationError("Access token is missing a key identifier.")

        jwks = self.jwks(jwks_uri)
        key = find_jwk(jwks, key_id)
        if key is None:
            jwks = self.jwks(jwks_uri, force_refresh=True)
            key = find_jwk(jwks, key_id)
        if key is None:
            raise TokenValidationError(
                "Signing key was not found in the configured JWKS."
            )

        try:
            return RSAAlgorithm.from_jwk(json.dumps(key))
        except (TypeError, ValueError, jwt.PyJWTError) as exc:
            raise TokenValidationError("Signing key is invalid.") from exc

    def jwks(self, jwks_uri: str, *, force_refresh: bool = False) -> dict[str, Any]:
        with self._lock:
            if (
                not force_refresh
                and self._jwks_cache is not None
                and time.time() < self._jwks_cache_expires_at
            ):
                return self._jwks_cache

        jwks = self.fetch_json(jwks_uri)
        if not isinstance(jwks.get("keys"), list):
            raise TokenValidationError(
                "JWKS payload does not contain any signing keys."
            )

        with self._lock:
            self._jwks_cache = jwks
            self._jwks_cache_expires_at = (
                time.time() + self._config.discovery_ttl_seconds
            )
            return jwks

    def fetch_json(self, url: str) -> dict[str, Any]:
        try:
            with niquests.Session(timeout=10.0) as session:
                response = session.get(url, allow_redirects=False)
                response.raise_for_status()
                payload = response.json()
        except niquests.exceptions.RequestException as exc:
            raise TokenValidationError(
                f"Failed to fetch identity metadata from {url}."
            ) from exc
        except ValueError as exc:
            raise TokenValidationError(
                f"Identity metadata from {url} is not valid JSON."
            ) from exc

        if not isinstance(payload, dict):
            raise TokenValidationError(
                f"Identity metadata from {url} has an invalid shape."
            )
        return payload


def build_auth_provider(config: ConfigAuthProvider) -> AuthProvider:
    if isinstance(config, ConfigDisabledAuthProvider):
        return DisabledAuthProvider()
    if isinstance(config, ConfigOidcAuthProvider | ConfigEntraIdAuthProvider):
        return OidcAuthProvider(config)
    raise ValueError(f"Unsupported auth provider configuration: {type(config)!r}")


def build_auth_provider_registry(
    groups: Iterable[ConfigMcpGroup],
) -> dict[str, AuthProvider]:
    return {group.name: build_auth_provider(group.auth) for group in groups}


def get_auth_provider_registry(config: Config) -> dict[str, AuthProvider]:
    global _AUTH_PROVIDER_CACHE

    if _AUTH_PROVIDER_CACHE is None or _AUTH_PROVIDER_CACHE[0] != id(config):
        _AUTH_PROVIDER_CACHE = (
            id(config),
            build_auth_provider_registry(config.mcp.groups),
        )
    return _AUTH_PROVIDER_CACHE[1]


def build_auth_challenge(
    *,
    resource_metadata_url: str,
    scopes: Iterable[str],
    error: str | None = None,
    error_description: str | None = None,
) -> str:
    parts = [
        'Bearer realm="agent-proxy"',
        f'resource_metadata="{resource_metadata_url}"',
    ]
    challenge_scope = " ".join(sorted(set(scopes)))
    if challenge_scope:
        parts.append(f'scope="{challenge_scope}"')
    if error is not None:
        parts.append(f'error="{error}"')
    if error_description is not None:
        parts.append(f'error_description="{error_description}"')
    return ", ".join(parts)


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
    return optional_string(claims.get("oid")) or str(claims["sub"])


def find_jwk(jwks: dict[str, Any], key_id: str) -> dict[str, Any] | None:
    for key in jwks["keys"]:
        if key.get("kid") == key_id:
            return key
    return None


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


def optional_string(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


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


def server_resource(server: ConfigMcpServer) -> str:
    if server.resource is None:
        raise TokenValidationError(
            f"MCP server '{server.name}' is missing a configured canonical resource URL."
        )
    return str(server.resource)


def server_accepted_audiences(server: ConfigMcpServer) -> tuple[str, ...]:
    return (server_resource(server), *server.accepted_audiences)
