"""
Dashboard visualization module.

Provides a local web-based dashboard (Dash/Plotly) for:
  - Propagation timeline chart
  - Narrative pattern distribution
  - Physics comparison data table
  - Document analysis summary
  - Cross-reference status board
  - Post volume over time

Can also export static HTML reports.
"""

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from src.config import REPORTS_DIR
from src.database import query_rows
from src.logger import get_logger

log = get_logger(__name__)

try:
    import plotly.graph_objects as go
    import plotly.express as px
    from plotly.subplots import make_subplots
except ImportError:
    go = None
    px = None
    log.warning("Plotly not installed; dashboard will generate static HTML only.")

try:
    import dash
    from dash import dcc, html, dash_table
except ImportError:
    dash = None
    log.warning("Dash not installed; interactive dashboard unavailable. Static reports still work.")


class Dashboard:
    """Generate visualizations and launch interactive dashboard."""

    def __init__(self):
        self.data_cache: dict[str, Any] = {}

    # ── Data Loading ─────────────────────────────────────────────────────
    def load_data(self) -> None:
        """Pull all current data from the SQLite database."""
        self.data_cache = {
            "social_posts": query_rows("social_posts"),
            "documents": query_rows("documents"),
            "academic_records": query_rows("academic_records"),
            "government_records": query_rows("government_records"),
            "physics_comparisons": query_rows("physics_comparisons"),
            "narrative_patterns": query_rows("narrative_patterns"),
            "propagation_edges": query_rows("propagation_edges"),
            "ipfs_evidence": query_rows("ipfs_evidence"),
            "taxonomy_entries": query_rows("taxonomy_entries"),
        }
        log.info("Dashboard data loaded: %s",
                 {k: len(v) for k, v in self.data_cache.items()})

    # ── Static HTML Report ───────────────────────────────────────────────
    def generate_static_report(self, filename: str = "research_report.html") -> Path:
        """Generate a self-contained HTML report with all findings."""
        self.load_data()

        sections = []
        sections.append(self._section_header())
        sections.append(self._section_timeline())
        sections.append(self._section_physics_table())
        sections.append(self._section_documents())
        sections.append(self._section_academic())
        sections.append(self._section_government())
        sections.append(self._section_narratives())
        sections.append(self._section_source_index())
        sections.append(self._section_ipfs_evidence())
        sections.append(self._section_taxonomy())

        html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Project Anchor – Research Report</title>
    <style>
        body {{ font-family: 'Segoe UI', Tahoma, sans-serif; margin: 40px; background: #f5f5f5; color: #222; }}
        .container {{ max-width: 1200px; margin: 0 auto; background: #fff; padding: 30px; border-radius: 8px; box-shadow: 0 2px 8px rgba(0,0,0,0.1); }}
        h1 {{ border-bottom: 3px solid #333; padding-bottom: 10px; }}
        h2 {{ color: #444; border-bottom: 1px solid #ddd; padding-bottom: 5px; margin-top: 30px; }}
        table {{ border-collapse: collapse; width: 100%; margin: 15px 0; font-size: 14px; }}
        th, td {{ border: 1px solid #ddd; padding: 8px 12px; text-align: left; }}
        th {{ background: #f0f0f0; font-weight: 600; }}
        tr:nth-child(even) {{ background: #fafafa; }}
        .stat {{ display: inline-block; background: #e8f4fd; padding: 8px 16px; margin: 4px; border-radius: 4px; }}
        .timestamp {{ color: #888; font-size: 12px; }}
        code {{ background: #f4f4f4; padding: 2px 6px; border-radius: 3px; font-size: 13px; }}
    </style>
</head>
<body>
<div class="container">
{"".join(sections)}
<hr>
<p class="timestamp">Report generated: {datetime.now(timezone.utc).isoformat()} UTC</p>
<p><em>This report contains structured data only. No conclusions or belief statements.</em></p>
</div>
</body>
</html>"""

        path = REPORTS_DIR / filename
        path.write_text(html_content, encoding="utf-8")
        log.info("Static report saved: %s", path)
        return path

    # ── Report Sections ──────────────────────────────────────────────────
    def _section_header(self) -> str:
        posts = self.data_cache.get("social_posts", [])
        docs = self.data_cache.get("documents", [])
        return f"""
<h1>Project Anchor – Forensic Research Report</h1>
<p>Case: <strong>August 12 Gravity Event – Thomas Webb</strong></p>
<div>
    <span class="stat">Posts collected: {len(posts)}</span>
    <span class="stat">Documents analyzed: {len(docs)}</span>
    <span class="stat">Academic records: {len(self.data_cache.get('academic_records', []))}</span>
    <span class="stat">Gov records checked: {len(self.data_cache.get('government_records', []))}</span>
    <span class="stat">Physics computations: {len(self.data_cache.get('physics_comparisons', []))}</span>
    <span class="stat">Taxonomy entries: {len(self.data_cache.get('taxonomy_entries', []))}</span>
</div>"""

    def _section_timeline(self) -> str:
        posts = sorted(
            self.data_cache.get("social_posts", []),
            key=lambda p: p.get("timestamp_utc", ""),
        )
        if not posts:
            return "<h2>Chronological Origin Timeline</h2><p>No data collected yet.</p>"

        rows = ""
        for p in posts[:50]:
            rows += f"""<tr>
    <td>{p.get('timestamp_utc', 'N/A')}</td>
    <td>{p.get('platform', '')}</td>
    <td><a href="{p.get('post_url', '#')}">{(p.get('post_text') or '')[:80]}...</a></td>
    <td>{p.get('author', 'N/A')}</td>
    <td>{p.get('search_term', '')}</td>
</tr>"""
        return f"""
<h2>Chronological Origin Timeline</h2>
<table>
<tr><th>Timestamp (UTC)</th><th>Platform</th><th>Content Preview</th><th>Author</th><th>Search Term</th></tr>
{rows}
</table>"""

    def _section_physics_table(self) -> str:
        physics = self.data_cache.get("physics_comparisons", [])
        if not physics:
            return "<h2>Physics Comparison Data Table</h2><p>No computations recorded.</p>"

        rows = ""
        for p in physics:
            rows += f"""<tr>
    <td>{p.get('description', '')}</td>
    <td><code>{p.get('equation', '')}</code></td>
    <td>{p.get('value', ''):.4e}</td>
    <td>{p.get('units', '')}</td>
    <td>{p.get('source_ref', '')}</td>
</tr>"""
        return f"""
<h2>Physics Comparison Data Table</h2>
<table>
<tr><th>Description</th><th>Equation</th><th>Value</th><th>Units</th><th>Source</th></tr>
{rows}
</table>"""

    def _section_documents(self) -> str:
        docs = self.data_cache.get("documents", [])
        if not docs:
            return "<h2>Document Structural Comparison</h2><p>No documents analyzed.</p>"

        rows = ""
        for d in docs:
            rows += f"""<tr>
    <td>{d.get('filename', '')}</td>
    <td><code>{(d.get('file_hash_sha256') or '')[:16]}...</code></td>
    <td>{d.get('fonts_used', '')}</td>
    <td>{d.get('classification_marking', '')}</td>
    <td>{d.get('structural_notes', '')}</td>
</tr>"""
        return f"""
<h2>Document Structural Comparison Report</h2>
<table>
<tr><th>Filename</th><th>SHA-256</th><th>Fonts Used</th><th>Markings</th><th>Structural Notes</th></tr>
{rows}
</table>"""

    def _section_academic(self) -> str:
        records = self.data_cache.get("academic_records", [])
        if not records:
            return "<h2>Academic Identity Verification</h2><p>No records found.</p>"

        rows = ""
        for r in records[:30]:
            rows += f"""<tr>
    <td>{r.get('author_name', '')}</td>
    <td>{r.get('title', '')}</td>
    <td>{r.get('journal', '')}</td>
    <td>{r.get('year', '')}</td>
    <td>{r.get('source_db', '')}</td>
    <td>{r.get('institution', '')}</td>
</tr>"""
        return f"""
<h2>Academic Identity Verification Status</h2>
<table>
<tr><th>Author</th><th>Title</th><th>Journal</th><th>Year</th><th>Source DB</th><th>Institution</th></tr>
{rows}
</table>"""

    def _section_government(self) -> str:
        records = self.data_cache.get("government_records", [])
        if not records:
            return "<h2>Public-Record Cross-Reference</h2><p>No records checked.</p>"

        rows = ""
        for r in records[:30]:
            rows += f"""<tr>
    <td>{r.get('database_name', '')}</td>
    <td>{r.get('query_used', '')}</td>
    <td>{r.get('record_title', '')}</td>
    <td>{r.get('match_status', '')}</td>
    <td>{r.get('fiscal_code', 'N/A')}</td>
</tr>"""
        return f"""
<h2>Public-Record Cross-Reference Report</h2>
<table>
<tr><th>Database</th><th>Query</th><th>Record Title</th><th>Match Status</th><th>Fiscal Code</th></tr>
{rows}
</table>"""

    def _section_narratives(self) -> str:
        patterns = self.data_cache.get("narrative_patterns", [])
        if not patterns:
            return "<h2>Narrative Pattern Mapping</h2><p>No patterns detected.</p>"

        rows = ""
        for p in patterns[:40]:
            rows += f"""<tr>
    <td>{p.get('pattern_type', '')}</td>
    <td>{p.get('pattern_label', '')}</td>
    <td>{p.get('confidence', 0):.2f}</td>
    <td>{p.get('source_id', '')}</td>
    <td>{(p.get('detail_json') or '')[:120]}</td>
</tr>"""
        return f"""
<h2>Narrative Pattern Mapping</h2>
<table>
<tr><th>Type</th><th>Pattern</th><th>Confidence</th><th>Source Post ID</th><th>Details</th></tr>
{rows}
</table>"""

    def _section_source_index(self) -> str:
        posts = self.data_cache.get("social_posts", [])
        urls = sorted(set(p.get("post_url", "") for p in posts if p.get("post_url")))
        if not urls:
            return "<h2>Source Index</h2><p>No sources indexed.</p>"

        items = "\n".join(f'<li><a href="{u}">{u}</a></li>' for u in urls[:100])
        return f"""
<h2>Source Index List</h2>
<p>Total unique sources: {len(urls)}</p>
<ol>{items}</ol>"""

    def _section_ipfs_evidence(self) -> str:
        """IPFS proof chain evidence section for static report."""
        evidence = self.data_cache.get("ipfs_evidence", [])
        if not evidence:
            return "<h2>IPFS Proof Chain</h2><p>No evidence pinned to IPFS yet.</p>"

        # Summary stats
        types_count = {}
        for e in evidence:
            t = e.get("evidence_type", "unknown")
            types_count[t] = types_count.get(t, 0) + 1

        head_cid = evidence[-1].get("proof_chain_cid", "N/A") if evidence else "N/A"
        type_badges = " ".join(
            f'<span class="stat">{t}: {c}</span>' for t, c in types_count.items()
        )

        rows = ""
        for e in evidence:
            gateway_link = f"http://127.0.0.1:8081/ipfs/{e.get('evidence_cid', '')}"
            rows += f"""<tr>
    <td>{e.get('sequence', '')}</td>
    <td>{e.get('evidence_type', '')}</td>
    <td>{(e.get('description') or '')[:80]}</td>
    <td><code>{(e.get('evidence_cid') or '')[:20]}...</code></td>
    <td><code>{(e.get('content_hash') or '')[:16]}...</code></td>
    <td><a href="{gateway_link}" target="_blank">View</a></td>
    <td>{e.get('pinned_at', '')}</td>
</tr>"""

        return f"""
<h2>IPFS Proof Chain – Immutable Evidence</h2>
<div>
    <span class="stat">Total pinned: {len(evidence)}</span>
    <span class="stat">Chain head: <code>{str(head_cid)[:20]}...</code></span>
    {type_badges}
</div>
<table>
<tr><th>#</th><th>Type</th><th>Description</th><th>Evidence CID</th><th>SHA-256</th><th>Gateway</th><th>Pinned At</th></tr>
{rows}
</table>"""

    def _section_taxonomy(self) -> str:
        """Taxonomy knowledge base section for static report."""
        entries = self.data_cache.get("taxonomy_entries", [])
        if not entries:
            return "<h2>Taxonomy Knowledge Base</h2><p>No taxonomy entries loaded.</p>"

        categories: dict[str, int] = {}
        for e in entries:
            cat = e.get("category", "unknown")
            categories[cat] = categories.get(cat, 0) + 1

        cat_badges = " ".join(
            f'<span class="stat">{c}: {n}</span>' for c, n in sorted(categories.items())
        )

        rows = ""
        for e in entries[:100]:
            rows += f"""<tr>
    <td>{e.get('term', '')}</td>
    <td>{e.get('category', '')}</td>
    <td>{e.get('subcategory', '')}</td>
    <td>{(e.get('definition') or '')[:100]}</td>
    <td>{e.get('verification_status', '')}</td>
</tr>"""

        return f"""
<h2>Taxonomy Knowledge Base</h2>
<div>
    <span class="stat">Total entries: {len(entries)}</span>
    {cat_badges}
</div>
<table>
<tr><th>Term</th><th>Category</th><th>Subcategory</th><th>Definition</th><th>Status</th></tr>
{rows}
</table>"""

    # ── Interactive Dash App ─────────────────────────────────────────────
    def launch_interactive(self, port: int = 8050) -> None:
        """Launch a Dash web application for interactive exploration."""
        if dash is None:
            log.error("Dash not installed. Use: pip install dash")
            return

        self.load_data()
        app = dash.Dash(__name__)

        app.layout = html.Div([
            html.H1("Project Anchor – Research Dashboard"),
            html.P("Forensic research aggregation – data correlation only."),

            dcc.Tabs([
                dcc.Tab(label="Timeline", children=[
                    html.Div(id="timeline-content"),
                ]),
                dcc.Tab(label="Physics", children=[
                    self._dash_physics_table(),
                ]),
                dcc.Tab(label="Documents", children=[
                    self._dash_documents_table(),
                ]),
                dcc.Tab(label="Narratives", children=[
                    self._dash_narratives_table(),
                ]),
                dcc.Tab(label="Sources", children=[
                    self._dash_source_list(),
                ]),
                dcc.Tab(label="IPFS Evidence", children=[
                    self._dash_ipfs_evidence(),
                ]),
                dcc.Tab(label="Taxonomy", children=[
                    self._dash_taxonomy_table(),
                ]),
            ]),
        ])

        log.info("Launching dashboard on port %d", port)
        app.run(debug=False, port=port)

    def _dash_physics_table(self):
        records = self.data_cache.get("physics_comparisons", [])
        if not records or dash is None:
            return html.P("No physics data.")
        return dash_table.DataTable(
            data=records,
            columns=[{"name": k, "id": k} for k in ["description", "equation", "value", "units", "source_ref"]],
            style_table={"overflowX": "auto"},
            style_cell={"textAlign": "left", "padding": "8px"},
        )

    def _dash_documents_table(self):
        records = self.data_cache.get("documents", [])
        if not records or dash is None:
            return html.P("No document data.")
        return dash_table.DataTable(
            data=records,
            columns=[{"name": k, "id": k} for k in ["filename", "file_hash_sha256", "fonts_used", "classification_marking"]],
            style_table={"overflowX": "auto"},
        )

    def _dash_narratives_table(self):
        records = self.data_cache.get("narrative_patterns", [])
        if not records or dash is None:
            return html.P("No narrative data.")
        return dash_table.DataTable(
            data=records,
            columns=[{"name": k, "id": k} for k in ["pattern_type", "pattern_label", "confidence", "detail_json"]],
            style_table={"overflowX": "auto"},
        )

    def _dash_source_list(self):
        posts = self.data_cache.get("social_posts", [])
        urls = sorted(set(p.get("post_url", "") for p in posts if p.get("post_url")))
        if not urls or dash is None:
            return html.P("No sources.")
        return html.Ol([html.Li(html.A(u, href=u, target="_blank")) for u in urls[:200]])

    def _dash_ipfs_evidence(self):
        """IPFS evidence table for interactive dashboard."""
        records = self.data_cache.get("ipfs_evidence", [])
        if not records or dash is None:
            return html.Div([
                html.P("No IPFS evidence pinned yet."),
                html.P("Run: python main.py --ipfs-archive"),
            ])
        return html.Div([
            html.H4(f"Proof Chain: {len(records)} items pinned"),
            html.P(f"Chain head CID: {records[-1].get('proof_chain_cid', 'N/A')}"),
            dash_table.DataTable(
                data=records,
                columns=[
                    {"name": "#", "id": "sequence"},
                    {"name": "Type", "id": "evidence_type"},
                    {"name": "Description", "id": "description"},
                    {"name": "Evidence CID", "id": "evidence_cid"},
                    {"name": "Content Hash", "id": "content_hash"},
                    {"name": "Pinned At", "id": "pinned_at"},
                ],
                style_table={"overflowX": "auto"},
                style_cell={"textAlign": "left", "padding": "8px", "maxWidth": "300px"},
                page_size=20,
            ),
        ])

    def _dash_taxonomy_table(self):
        """Taxonomy knowledge base table for interactive dashboard."""
        records = self.data_cache.get("taxonomy_entries", [])
        if not records or dash is None:
            return html.Div([
                html.P("No taxonomy entries loaded yet."),
                html.P("Run: python main.py --taxonomy"),
            ])

        # Summary by category
        categories: dict[str, int] = {}
        for r in records:
            cat = r.get("category", "unknown")
            categories[cat] = categories.get(cat, 0) + 1

        status_counts: dict[str, int] = {}
        for r in records:
            s = r.get("verification_status", "unknown")
            status_counts[s] = status_counts.get(s, 0) + 1

        return html.Div([
            html.H4(f"Taxonomy Knowledge Base: {len(records)} entries"),
            html.Div([
                html.H5("By Category"),
                html.Ul([html.Li(f"{cat}: {cnt}") for cat, cnt in sorted(categories.items())]),
            ], style={"display": "inline-block", "verticalAlign": "top", "marginRight": "40px"}),
            html.Div([
                html.H5("By Status"),
                html.Ul([html.Li(f"{s}: {cnt}") for s, cnt in sorted(status_counts.items())]),
            ], style={"display": "inline-block", "verticalAlign": "top"}),
            html.Hr(),
            dash_table.DataTable(
                data=records,
                columns=[
                    {"name": "Term", "id": "term"},
                    {"name": "Category", "id": "category"},
                    {"name": "Subcategory", "id": "subcategory"},
                    {"name": "Definition", "id": "definition"},
                    {"name": "Status", "id": "verification_status"},
                    {"name": "Source", "id": "source_ref"},
                ],
                style_table={"overflowX": "auto"},
                style_cell={"textAlign": "left", "padding": "8px", "maxWidth": "400px"},
                filter_action="native",
                sort_action="native",
                page_size=25,
            ),
        ])
