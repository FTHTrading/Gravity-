"""
Evidence Archiver – Orchestrates pinning all research data to IPFS.

Pulls data from the Project Anchor database and pins every category
of evidence to IPFS via the ProofChain, creating an immutable,
content-addressed archive of the entire investigation.

Archive categories:
    1. Social media posts (Reddit, forums)
    2. PDF documents (with metadata analysis)
    3. Government records (NASA NTRS, FOIA, FPDS)
    4. Academic records (CrossRef, Semantic Scholar, OpenAlex)
    5. Physics computation results
    6. Narrative analysis patterns
    7. Propagation graph edges
    8. Full research report (aggregate)
"""

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from src.database import query_rows
from src.config import REPORTS_DIR, DATA_DIR
from src.logger import get_logger
from src.ipfs.proof_chain import ProofChain

log = get_logger(__name__)


# ── Table → Evidence Type Mapping ────────────────────────────────────────
TABLE_CONFIG = {
    "social_posts": {
        "evidence_type": "social_post",
        "description_field": "title",
        "description_prefix": "Social post",
    },
    "documents": {
        "evidence_type": "document",
        "description_field": "filename",
        "description_prefix": "PDF document",
    },
    "government_records": {
        "evidence_type": "government_record",
        "description_field": "title",
        "description_prefix": "Government record",
    },
    "academic_records": {
        "evidence_type": "academic_record",
        "description_field": "title",
        "description_prefix": "Academic record",
    },
    "physics_comparisons": {
        "evidence_type": "physics_computation",
        "description_field": "comparison_type",
        "description_prefix": "Physics computation",
    },
    "narrative_patterns": {
        "evidence_type": "narrative_pattern",
        "description_field": "pattern_type",
        "description_prefix": "Narrative pattern",
    },
    "propagation_edges": {
        "evidence_type": "propagation_edge",
        "description_field": "edge_type",
        "description_prefix": "Propagation edge",
    },
}


class EvidenceArchiver:
    """
    Coordinates archiving all Project Anchor research data to IPFS.

    Usage:
        from src.ipfs.ipfs_client import IPFSClient
        from src.ipfs.evidence_archiver import EvidenceArchiver

        client = IPFSClient()
        archiver = EvidenceArchiver(client)
        report = archiver.archive_all()
    """

    def __init__(self, ipfs_client):
        self.ipfs = ipfs_client
        self.chain = ProofChain(ipfs_client)
        self.archive_report = {
            "archived_at": datetime.now(timezone.utc).isoformat(),
            "categories": {},
            "total_items_pinned": 0,
            "errors": [],
        }

    # ── Archive Everything ───────────────────────────────────────────────
    def archive_all(self, publish_ipns: bool = True) -> dict:
        """
        Archive all database evidence, local files, and aggregate report.

        Args:
            publish_ipns: If True, publish final chain head to IPNS

        Returns:
            Full archive report dict
        """
        log.info("=== IPFS Evidence Archiver: Full Archive ===")

        # 1. Archive each DB table
        for table, cfg in TABLE_CONFIG.items():
            self._archive_table(table, cfg)

        # 2. Archive local PDF files
        self._archive_pdfs()

        # 3. Archive existing report files
        self._archive_reports()

        # 4. Pin the aggregate manifest
        manifest = self.chain.export_chain_manifest()
        manifest_result = self.chain.add_evidence(
            manifest,
            evidence_type="archive_manifest",
            description="Complete archive manifest of all evidence",
            content_filename="archive_manifest.json",
        )
        self.archive_report["manifest_cid"] = manifest_result["evidence_cid"]
        self.archive_report["proof_chain_head"] = self.chain.head_cid
        self.archive_report["chain_length"] = self.chain.chain_length

        # 5. Publish to IPNS
        if publish_ipns:
            try:
                ipns_result = self.chain.publish_to_ipns()
                self.archive_report["ipns"] = ipns_result
                log.info("Published to IPNS: %s", ipns_result)
            except Exception as exc:
                self.archive_report["ipns_error"] = str(exc)
                log.warning("IPNS publish failed: %s", exc)

        log.info(
            "Archive complete: %d items pinned, %d errors",
            self.archive_report["total_items_pinned"],
            len(self.archive_report["errors"]),
        )
        return self.archive_report

    # ── Table Archiver ───────────────────────────────────────────────────
    def _archive_table(self, table: str, cfg: dict):
        """Archive all rows from a database table."""
        try:
            rows = query_rows(table)
        except Exception as exc:
            log.warning("Could not query table %s: %s", table, exc)
            self.archive_report["errors"].append({
                "table": table, "error": str(exc)
            })
            return

        if not rows:
            log.info("Table %s: no rows to archive.", table)
            return

        log.info("Archiving %d rows from %s ...", len(rows), table)
        pinned = 0

        # Pin individual rows as evidence
        for row in rows:
            try:
                desc_field = cfg.get("description_field", "id")
                desc = f"{cfg['description_prefix']}: {row.get(desc_field, 'N/A')}"
                self.chain.add_evidence(
                    row,
                    evidence_type=cfg["evidence_type"],
                    description=desc[:200],
                    content_filename=f"{table}_row.json",
                    metadata={"source_table": table},
                )
                pinned += 1
            except Exception as exc:
                self.archive_report["errors"].append({
                    "table": table,
                    "row_id": row.get("id"),
                    "error": str(exc),
                })

        # Also pin the full table export as a single object
        try:
            self.chain.add_evidence(
                rows,
                evidence_type=f"{cfg['evidence_type']}_batch",
                description=f"Full export: {table} ({len(rows)} records)",
                content_filename=f"{table}_full.json",
            )
            pinned += 1
        except Exception as exc:
            self.archive_report["errors"].append({
                "table": table, "batch": True, "error": str(exc)
            })

        self.archive_report["categories"][table] = {
            "rows_pinned": pinned,
            "total_rows": len(rows),
        }
        self.archive_report["total_items_pinned"] += pinned

    # ── PDF Archiver ─────────────────────────────────────────────────────
    def _archive_pdfs(self):
        """Archive any PDF files found in the data directory."""
        pdf_dir = Path(DATA_DIR)
        pdfs = list(pdf_dir.glob("**/*.pdf"))
        if not pdfs:
            log.info("No PDFs found in %s", DATA_DIR)
            return

        log.info("Archiving %d PDF files ...", len(pdfs))
        pinned = 0
        for pdf_path in pdfs:
            try:
                self.chain.add_file_evidence(
                    str(pdf_path),
                    evidence_type="pdf_document",
                    description=f"PDF: {pdf_path.name}",
                    metadata={"original_path": str(pdf_path)},
                )
                pinned += 1
            except Exception as exc:
                self.archive_report["errors"].append({
                    "file": str(pdf_path), "error": str(exc)
                })

        self.archive_report["categories"]["pdf_files"] = {"pinned": pinned}
        self.archive_report["total_items_pinned"] += pinned

    # ── Report Archiver ──────────────────────────────────────────────────
    def _archive_reports(self):
        """Archive any JSON reports in the reports directory."""
        report_dir = Path(REPORTS_DIR)
        if not report_dir.exists():
            return

        reports = list(report_dir.glob("*.json"))
        if not reports:
            return

        log.info("Archiving %d report files ...", len(reports))
        pinned = 0
        for report_path in reports:
            try:
                data = json.loads(report_path.read_text(encoding="utf-8"))
                self.chain.add_report_evidence(data, report_path.stem)
                pinned += 1
            except Exception as exc:
                self.archive_report["errors"].append({
                    "file": str(report_path), "error": str(exc)
                })

        self.archive_report["categories"]["reports"] = {"pinned": pinned}
        self.archive_report["total_items_pinned"] += pinned

    # ── Selective Archive ────────────────────────────────────────────────
    def archive_table(self, table_name: str) -> dict:
        """Archive a single table."""
        cfg = TABLE_CONFIG.get(table_name)
        if not cfg:
            return {"error": f"Unknown table: {table_name}"}

        self._archive_table(table_name, cfg)
        return self.archive_report

    def archive_physics_results(self, results: list[dict]) -> dict:
        """Directly archive physics results from the computation engine."""
        return self.chain.add_physics_evidence(results)

    # ── Status ───────────────────────────────────────────────────────────
    def get_archive_status(self) -> dict:
        """Return current archive statistics from the database."""
        rows = query_rows("ipfs_evidence")
        types = {}
        for r in rows:
            t = r.get("evidence_type", "unknown")
            types[t] = types.get(t, 0) + 1

        return {
            "total_pinned": len(rows),
            "by_type": types,
            "chain_head": self.chain.head_cid,
            "chain_length": self.chain.chain_length,
        }

    def verify_archive(self) -> dict:
        """Run full proof chain verification."""
        return self.chain.verify_chain()
