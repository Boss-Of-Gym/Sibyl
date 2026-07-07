FROM python:3.13-slim AS builder

COPY --from=ghcr.io/astral-sh/uv:0.5 /uv /uvx /bin/

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never

WORKDIR /app

COPY pyproject.toml uv.lock ./

RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-install-project --no-dev

COPY src/ src/

RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev


FROM python:3.13-slim AS runtime

RUN groupadd --system sibyl && useradd --system --gid sibyl --create-home sibyl

WORKDIR /app

COPY --from=builder --chown=sibyl:sibyl /app/.venv /app/.venv
COPY --from=builder --chown=sibyl:sibyl /app/src /app/src
COPY --chown=sibyl:sibyl alembic.ini /app/alembic.ini
COPY --chown=sibyl:sibyl alembic/ /app/alembic/

ENV PATH="/app/.venv/bin:$PATH"

USER sibyl


FROM runtime AS api

EXPOSE 8000

CMD ["uvicorn", "sibyl.api.app:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000"]


FROM runtime AS worker

EXPOSE 8001

CMD ["python", "-m", "sibyl.worker"]
