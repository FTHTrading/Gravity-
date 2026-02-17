"""
Celery Worker Pool — GRAVITY-
==============================
Async task queue for parallel data collection, scoring, and analysis.
Each phase can scale workers independently.

Usage:
  celery -A scaling.worker_pool worker --loglevel=info --concurrency=4
  celery -A scaling.worker_pool beat --loglevel=info   # scheduled tasks

Architecture:
  ┌──────────┐    ┌───────┐    ┌──────────┐    ┌──────┐
  │ API/CLI  │───▶│ Redis │───▶│ Workers  │───▶│  DB  │
  └──────────┘    └───────┘    └──────────┘    └──────┘
                                  N workers
"""

from __future__ import annotations

import os
import time
from datetime import timedelta

from celery import Celery
from celery.schedules import crontab

from scaling.config import (
    CELERY_BROKER_URL, CELERY_RESULT_BACKEND,
    WORKER_CONCURRENCY, TASK_SOFT_TIME_LIMIT, TASK_HARD_TIME_LIMIT,
)

# ── Celery App ───────────────────────────────────────────────────────
celery_app = Celery(
    "gravity",
    broker=CELERY_BROKER_URL,
    backend=CELERY_RESULT_BACKEND,
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    worker_concurrency=WORKER_CONCURRENCY,
    task_soft_time_limit=TASK_SOFT_TIME_LIMIT,
    task_hard_time_limit=TASK_HARD_TIME_LIMIT,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    task_track_started=True,
    result_expires=timedelta(hours=24),
    # Retry on connection errors
    broker_connection_retry_on_startup=True,
)

# ── Beat Schedule (Periodic Tasks) ──────────────────────────────────
celery_app.conf.beat_schedule = {
    "rescore-all-claims-hourly": {
        "task": "scaling.worker_pool.score_all_claims_task",
        "schedule": crontab(minute=0),  # every hour
    },
    "check-alerts-15min": {
        "task": "scaling.worker_pool.check_alerts_task",
        "schedule": timedelta(minutes=15),
    },
    "collect-reddit-6h": {
        "task": "scaling.worker_pool.scrape_reddit",
        "schedule": crontab(minute=0, hour="*/6"),
    },
    "reputation-scoring-daily": {
        "task": "scaling.worker_pool.score_source_reputations",
        "schedule": crontab(minute=30, hour=2),  # 2:30 AM UTC
    },
}


# ═══════════════════════════════════════════ PHASE I TASKS
@celery_app.task(bind=True, name="scaling.worker_pool.collect_data",
                 max_retries=3, default_retry_delay=60)
def collect_data(self, query: str, sources: list[str], max_results: int = 50):
    """Run multi-source data collection."""
    results = {}
    errors = []

    if "web" in sources:
        try:
            from src.collectors.web_search_scraper import WebSearchScraper
            scraper = WebSearchScraper()
            results["web"] = scraper.search(query, max_results=max_results)
        except Exception as e:
            errors.append({"source": "web", "error": str(e)})

    if "reddit" in sources:
        try:
            from src.collectors.reddit_scraper import RedditScraper
            scraper = RedditScraper()
            results["reddit"] = scraper.search(query, max_results=max_results)
        except Exception as e:
            errors.append({"source": "reddit", "error": str(e)})

    if "wayback" in sources:
        try:
            from src.collectors.wayback_scraper import WaybackScraper
            scraper = WaybackScraper()
            results["wayback"] = scraper.search(query, max_results=max_results)
        except Exception as e:
            errors.append({"source": "wayback", "error": str(e)})

    return {
        "query": query,
        "sources_queried": sources,
        "results_count": {k: len(v) if isinstance(v, list) else 1 for k, v in results.items()},
        "errors": errors,
    }


@celery_app.task(name="scaling.worker_pool.scrape_reddit", max_retries=3)
def scrape_reddit():
    """Scrape Reddit for Project Anchor search terms."""
    from src.collectors.reddit_scraper import RedditScraper
    from src.config import SEARCH_TERMS
    scraper = RedditScraper()
    total = 0
    for term in SEARCH_TERMS:
        results = scraper.search(term, max_results=25)
        total += len(results) if isinstance(results, list) else 0
    return {"source": "reddit", "terms_searched": len(SEARCH_TERMS), "results": total}


@celery_app.task(name="scaling.worker_pool.scrape_wayback", max_retries=3)
def scrape_wayback():
    """Scrape Wayback Machine archives."""
    from src.collectors.wayback_scraper import WaybackScraper
    from src.config import SEARCH_TERMS
    scraper = WaybackScraper()
    total = 0
    for term in SEARCH_TERMS:
        results = scraper.search(term, max_results=25)
        total += len(results) if isinstance(results, list) else 0
    return {"source": "wayback", "terms_searched": len(SEARCH_TERMS), "results": total}


# ═══════════════════════════════════════════ PHASE II TASKS
@celery_app.task(name="scaling.worker_pool.generate_audit_report")
def generate_audit_report():
    """Generate a full audit report."""
    from src.reports.audit_generator import AuditGenerator
    gen = AuditGenerator()
    report = gen.generate()
    return {"status": "completed", "report_id": report.get("id") if isinstance(report, dict) else None}


@celery_app.task(name="scaling.worker_pool.create_merkle_snapshot")
def create_merkle_snapshot():
    """Create Merkle tree snapshot."""
    from src.proofs.merkle_snapshot import MerkleSnapshot
    snap = MerkleSnapshot()
    root = snap.create_snapshot()
    return {"merkle_root": root}


# ═══════════════════════════════════════════ PHASE IV TASKS
@celery_app.task(name="scaling.worker_pool.score_all_claims_task")
def score_all_claims_task():
    """Score all claims with Bayesian confidence."""
    from src.graph.confidence_scorer import ConfidenceScorer
    scorer = ConfidenceScorer()
    results = scorer.score_all()
    return {
        "status": "completed",
        "claims_scored": len(results) if isinstance(results, list) else 0,
    }


@celery_app.task(name="scaling.worker_pool.calculate_entropy")
def calculate_entropy():
    """Calculate mutation entropy for all claims."""
    from src.graph.mutation_entropy import MutationEntropy
    me = MutationEntropy()
    result = me.calculate_all()
    return {"entropy": result}


# ═══════════════════════════════════════════ PHASE V TASKS
@celery_app.task(name="scaling.worker_pool.check_alerts_task")
def check_alerts_task():
    """Run alert engine to detect threshold breaches."""
    from src.graph.alert_engine import AlertEngine
    engine = AlertEngine()
    alerts = engine.check_all()
    return {
        "alerts_triggered": len(alerts) if isinstance(alerts, list) else 0,
        "alerts": alerts,
    }


@celery_app.task(name="scaling.worker_pool.build_timelines")
def build_timelines():
    """Build confidence timelines for all claims."""
    from src.graph.confidence_timeline import ConfidenceTimeline
    ct = ConfidenceTimeline()
    result = ct.build_all()
    return {"timelines_built": result}


@celery_app.task(name="scaling.worker_pool.stability_classification")
def stability_classification():
    """Classify stability for all claims."""
    from src.graph.stability_classifier import StabilityClassifier
    sc = StabilityClassifier()
    result = sc.classify_all()
    return {"classifications": result}


# ═══════════════════════════════════════════ PHASE VI TASKS
@celery_app.task(name="scaling.worker_pool.score_source_reputations")
def score_source_reputations():
    """Score reputation for all known sources."""
    from src.graph.source_reputation import SourceReputation
    sr = SourceReputation()
    result = sr.score_all()
    return {
        "sources_scored": len(result) if isinstance(result, list) else 0,
    }


@celery_app.task(name="scaling.worker_pool.build_influence_network")
def build_influence_network():
    """Build the influence network graph."""
    from src.graph.influence_network import InfluenceNetwork
    net = InfluenceNetwork()
    result = net.build()
    return {"network": result}


@celery_app.task(name="scaling.worker_pool.detect_coordination")
def detect_coordination():
    """Detect coordinated behavior patterns."""
    from src.graph.coordination_detector import CoordinationDetector
    cd = CoordinationDetector()
    result = cd.detect()
    return {"coordination_patterns": result}


# ═══════════════════════════════════════════ PIPELINE TASKS
@celery_app.task(name="scaling.worker_pool.full_pipeline")
def full_pipeline():
    """Run the complete 6-phase pipeline end-to-end."""
    results = {}

    # Phase I: Collection
    results["phase_1"] = collect_data("Project Anchor", ["web", "reddit", "wayback"], 50)

    # Phase II: Integrity
    results["phase_2"] = create_merkle_snapshot()

    # Phase IV: Scoring
    results["phase_4"] = score_all_claims_task()

    # Phase V: Temporal
    results["phase_5_alerts"] = check_alerts_task()
    results["phase_5_stability"] = stability_classification()

    # Phase VI: Intelligence
    results["phase_6_reputation"] = score_source_reputations()
    results["phase_6_coordination"] = detect_coordination()

    return {"pipeline": "completed", "phases": results}
