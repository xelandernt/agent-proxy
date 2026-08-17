from fastapi.testclient import TestClient

from proxy.app.main import create_app
from proxy.settings import GatewayConfig


def test_healthz_is_public_and_reports_ok() -> None:
    with TestClient(create_app(GatewayConfig())) as client:
        response = client.get("/healthz")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
