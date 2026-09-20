# ──────────────────────────────────────────────────────────────
# Base: system deps + uv, shared by docs and runtime stages
# ──────────────────────────────────────────────────────────────
FROM python:3.12-slim AS base

# Pin uv so builds are reproducible. Update on purpose, not by accident.
COPY --from=ghcr.io/astral-sh/uv:0.8 /uv /usr/local/bin/uv

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

WORKDIR /app

# System deps: matches the devcontainer, plus additions for the slim base
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    g++ \
    poppler-utils \
    tesseract-ocr \
    tesseract-ocr-eng \
    libgl1 \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml uv.lock ./

# ──────────────────────────────────────────────────────────────
# Docs: install WITH dev deps, generate static HTML, discard
# ──────────────────────────────────────────────────────────────
FROM base AS docs

RUN uv sync --frozen --no-install-project

COPY . .
RUN uv sync --frozen

# PDOC_GENERATING=1 → get_manager() returns a mock so imports don't hit the DB
RUN PDOC_GENERATING=1 uv run pdoc ./src -o ./docs --docformat google

# ──────────────────────────────────────────────────────────────
# Runtime: production image, no dev deps, just the HTML output
# ──────────────────────────────────────────────────────────────
FROM base AS runtime

# Create the user first so files can be copied in with the right owner.
# A fixed UID makes bind-mount permissions predictable on the host.
RUN useradd --create-home --uid 1000 appuser

RUN uv sync --frozen --no-install-project --no-dev

COPY --chown=appuser:appuser . .
RUN uv sync --frozen --no-dev && chown -R appuser:appuser /app/.venv

COPY --from=docs --chown=appuser:appuser /app/docs ./docs

# These describe the image, so they belong here rather than in compose.
# DATA_DIR must match the volume target in docker-compose.yml.
ENV APP_ENV=production \
    DATA_DIR=/app/data \
    PORT=5000 \
    PATH="/app/.venv/bin:$PATH"

RUN mkdir -p /app/data/uploads && chown -R appuser:appuser /app/data

USER appuser

EXPOSE 5000

# Exec form, with the venv binary called directly. Gunicorn runs as PID 1 and
# gets SIGTERM from `docker stop`. Server settings come from gunicorn.conf.py
# and app settings from src/config.py. Both read the environment.
CMD ["gunicorn", "-c", "/app/gunicorn.conf.py", "src.run:app"]