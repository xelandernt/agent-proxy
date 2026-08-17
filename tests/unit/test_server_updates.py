from __future__ import annotations

from proxy.auth_providers.models import config_to_public_auth_payload
from proxy.providers import Auth0AuthProviderConfig


def test_public_provider_payload_omits_credentials() -> None:
    config = Auth0AuthProviderConfig(
        provider="auth0",
        config_url="https://tenant.example/.well-known/openid-configuration",
        client_id="client-id",
        client_secret="original-secret",
        audience="https://api.example",
    )

    public = config_to_public_auth_payload(config)

    assert public["provider"] == "auth0"
    assert public["client_id"] == "client-id"
    assert "client_secret" not in public
    assert "original-secret" not in repr(public)
