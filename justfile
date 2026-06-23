[default]
[private]
_:
    @just --list --list-submodules

# upgrade dependencies
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

# run Docker-backed integration tests
test-integration *args:
    uv run --no-sync pytest tests/integration {{ args }} -q

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

# generate configuration schema
config-schema:
    uv run proxy config-schema ./resources/config.schema.json

# start mcp inspector
inspector:
    npx -y @modelcontextprotocol/inspector

# start docker containers
compose:
    docker compose up -d --wait

# stop docker containers
stop:
    docker compose --profile "*" down

# start application in development mode
dev:
    @just compose
    uv run --env-file ".env" proxy run
