import json
import threading
import time
from typing import Any

import jwt
import niquests
from jwt.algorithms import RSAAlgorithm

from proxy.auth.models import (
    AuthenticatedPrincipal,
    TokenValidationError,
    audiences_match_resource,
    extract_audiences,
    extract_scopes,
    find_jwk,
    optional_string,
    principal_subject,
    server_accepted_audiences,
)
from proxy.auth.providers import OAuthBearerAuthProvider
from proxy.settings import (
    EntraIdAuthProviderConfig,
    McpServerConfig,
    OidcAuthProviderConfig,
)


class OidcAuthProvider(OAuthBearerAuthProvider):
    """OIDC-based authentication provider.

    Validates Bearer tokens against an OIDC-compliant issuer by fetching
    OpenID Discovery metadata and JWKS, caching both with configurable TTL.

    Args:
        config: OIDC or Entra ID auth provider configuration.
    """

    def __init__(
        self, config: OidcAuthProviderConfig | EntraIdAuthProviderConfig
    ) -> None:
        self._config = config
        self._lock = threading.Lock()
        self._metadata_cache: dict[str, Any] | None = None
        self._metadata_cache_expires_at = 0.0
        self._jwks_cache: dict[str, Any] | None = None
        self._jwks_cache_expires_at = 0.0

    def authorization_servers(self) -> tuple[str, ...]:
        """Return the issuer URL as the sole authorization server.

        Returns:
            A tuple containing the issuer URL.
        """
        return (self._config.issuer_url,)

    def authenticate_token(
        self, token: str, *, server: McpServerConfig
    ) -> AuthenticatedPrincipal:
        """Validate an access token and extract the principal.

        Fetches OIDC discovery metadata and the signing key, decodes and
        verifies the JWT, checks the audience matches the MCP server, and
        returns the authenticated principal with granted scopes.

        Args:
            token: The raw bearer token string.
            server: The MCP server configuration for audience validation.

        Returns:
            The authenticated principal.

        Raises:
            TokenValidationError: If the token is invalid, the issuer is
                unknown, the audience does not match, or signing key
                retrieval fails.
        """
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
        """Fetch and cache the OIDC discovery metadata.

        Uses a thread-safe cache with configurable TTL to avoid fetching
        the metadata on every request.

        Returns:
            The OIDC discovery metadata as a dictionary.

        Raises:
            TokenValidationError: If the metadata is missing required fields
                (issuer, jwks_uri) or cannot be fetched.
        """
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
        """Find and return the RSA signing key for a token.

        Extracts the key ID (kid) from the unverified JWT header, fetches
        the JWKS (with a retry + force refresh on first miss), and converts
        the matching JWK to an RSA key.

        Args:
            token: The raw JWT access token.
            jwks_uri: URL to fetch the JWKS from.

        Returns:
            An RSA signing key usable for JWT verification.

        Raises:
            TokenValidationError: If the header is malformed, algorithm is
                unsupported, key ID is missing, or no matching key is found.
        """
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
        """Fetch and cache the JWKS from the provider.

        Uses a thread-safe cache with configurable TTL. Pass
        ``force_refresh=True`` to bypass the cache.

        Args:
            jwks_uri: URL to fetch the JWKS from.
            force_refresh: If True, ignore the cache and fetch fresh keys.

        Returns:
            The JWKS dictionary containing signing keys.

        Raises:
            TokenValidationError: If the JWKS payload has no ``keys`` array
                or cannot be fetched.
        """
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
        """Fetch a JSON payload from a URL.

        Args:
            url: The URL to fetch.

        Returns:
            The parsed JSON response as a dictionary.

        Raises:
            TokenValidationError: If the request fails or the response is
                not valid JSON or is not a dict.
        """
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
