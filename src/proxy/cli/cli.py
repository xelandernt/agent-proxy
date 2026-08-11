from __future__ import annotations

import json
from pathlib import Path

from cyclopts import App

from proxy.settings import DatabaseConfig, GatewayConfig, load_config

cli = App(name="proxy")


@cli.command()
def config_schema(output_path: Path) -> None:
    """Write the gateway configuration JSON Schema."""

    schema = json.dumps(GatewayConfig.model_json_schema(), indent=2)
    output_path.write_text(f"{schema}\n")


@cli.command()
def openapi(output_path: Path) -> None:
    """Write the gateway OpenAPI schema for client generation."""

    from proxy.app.main import create_app

    # The schema only describes routes and models; no database connection or
    # server boot is needed, so a placeholder configuration suffices.
    config = GatewayConfig(
        database=DatabaseConfig(
            url="postgresql+asyncpg://placeholder:placeholder@localhost/placeholder"
        )
    )
    schema = json.dumps(create_app(config).openapi(), indent=2)
    output_path.write_text(f"{schema}\n")


@cli.command(name="run")
def run(
    host: str | None = None,
    port: int | None = None,
    reload: bool = False,
    root_path: str = "",
) -> None:
    """Run the MCP authentication gateway with Uvicorn."""

    import uvicorn

    config = load_config()
    uvicorn.run(
        "proxy.app.main:create_app",
        host=host or config.host.address,
        port=port or config.host.port,
        reload=reload,
        root_path=root_path,
        factory=True,
    )
