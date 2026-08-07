from __future__ import annotations

import json
from pathlib import Path

from cyclopts import App

from proxy.settings import GatewayConfig, load_config

cli = App(name="proxy")


@cli.command()
def config_schema(output_path: Path) -> None:
    """Write the gateway configuration JSON Schema."""

    schema = json.dumps(GatewayConfig.model_json_schema(), indent=2)
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
