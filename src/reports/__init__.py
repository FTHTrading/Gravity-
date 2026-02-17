"""
Report generator – assembles all module outputs into structured reports.

Produces:
  1. Chronological origin timeline
  2. Document structural comparison report
  3. Public-record cross-reference report
  4. Academic identity verification status
  5. Physics comparison data table
  6. Narrative pattern mapping
  7. Source index list
"""

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from src.config import REPORTS_DIR
from src.database import query_rows
from src.logger import get_logger

log = get_logger(__name__)


class ReportGenerator:
    """Generate structured JSON and text reports from collected data."""

    def generate_all(self) -> dict[str, Path]:
        """Generate all report files and return paths."""
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        reports = {}

        reports["timeline"] = self._report_timeline(timestamp)
        reports["documents"] = self._report_documents(timestamp)
        reports["government_crossref"] = self._report_government(timestamp)
        reports["academic_verification"] = self._report_academic(timestamp)
        reports["physics_comparison"] = self._report_physics(timestamp)
        reports["narrative_patterns"] = self._report_narratives(timestamp)
        reports["source_index"] = self._report_source_index(timestamp)

        log.info("All reports generated: %s", {k: str(v) for k, v in reports.items()})
        return reports

    def _save_json(self, data: Any, name: str, timestamp: str) -> Path:
        path = REPORTS_DIR / f"{name}_{timestamp}.json"
        path.write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")
        return path

    def _report_timeline(self, ts: str) -> Path:
        posts = query_rows("social_posts")
        posts.sort(key=lambda p: p.get("timestamp_utc", ""))
        return self._save_json({
            "report": "Chronological Origin Timeline",
            "generated_utc": datetime.now(timezone.utc).isoformat(),
            "total_entries": len(posts),
            "entries": posts,
        }, "timeline", ts)

    def _report_documents(self, ts: str) -> Path:
        docs = query_rows("documents")
        return self._save_json({
            "report": "Document Structural Comparison Report",
            "generated_utc": datetime.now(timezone.utc).isoformat(),
            "total_documents": len(docs),
            "documents": docs,
        }, "documents", ts)

    def _report_government(self, ts: str) -> Path:
        records = query_rows("government_records")
        return self._save_json({
            "report": "Public-Record Cross-Reference Report",
            "generated_utc": datetime.now(timezone.utc).isoformat(),
            "total_records": len(records),
            "records": records,
        }, "government_crossref", ts)

    def _report_academic(self, ts: str) -> Path:
        records = query_rows("academic_records")
        return self._save_json({
            "report": "Academic Identity Verification Status",
            "generated_utc": datetime.now(timezone.utc).isoformat(),
            "total_records": len(records),
            "records": records,
        }, "academic_verification", ts)

    def _report_physics(self, ts: str) -> Path:
        records = query_rows("physics_comparisons")
        return self._save_json({
            "report": "Physics Comparison Data Table",
            "generated_utc": datetime.now(timezone.utc).isoformat(),
            "total_computations": len(records),
            "computations": records,
        }, "physics_comparison", ts)

    def _report_narratives(self, ts: str) -> Path:
        records = query_rows("narrative_patterns")
        return self._save_json({
            "report": "Narrative Pattern Mapping",
            "generated_utc": datetime.now(timezone.utc).isoformat(),
            "total_patterns": len(records),
            "patterns": records,
        }, "narrative_patterns", ts)

    def _report_source_index(self, ts: str) -> Path:
        posts = query_rows("social_posts")
        urls = sorted(set(p.get("post_url", "") for p in posts if p.get("post_url")))
        return self._save_json({
            "report": "Source Index List",
            "generated_utc": datetime.now(timezone.utc).isoformat(),
            "total_unique_sources": len(urls),
            "sources": urls,
        }, "source_index", ts)
