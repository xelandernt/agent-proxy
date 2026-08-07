from __future__ import annotations

from unittest.mock import Mock, call

import pytest
from fastapi import FastAPI

from proxy import observability
from proxy.settings import LogfireConfig


@pytest.fixture(autouse=True)
def reset_observability(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(observability, "_OBSERVABILITY_CONFIGURED", False)


def test_configures_logfire_and_instruments_fastapi(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    configure = Mock()
    instrument_system_metrics = Mock()
    instrument_fastapi = Mock()
    monkeypatch.setattr(observability.logfire, "configure", configure)
    monkeypatch.setattr(
        observability.logfire,
        "instrument_system_metrics",
        instrument_system_metrics,
    )
    monkeypatch.setattr(
        observability.logfire,
        "instrument_fastapi",
        instrument_fastapi,
    )
    app = FastAPI()

    observability.configure_observability(
        app,
        LogfireConfig.model_validate(
            {
                "token": "secret-token",
                "environment": "production",
                "service_name": "mcp-gateway",
            }
        ),
    )

    configure.assert_called_once_with(
        send_to_logfire="if-token-present",
        environment="production",
        service_name="mcp-gateway",
        token="secret-token",
    )
    instrument_system_metrics.assert_called_once_with(base="basic")
    instrument_fastapi.assert_called_once_with(app)


def test_process_configuration_is_reused_but_each_app_is_instrumented(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    configure = Mock()
    instrument_system_metrics = Mock()
    instrument_fastapi = Mock()
    monkeypatch.setattr(observability.logfire, "configure", configure)
    monkeypatch.setattr(
        observability.logfire,
        "instrument_system_metrics",
        instrument_system_metrics,
    )
    monkeypatch.setattr(
        observability.logfire,
        "instrument_fastapi",
        instrument_fastapi,
    )
    settings = LogfireConfig()
    first_app = FastAPI()
    second_app = FastAPI()

    observability.configure_observability(first_app, settings)
    observability.configure_observability(second_app, settings)

    configure.assert_called_once()
    instrument_system_metrics.assert_called_once()
    assert instrument_fastapi.call_args_list == [
        call(first_app),
        call(second_app),
    ]
