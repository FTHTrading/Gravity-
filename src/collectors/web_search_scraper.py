"""
Generic web search scraper using DuckDuckGo HTML endpoint.
Collects public search-engine indexed references to search terms.
"""

import re
from datetime import datetime, timezone
from typing import Any
from urllib.parse import unquote

from src.collectors.base_scraper import BaseScraper
from src.logger import get_logger

log = get_logger(__name__)

DDG_URL = "https://html.duckduckgo.com/html/"


class WebSearchScraper(BaseScraper):
    platform = "web_search"

    def search(self, term: str, max_results: int = 30) -> list[dict[str, Any]]:
        results: list[dict] = []
        try:
            resp = self.session.post(
                DDG_URL,
                data={"q": term},
                headers={"User-Agent": "Mozilla/5.0"},
                timeout=30,
            )
            resp.raise_for_status()
        except Exception as exc:
            log.error("Web search failed for '%s': %s", term, exc)
            return results

        # Parse result snippets from HTML
        links = re.findall(
            r'<a rel="nofollow" class="result__a" href="([^"]+)">(.*?)</a>',
            resp.text,
        )
        snippets = re.findall(
            r'<a class="result__snippet"[^>]*>(.*?)</a>',
            resp.text,
        )

        for i, (url, title) in enumerate(links[:max_results]):
            clean_url = unquote(url)
            snippet = snippets[i] if i < len(snippets) else ""
            # Strip HTML tags from snippet
            snippet = re.sub(r"<[^>]+>", "", snippet)
            title = re.sub(r"<[^>]+>", "", title)

            record = {
                "platform": self.platform,
                "post_url": clean_url,
                "author": None,
                "post_text": f"{title}\n{snippet}",
                "timestamp_utc": datetime.now(timezone.utc).isoformat(),
                "search_term": term,
                "metadata_json": str({"rank": i + 1}),
            }
            self.store_post(record)
            results.append(record)

        log.info("WebSearch: %d results for '%s'", len(results), term)
        return results
