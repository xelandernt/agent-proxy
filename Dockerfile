FROM python:3.13-slim

# Install uv
RUN pip install uv

WORKDIR /app

# Configure uv
ENV UV_CACHE_DIR=/root/.cache/uv \
    UV_LINK_MODE=copy \
    UV_COMPILE_BYTECODE=1

# Install dependencies
RUN --mount=type=cache,target=$UV_CACHE_DIR \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    uv sync --frozen --no-install-project --no-dev

COPY . /app

RUN --mount=type=cache,target=$UV_CACHE_DIR \
    uv sync --frozen --no-dev --no-editable

ENV PATH="/app/.venv/bin:$PATH"

CMD ["proxy", "run", "--host", "0.0.0.0", "--port", "8008"]
