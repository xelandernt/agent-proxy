from pathlib import Path

from cyclopts import App


cli = App(name="proxy")


@cli.command()
def config() -> None:
    from proxy.settings import CONFIG

    print(CONFIG.model_dump_json(indent=4))


@cli.command()
def config_schema(output_path: Path) -> None:
    import json
    from proxy.settings import CONFIG

    with open(output_path, "w") as f:
        f.write(json.dumps(CONFIG.model_json_schema()))


@cli.command(name="run", help="Run the FastAPI application")
def run(
    host: str = "127.0.0.1",
    port: int = 8008,
    reload: bool = True,
    root_path: str = "/",
) -> None:
    import uvicorn

    uvicorn.run(
        "proxy.app.main:app",
        host=host,
        port=port,
        reload=reload,
        root_path=root_path,
    )
