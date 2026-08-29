# Search For Research — match API (SFR-2).
#
# The image carries code and dependencies only. The model weights are NOT baked in
# (FRIDA is ~2 GB): they are downloaded once into the mounted HF cache volume on
# first start. The index is built offline (`make index-sfr2`) and mounted read-only.
FROM python:3.12-slim AS base

# torch from the CPU index: the default wheels on linux/amd64 pull CUDA (gigabytes)
# that a CPU-only VPS will never use. On linux/arm64 this is already the default.
ENV UV_TORCH_BACKEND=cpu \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never \
    PYTHONUNBUFFERED=1 \
    HF_HOME=/models

RUN apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:0.11 /uv /usr/local/bin/uv

WORKDIR /app

# Dependencies first: this layer is cached until the lock file itself changes.
COPY pyproject.toml uv.lock ./
COPY packages/sfr-core/pyproject.toml packages/sfr-core/
COPY packages/sfr-etl/pyproject.toml packages/sfr-etl/
COPY packages/sfr-match/pyproject.toml packages/sfr-match/
COPY apps/api/pyproject.toml apps/api/
RUN mkdir -p packages/sfr-core/src/sfr_core packages/sfr-etl/src/sfr_etl \
    packages/sfr-match/src/sfr_match apps/api/src/sfr_api \
    && touch packages/sfr-core/src/sfr_core/__init__.py \
    packages/sfr-etl/src/sfr_etl/__init__.py \
    packages/sfr-match/src/sfr_match/__init__.py \
    apps/api/src/sfr_api/__init__.py \
    && uv sync --frozen --package sfr-api --no-dev

COPY packages/ packages/
COPY apps/api/ apps/api/
RUN uv sync --frozen --package sfr-api --no-dev

ENV PATH="/app/.venv/bin:$PATH" \
    SFR_API_INDEX_ROOT=/app/data/indexes_sfr2

EXPOSE 8000
HEALTHCHECK --interval=5s --timeout=3s --start-period=180s --retries=40 \
    CMD curl -fsS http://127.0.0.1:8000/api/health || exit 1

CMD ["uvicorn", "sfr_api.main:app", "--factory", "--host", "0.0.0.0", "--port", "8000"]
