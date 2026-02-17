"""
Base scraper class providing shared HTTP session management,
rate limiting, and standardized result formatting.
"""

import time
import hashlib
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Any

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from src.config import USER_AGENT, REQUEST_DELAY_SECONDS, MAX_RETRIES
from src.logger import get_logger
from src.database import insert_row

log = get_logger(__name__)


class BaseScraper(ABC):
    """Abstract base for all data-collection scrapers."""

    platform: str = "unknown"

    def __init__(self):
        self.session = self._build_session()
        self._last_request_time = 0.0

    # ── HTTP Session ─────────────────────────────────────────────────────
    @staticmethod
    def _build_session() -> requests.Session:
        session = requests.Session()
        session.headers.update({"User-Agent": USER_AGENT})
        retry = Retry(
            total=MAX_RETRIES,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504],
        )
        adapter = HTTPAdapter(max_retries=retry)
        session.mount("https://", adapter)
        session.mount("http://", adapter)
        return session

    # ── Rate Limiting ────────────────────────────────────────────────────
    def _throttle(self) -> None:
        elapsed = time.time() - self._last_request_time
        if elapsed < REQUEST_DELAY_SECONDS:
            time.sleep(REQUEST_DELAY_SECONDS - elapsed)
        self._last_request_time = time.time()

    def get(self, url: str, **kwargs) -> requests.Response:
        self._throttle()
        log.info("[%s] GET %s", self.platform, url)
        resp = self.session.get(url, timeout=30, **kwargs)
        resp.raise_for_status()
        return resp

    # ── Persistence Helpers ──────────────────────────────────────────────
    def store_post(self, data: dict) -> int:
        data.setdefault("platform", self.platform)
        data.setdefault("scraped_at", datetime.now(timezone.utc).isoformat())
        return insert_row("social_posts", data)

    @staticmethod
    def content_hash(text: str) -> str:
        return hashlib.sha256(text.encode("utf-8")).hexdigest()

    # ── Interface ────────────────────────────────────────────────────────
    @abstractmethod
    def search(self, term: str, max_results: int = 50) -> list[dict[str, Any]]:
        """Search the platform for the given term. Return list of post dicts."""
        ...

    def run_all_terms(self, terms: list[str], max_results: int = 50) -> list[dict]:
        """Execute search across all configured terms."""
        all_results = []
        for term in terms:
            log.info("[%s] Searching: %s", self.platform, term)
            try:
                results = self.search(term, max_results=max_results)
                all_results.extend(results)
            except Exception as exc:
                log.error("[%s] Error searching '%s': %s", self.platform, term, exc)
        log.info("[%s] Total results collected: %d", self.platform, len(all_results))
        return all_results
