from fastapi.testclient import TestClient

from proxy.app.main import create_app
from proxy.settings import GatewayConfig


def test_healthz_is_public_and_reports_ok() -> None:
    config = GatewayConfig.model_validate(
        {
            "admin": {"auth": {"provider": "static"}},
            "user": {
                "auth": {
                    "provider": "jwt",
                    "public_key": "test-user-auth-secret",
                    "algorithm": "HS256",
                }
            },
            "model_gateway": {
                "credential_encryption_key": (
                    "Zop6ZBEB1OB1D8SfORA4msZDzY1hEvqCnpF2DGpxs-E="
                )
            },
        }
    )
    with TestClient(create_app(config)) as client:
        response = client.get("/healthz")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
