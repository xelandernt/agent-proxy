"""Gateway-hosted OAuth authorization server for the admin UI, backed by Keycloak.

The gateway presents itself to the admin UI as an RFC 8414 authorization
server mounted under ``/admin/oauth`` and proxies the interactive flow to a
confidential Keycloak client. The tokens handed back to the UI are the
Keycloak-issued access tokens themselves, so the admin API can verify them
directly against the realm's JWKS — the same tokens work whether they arrive
via the browser flow or are pasted in manually.
"""

from __future__ import annotations

import base64
import hashlib
import logging
import secrets
import time
from dataclasses import dataclass
from urllib.parse import urlencode

import httpx2
from authlib.jose import JsonWebKey
from authlib.jose import jwt as authlib_jwt
from authlib.jose.rfc7517.jwk import KeySet
from starlette.requests import Request
from starlette.responses import JSONResponse, RedirectResponse
from starlette.routing import Route

from proxy.providers import KeycloakAuthProviderConfig

logger = logging.getLogger(__name__)

#: How long a fetched JWKS set is trusted before being re-fetched.
JWKS_CACHE_SECONDS = 3600

#: Timeout for requests the gateway makes to the Keycloak realm.
UPSTREAM_TIMEOUT_SECONDS = 10


@dataclass
class RegisteredClient:
    """An MCP/UI client registered with the gateway's authorization server."""

    client_id: str
    redirect_uris: list[str]
    client_name: str = ""


@dataclass
class PendingAuthorization:
    """A browser flow whose user is currently at the Keycloak login page."""

    client_id: str
    redirect_uri: str
    code_challenge: str | None
    scope: str


@dataclass
class IssuedCode:
    """A one-time authorization code issued to the UI after Keycloak login."""

    client_id: str
    code_challenge: str | None
    access_token: str
    expires_in: int


def _s256(verifier: str) -> str:
    """RFC 7636 S256 PKCE challenge for a code verifier."""

    digest = hashlib.sha256(verifier.encode("ascii")).digest()
    return base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")


def register_upstream_client(realm_url: str, redirect_uri: str) -> tuple[str, str]:
    """Register a confidential gateway client with Keycloak's DCR endpoint.

    Returns the ``(client_id, client_secret)`` pair issued by the realm. The
    redirect URI registered is the gateway's own OAuth callback. Keycloak's
    ``/clients-registrations/default`` endpoint accepts ``ClientRepresentation``
    fields and returns the client secret for confidential clients.
    """

    payload = {
        "name": "agent-proxy-admin",
        "redirectUris": [redirect_uri],
        "publicClient": False,
        "standardFlowEnabled": True,
        "directAccessGrantsEnabled": False,
        "clientAuthenticatorType": "client-secret",
        "protocol": "openid-connect",
        "defaultClientScopes": ["openid"],
    }
    try:
        response = httpx2.post(
            f"{realm_url.rstrip('/')}/clients-registrations/default",
            json=payload,
            timeout=UPSTREAM_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        data = response.json()
    except Exception:
        logger.exception("Keycloak dynamic client registration failed.")
        raise
    client_id = data.get("clientId")
    client_secret = data.get("secret")
    if not client_id or not client_secret:
        raise ValueError(
            "Keycloak dynamic client registration returned no client credentials."
        )
    return client_id, client_secret


class KeycloakAdminOAuthProvider:
    """OAuth authorization server and token verifier for the admin boundary.

    Routes are returned unprefixed; the gateway mounts them under
    ``/admin/oauth`` so the metadata issuer stays self-consistent.
    """

    def __init__(
        self,
        *,
        realm_url: str,
        base_url: str,
        client_id: str,
        client_secret: str,
        audience: str | list[str] | None = None,
        required_scopes: list[str] | None = None,
    ) -> None:
        self.realm_url = realm_url.rstrip("/")
        self.base_url = base_url.rstrip("/")
        self.client_id = client_id
        self.client_secret = client_secret
        self.audience = audience
        self.required_scopes = required_scopes or ["openid"]
        self.scopes_supported = ["openid", "email", "profile", "offline_access"]

        self._clients: dict[str, RegisteredClient] = {}
        self._pending: dict[str, PendingAuthorization] = {}
        self._codes: dict[str, IssuedCode] = {}
        self._jwks: tuple[float, KeySet] | None = None

    @classmethod
    def from_config(
        cls,
        config: KeycloakAuthProviderConfig,
        *,
        base_url: str,
    ) -> KeycloakAdminOAuthProvider:
        """Build the provider, resolving upstream credentials from config or DCR."""

        if config.client_id is not None and config.client_secret is not None:
            client_id = config.client_id
            client_secret = config.client_secret.get_secret_value()
        else:
            client_id, client_secret = register_upstream_client(
                str(config.realm_url), f"{base_url}/callback"
            )
        return cls(
            realm_url=str(config.realm_url),
            base_url=base_url,
            client_id=client_id,
            client_secret=client_secret,
            audience=config.audience,
            required_scopes=config.required_scopes,
        )

    def get_routes(self) -> list[Route]:
        """The authorization server's discovery, registration, and OAuth routes."""

        return [
            Route(
                "/.well-known/oauth-authorization-server",
                endpoint=self.authorization_server_metadata,
                methods=["GET"],
            ),
            Route("/register", endpoint=self.register, methods=["POST"]),
            Route("/authorize", endpoint=self.authorize, methods=["GET"]),
            Route("/callback", endpoint=self.callback, methods=["GET"]),
            Route("/token", endpoint=self.token, methods=["POST"]),
        ]

    async def verify_token(self, token: str) -> dict[str, object] | None:
        """Verify a Keycloak-issued access token against the realm's JWKS."""

        try:
            claims = await self._decode_token(token)
        except Exception:
            logger.warning("Rejected invalid admin access token.", exc_info=True)
            return None
        if claims is None:
            return None
        return dict(claims)

    # --- authorization server endpoints ----------------------------------

    def authorization_server_metadata(self, request: Request) -> JSONResponse:
        """RFC 8414 discovery document for the gateway's authorization server."""

        return JSONResponse(
            {
                "issuer": self.base_url,
                "authorization_endpoint": f"{self.base_url}/authorize",
                "token_endpoint": f"{self.base_url}/token",
                "registration_endpoint": f"{self.base_url}/register",
                "scopes_supported": self.scopes_supported,
                "response_types_supported": ["code"],
                "grant_types_supported": ["authorization_code"],
                "code_challenge_methods_supported": ["S256"],
                "token_endpoint_auth_methods_supported": ["none"],
            }
        )

    async def register(self, request: Request) -> JSONResponse:
        """Dynamic client registration for UI and MCP clients."""

        payload = await request.json()
        redirect_uris = payload.get("redirect_uris") or []
        if not redirect_uris:
            return JSONResponse(
                {
                    "error": "invalid_client_metadata",
                    "error_description": "redirect_uris is required.",
                },
                status_code=400,
            )
        client_id = secrets.token_urlsafe(24)
        self._clients[client_id] = RegisteredClient(
            client_id=client_id,
            redirect_uris=[str(uri) for uri in redirect_uris],
            client_name=str(payload.get("client_name", "")),
        )
        return JSONResponse(
            {
                "client_id": client_id,
                "client_secret": "",
                "client_name": payload.get("client_name", ""),
                "redirect_uris": [str(uri) for uri in redirect_uris],
                "grant_types": payload.get("grant_types") or ["authorization_code"],
                "response_types": payload.get("response_types") or ["code"],
                "token_endpoint_auth_method": "none",
                "application_type": payload.get("application_type") or "web",
            },
            status_code=201,
        )

    async def authorize(self, request: Request) -> RedirectResponse | JSONResponse:
        """Validate the UI's request and send the user to Keycloak to log in."""

        params = request.query_params
        client = self._clients.get(params.get("client_id", ""))
        redirect_uri = params.get("redirect_uri", "")
        state = params.get("state", "")

        if client is None or redirect_uri not in client.redirect_uris:
            return self._error("invalid_request", "Unknown client or redirect URI.")
        if params.get("response_type") != "code":
            return self._error(
                "unsupported_response_type", "Only response_type=code is supported."
            )
        if not state:
            return self._error("invalid_request", "Missing state parameter.")
        challenge_method = params.get("code_challenge_method", "")
        if challenge_method not in ("", "S256"):
            return self._error(
                "invalid_request", "Only code_challenge_method=S256 is supported."
            )

        self._pending[state] = PendingAuthorization(
            client_id=client.client_id,
            redirect_uri=redirect_uri,
            code_challenge=params.get("code_challenge"),
            scope=params.get("scope") or "openid",
        )
        upstream = {
            "client_id": self.client_id,
            "redirect_uri": f"{self.base_url}/callback",
            "response_type": "code",
            "scope": "openid",
            "state": state,
        }
        upstream_url = (
            f"{self.realm_url}/protocol/openid-connect/auth?{urlencode(upstream)}"
        )
        return RedirectResponse(upstream_url, status_code=302)

    async def callback(self, request: Request) -> RedirectResponse | JSONResponse:
        """Exchange the Keycloak code and hand the UI a one-time gateway code."""

        params = request.query_params
        if params.get("error"):
            return self._error(
                params.get("error", "server_error"),
                params.get("error_description"),
            )
        state = params.get("state", "")
        pending = self._pending.pop(state, None)
        keycloak_code = params.get("code", "")
        if pending is None or not keycloak_code:
            return self._error("invalid_request", "Invalid or missing state.")
        try:
            tokens = await self._exchange_keycloak_code(keycloak_code)
        except Exception:
            logger.exception("Failed to exchange authorization code with Keycloak.")
            return self._error(
                "server_error", "Failed to exchange the authorization code."
            )

        access_token = tokens.get("access_token")
        if not isinstance(access_token, str) or not access_token:
            return self._error("server_error", "Keycloak returned no access token.")
        expires_in = tokens.get("expires_in", 3600)
        code = secrets.token_urlsafe(32)
        self._codes[code] = IssuedCode(
            client_id=pending.client_id,
            code_challenge=pending.code_challenge,
            access_token=access_token,
            expires_in=int(expires_in) if isinstance(expires_in, int) else 3600,
        )
        redirect = (
            f"{pending.redirect_uri}?"
            f"{urlencode({'code': code, 'state': state, 'client_id': pending.client_id})}"
        )
        return RedirectResponse(redirect, status_code=302)

    async def token(self, request: Request) -> JSONResponse:
        """Issue the Keycloak access token to the UI after PKCE validation."""

        form = await request.form()
        if form.get("grant_type") != "authorization_code":
            return JSONResponse({"error": "unsupported_grant_type"}, status_code=400)

        issued = self._codes.pop(str(form.get("code", "")), None)
        if issued is None or form.get("client_id") != issued.client_id:
            return JSONResponse({"error": "invalid_grant"}, status_code=400)
        verifier = form.get("code_verifier")
        if issued.code_challenge and not (
            verifier and _s256(str(verifier)) == issued.code_challenge
        ):
            return JSONResponse({"error": "invalid_grant"}, status_code=400)

        return JSONResponse(
            {
                "access_token": issued.access_token,
                "token_type": "Bearer",
                "expires_in": issued.expires_in,
            }
        )

    # --- Keycloak upstream helpers ----------------------------------------

    async def _exchange_keycloak_code(self, code: str) -> dict[str, object]:
        """Exchange an authorization code for tokens at the realm's token endpoint."""

        data = {
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": f"{self.base_url}/callback",
            "client_id": self.client_id,
            "client_secret": self.client_secret,
        }
        async with httpx2.AsyncClient(timeout=UPSTREAM_TIMEOUT_SECONDS) as client:
            response = await client.post(
                f"{self.realm_url}/protocol/openid-connect/token", data=data
            )
        response.raise_for_status()
        return response.json()

    async def _fetch_jwks(self) -> KeySet:
        """Fetch and cache the realm's JSON Web Key Set."""

        now = time.monotonic()
        if self._jwks is not None and now - self._jwks[0] < JWKS_CACHE_SECONDS:
            return self._jwks[1]
        async with httpx2.AsyncClient(timeout=UPSTREAM_TIMEOUT_SECONDS) as client:
            response = await client.get(
                f"{self.realm_url}/protocol/openid-connect/certs"
            )
        response.raise_for_status()
        key_set = JsonWebKey.import_key_set(response.json())
        self._jwks = (now, key_set)
        return self._jwks[1]

    async def _decode_token(self, token: str) -> dict[str, object] | None:
        """Decode and validate a realm access token, or None when invalid."""

        keys = await self._fetch_jwks()
        claims = authlib_jwt.decode(
            token,
            keys,
            claims_options={
                "iss": {"essential": True, "value": self.realm_url},
                "exp": {"essential": True},
            },
        )
        claims.validate()
        if not self._audience_matches(claims):
            return None
        scope = str(claims.get("scope") or "")
        if not all(required in scope.split() for required in self.required_scopes):
            return None
        return dict(claims)

    def _audience_matches(self, claims: dict[str, object]) -> bool:
        """Whether the token is meant for this gateway.

        Keycloak tokens minted for the gateway's client carry no ``aud`` claim
        but set ``azp`` to the client; tokens pasted from other realm clients
        are accepted when their ``aud`` matches a configured audience.
        """

        audiences = self._valid_audiences()
        raw_aud = claims.get("aud")
        if isinstance(raw_aud, str):
            aud = [raw_aud]
        elif isinstance(raw_aud, list):
            aud = [value for value in raw_aud if isinstance(value, str)]
        else:
            aud = []
        if any(value in audiences for value in aud):
            return True
        return claims.get("azp") == self.client_id

    def _valid_audiences(self) -> list[str]:
        """Audiences this gateway accepts: its own client plus any configured one."""

        audiences = [self.client_id]
        if isinstance(self.audience, str):
            audiences.append(self.audience)
        elif self.audience is not None:
            audiences.extend(self.audience)
        return audiences

    def _error(self, error: str, description: str | None) -> JSONResponse:
        payload: dict[str, object] = {"error": error}
        if description:
            payload["error_description"] = description
        return JSONResponse(payload, status_code=400)
