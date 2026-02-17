"""
Scaling Configuration
=====================
Environment-aware configuration for production deployments.
Supports SQLite (dev) and PostgreSQL (prod) backends,
Redis task broker, and observability settings.
"""

import os
from pathlib import Path


# ── Environment ──────────────────────────────────────────────────────
ENV = os.getenv("PROJECT_ANCHOR_ENV", "development")
IS_PROD = ENV == "production"

# ── Database ─────────────────────────────────────────────────────────
# SQLite for development, PostgreSQL for production
DATABASE_URL = os.getenv(
    "PROJECT_ANCHOR_DB_URL",
    f"sqlite:///{Path(__file__).resolve().parent.parent / 'data' / 'project_anchor.db'}"
)

# Connection pool settings (PostgreSQL only)
DB_POOL_SIZE = int(os.getenv("DB_POOL_SIZE", "10"))
DB_MAX_OVERFLOW = int(os.getenv("DB_MAX_OVERFLOW", "20"))
DB_POOL_TIMEOUT = int(os.getenv("DB_POOL_TIMEOUT", "30"))
DB_POOL_RECYCLE = int(os.getenv("DB_POOL_RECYCLE", "1800"))

# ── Redis / Task Queue ──────────────────────────────────────────────
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
CELERY_BROKER_URL = os.getenv("CELERY_BROKER_URL", REDIS_URL)
CELERY_RESULT_BACKEND = os.getenv("CELERY_RESULT_BACKEND", REDIS_URL)

# Worker concurrency
WORKER_CONCURRENCY = int(os.getenv("WORKER_CONCURRENCY", "4"))
TASK_SOFT_TIME_LIMIT = int(os.getenv("TASK_SOFT_TIME_LIMIT", "300"))
TASK_HARD_TIME_LIMIT = int(os.getenv("TASK_HARD_TIME_LIMIT", "600"))

# ── API ──────────────────────────────────────────────────────────────
API_HOST = os.getenv("API_HOST", "0.0.0.0")
API_PORT = int(os.getenv("API_PORT", "8000"))
API_WORKERS = int(os.getenv("API_WORKERS", "4"))
API_RATE_LIMIT = os.getenv("API_RATE_LIMIT", "100/minute")
API_SECRET_KEY = os.getenv("API_SECRET_KEY", "change-me-in-production")
JWT_ALGORITHM = "HS256"
JWT_EXPIRATION_HOURS = int(os.getenv("JWT_EXPIRATION_HOURS", "24"))

# ── IPFS ─────────────────────────────────────────────────────────────
IPFS_API_URL = os.getenv("IPFS_API_URL", "http://localhost:5001")
IPFS_GATEWAY_URL = os.getenv("IPFS_GATEWAY_URL", "http://localhost:8080")

# ── Observability ────────────────────────────────────────────────────
PROMETHEUS_ENABLED = os.getenv("PROMETHEUS_ENABLED", "true").lower() == "true"
PROMETHEUS_PORT = int(os.getenv("PROMETHEUS_PORT", "9090"))
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO" if IS_PROD else "DEBUG")
LOG_FORMAT = os.getenv("LOG_FORMAT", "json" if IS_PROD else "text")
OTEL_ENABLED = os.getenv("OTEL_ENABLED", "false").lower() == "true"
OTEL_ENDPOINT = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:4317")

# ── Feature Flags ────────────────────────────────────────────────────
ENABLE_ASYNC_COLLECTION = os.getenv("ENABLE_ASYNC_COLLECTION", "true").lower() == "true"
ENABLE_SCHEDULED_SCORING = os.getenv("ENABLE_SCHEDULED_SCORING", "true").lower() == "true"
ENABLE_ALERT_WEBHOOKS = os.getenv("ENABLE_ALERT_WEBHOOKS", "false").lower() == "true"
ALERT_WEBHOOK_URL = os.getenv("ALERT_WEBHOOK_URL", "")

# ── Rate Limits (per-source) ────────────────────────────────────────
SCRAPER_RATE_LIMITS = {
    "reddit": float(os.getenv("RATE_LIMIT_REDDIT", "1.0")),       # req/sec
    "wayback": float(os.getenv("RATE_LIMIT_WAYBACK", "0.5")),
    "web_search": float(os.getenv("RATE_LIMIT_WEBSEARCH", "0.5")),
    "gov_records": float(os.getenv("RATE_LIMIT_GOV", "0.25")),
    "academic": float(os.getenv("RATE_LIMIT_ACADEMIC", "0.25")),
}
