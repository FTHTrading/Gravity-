"""
Audit Report Generator – Comprehensive Evidence Reports

Provides:
  - Full evidence timeline generation
  - CID table with signature verification status
  - Snapshot verification history
  - IPNS pointer state
  - Physics model results summary
  - FOIA document inventory
  - Investigation case summaries
  - Export to JSON, Markdown, and HTML

Generates institutional-grade audit reports suitable for
third-party verification of the entire evidence chain.
"""

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from src.config import AUDIT_DIR
from src.database import query_rows, count_rows, get_connection
from src.logger import get_logger

log = get_logger(__name__)


class AuditReportGenerator:
    """Generates comprehensive audit reports of all system evidence."""

    def __init__(self, output_dir: Path = AUDIT_DIR):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def generate_full_report(self) -> dict:
        """Generate a complete audit report covering all system state."""
        log.info("Generating comprehensive audit report...")

        now = datetime.now(timezone.utc).isoformat()
        timestamp_slug = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")

        report = {
            "report_type": "full_audit",
            "system": "Project Anchor Research System",
            "version": "2.0 – Phase II",
            "generated_at": now,
            "sections": {},
        }

        # Section 1: Database Overview
        report["sections"]["database_overview"] = self._database_overview()

        # Section 2: Evidence Chain (IPFS)
        report["sections"]["evidence_chain"] = self._evidence_chain_summary()

        # Section 3: Cryptographic Keys
        report["sections"]["crypto_keys"] = self._crypto_key_summary()

        # Section 4: Merkle Snapshots
        report["sections"]["merkle_snapshots"] = self._merkle_snapshot_summary()

        # Section 5: Physics Results
        report["sections"]["physics_results"] = self._physics_summary()

        # Section 6: FOIA Documents
        report["sections"]["foia_documents"] = self._foia_summary()

        # Section 7: Investigation Cases
        report["sections"]["investigations"] = self._investigation_summary()

        # Section 8: Scientist Cases
        report["sections"]["scientist_cases"] = self._scientist_summary()

        # Section 9: Audit Trail
        report["sections"]["audit_trail"] = self._audit_trail()

        # Section 10: Taxonomy Coverage
        report["sections"]["taxonomy"] = self._taxonomy_summary()

        # Export in multiple formats
        json_path = self._export_json(report, timestamp_slug)
        md_path = self._export_markdown(report, timestamp_slug)
        html_path = self._export_html(report, timestamp_slug)

        report["export_paths"] = {
            "json": str(json_path),
            "markdown": str(md_path),
            "html": str(html_path),
        }

        log.info("Audit report generated: %s", json_path)
        return report

    # ── Report Sections ──────────────────────────────────────────────────

    def _database_overview(self) -> dict:
        """Summary of all database tables and row counts."""
        tables = [
            "social_posts", "documents", "academic_records",
            "government_records", "propagation_edges",
            "physics_comparisons", "narrative_patterns",
            "ipfs_evidence", "taxonomy_entries",
            "crypto_keys", "merkle_snapshots",
            "foia_documents", "investigation_cases",
            "case_claims", "scientist_cases", "audit_logs",
        ]
        counts = {}
        total = 0
        for table in tables:
            try:
                c = count_rows(table)
                counts[table] = c
                total += c
            except Exception:
                counts[table] = 0
        return {
            "total_tables": len(tables),
            "total_rows": total,
            "table_counts": counts,
        }

    def _evidence_chain_summary(self) -> dict:
        """IPFS evidence chain status."""
        evidence = query_rows("ipfs_evidence", "1=1 ORDER BY sequence DESC LIMIT 100")
        signed = [e for e in evidence if e.get("signature")]
        return {
            "total_evidence_items": count_rows("ipfs_evidence"),
            "signed_items": len(signed),
            "unsigned_items": len(evidence) - len(signed),
            "latest_items": [
                {
                    "cid": e["evidence_cid"],
                    "type": e["evidence_type"],
                    "description": e.get("description", ""),
                    "signed": bool(e.get("signature")),
                    "pinned_at": e["pinned_at"],
                }
                for e in evidence[:10]
            ],
        }

    def _crypto_key_summary(self) -> dict:
        """Cryptographic key inventory."""
        keys = query_rows("crypto_keys")
        return {
            "total_keys": len(keys),
            "active_keys": len([k for k in keys if k.get("is_active")]),
            "keys": [
                {
                    "name": k["key_name"],
                    "algorithm": k["algorithm"],
                    "fingerprint": k["fingerprint"],
                    "created_at": k["created_at"],
                    "active": bool(k["is_active"]),
                }
                for k in keys
            ],
        }

    def _merkle_snapshot_summary(self) -> dict:
        """Merkle snapshot verification history."""
        snapshots = query_rows("merkle_snapshots", "1=1 ORDER BY id DESC LIMIT 20")
        return {
            "total_snapshots": count_rows("merkle_snapshots"),
            "snapshots": [
                {
                    "root_hash": s["root_hash"][:32] + "...",
                    "total_rows": s["total_rows"],
                    "ipfs_cid": s.get("ipfs_cid"),
                    "status": s["status"],
                    "created_at": s["created_at"],
                    "verified_at": s.get("verified_at"),
                }
                for s in snapshots
            ],
        }

    def _physics_summary(self) -> dict:
        """Physics computation results summary."""
        results = query_rows("physics_comparisons", "1=1 ORDER BY id")
        return {
            "total_computations": len(results),
            "results": [
                {
                    "description": r["description"],
                    "equation": r.get("equation", ""),
                    "value": r["value"],
                    "units": r["units"],
                }
                for r in results
            ],
        }

    def _foia_summary(self) -> dict:
        """FOIA document inventory."""
        docs = query_rows("foia_documents", "1=1 ORDER BY id DESC LIMIT 50")
        agencies = {}
        for d in docs:
            ag = d.get("source_agency", "unknown")
            agencies[ag] = agencies.get(ag, 0) + 1
        return {
            "total_documents": count_rows("foia_documents"),
            "by_agency": agencies,
            "recent": [
                {
                    "title": d.get("title", ""),
                    "agency": d["source_agency"],
                    "classification": d.get("classification", ""),
                    "authenticity": d.get("authenticity", ""),
                    "ingested_at": d["ingested_at"],
                }
                for d in docs[:10]
            ],
        }

    def _investigation_summary(self) -> dict:
        """Investigation case summaries."""
        cases = query_rows("investigation_cases", "1=1 ORDER BY id DESC")
        return {
            "total_cases": len(cases),
            "cases": [
                {
                    "name": c["case_name"],
                    "type": c["case_type"],
                    "subject": c.get("subject", ""),
                    "status": c["status"],
                    "claims": count_rows("case_claims", "case_id = ?", (c["id"],)),
                }
                for c in cases
            ],
        }

    def _scientist_summary(self) -> dict:
        """Scientist cases overview."""
        cases = query_rows("scientist_cases", "1=1 ORDER BY death_year")
        return {
            "total_cases": len(cases),
            "cases": [
                {
                    "name": c["name"],
                    "field": c.get("field", ""),
                    "death_year": c.get("death_year"),
                    "cause": c.get("cause_of_death", ""),
                    "disputed": bool(c.get("disputed", 0)),
                }
                for c in cases
            ],
        }

    def _audit_trail(self) -> dict:
        """Audit log summary."""
        logs = query_rows("audit_logs", "1=1 ORDER BY id DESC LIMIT 50")
        ops = {}
        for l in logs:
            op = l["operation"]
            ops[op] = ops.get(op, 0) + 1
        return {
            "total_entries": count_rows("audit_logs"),
            "operations_summary": ops,
            "recent_entries": [
                {
                    "operation": l["operation"],
                    "module": l.get("module", ""),
                    "status": l["status"],
                    "cid": l.get("cid_reference", ""),
                    "timestamp": l["created_at"],
                }
                for l in logs[:20]
            ],
        }

    def _taxonomy_summary(self) -> dict:
        """Taxonomy knowledge base coverage."""
        total = count_rows("taxonomy_entries")
        with get_connection() as conn:
            categories = conn.execute(
                "SELECT category, COUNT(*) as cnt FROM taxonomy_entries GROUP BY category"
            ).fetchall()
        cat_dict = {r["category"]: r["cnt"] for r in categories}
        return {
            "total_entries": total,
            "categories": cat_dict,
        }

    # ── Export Formats ───────────────────────────────────────────────────

    def _export_json(self, report: dict, timestamp: str) -> Path:
        path = self.output_dir / f"audit_{timestamp}.json"
        path.write_text(
            json.dumps(report, indent=2, default=str, ensure_ascii=False),
            encoding="utf-8",
        )
        return path

    def _export_markdown(self, report: dict, timestamp: str) -> Path:
        path = self.output_dir / f"audit_{timestamp}.md"
        lines = []
        lines.append("# Project Anchor – Audit Report")
        lines.append(f"\n**Generated:** {report['generated_at']}")
        lines.append(f"**Version:** {report['version']}")
        lines.append("")

        sections = report.get("sections", {})

        # Database Overview
        if "database_overview" in sections:
            db = sections["database_overview"]
            lines.append("## 1. Database Overview")
            lines.append(f"- **Total tables:** {db['total_tables']}")
            lines.append(f"- **Total rows:** {db['total_rows']}")
            lines.append("")
            lines.append("| Table | Rows |")
            lines.append("|-------|------|")
            for tbl, cnt in db["table_counts"].items():
                lines.append(f"| {tbl} | {cnt} |")
            lines.append("")

        # Evidence Chain
        if "evidence_chain" in sections:
            ev = sections["evidence_chain"]
            lines.append("## 2. Evidence Chain (IPFS)")
            lines.append(f"- **Total items:** {ev['total_evidence_items']}")
            lines.append(f"- **Signed:** {ev['signed_items']}")
            lines.append(f"- **Unsigned:** {ev['unsigned_items']}")
            lines.append("")

        # Crypto Keys
        if "crypto_keys" in sections:
            ck = sections["crypto_keys"]
            lines.append("## 3. Cryptographic Keys")
            lines.append(f"- **Total keys:** {ck['total_keys']}")
            lines.append(f"- **Active keys:** {ck['active_keys']}")
            lines.append("")
            if ck.get("keys"):
                lines.append("| Name | Algorithm | Fingerprint | Active |")
                lines.append("|------|-----------|-------------|--------|")
                for k in ck["keys"]:
                    lines.append(
                        f"| {k['name']} | {k['algorithm']} | "
                        f"`{k['fingerprint']}` | {'Yes' if k['active'] else 'No'} |"
                    )
                lines.append("")

        # Merkle Snapshots
        if "merkle_snapshots" in sections:
            ms = sections["merkle_snapshots"]
            lines.append("## 4. Merkle Snapshots")
            lines.append(f"- **Total snapshots:** {ms['total_snapshots']}")
            lines.append("")

        # Physics
        if "physics_results" in sections:
            ph = sections["physics_results"]
            lines.append("## 5. Physics Computations")
            lines.append(f"- **Total computations:** {ph['total_computations']}")
            lines.append("")

        # FOIA
        if "foia_documents" in sections:
            foia = sections["foia_documents"]
            lines.append("## 6. FOIA Documents")
            lines.append(f"- **Total documents:** {foia['total_documents']}")
            if foia.get("by_agency"):
                for ag, cnt in foia["by_agency"].items():
                    lines.append(f"  - {ag}: {cnt}")
            lines.append("")

        # Investigations
        if "investigations" in sections:
            inv = sections["investigations"]
            lines.append("## 7. Investigation Cases")
            lines.append(f"- **Total cases:** {inv['total_cases']}")
            lines.append("")

        # Scientist Cases
        if "scientist_cases" in sections:
            sc = sections["scientist_cases"]
            lines.append("## 8. Scientist Cases")
            lines.append(f"- **Total cases:** {sc['total_cases']}")
            lines.append("")
            if sc.get("cases"):
                lines.append("| Name | Field | Year | Cause | Disputed |")
                lines.append("|------|-------|------|-------|----------|")
                for c in sc["cases"]:
                    lines.append(
                        f"| {c['name']} | {c.get('field','')} | "
                        f"{c.get('death_year','')} | {c.get('cause','')} | "
                        f"{'Yes' if c.get('disputed') else 'No'} |"
                    )
                lines.append("")

        # Audit Trail
        if "audit_trail" in sections:
            at = sections["audit_trail"]
            lines.append("## 9. Audit Trail")
            lines.append(f"- **Total entries:** {at['total_entries']}")
            lines.append("")

        # Taxonomy
        if "taxonomy" in sections:
            tx = sections["taxonomy"]
            lines.append("## 10. Taxonomy Coverage")
            lines.append(f"- **Total entries:** {tx['total_entries']}")
            lines.append("")

        lines.append("---")
        lines.append("*Report generated by Project Anchor Phase II Audit Engine*")

        path.write_text("\n".join(lines), encoding="utf-8")
        return path

    def _export_html(self, report: dict, timestamp: str) -> Path:
        """Generate an HTML audit report."""
        path = self.output_dir / f"audit_{timestamp}.html"

        sections = report.get("sections", {})
        db = sections.get("database_overview", {})
        ev = sections.get("evidence_chain", {})
        ck = sections.get("crypto_keys", {})

        table_rows = ""
        for tbl, cnt in db.get("table_counts", {}).items():
            table_rows += f"<tr><td>{tbl}</td><td>{cnt}</td></tr>\n"

        html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>Project Anchor – Audit Report</title>
    <style>
        body {{ font-family: 'Segoe UI', sans-serif; max-width: 1000px;
               margin: 40px auto; padding: 20px; background: #0d1117; color: #c9d1d9; }}
        h1 {{ color: #58a6ff; border-bottom: 2px solid #30363d; padding-bottom: 10px; }}
        h2 {{ color: #79c0ff; margin-top: 30px; }}
        table {{ border-collapse: collapse; width: 100%; margin: 15px 0; }}
        th, td {{ border: 1px solid #30363d; padding: 8px 12px; text-align: left; }}
        th {{ background: #161b22; color: #58a6ff; }}
        tr:nth-child(even) {{ background: #161b22; }}
        .stat {{ font-size: 1.4em; color: #58a6ff; font-weight: bold; }}
        .grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
                 gap: 15px; margin: 20px 0; }}
        .card {{ background: #161b22; border: 1px solid #30363d; border-radius: 8px;
                 padding: 15px; }}
        .card h3 {{ margin: 0 0 8px 0; color: #79c0ff; font-size: 0.9em; }}
        .card .value {{ font-size: 1.8em; color: #58a6ff; }}
        code {{ background: #1f2937; padding: 2px 6px; border-radius: 3px; }}
        footer {{ margin-top: 40px; border-top: 1px solid #30363d;
                  padding-top: 15px; color: #8b949e; font-size: 0.85em; }}
    </style>
</head>
<body>
    <h1>Project Anchor – Audit Report</h1>
    <p>Generated: <strong>{report['generated_at']}</strong> | Version: {report['version']}</p>

    <div class="grid">
        <div class="card">
            <h3>Total DB Rows</h3>
            <div class="value">{db.get('total_rows', 0)}</div>
        </div>
        <div class="card">
            <h3>Evidence Items</h3>
            <div class="value">{ev.get('total_evidence_items', 0)}</div>
        </div>
        <div class="card">
            <h3>Crypto Keys</h3>
            <div class="value">{ck.get('total_keys', 0)}</div>
        </div>
        <div class="card">
            <h3>Tables</h3>
            <div class="value">{db.get('total_tables', 0)}</div>
        </div>
    </div>

    <h2>Database Tables</h2>
    <table>
        <thead><tr><th>Table</th><th>Rows</th></tr></thead>
        <tbody>{table_rows}</tbody>
    </table>

    <footer>
        Project Anchor Phase II Audit Engine &bull; Immutable Research Intelligence System
    </footer>
</body>
</html>"""

        path.write_text(html, encoding="utf-8")
        return path
