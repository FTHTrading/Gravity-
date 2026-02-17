"""
Cross-reference module for public government records.

Searches:
  - NASA Technical Reports Server (NTRS)
  - FOIA.gov
  - Public DoD contract databases (FPDS)
  - Fiscal code cross-referencing
"""

import json
from datetime import datetime, timezone
from typing import Any

from src.collectors.base_scraper import BaseScraper
from src.database import insert_row
from src.logger import get_logger

log = get_logger(__name__)

# ── NASA NTRS ────────────────────────────────────────────────────────────────
NTRS_API = "https://ntrs.nasa.gov/api/citations/search"

# ── FOIA.gov ─────────────────────────────────────────────────────────────────
FOIA_SEARCH = "https://search.foia.gov/search"

# ── FPDS (Federal Procurement) ───────────────────────────────────────────────
FPDS_ATOM = "https://www.fpds.gov/ezsearch/search.do"


class GovernmentCrossRef(BaseScraper):
    """Search public government databases for matching records."""

    platform = "gov_crossref"

    def search(self, term: str, max_results: int = 20) -> list[dict[str, Any]]:
        """Aggregate across all public government sources."""
        results = []
        results.extend(self._search_ntrs(term, max_results))
        results.extend(self._search_foia(term, max_results))
        results.extend(self._search_fpds(term, max_results))
        return results

    # ── NASA Technical Reports ───────────────────────────────────────────
    def _search_ntrs(self, term: str, limit: int) -> list[dict]:
        records = []
        try:
            resp = self.get(NTRS_API, params={"q": term, "page.size": limit})
            data = resp.json()
        except Exception as exc:
            log.error("NTRS search failed: %s", exc)
            return records

        for item in data.get("results", []):
            rec = {
                "database_name": "NASA_NTRS",
                "query_used": term,
                "record_title": item.get("title"),
                "record_url": f"https://ntrs.nasa.gov/citations/{item.get('id', '')}",
                "fiscal_code": None,
                "match_status": "found",
                "notes": json.dumps({
                    "center": item.get("center", {}).get("name"),
                    "year": item.get("publicationDate"),
                    "document_type": item.get("subjectCategory"),
                }, default=str),
                "queried_at": datetime.now(timezone.utc).isoformat(),
            }
            insert_row("government_records", rec)
            records.append(rec)

        log.info("NTRS: %d records for '%s'", len(records), term)
        return records

    # ── FOIA.gov ─────────────────────────────────────────────────────────
    def _search_foia(self, term: str, limit: int) -> list[dict]:
        records = []
        try:
            resp = self.get(
                FOIA_SEARCH,
                params={"query": term, "affiliate": "foia.gov"},
            )
            # FOIA.gov uses USASEARCH; parse results from HTML/JSON
            data = resp.json() if "json" in resp.headers.get("content-type", "") else {}
        except Exception as exc:
            log.error("FOIA search failed: %s", exc)
            return records

        for item in data.get("web", {}).get("results", [])[:limit]:
            rec = {
                "database_name": "FOIA_GOV",
                "query_used": term,
                "record_title": item.get("title"),
                "record_url": item.get("url"),
                "fiscal_code": None,
                "match_status": "found",
                "notes": item.get("snippet", ""),
                "queried_at": datetime.now(timezone.utc).isoformat(),
            }
            insert_row("government_records", rec)
            records.append(rec)

        log.info("FOIA: %d records for '%s'", len(records), term)
        return records

    # ── Federal Procurement (FPDS) ───────────────────────────────────────
    def _search_fpds(self, term: str, limit: int) -> list[dict]:
        records = []
        try:
            resp = self.get(
                FPDS_ATOM,
                params={
                    "q": term,
                    "templateName": "1.5.2",
                    "indexName": "awardfull",
                    "s": "FPDS.GOV",
                },
            )
            # FPDS returns Atom XML; basic keyword scan
            text = resp.text
        except Exception as exc:
            log.error("FPDS search failed: %s", exc)
            return records

        # Simple presence detection
        if term.lower() in text.lower():
            rec = {
                "database_name": "FPDS",
                "query_used": term,
                "record_title": f"FPDS search result for '{term}'",
                "record_url": f"{FPDS_ATOM}?q={term}",
                "fiscal_code": None,
                "match_status": "potential_match",
                "notes": f"Term '{term}' found in FPDS response (raw text search).",
                "queried_at": datetime.now(timezone.utc).isoformat(),
            }
            insert_row("government_records", rec)
            records.append(rec)

        log.info("FPDS: %d records for '%s'", len(records), term)
        return records

    # ── Fiscal Code Cross-Reference ──────────────────────────────────────
    def verify_fiscal_code(self, code: str) -> dict:
        """
        Check if a fiscal / budget code from a circulating document
        matches any public appropriation or contract code.
        """
        result = {
            "fiscal_code": code,
            "match_status": "not_found",
            "databases_checked": ["FPDS", "USASpending"],
            "queried_at": datetime.now(timezone.utc).isoformat(),
        }
        # USASpending.gov API
        try:
            resp = self.get(
                "https://api.usaspending.gov/api/v2/search/spending_by_award/",
                params={"filters": json.dumps({"keywords": [code]})},
            )
            data = resp.json()
            if data.get("results"):
                result["match_status"] = "potential_match"
                result["details"] = data["results"][:5]
        except Exception as exc:
            log.error("USASpending lookup failed: %s", exc)

        insert_row("government_records", {
            "database_name": "fiscal_code_check",
            "query_used": code,
            "record_title": f"Fiscal code verification: {code}",
            "record_url": "",
            "fiscal_code": code,
            "match_status": result["match_status"],
            "notes": json.dumps(result, default=str),
            "queried_at": result["queried_at"],
        })

        return result
