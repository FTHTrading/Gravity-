"""
Academic record cross-reference module.

Searches public academic databases for:
  - Author identity verification
  - Publication history
  - Institutional affiliation
  - Topic-specific publications

Databases used:
  - CrossRef (open API)
  - Semantic Scholar (open API)
  - OpenAlex (open API)
"""

import json
from datetime import datetime, timezone
from typing import Any

from src.collectors.base_scraper import BaseScraper
from src.database import insert_row
from src.logger import get_logger

log = get_logger(__name__)

CROSSREF_API = "https://api.crossref.org/works"
SEMANTIC_SCHOLAR_API = "https://api.semanticscholar.org/graph/v1/paper/search"
OPENALEX_API = "https://api.openalex.org/works"
OPENALEX_AUTHORS = "https://api.openalex.org/authors"


class AcademicCrossRef(BaseScraper):
    """Search open academic databases and record findings."""

    platform = "academic"

    def search(self, term: str, max_results: int = 20) -> list[dict[str, Any]]:
        results = []
        results.extend(self._search_crossref(term, max_results))
        results.extend(self._search_semantic_scholar(term, max_results))
        results.extend(self._search_openalex(term, max_results))
        return results

    # ── CrossRef ─────────────────────────────────────────────────────────
    def _search_crossref(self, term: str, limit: int) -> list[dict]:
        records = []
        try:
            resp = self.get(CROSSREF_API, params={
                "query": term,
                "rows": limit,
                "sort": "relevance",
            })
            data = resp.json()
        except Exception as exc:
            log.error("CrossRef search failed: %s", exc)
            return records

        for item in data.get("message", {}).get("items", []):
            authors = item.get("author", [])
            author_str = "; ".join(
                f"{a.get('given', '')} {a.get('family', '')}".strip()
                for a in authors
            )
            rec = {
                "search_term": term,
                "author_name": author_str,
                "title": " ".join(item.get("title", [])),
                "journal": " ".join(item.get("container-title", [])),
                "year": (item.get("published-print") or item.get("published-online") or {})
                    .get("date-parts", [[None]])[0][0],
                "doi": item.get("DOI"),
                "institution": json.dumps([
                    a.get("affiliation", []) for a in authors
                ], default=str),
                "abstract": None,
                "source_db": "CrossRef",
                "queried_at": datetime.now(timezone.utc).isoformat(),
            }
            insert_row("academic_records", rec)
            records.append(rec)

        log.info("CrossRef: %d records for '%s'", len(records), term)
        return records

    # ── Semantic Scholar ─────────────────────────────────────────────────
    def _search_semantic_scholar(self, term: str, limit: int) -> list[dict]:
        records = []
        try:
            resp = self.get(SEMANTIC_SCHOLAR_API, params={
                "query": term,
                "limit": min(limit, 100),
                "fields": "title,authors,year,abstract,externalIds,venue",
            })
            data = resp.json()
        except Exception as exc:
            log.error("Semantic Scholar search failed: %s", exc)
            return records

        for item in data.get("data", []):
            authors = item.get("authors", [])
            author_str = "; ".join(a.get("name", "") for a in authors)
            rec = {
                "search_term": term,
                "author_name": author_str,
                "title": item.get("title"),
                "journal": item.get("venue"),
                "year": item.get("year"),
                "doi": (item.get("externalIds") or {}).get("DOI"),
                "institution": None,
                "abstract": (item.get("abstract") or "")[:500],
                "source_db": "SemanticScholar",
                "queried_at": datetime.now(timezone.utc).isoformat(),
            }
            insert_row("academic_records", rec)
            records.append(rec)

        log.info("SemanticScholar: %d records for '%s'", len(records), term)
        return records

    # ── OpenAlex ─────────────────────────────────────────────────────────
    def _search_openalex(self, term: str, limit: int) -> list[dict]:
        records = []
        try:
            resp = self.get(OPENALEX_API, params={
                "search": term,
                "per_page": min(limit, 50),
            })
            data = resp.json()
        except Exception as exc:
            log.error("OpenAlex search failed: %s", exc)
            return records

        for item in data.get("results", []):
            authorships = item.get("authorships", [])
            author_str = "; ".join(
                a.get("author", {}).get("display_name", "") for a in authorships
            )
            institutions = [
                inst.get("display_name")
                for a in authorships
                for inst in a.get("institutions", [])
                if inst.get("display_name")
            ]
            rec = {
                "search_term": term,
                "author_name": author_str,
                "title": item.get("display_name"),
                "journal": (item.get("primary_location") or {}).get("source", {}).get("display_name") if item.get("primary_location") else None,
                "year": item.get("publication_year"),
                "doi": item.get("doi"),
                "institution": json.dumps(institutions),
                "abstract": None,
                "source_db": "OpenAlex",
                "queried_at": datetime.now(timezone.utc).isoformat(),
            }
            insert_row("academic_records", rec)
            records.append(rec)

        log.info("OpenAlex: %d records for '%s'", len(records), term)
        return records

    # ── Author Identity Search ───────────────────────────────────────────
    def search_author(self, name: str) -> list[dict]:
        """Search specifically for an author across databases."""
        results = []

        # OpenAlex author search
        try:
            resp = self.get(OPENALEX_AUTHORS, params={
                "search": name,
                "per_page": 10,
            })
            data = resp.json()
            for item in data.get("results", []):
                results.append({
                    "name": item.get("display_name"),
                    "works_count": item.get("works_count"),
                    "cited_by_count": item.get("cited_by_count"),
                    "affiliations": [
                        aff.get("institution", {}).get("display_name")
                        for aff in item.get("affiliations", [])
                    ],
                    "source": "OpenAlex",
                })
        except Exception as exc:
            log.error("OpenAlex author search failed: %s", exc)

        log.info("Author search '%s': %d profiles found", name, len(results))
        return results
