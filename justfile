mod ui "ui/justfile"

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

# generate configuration schema
config-schema:
    uv run proxy config-schema ./resources/config.schema.json

# start mcp inspector
inspector:
    npx -y @modelcontextprotocol/inspector

# start Docker dependencies, then run the gateway locally with reload
dev:
    docker compose up --build --wait -d
    uv run proxy run --reload

# build and start the Keycloak and example MCP server dependencies
compose:
    docker compose up --build --wait -d

# follow logs from the local Compose stack
compose-logs:
    docker compose logs --follow

# stop and remove the local Compose stack
stop:
    docker compose down --remove-orphans
