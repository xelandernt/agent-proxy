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
