from __future__ import annotations

import logfire
from fastapi import FastAPI

from proxy.settings import LogfireConfig

_OBSERVABILITY_CONFIGURED = False


def configure_observability(app: FastAPI, settings: LogfireConfig) -> None:
    """Configure process-wide Logfire telemetry and instrument one gateway app."""

    global _OBSERVABILITY_CONFIGURED
    if not _OBSERVABILITY_CONFIGURED:
        logfire.configure(
            send_to_logfire="if-token-present",
            environment=settings.environment,
            service_name=settings.service_name,
            token=settings.token.get_secret_value() if settings.token else None,
        )
        logfire.instrument_system_metrics(base="basic")
        _OBSERVABILITY_CONFIGURED = True

    logfire.instrument_fastapi(app)
