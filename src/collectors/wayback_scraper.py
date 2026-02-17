"""
Web archive / Wayback Machine scraper.
Queries the CDX API to find earliest archived references to search terms.
"""

from datetime import datetime, timezone
from typing import Any

from src.collectors.base_scraper import BaseScraper
from src.logger import get_logger

log = get_logger(__name__)

CDX_API = "https://web.archive.org/cdx/search/cdx"


class WaybackScraper(BaseScraper):
    platform = "wayback"

    def search(self, term: str, max_results: int = 50) -> list[dict[str, Any]]:
        """
        Search the Wayback Machine CDX API for URLs containing the term.
        Returns archived page records sorted by timestamp (earliest first).
        """
        results: list[dict] = []
        params = {
            "url": f"*{term}*",
            "output": "json",
            "fl": "timestamp,original,mimetype,statuscode,length",
            "limit": max_results,
            "sort": "asc",  # earliest first
        }
        try:
            resp = self.get(CDX_API, params=params)
            rows = resp.json()
        except Exception as exc:
            log.error("Wayback search failed for '%s': %s", term, exc)
            return results

        if not rows or len(rows) < 2:
            return results

        headers = rows[0]
        for row in rows[1:]:
            entry = dict(zip(headers, row))
            ts = entry.get("timestamp", "")
            try:
                dt = datetime.strptime(ts, "%Y%m%d%H%M%S").replace(tzinfo=timezone.utc)
            except ValueError:
                dt = None

            record = {
                "platform": self.platform,
                "post_url": f"https://web.archive.org/web/{ts}/{entry.get('original', '')}",
                "author": None,
                "post_text": None,
                "timestamp_utc": dt.isoformat() if dt else ts,
                "search_term": term,
                "metadata_json": str(entry),
            }
            self.store_post(record)
            results.append(record)

        log.info("Wayback: %d archived references for '%s'", len(results), term)
        return results
