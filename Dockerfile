# syntax=docker/dockerfile:1
# ═══════════════════════════════════════════════════════════════════
# GRAVITY- | Project Anchor — Multi-Stage Docker Build
# ═══════════════════════════════════════════════════════════════════

# ── Stage 1: Builder ──────────────────────────────────────────────
FROM python:3.11-slim AS builder

WORKDIR /build

# Install build deps only (cached)
COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt \
    && pip install --no-cache-dir --prefix=/install \
       celery[redis] redis fastapi uvicorn[standard] \
       sqlalchemy alembic psycopg2-binary \
       prometheus-client opentelemetry-api opentelemetry-sdk \
       pytest pytest-cov

# ── Stage 2: Runtime ─────────────────────────────────────────────
FROM python:3.11-slim AS runtime

LABEL maintainer="FTHTrading" \
      description="Project Anchor — 6-phase forensic research system" \
      version="1.0.0"

# Copy installed packages
COPY --from=builder /install /usr/local

WORKDIR /app

# Copy application code
COPY src/ src/
COPY scaling/ scaling/
COPY tests/ tests/
COPY main.py .
COPY requirements.txt .

# Create runtime directories
RUN mkdir -p data/keys data/foia data/equations logs reports/audits \
    && groupadd -r anchor && useradd -r -g anchor anchor \
    && chown -R anchor:anchor /app

# Environment
ENV PYTHONUNBUFFERED=1 \
    PYTHONIOENCODING=utf-8 \
    PYTHONDONTWRITEBYTECODE=1 \
    PROJECT_ANCHOR_HOME=/app

# Health check
HEALTHCHECK --interval=30s --timeout=10s --retries=3 \
    CMD python -c "import src.database; print('OK')"

USER anchor

# Default: run tests to verify image
CMD ["python", "-m", "pytest", "tests/", "-v", "--tb=short"]

# For API mode: docker run gravity-anchor:latest uvicorn scaling.api:app --host 0.0.0.0 --port 8000
# For worker:   docker run gravity-anchor:latest celery -A scaling.worker_pool worker --loglevel=info
