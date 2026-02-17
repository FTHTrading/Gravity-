"""
Reddit scraper using the public Pushshift-style APIs and Reddit JSON endpoints.
Collects posts and comments matching configured search terms.

Note: Requires no API key for basic .json endpoint access.
For higher volume, set REDDIT_CLIENT_ID and REDDIT_CLIENT_SECRET env vars.
"""

import os
from datetime import datetime, timezone
from typing import Any

from src.collectors.base_scraper import BaseScraper
from src.logger import get_logger

log = get_logger(__name__)

REDDIT_SEARCH_URL = "https://www.reddit.com/search.json"


class RedditScraper(BaseScraper):
    platform = "reddit"

    def search(self, term: str, max_results: int = 50) -> list[dict[str, Any]]:
        results: list[dict] = []
        params = {
            "q": term,
            "sort": "new",
            "limit": min(max_results, 100),
            "restrict_sr": False,
            "type": "link",
        }
        try:
            resp = self.get(REDDIT_SEARCH_URL, params=params)
            data = resp.json()
        except Exception as exc:
            log.error("Reddit search failed for '%s': %s", term, exc)
            return results

        for child in data.get("data", {}).get("children", []):
            post = child.get("data", {})
            record = {
                "platform": self.platform,
                "post_url": f"https://www.reddit.com{post.get('permalink', '')}",
                "author": post.get("author"),
                "post_text": post.get("title", "") + "\n" + post.get("selftext", ""),
                "timestamp_utc": datetime.fromtimestamp(
                    post.get("created_utc", 0), tz=timezone.utc
                ).isoformat(),
                "search_term": term,
                "metadata_json": str({
                    "subreddit": post.get("subreddit"),
                    "score": post.get("score"),
                    "num_comments": post.get("num_comments"),
                    "id": post.get("id"),
                }),
            }
            self.store_post(record)
            results.append(record)

        log.info("Reddit: %d results for '%s'", len(results), term)
        return results
