# syntax=docker/dockerfile:1
FROM ghcr.io/astral-sh/uv:0.11.27 AS uv
FROM python:3.13-slim-bookworm AS builder
COPY --from=uv /uv /usr/local/bin/uv
WORKDIR /app
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_PYTHON_DOWNLOADS=never
COPY pyproject.toml uv.lock README.md LICENSE ./
COPY src ./src
COPY results/phase3 ./results/phase3
RUN uv sync --locked --no-dev --no-editable

FROM python:3.13-slim-bookworm AS runtime
ARG BUILD_COMMIT=unknown
ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    RINGSENTINEL_BUILD_COMMIT=$BUILD_COMMIT \
    RINGSENTINEL_ENVIRONMENT=production \
    RINGSENTINEL_AUTH_MODE=disabled \
    RINGSENTINEL_DEMO_ENABLED=false \
    RINGSENTINEL_FRONTEND_ORIGINS='["https://localhost"]' \
    RINGSENTINEL_DATABASE_URL=sqlite:////app/work/ringsentinel.db \
    RINGSENTINEL_STORAGE_ROOT=/app/work/storage \
    RINGSENTINEL_LLM_PROVIDER=deterministic
WORKDIR /app
RUN groupadd --gid 10001 ringsentinel \
    && useradd --uid 10001 --gid ringsentinel --no-create-home ringsentinel \
    && mkdir -p /app/work/storage \
    && chown -R ringsentinel:ringsentinel /app/work
COPY --from=builder /app/.venv /app/.venv
USER 10001:10001
EXPOSE 8000
HEALTHCHECK --interval=15s --timeout=5s --start-period=15s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/v1/health', timeout=3)"
# One API worker owns one local scheduler; never multiply workers with this executor.
CMD ["uvicorn", "ringsentinel.api.app:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1", "--timeout-keep-alive", "5", "--timeout-graceful-shutdown", "20", "--no-access-log"]
