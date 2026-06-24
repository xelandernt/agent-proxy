from pathlib import Path

from cyclopts import App


cli = App(name="proxy")


@cli.command()
def config() -> None:
    """Print the current proxy configuration as pretty-printed JSON."""
    from proxy.settings import CONFIG

    print(CONFIG.model_dump_json(indent=4))


@cli.command()
def config_schema(output_path: Path) -> None:
    """Write the JSON Schema for the proxy configuration to a file.

    Args:
        output_path: Path to the output file.
    """
    import json
    from proxy.settings import CONFIG

    output_path.write_text(json.dumps(CONFIG.model_json_schema()) + "\n")


@cli.command(name="run", help="Run the FastAPI application")
def run(
    host: str = "127.0.0.1",
    port: int = 8008,
    reload: bool = True,
    root_path: str = "/",
) -> None:
    """Start the Agent Proxy FastAPI application via uvicorn.

    Args:
        host: Host address to bind to.
        port: Port to listen on.
        reload: Whether to enable auto-reload on code changes.
        root_path: ASGI root path for reverse proxy mounting.
    """
    import uvicorn

    uvicorn.run(
        "proxy.app.main:app",
        host=host,
        port=port,
        reload=reload,
        root_path=root_path,
    )
