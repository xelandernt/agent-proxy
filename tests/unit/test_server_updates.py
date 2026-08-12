from __future__ import annotations

import pytest

from proxy.providers import Auth0AuthProviderConfig, GoogleAuthProviderConfig
from proxy.servers.models import SECRET_MASK, merge_masked_auth_secrets


def test_masked_secret_preserves_current_value() -> None:
    current = Auth0AuthProviderConfig(
        provider="auth0",
        config_url="https://tenant.example/.well-known/openid-configuration",
        client_id="client-id",
        client_secret="original-secret",
        audience="https://api.example",
    )
    updated = Auth0AuthProviderConfig(
        provider="auth0",
        config_url="https://new.example/.well-known/openid-configuration",
        client_id="new-client-id",
        client_secret=SECRET_MASK,
        audience="https://new-api.example",
    )

    merged = merge_masked_auth_secrets(current, updated)

    assert isinstance(merged, Auth0AuthProviderConfig)
    assert merged.client_secret.get_secret_value() == "original-secret"
    assert str(merged.config_url).startswith("https://new.example/")
    assert merged.client_id == "new-client-id"


def test_submitted_secret_replaces_current_value() -> None:
    current = Auth0AuthProviderConfig(
        provider="auth0",
        config_url="https://tenant.example/.well-known/openid-configuration",
        client_id="client-id",
        client_secret="original-secret",
        audience="https://api.example",
    )
    updated = current.model_copy(
        update={"client_secret": type(current.client_secret)("replacement-secret")}
    )

    merged = merge_masked_auth_secrets(current, updated)

    assert isinstance(merged, Auth0AuthProviderConfig)
    assert merged.client_secret.get_secret_value() == "replacement-secret"


def test_masked_secret_cannot_cross_provider_boundary() -> None:
    current = GoogleAuthProviderConfig(
        provider="google",
        client_id="client-id",
        client_secret=None,
        jwt_signing_key="signing-key",
    )
    updated = Auth0AuthProviderConfig(
        provider="auth0",
        config_url="https://tenant.example/.well-known/openid-configuration",
        client_id="client-id",
        client_secret=SECRET_MASK,
        audience="https://api.example",
    )

    with pytest.raises(TypeError, match="same provider"):
        merge_masked_auth_secrets(current, updated)
