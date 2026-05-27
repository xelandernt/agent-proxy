FROM python:3.13-slim AS base

# Install uv
RUN pip install uv

WORKDIR /app

# Configure uv
ENV UV_CACHE_DIR=/root/.cache/uv \
    UV_LINK_MODE=copy \
    UV_COMPILE_BYTECODE=1

# Install curl for healthcheck
RUN --mount=type=cache,target=/var/cache/apt,sharing=locked \
    --mount=type=cache,target=/var/lib/apt,sharing=locked \
    apt update && apt-get --no-install-recommends install -y \
    curl


FROM base AS backend

# Install dependencies
RUN --mount=type=cache,target=$UV_CACHE_DIR \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    uv sync --frozen --no-install-project --no-dev

ADD . /app

RUN --mount=type=cache,target=$UV_CACHE_DIR \
    uv sync --frozen --no-dev --no-editable

ENV PATH="/app/.venv/bin:$PATH"

ENTRYPOINT []

CMD proxy run --host 0.0.0.0 --port ${BACKEND__HOST__PORT} --no-reload --root-path ${ROOT_PATH}
