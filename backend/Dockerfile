# ──────────────────────────────────────────────────────────────
# Base: system deps + uv, shared by docs and runtime stages
# ──────────────────────────────────────────────────────────────
FROM python:3.12-slim AS base

WORKDIR /app

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# System deps — matches devcontainer + additions for slim base
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

# Include dev group so pdoc is available
RUN uv sync --frozen --no-install-project

COPY . .
RUN uv sync --frozen

# PDOC_GENERATING=1 → get_manager() returns a mock so imports don't hit the DB
RUN PDOC_GENERATING=1 uv run pdoc ./src -o ./docs --docformat google


# ──────────────────────────────────────────────────────────────
# Runtime: production image, no dev deps, just the HTML output
# ──────────────────────────────────────────────────────────────
FROM base AS runtime

RUN uv sync --frozen --no-install-project --no-dev

COPY . .
RUN uv sync --frozen --no-dev

# Pull in the generated docs only (pdoc itself is NOT installed here)
COPY --from=docs /app/docs ./docs

RUN mkdir -p /app/data/uploads

RUN useradd --create-home appuser && chown -R appuser:appuser /app
USER appuser

EXPOSE 5000

CMD ["uv", "run", "--no-dev", "gunicorn", "--bind", "0.0.0.0:5000", "--workers", "2", "src.run:app"]