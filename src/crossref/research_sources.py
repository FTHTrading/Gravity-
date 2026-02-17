"""
arXiv & DTIC research source scrapers.

Searches:
  - arXiv.org (preprint server) via Atom API
  - DTIC (Defense Technical Information Center) via web search

Categories targeted:
  - gr-qc   : General Relativity and Quantum Cosmology
  - hep-th  : High Energy Physics – Theory
  - astro-ph: Astrophysics
  - physics.space-ph: Space Physics
"""

import json
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from typing import Any

from src.collectors.base_scraper import BaseScraper
from src.config import ARXIV_API, DTIC_SEARCH
from src.database import insert_row
from src.logger import get_logger

log = get_logger(__name__)

# arXiv Atom namespace
ATOM_NS = {"atom": "http://www.w3.org/2005/Atom"}
ARXIV_NS = {"arxiv": "http://arxiv.org/schemas/atom"}


class ArxivScraper(BaseScraper):
    """Search arXiv preprint server for gravity/propulsion papers."""

    platform = "arxiv"

    def search(self, term: str, max_results: int = 20,
               categories: list[str] | None = None) -> list[dict[str, Any]]:
        """
        Search arXiv via the Atom API.

        Args:
            term: Search query
            max_results: Max papers to return
            categories: arXiv category filters (e.g. ["gr-qc", "hep-th"])
        """
        records = []

        # Build query with optional category filter
        query = f"all:{term}"
        if categories:
            cat_filter = " OR ".join(f"cat:{c}" for c in categories)
            query = f"({query}) AND ({cat_filter})"

        try:
            resp = self.get(ARXIV_API, params={
                "search_query": query,
                "start": 0,
                "max_results": max_results,
                "sortBy": "relevance",
                "sortOrder": "descending",
            })
            resp.raise_for_status()
        except Exception as exc:
            log.error("arXiv search failed for '%s': %s", term, exc)
            return records

        # Parse Atom XML
        try:
            root = ET.fromstring(resp.text)
        except ET.ParseError as exc:
            log.error("arXiv XML parse failed: %s", exc)
            return records

        for entry in root.findall("atom:entry", ATOM_NS):
            title = (entry.findtext("atom:title", "", ATOM_NS) or "").strip().replace("\n", " ")
            summary = (entry.findtext("atom:summary", "", ATOM_NS) or "").strip()[:500]
            published = entry.findtext("atom:published", "", ATOM_NS)

            # Authors
            authors = []
            for author_elem in entry.findall("atom:author", ATOM_NS):
                name = author_elem.findtext("atom:name", "", ATOM_NS)
                if name:
                    authors.append(name)

            # Links
            pdf_url = ""
            abs_url = ""
            for link in entry.findall("atom:link", ATOM_NS):
                if link.get("title") == "pdf":
                    pdf_url = link.get("href", "")
                elif link.get("rel") == "alternate":
                    abs_url = link.get("href", "")

            # Categories
            cats = [c.get("term", "") for c in entry.findall("atom:category", ATOM_NS)]

            # arXiv ID
            arxiv_id = (entry.findtext("atom:id", "", ATOM_NS) or "").split("/abs/")[-1]

            rec = {
                "search_term": term,
                "author_name": "; ".join(authors),
                "title": title,
                "journal": f"arXiv:{arxiv_id}",
                "year": int(published[:4]) if published and len(published) >= 4 else None,
                "doi": None,
                "institution": None,
                "abstract": summary,
                "source_db": "arXiv",
                "queried_at": datetime.now(timezone.utc).isoformat(),
            }
            insert_row("academic_records", rec)
            records.append(rec)

        log.info("arXiv: %d results for '%s'", len(records), term)
        return records

    def search_gravity_propulsion(self, term: str, max_results: int = 20) -> list[dict]:
        """Search specifically in gravity and propulsion categories."""
        return self.search(
            term, max_results,
            categories=["gr-qc", "hep-th", "astro-ph", "physics.space-ph", "physics.gen-ph"],
        )


class DTICScraper(BaseScraper):
    """Search DTIC for public defense research reports."""

    platform = "dtic"

    def search(self, term: str, max_results: int = 20) -> list[dict[str, Any]]:
        """
        Search DTIC public catalog.
        DTIC does not have a structured JSON API, so we do a basic
        web GET and extract what we can from the response.
        """
        records = []
        try:
            resp = self.get(DTIC_SEARCH, params={"q": term})
            text = resp.text
        except Exception as exc:
            log.error("DTIC search failed for '%s': %s", term, exc)
            return records

        # Basic presence check — DTIC returns HTML
        if term.lower() in text.lower():
            rec = {
                "database_name": "DTIC",
                "query_used": term,
                "record_title": f"DTIC search results for '{term}'",
                "record_url": f"{DTIC_SEARCH}?q={term.replace(' ', '+')}",
                "fiscal_code": None,
                "match_status": "potential_match",
                "notes": f"Term '{term}' found in DTIC public catalog response.",
                "queried_at": datetime.now(timezone.utc).isoformat(),
            }
            insert_row("government_records", rec)
            records.append(rec)
        else:
            rec = {
                "database_name": "DTIC",
                "query_used": term,
                "record_title": f"DTIC search: no match for '{term}'",
                "record_url": f"{DTIC_SEARCH}?q={term.replace(' ', '+')}",
                "fiscal_code": None,
                "match_status": "not_found",
                "notes": f"Term '{term}' not found in DTIC response.",
                "queried_at": datetime.now(timezone.utc).isoformat(),
            }
            insert_row("government_records", rec)
            records.append(rec)

        log.info("DTIC: %d results for '%s'", len(records), term)
        return records
