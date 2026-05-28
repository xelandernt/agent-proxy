[private]
default:
    @just --list

upgrade:
    uv lock --upgrade
    @just install

# install dependencies
install:
    uv sync --all-extras --frozen
    @just hook

# lint project
lint:
    uv run prek run --all-files

# test project
test *args:
    uv run --no-sync pytest {{ args }}

# type check project
typecheck:
    uv run pyrefly check

# install pre-commit hooks
hook:
    uv run prek install --install-hooks --overwrite

# uninstall pre-commit hooks
unhook:
    uv run prek uninstall

# publish project on pypi
publish:
    rm -rf dist
    uv build
    uv publish --token $PYPI_TOKEN

config-schema:
    uv run proxy config-schema ./resources/config.schema.json

inspector:
    npx -y @modelcontextprotocol/inspector

compose:
    docker compose up -d --wait

stop:
    docker compose --profile "*" down

dev:
    @just compose
    uv run --env-file ".env" proxy run
