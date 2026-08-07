from __future__ import annotations

from fastmcp.server.auth import AccessToken, AuthProvider


class StaticAuthProvider(AuthProvider):
    """Small deterministic provider used by gateway tests."""

    async def verify_token(self, token: str) -> AccessToken | None:
        if token != "valid-token":
            return None
        return AccessToken(
            token=token,
            client_id="test-client",
            subject="test-user",
            scopes=["mcp"],
        )
