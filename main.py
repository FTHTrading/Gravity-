"""
Project Anchor – Main Orchestrator & CLI

Entry point for the forensic research aggregation system.
Coordinates all modules and provides a command-line interface.

Usage:
    python main.py --all              Run complete pipeline
    python main.py --collect          Data collection only
    python main.py --analyze-pdf FILE Analyze a specific PDF
    python main.py --physics          Run physics computations
    python main.py --waves            Run wave science computations
    python main.py --nlp              Run NLP analysis on collected data
    python main.py --graph            Build propagation graph
    python main.py --report           Generate all reports
    python main.py --dashboard        Launch interactive dashboard
    python main.py --static-report    Generate static HTML report
    python main.py --taxonomy         Load taxonomy knowledge base into DB
    python main.py --taxonomy-search  Search taxonomy entries
    python main.py --taxonomy-export  Export taxonomy to JSON
    python main.py --arxiv TERM       Search arXiv for a term
    python main.py --extended-search  Run all extended terms through scrapers
  Phase II:
    python main.py --key-generate     Generate Ed25519 signing keypair
    python main.py --sign-cid CID     Sign a CID with default key
    python main.py --verify-cid CID   Verify a CID signature
    python main.py --snapshot         Create Merkle snapshot of database
    python main.py --verify-snapshot  Verify latest Merkle snapshot
    python main.py --ipns-publish CID Publish CID to IPNS
    python main.py --ipns-resolve     Resolve current IPNS pointer
    python main.py --generate-audit   Generate comprehensive audit report
    python main.py --foia-search Q    Search all FOIA sources for query
    python main.py --tesla            Run Tesla full investigation
    python main.py --load-scientists  Load scientist cases database
    python main.py --search-scientists QUERY  Search scientist cases
    python main.py --gateway-health   Check multi-gateway health
"""

import argparse
import sys
from pathlib import Path

from src.config import SEARCH_TERMS, ACADEMIC_TERMS, ALL_EXTENDED_TERMS
from src.database import init_db
from src.logger import get_logger
from src.reports import ReportGenerator

log = get_logger("main")


def run_collection():
    """Execute all data collection scrapers."""
    log.info("=" * 60)
    log.info("PHASE 1: DATA COLLECTION")
    log.info("=" * 60)

    from src.collectors.reddit_scraper import RedditScraper
    from src.collectors.wayback_scraper import WaybackScraper
    from src.collectors.web_search_scraper import WebSearchScraper

    scrapers = [
        RedditScraper(),
        WaybackScraper(),
        WebSearchScraper(),
    ]

    for scraper in scrapers:
        log.info("Running scraper: %s", scraper.platform)
        try:
            scraper.run_all_terms(SEARCH_TERMS)
        except Exception as exc:
            log.error("Scraper %s failed: %s", scraper.platform, exc)


def run_academic_search():
    """Search academic databases."""
    log.info("=" * 60)
    log.info("PHASE 2: ACADEMIC CROSS-REFERENCE")
    log.info("=" * 60)

    from src.crossref.academic_records import AcademicCrossRef

    acad = AcademicCrossRef()
    for term in ACADEMIC_TERMS:
        try:
            acad.search(term)
        except Exception as exc:
            log.error("Academic search failed for '%s': %s", term, exc)

    # Specific author search
    try:
        results = acad.search_author("Thomas Webb")
        log.info("Author 'Thomas Webb' search: %d profiles", len(results))
    except Exception as exc:
        log.error("Author search failed: %s", exc)


def run_government_crossref():
    """Search public government records."""
    log.info("=" * 60)
    log.info("PHASE 3: GOVERNMENT RECORD CROSS-REFERENCE")
    log.info("=" * 60)

    from src.crossref.government_records import GovernmentCrossRef

    gov = GovernmentCrossRef()
    search_terms = ["Project Anchor", "Thomas Webb NASA", "gravity anomaly research"]
    for term in search_terms:
        try:
            gov.search(term)
        except Exception as exc:
            log.error("Government search failed for '%s': %s", term, exc)


def run_pdf_analysis(filepath: str):
    """Analyze a specific PDF document."""
    log.info("=" * 60)
    log.info("PHASE 4: PDF DOCUMENT ANALYSIS")
    log.info("=" * 60)

    from src.analyzers.pdf_analyzer import PDFAnalyzer

    path = Path(filepath)
    if not path.exists():
        log.error("File not found: %s", filepath)
        return

    analyzer = PDFAnalyzer(path)
    analyzer.save_to_db(source_url=str(path))

    # Print summary
    meta = analyzer.extract_metadata()
    fonts = analyzer.extract_fonts()
    markings = analyzer.detect_classification_markings()
    report = analyzer.check_structural_consistency()

    log.info("Metadata: %s", meta)
    log.info("Fonts: %s", fonts)
    log.info("Markings: %s", markings)
    log.info("Inconsistencies: %d found", len(report.get("inconsistencies", [])))


def run_physics():
    """Execute gravitational physics computation suite."""
    log.info("=" * 60)
    log.info("PHASE 5: PHYSICS CONSISTENCY ANALYSIS")
    log.info("=" * 60)

    from src.physics.gravity_engine import GravityPhysicsEngine

    engine = GravityPhysicsEngine()
    results = engine.run_full_comparison()

    for r in results:
        log.info(
            "  %-60s  %.4e %s",
            r["description"],
            r["value"],
            r["units"],
        )


def run_waves():
    """Execute wave science computation suite."""
    log.info("=" * 60)
    log.info("WAVE SCIENCE COMPUTATIONS")
    log.info("=" * 60)

    from src.physics.wave_engine import WaveScienceEngine

    engine = WaveScienceEngine()
    results = engine.run_full_suite()

    for r in results:
        log.info(
            "  %-60s  %.4e %s",
            r["description"],
            r["value"],
            r["units"],
        )


def run_nlp():
    """Run NLP narrative analysis on collected posts."""
    log.info("=" * 60)
    log.info("PHASE 6: NARRATIVE STRUCTURE ANALYSIS")
    log.info("=" * 60)

    from src.nlp.narrative_analyzer import NarrativeAnalyzer

    analyzer = NarrativeAnalyzer()
    report = analyzer.analyze_all_posts()
    log.info("NLP report: %s", report)


def run_graph():
    """Build and analyze propagation graph."""
    log.info("=" * 60)
    log.info("PHASE 7: PROPAGATION GRAPH ANALYSIS")
    log.info("=" * 60)

    from src.graph.propagation_graph import PropagationGraph

    graph = PropagationGraph()
    graph.build_from_db()
    metrics = graph.compute_metrics()
    timeline = graph.generate_timeline()
    clusters = graph.detect_amplification_clusters()

    log.info("Graph metrics: %s", metrics)
    log.info("Timeline events: %d", len(timeline))
    log.info("Clusters: %d", len(clusters))

    graph.export_graphml()
    graph.export_json()
    graph.plot_timeline()


def run_reports():
    """Generate all structured reports."""
    log.info("=" * 60)
    log.info("GENERATING REPORTS")
    log.info("=" * 60)

    gen = ReportGenerator()
    paths = gen.generate_all()
    for name, path in paths.items():
        log.info("  %s → %s", name, path)


def run_static_report():
    """Generate static HTML dashboard report."""
    from src.dashboard.dashboard import Dashboard
    dash = Dashboard()
    path = dash.generate_static_report()
    log.info("Static report: %s", path)


def run_dashboard():
    """Launch interactive dashboard."""
    from src.dashboard.dashboard import Dashboard
    dash = Dashboard()
    dash.launch_interactive()


# ── IPFS Functions ───────────────────────────────────────────────────────────
def _get_ipfs_client():
    """Create and return an IPFS client, with connectivity check."""
    from src.ipfs.ipfs_client import IPFSClient
    client = IPFSClient()
    if not client.is_online():
        log.error("IPFS node is not reachable. Is Kubo running?")
        return None
    return client


def run_ipfs_status():
    """Show IPFS node status and archive statistics."""
    log.info("=" * 60)
    log.info("IPFS NODE STATUS")
    log.info("=" * 60)

    client = _get_ipfs_client()
    if not client:
        return

    summary = client.status_summary()
    for key, val in summary.items():
        log.info("  %-20s  %s", key, val)

    from src.ipfs.evidence_archiver import EvidenceArchiver
    archiver = EvidenceArchiver(client)
    status = archiver.get_archive_status()
    log.info("")
    log.info("  Archive total pinned: %d", status["total_pinned"])
    log.info("  Chain head CID:      %s", status["chain_head"])
    log.info("  Chain length:        %d", status["chain_length"])
    if status["by_type"]:
        for t, c in status["by_type"].items():
            log.info("    %-30s %d", t, c)


def run_ipfs_archive():
    """Archive all research evidence to IPFS."""
    log.info("=" * 60)
    log.info("IPFS EVIDENCE ARCHIVE")
    log.info("=" * 60)

    client = _get_ipfs_client()
    if not client:
        return

    from src.ipfs.evidence_archiver import EvidenceArchiver
    archiver = EvidenceArchiver(client)
    report = archiver.archive_all()

    log.info("Archive complete:")
    log.info("  Total items pinned:  %d", report["total_items_pinned"])
    log.info("  Chain head:          %s", report.get("proof_chain_head"))
    log.info("  Manifest CID:        %s", report.get("manifest_cid"))
    log.info("  Errors:              %d", len(report.get("errors", [])))
    if report.get("ipns"):
        log.info("  IPNS name:           %s", report["ipns"].get("Name"))


def run_ipfs_pin_file(filepath: str):
    """Pin a specific file to IPFS and add to proof chain."""
    log.info("=" * 60)
    log.info("IPFS PIN FILE")
    log.info("=" * 60)

    client = _get_ipfs_client()
    if not client:
        return

    from src.ipfs.proof_chain import ProofChain
    chain = ProofChain(client)
    result = chain.add_file_evidence(filepath)

    log.info("File pinned to IPFS:")
    log.info("  Evidence CID:  %s", result["evidence_cid"])
    log.info("  Proof CID:     %s", result["proof_link_cid"])
    log.info("  Gateway URL:   %s", result["gateway_url"])
    log.info("  Sequence:      %d", result["sequence"])


def run_ipfs_verify():
    """Verify the integrity of the IPFS proof chain."""
    log.info("=" * 60)
    log.info("IPFS PROOF CHAIN VERIFICATION")
    log.info("=" * 60)

    client = _get_ipfs_client()
    if not client:
        return

    from src.ipfs.proof_chain import ProofChain
    chain = ProofChain(client)
    report = chain.verify_chain()

    log.info("Verification result:")
    log.info("  Status:          %s", report["status"])
    log.info("  Links verified:  %d", report["links_verified"])
    log.info("  Head CID:        %s", report.get("head_cid"))
    if report.get("broken_links"):
        for b in report["broken_links"]:
            log.warning("  BROKEN: seq=%s cid=%s error=%s",
                        b.get("sequence"), b.get("cid"), b.get("error"))


# ── Taxonomy & Extended Search Functions ─────────────────────────────────────

def run_taxonomy_load():
    """Load all taxonomy entries into the database."""
    log.info("=" * 60)
    log.info("TAXONOMY KNOWLEDGE BASE – LOADING")
    log.info("=" * 60)

    from src.taxonomy.knowledge_base import save_all_to_db, get_all_entries

    entries = get_all_entries()
    log.info("Total taxonomy entries: %d", len(entries))
    save_all_to_db()
    log.info("All taxonomy entries saved to database.")


def run_taxonomy_search(query: str):
    """Search taxonomy entries for a term."""
    log.info("=" * 60)
    log.info("TAXONOMY SEARCH: '%s'", query)
    log.info("=" * 60)

    from src.taxonomy.knowledge_base import search_taxonomy

    results = search_taxonomy(query)
    log.info("Found %d matching entries:", len(results))
    for entry in results:
        log.info("  [%s/%s] %s – %s (status: %s)",
                 entry.category, entry.subcategory,
                 entry.term, entry.definition[:80],
                 entry.verification_status)


def run_taxonomy_export():
    """Export taxonomy knowledge base to JSON."""
    log.info("=" * 60)
    log.info("TAXONOMY EXPORT")
    log.info("=" * 60)

    from src.taxonomy.knowledge_base import export_taxonomy_json
    from src.config import REPORTS_DIR

    output_path = REPORTS_DIR / "taxonomy_knowledge_base.json"
    data = export_taxonomy_json()

    import json
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    log.info("Taxonomy exported to: %s", output_path)
    log.info("Total entries: %d", len(data))


def run_arxiv_search(term: str):
    """Search arXiv for a specific term."""
    log.info("=" * 60)
    log.info("arXiv SEARCH: '%s'", term)
    log.info("=" * 60)

    from src.crossref.research_sources import ArxivScraper

    scraper = ArxivScraper()
    results = scraper.search_gravity_propulsion(term, max_results=25)
    log.info("arXiv returned %d papers for '%s'", len(results), term)
    for r in results:
        log.info("  [%s] %s – %s", r.get("year", "?"), r.get("title", "?")[:70], r.get("journal", ""))


def run_extended_search():
    """Run all extended search terms through arXiv and DTIC scrapers."""
    log.info("=" * 60)
    log.info("EXTENDED RESEARCH SOURCE SEARCH")
    log.info("=" * 60)

    from src.crossref.research_sources import ArxivScraper, DTICScraper

    arxiv = ArxivScraper()
    dtic = DTICScraper()

    total_arxiv = 0
    total_dtic = 0

    for term in ALL_EXTENDED_TERMS:
        log.info("Searching: '%s'", term)
        try:
            results = arxiv.search_gravity_propulsion(term, max_results=10)
            total_arxiv += len(results)
        except Exception as exc:
            log.error("arXiv failed for '%s': %s", term, exc)
        try:
            results = dtic.search(term)
            total_dtic += len(results)
        except Exception as exc:
            log.error("DTIC failed for '%s': %s", term, exc)

    log.info("Extended search complete:")
    log.info("  Total arXiv papers:  %d", total_arxiv)
    log.info("  Total DTIC records:  %d", total_dtic)
    log.info("  Search terms used:   %d", len(ALL_EXTENDED_TERMS))


# ── Phase II: Crypto / Proof / FOIA / Investigation Functions ────────────────

def run_key_generate():
    """Generate a new Ed25519 signing keypair."""
    log.info("=" * 60)
    log.info("GENERATE ED25519 KEYPAIR")
    log.info("=" * 60)

    from src.crypto.signature_manager import SignatureManager
    mgr = SignatureManager()
    info = mgr.generate_keypair()
    log.info("  Key name:      %s", info.key_name)
    log.info("  Fingerprint:   %s", info.fingerprint)
    log.info("  Created:       %s", info.created_at)
    log.info("  Keys dir:      %s", mgr.keys_dir)


def run_sign_cid(cid: str):
    """Sign a CID with the default (latest) key."""
    log.info("=" * 60)
    log.info("SIGN CID: %s", cid)
    log.info("=" * 60)

    from src.crypto.signature_manager import SignatureManager
    mgr = SignatureManager()
    result = mgr.sign_cid(cid)
    if result:
        log.info("  Signature:     %s…", result["signature_hex"][:64])
        log.info("  Fingerprint:   %s", result["fingerprint"])
    else:
        log.error("Signing failed. Do you have a keypair? Run --key-generate first.")


def run_verify_cid(cid: str):
    """Verify a CID signature."""
    log.info("=" * 60)
    log.info("VERIFY CID: %s", cid)
    log.info("=" * 60)

    from src.crypto.signature_manager import SignatureManager
    from src.database import get_connection

    conn = get_connection()
    row = conn.execute(
        "SELECT signature, pubkey_fingerprint FROM ipfs_evidence WHERE cid = ? AND signature IS NOT NULL",
        (cid,)
    ).fetchone()
    conn.close()

    if not row:
        log.error("No signed evidence found for CID: %s", cid)
        return

    mgr = SignatureManager()
    result = mgr.verify_cid(cid, row[0])
    if result.get("verified"):
        log.info("  ✓ Signature VALID for CID %s", cid)
    else:
        log.error("  ✗ Signature INVALID for CID %s: %s", cid, result.get("error", ""))


def run_snapshot():
    """Create a Merkle snapshot of the current database state."""
    log.info("=" * 60)
    log.info("CREATE MERKLE SNAPSHOT")
    log.info("=" * 60)

    from src.proofs.merkle_snapshot import MerkleSnapshotEngine
    engine = MerkleSnapshotEngine()
    snap = engine.create_snapshot()
    log.info("  Root hash:     %s", snap["root_hash"])
    log.info("  Leaf count:    %d", snap["leaf_count"])
    log.info("  IPFS CID:      %s", snap.get("ipfs_cid", "N/A"))
    log.info("  Snapshot ID:   %s", snap.get("id", "?"))


def run_verify_snapshot():
    """Verify the latest Merkle snapshot against current DB state."""
    log.info("=" * 60)
    log.info("VERIFY MERKLE SNAPSHOT")
    log.info("=" * 60)

    from src.proofs.merkle_snapshot import MerkleSnapshotEngine
    engine = MerkleSnapshotEngine()
    latest = engine.get_latest_root()
    if not latest:
        log.error("No snapshots found. Create one with --snapshot first.")
        return

    ok = engine.verify_snapshot(latest)
    if ok:
        log.info("  ✓ Database integrity VERIFIED – root matches: %s", latest)
    else:
        log.error("  ✗ Database MODIFIED since last snapshot (root was: %s)", latest)


def run_ipns_publish(cid: str):
    """Publish a CID to IPNS."""
    log.info("=" * 60)
    log.info("IPNS PUBLISH: %s", cid)
    log.info("=" * 60)

    from src.ipfs.ipns_publisher import IPNSPublisher
    publisher = IPNSPublisher()
    result = publisher.publish(cid)
    if result:
        log.info("  IPNS Name:   %s", result.get("Name"))
        log.info("  Value:       %s", result.get("Value"))
    else:
        log.error("IPNS publish failed. Is IPFS running?")


def run_ipns_resolve():
    """Resolve current IPNS pointer."""
    log.info("=" * 60)
    log.info("IPNS RESOLVE")
    log.info("=" * 60)

    from src.ipfs.ipns_publisher import IPNSPublisher
    publisher = IPNSPublisher()
    path = publisher.resolve()
    if path:
        log.info("  Resolved path: %s", path)
    else:
        log.error("IPNS resolve failed or no name published yet.")


def run_generate_audit():
    """Generate comprehensive audit report in all formats."""
    log.info("=" * 60)
    log.info("GENERATE AUDIT REPORT")
    log.info("=" * 60)

    from src.reports.audit_generator import AuditReportGenerator
    gen = AuditReportGenerator()
    report = gen.generate_full_report()
    log.info("Audit report generated with %d sections.", len(report.get("sections", {})))
    log.info("  Exported to: reports/audits/")


def run_foia_search(query: str):
    """Search all FOIA sources for a query."""
    log.info("=" * 60)
    log.info("FOIA SEARCH: '%s'", query)
    log.info("=" * 60)

    from src.foia.foia_ingester import FOIASearchEngine
    engine = FOIASearchEngine()
    results = engine.search_all(query)
    log.info("Results by source:")
    for source, docs in results.items():
        log.info("  %-20s %d documents", source, len(docs))
    total = sum(len(d) for d in results.values())
    log.info("  Total:              %d documents ingested", total)


def run_tesla_investigation():
    """Run the full Tesla investigation protocol."""
    log.info("=" * 60)
    log.info("TESLA INVESTIGATION – FULL PROTOCOL")
    log.info("=" * 60)

    from src.investigations.tesla_module import TeslaInvestigation
    tesla = TeslaInvestigation()
    report = tesla.run_full_investigation()
    log.info("Tesla investigation complete:")
    log.info("  Case ID:         %s", report.get("case_id", "?"))
    log.info("  Phases run:      %d", len(report.get("phases", {})))
    for phase_name, phase_data in report.get("phases", {}).items():
        if isinstance(phase_data, dict):
            log.info("    %-25s %d items", phase_name,
                     len(phase_data.get("results", phase_data.get("claims", phase_data.get("clusters", [])))))
        elif isinstance(phase_data, list):
            log.info("    %-25s %d items", phase_name, len(phase_data))


def run_load_scientist_cases():
    """Load all scientist cases into the database."""
    log.info("=" * 60)
    log.info("SCIENTIST CASES – LOADING")
    log.info("=" * 60)

    from src.investigations.scientist_cases import ScientistCasesDatabase
    db = ScientistCasesDatabase()
    loaded = db.load_all_cases()
    log.info("Loaded %d new scientist cases into database.", loaded)

    stats = db.get_statistics()
    log.info("  Disputed:    %d", stats.get("disputed_cases", 0))
    log.info("  By field:    %s", stats.get("by_field", {}))


def run_search_scientists(query: str):
    """Search scientist cases database."""
    log.info("=" * 60)
    log.info("SCIENTIST CASES – SEARCH: '%s'", query)
    log.info("=" * 60)

    from src.investigations.scientist_cases import ScientistCasesDatabase
    db = ScientistCasesDatabase()
    results = db.search_cases(query)
    log.info("Found %d matching cases:", len(results))
    for case in results:
        log.info("  [%s] %s – %s (%s)", case.get("year", "?"),
                 case.get("name", "?"), case.get("field", "?"),
                 case.get("official_cause", "?"))


def run_gateway_health():
    """Check health of all configured IPFS gateways."""
    log.info("=" * 60)
    log.info("MULTI-GATEWAY HEALTH CHECK")
    log.info("=" * 60)

    from src.ipfs.multi_gateway import MultiGatewayPinner
    pinner = MultiGatewayPinner()
    report = pinner.gateway_health_check()
    for gw in report:
        status = "✓ OK" if gw.get("healthy") else "✗ DOWN"
        log.info("  %-40s %s  (%dms)", gw.get("gateway", "?"), status,
                 gw.get("response_time_ms", 0))


# ── Phase III: Math Forensics CLI handlers ──────────────────────────────

def run_parse_equation(text: str):
    """Parse a plaintext equation."""
    log.info("=" * 60)
    log.info("EQUATION PARSER – PLAINTEXT")
    log.info("=" * 60)

    from src.math.equation_parser import EquationParser
    parser = EquationParser()
    result = parser.parse_plaintext(text, name="cli_input")
    if result.parse_error:
        log.error("Parse error: %s", result.parse_error)
    else:
        log.info("  Name:       %s", result.name)
        log.info("  SymPy:      %s", result.sympy_repr)
        log.info("  LaTeX:      %s", result.latex_form)
        log.info("  Simplified: %s", result.simplified_form)
        log.info("  Symbols:    %s", ", ".join(result.symbols_found))
        log.info("  SHA-256:    %s", result.sha256)
        if result.is_equation:
            log.info("  LHS:        %s", result.lhs)
            log.info("  RHS:        %s", result.rhs)
        metrics = parser.get_complexity_metrics(result)
        log.info("  Complexity:  %s (ops=%d, depth=%d)",
                 metrics["complexity_class"], metrics["operation_count"],
                 metrics["tree_depth"])


def run_parse_latex(latex: str):
    """Parse a LaTeX equation string."""
    log.info("=" * 60)
    log.info("EQUATION PARSER – LaTeX")
    log.info("=" * 60)

    from src.math.equation_parser import EquationParser
    parser = EquationParser()
    result = parser.parse_latex(latex, name="cli_latex")
    if result.parse_error:
        log.error("Parse error: %s", result.parse_error)
    else:
        log.info("  SymPy:      %s", result.sympy_repr)
        log.info("  Simplified: %s", result.simplified_form)
        log.info("  Symbols:    %s", ", ".join(result.symbols_found))
        log.info("  SHA-256:    %s", result.sha256)


def run_dim_check(eq_name: str):
    """Dimensional analysis on a known equation."""
    log.info("=" * 60)
    log.info("DIMENSIONAL ANALYSIS – %s", eq_name)
    log.info("=" * 60)

    from src.math.dimensional_analyzer import DimensionalAnalyzer
    analyzer = DimensionalAnalyzer()
    report = analyzer.check_known_equation(eq_name)
    if report is None:
        log.error("Unknown equation name '%s'. Known: newton_gravity, einstein_energy, "
                  "coulomb, gravitational_pe, kinetic_energy, escape_velocity", eq_name)
        return
    log.info("  Status:        %s", report.status)
    log.info("  LHS dimension: %s", report.lhs_dimension or "(none)")
    log.info("  RHS dimension: %s", report.rhs_dimension or "(none)")
    log.info("  Match:         %s", report.dimensions_match)
    if report.errors:
        for e in report.errors:
            log.error("  ERROR: %s", e)
    if report.warnings:
        for w in report.warnings:
            log.warning("  WARN: %s", w)


def run_simplify_equation(text: str):
    """Simplify an expression using symbolic refactoring."""
    log.info("=" * 60)
    log.info("SYMBOLIC SIMPLIFY")
    log.info("=" * 60)

    from src.math.equation_parser import EquationParser
    from src.math.symbolic_refactor import SymbolicRefactor

    parser = EquationParser()
    parsed = parser.parse_plaintext(text, name="cli_simplify")
    if parsed.parse_error:
        log.error("Parse error: %s", parsed.parse_error)
        return

    refactor = SymbolicRefactor()
    result = refactor.simplify(parsed)
    log.info("  Input:       %s", result.input_expr)
    log.info("  Output:      %s", result.output_expr)
    log.info("  Equivalent:  %s", result.is_equivalent)
    log.info("  Complexity:  %d → %d", result.complexity_before, result.complexity_after)


def run_math_audit():
    """Run full math forensics audit on built-in known equations."""
    log.info("=" * 60)
    log.info("MATHEMATICAL FORENSICS AUDIT")
    log.info("=" * 60)

    from src.math.equation_parser import EquationParser
    from src.math.dimensional_analyzer import DimensionalAnalyzer
    from src.math.symbolic_refactor import SymbolicRefactor
    from src.math.equation_audit_report import EquationAuditReport

    parser = EquationParser()
    analyzer = DimensionalAnalyzer()
    refactor = SymbolicRefactor()

    # Parse known equations
    known = {
        "Einstein E=mc²": "E = m*c**2",
        "Newton Gravity": "F = G*M*m/r**2",
        "Kinetic Energy": "E = m*v**2/2",
        "Gravitational PE": "E = -G*M*m/r",
        "Escape Velocity": "v = (2*G*M/r)**(1/2)",
    }

    parsed_eqs = []
    dim_reports = []
    refactor_results = []

    for name, text in known.items():
        p = parser.parse_plaintext(text, name=name)
        parsed_eqs.append(p)
        dim_reports.append(analyzer.analyze(p))
        refactor_results.append(refactor.simplify(p))

    report_gen = EquationAuditReport()
    report_text = report_gen.generate(
        parsed_equations=parsed_eqs,
        dimensional_reports=dim_reports,
        refactor_results=refactor_results,
    )
    print(report_text)


# ── Phase III: Claim Graph CLI handlers ─────────────────────────────────

def run_add_claim(text: str):
    """Add a claim to the evidence graph."""
    log.info("=" * 60)
    log.info("CLAIM GRAPH – ADD CLAIM")
    log.info("=" * 60)

    from src.graph.claim_graph import ClaimGraph
    graph = ClaimGraph()
    claim_id = graph.add_claim(claim_text=text)
    log.info("  Claim #%d added.", claim_id)


def run_add_source(title: str):
    """Add a source node."""
    log.info("=" * 60)
    log.info("CLAIM GRAPH – ADD SOURCE")
    log.info("=" * 60)

    from src.graph.claim_graph import ClaimGraph
    graph = ClaimGraph()
    source_id = graph.add_source(title=title)
    log.info("  Source #%d added.", source_id)


def run_link_claim(spec: str):
    """Link two nodes: 'claim_id,source_id,relationship'."""
    log.info("=" * 60)
    log.info("CLAIM GRAPH – LINK")
    log.info("=" * 60)

    parts = spec.split(",")
    if len(parts) < 3:
        log.error("Format: claim_id,source_id,relationship")
        return

    from src.graph.claim_graph import ClaimGraph
    graph = ClaimGraph()
    link_id = graph.link(
        from_type="claim", from_id=int(parts[0]),
        to_type="source", to_id=int(parts[1]),
        relationship=parts[2].strip(),
    )
    log.info("  Link #%d created.", link_id)


def run_claim_stats():
    """Show claim graph statistics."""
    log.info("=" * 60)
    log.info("CLAIM GRAPH – STATISTICS")
    log.info("=" * 60)

    from src.graph.claim_graph import ClaimGraph
    graph = ClaimGraph()
    stats = graph.get_statistics()
    log.info("  Claims:           %d", stats["total_claims"])
    log.info("  Sources:          %d", stats["total_sources"])
    log.info("  Links:            %d", stats["total_links"])
    log.info("  Contradictions:   %d", stats["total_contradictions"])
    log.info("  Avg confidence:   %.2f", stats["avg_confidence"])
    log.info("  By type:          %s", stats["claims_by_type"])
    log.info("  By status:        %s", stats["claims_by_status"])


def run_provenance(claim_id: int):
    """Show provenance chain for a claim."""
    log.info("=" * 60)
    log.info("CLAIM GRAPH – PROVENANCE (claim #%d)", claim_id)
    log.info("=" * 60)

    from src.graph.claim_graph import ClaimGraph
    graph = ClaimGraph()
    chain = graph.get_provenance(claim_id)
    for node in chain:
        indent = "  " * (node["depth"] + 1)
        label = node.get("text", node.get("title", "?"))[:60]
        log.info("%s[%s#%d] %s", indent, node["type"], node["id"], label)


def run_contradictions():
    """List all contradictions in the claim graph."""
    log.info("=" * 60)
    log.info("CLAIM GRAPH – CONTRADICTIONS")
    log.info("=" * 60)

    from src.graph.claim_graph import ClaimGraph
    graph = ClaimGraph()
    contradictions = graph.find_contradictions()
    if not contradictions:
        log.info("  No contradictions found.")
        return
    for c in contradictions:
        log.info("  Link #%d: %s#%d ↔ %s#%d",
                 c["link_id"], c["from_type"], c["from_id"],
                 c["to_type"], c["to_id"])
        if "from_text" in c:
            log.info("    FROM: %s", c["from_text"][:80])
        if "to_text" in c:
            log.info("    TO:   %s", c["to_text"][:80])


# ── Phase IV: Claim Confidence & Mutation Entropy CLI handlers ────────

def run_score_claim(claim_id: int):
    """Score a single claim with the Bayesian confidence engine."""
    log.info("=" * 60)
    log.info("CONFIDENCE SCORER – CLAIM #%d", claim_id)
    log.info("=" * 60)

    from src.graph.confidence_scorer import ConfidenceScorer
    scorer = ConfidenceScorer()
    score = scorer.score_claim(claim_id)
    log.info("  Composite:     %.4f", score.composite)
    log.info("    %-20s %.4f", "prior", score.prior)
    log.info("    %-20s %.4f", "source_credibility", score.source_credibility)
    log.info("    %-20s %.4f", "citation_support", score.citation_support)
    log.info("    %-20s %.4f", "contradiction", score.contradiction_penalty)
    log.info("    %-20s %.4f", "verification", score.verification_bonus)
    log.info("    %-20s %.4f", "mutation_decay", score.mutation_decay)
    scorer.save_score(score)
    log.info("  Score saved to database.")


def run_score_all():
    """Score all claims and rank by confidence."""
    log.info("=" * 60)
    log.info("CONFIDENCE SCORER – ALL CLAIMS")
    log.info("=" * 60)

    from src.graph.confidence_scorer import ConfidenceScorer
    scorer = ConfidenceScorer()
    results = scorer.score_all_claims()
    log.info("  Scored %d claims.", len(results))
    ranked = scorer.rank_claims(top_n=20)
    for cid, sc, text in ranked:
        log.info("    #%-4d  %.4f  %s", cid, sc, text)


def run_mutation_entropy(claim_id: int):
    """Analyze mutation entropy for a claim chain."""
    log.info("=" * 60)
    log.info("MUTATION ENTROPY – CLAIM #%d", claim_id)
    log.info("=" * 60)

    from src.graph.mutation_entropy import MutationEntropy
    engine = MutationEntropy()
    metrics = engine.analyze_chain(claim_id)
    if metrics:
        log.info("  Chain length:        %d", metrics.chain_length)
        log.info("  Shannon entropy:     %.4f", metrics.shannon_entropy)
        log.info("  Drift velocity:      %.4f", metrics.drift_velocity)
        log.info("  Max diff ratio:      %.4f", metrics.max_diff_ratio)
        log.info("  Semantic stability:  %.4f", metrics.semantic_stability)
        engine.save_metrics(metrics)
        log.info("  Metrics saved to database.")
    else:
        log.info("  No mutation chain found for claim #%d.", claim_id)


def run_citation_density(claim_id: int):
    """Analyze citation density for a claim."""
    log.info("=" * 60)
    log.info("CITATION DENSITY – CLAIM #%d", claim_id)
    log.info("=" * 60)

    from src.graph.citation_density import CitationDensity
    engine = CitationDensity()
    metrics = engine.analyze_claim(claim_id)
    if metrics:
        log.info("  Direct citations:    %d", metrics.direct_citations)
        log.info("  Unique sources:      %d", metrics.unique_sources)
        log.info("  Supporting claims:   %d", metrics.supporting_claims)
        log.info("  Contradicting:       %d", metrics.contradicting_claims)
        log.info("  Citation depth:      %d", metrics.citation_depth)
        log.info("  Density score:       %.4f", metrics.density_score)
    else:
        log.info("  Claim #%d not found.", claim_id)


def run_tension_map():
    """Show contradiction tension map across all claims."""
    log.info("=" * 60)
    log.info("CONTRADICTION TENSION MAP")
    log.info("=" * 60)

    from src.graph.contradiction_analyzer import ContradictionAnalyzer
    analyzer = ContradictionAnalyzer()
    tmap = analyzer.tension_map()
    summary = analyzer.get_summary()

    log.info("  Total claims:   %d", summary["total_claims"])
    log.info("  Contested:      %d", summary["contested_claims"])
    log.info("  Avg tension:    %.4f", summary["avg_tension"])

    clusters = analyzer.find_conflict_clusters()
    if clusters:
        log.info("  Conflict clusters: %d", len(clusters))
        for i, cl in enumerate(clusters[:10], 1):
            members = ", ".join(f"#{m}" for m in cl.claim_ids[:8])
            log.info("    Cluster %d: size=%d tension=%.2f [%s]",
                     i, cl.size, cl.total_tension, members)

    if tmap:
        log.info("  Highest tension claims:")
        for entry in tmap[:10]:
            log.info("    #%-4d  tension=%.4f", entry["claim_id"], entry["tension"])


def run_propagation_velocity(claim_id: int):
    """Track propagation velocity for a claim."""
    log.info("=" * 60)
    log.info("PROPAGATION VELOCITY – CLAIM #%d", claim_id)
    log.info("=" * 60)

    from src.graph.propagation_tracker import PropagationTracker
    tracker = PropagationTracker()
    metrics = tracker.analyze_propagation(claim_id)
    log.info("  Total spread:        %d", metrics.total_spread)
    log.info("  Unique sources:      %d", metrics.unique_sources)
    log.info("  Amplification:       %.4f", metrics.amplification_factor)
    log.info("  Velocity:            %.4f events/hr", metrics.velocity)
    log.info("  Time span:           %.2f hours", metrics.time_span_hours)
    log.info("  Cascade depth:       %d", metrics.cascade_depth)
    log.info("  First seen:          %s", metrics.first_seen)
    log.info("  Last seen:           %s", metrics.last_seen)


def run_claim_report(claim_id: int = 0):
    """Generate aggregate epistemic scoring report."""
    log.info("=" * 60)
    log.info("EPISTEMIC SCORING REPORT")
    log.info("=" * 60)

    from src.graph.claim_scoring_report import ClaimScoringReport
    report_gen = ClaimScoringReport()
    if claim_id:
        report_text = report_gen.generate(claim_ids=[claim_id])
    else:
        report_text = report_gen.generate()
    print(report_text)


def run_quick_score(claim_id: int):
    """One-line epistemic summary for a claim."""
    from src.graph.claim_scoring_report import ClaimScoringReport
    report_gen = ClaimScoringReport()
    print(report_gen.quick_score(claim_id))


# ── Phase V: Temporal Epistemic Dynamics CLI handlers ────────────

def run_confidence_snapshot(claim_id: int):
    """Snapshot confidence for a claim (or all if 0)."""
    log.info("=" * 60)
    log.info("CONFIDENCE TIMELINE – SNAPSHOT")
    log.info("=" * 60)

    from src.graph.confidence_timeline import ConfidenceTimeline
    tl = ConfidenceTimeline()
    if claim_id == 0:
        points = tl.snapshot_all()
        log.info("  Snapshotted %d claims.", len(points))
    else:
        point = tl.snapshot_claim(claim_id)
        log.info("  Claim #%d → %.4f at %s", claim_id, point.score_value, point.snapshot_at)


def run_confidence_trend(claim_id: int):
    """Analyze confidence trend for a claim."""
    log.info("=" * 60)
    log.info("CONFIDENCE TREND – CLAIM #%d", claim_id)
    log.info("=" * 60)

    from src.graph.confidence_timeline import ConfidenceTimeline
    tl = ConfidenceTimeline()
    trend = tl.analyze_trend(claim_id)
    log.info("  Current:       %.4f", trend.current_score)
    log.info("  Mean:          %.4f", trend.mean_score)
    log.info("  Std deviation: %.4f", trend.std_dev)
    log.info("  MA(5):         %.4f", trend.moving_avg)
    log.info("  EMA:           %.4f", trend.ema)
    log.info("  dC/dt:         %.6f /hr", trend.rate_of_change)
    log.info("  Direction:     %s", trend.trend_direction)
    log.info("  Converging:    %s", trend.is_converging)
    log.info("  Plateau:       %s (%.2f hrs)", trend.is_plateau, trend.plateau_duration_hours)
    log.info("  Snapshots:     %d", trend.total_snapshots)


def run_entropy_snapshot(claim_id: int):
    """Snapshot entropy for a claim (or all if 0)."""
    log.info("=" * 60)
    log.info("ENTROPY TIMELINE – SNAPSHOT")
    log.info("=" * 60)

    from src.graph.entropy_trend import EntropyTrendEngine
    engine = EntropyTrendEngine()
    if claim_id == 0:
        points = engine.snapshot_all()
        log.info("  Snapshotted %d claims.", len(points))
    else:
        point = engine.snapshot_claim(claim_id)
        log.info("  Claim #%d → H=%.4f drift=%.4f", claim_id,
                 point.shannon_entropy, point.drift_velocity)


def run_entropy_trend(claim_id: int):
    """Analyze entropy trend for a claim."""
    log.info("=" * 60)
    log.info("ENTROPY TREND – CLAIM #%d", claim_id)
    log.info("=" * 60)

    from src.graph.entropy_trend import EntropyTrendEngine
    engine = EntropyTrendEngine()
    trend = engine.analyze_trend(claim_id)
    log.info("  Current H:     %.4f", trend.current_entropy)
    log.info("  Mean H:        %.4f", trend.mean_entropy)
    log.info("  Std deviation: %.4f", trend.std_dev)
    log.info("  dH/dt:         %.6f /hr", trend.dh_dt)
    log.info("  d²H/dt²:       %.6f /hr²", trend.d2h_dt2)
    log.info("  Direction:     %s", trend.trend_direction)
    log.info("  Spike:         %s (mag=%.2f)", trend.is_spike, trend.spike_magnitude)
    log.info("  Collapse:      %s", trend.is_collapse)
    log.info("  Snapshots:     %d", trend.total_snapshots)


def run_drift_kinematics(claim_id: int):
    """Analyze drift kinematics for a claim."""
    log.info("=" * 60)
    log.info("DRIFT KINEMATICS – CLAIM #%d", claim_id)
    log.info("=" * 60)

    from src.graph.drift_kinematics import DriftKinematicsEngine
    engine = DriftKinematicsEngine()
    kin = engine.analyze(claim_id)
    log.info("  Current drift:    %.6f", kin.current_drift)
    log.info("  Velocity (dd/dt): %.6f", kin.current_velocity)
    log.info("  Acceleration:     %.6f", kin.current_acceleration)
    log.info("  Jerk:             %.6f", kin.current_jerk)
    log.info("  Mean velocity:    %.6f", kin.mean_velocity)
    log.info("  Max velocity:     %.6f", kin.max_velocity)
    log.info("  Phase:            %s", kin.phase)
    log.info("  Inflections:      %d", len(kin.inflection_points))
    log.info("  Snapshots:        %d", kin.total_snapshots)


def run_classify_claim(claim_id: int):
    """Classify a claim's stability state."""
    log.info("=" * 60)
    log.info("STABILITY CLASSIFIER – CLAIM #%d", claim_id)
    log.info("=" * 60)

    from src.graph.stability_classifier import StabilityClassifier
    classifier = StabilityClassifier()
    profile = classifier.classify(claim_id)
    log.info("  Classification:   %s", profile.classification.upper())
    log.info("  Confidence trend: %.6f", profile.confidence_trend)
    log.info("  Entropy trend:    %.6f", profile.entropy_trend)
    log.info("  Drift accel:      %.6f", profile.drift_accel)
    log.info("  Signal flags:     %d", len(profile.signal_flags))
    for flag in profile.signal_flags:
        log.info("    • %s", flag)


def run_classify_all():
    """Classify all claims and show distribution."""
    log.info("=" * 60)
    log.info("STABILITY CLASSIFIER – ALL CLAIMS")
    log.info("=" * 60)

    from src.graph.stability_classifier import StabilityClassifier
    classifier = StabilityClassifier()
    profiles = classifier.classify_all()
    summary = classifier.get_summary()
    log.info("  Classified %d claims:", len(profiles))
    for state in ("stable", "converging", "volatile", "diverging", "critical"):
        log.info("    %-12s %d", state, summary.get(state, 0))


def run_alert_scan(claim_id: int):
    """Scan a claim (or all if 0) for alerts."""
    log.info("=" * 60)
    log.info("ALERT ENGINE – SCAN")
    log.info("=" * 60)

    from src.graph.alert_engine import AlertEngine
    engine = AlertEngine()
    if claim_id == 0:
        alerts = engine.scan_all()
    else:
        alerts = engine.scan_claim(claim_id)
    log.info("  Generated %d alerts.", len(alerts))
    for alert in alerts[:20]:
        log.info("  [%s] %s: %s", alert.severity.upper(), alert.alert_type, alert.title)


def run_alert_list():
    """List all unacknowledged alerts."""
    log.info("=" * 60)
    log.info("ALERT ENGINE – PENDING ALERTS")
    log.info("=" * 60)

    from src.graph.alert_engine import AlertEngine
    engine = AlertEngine()
    alerts = engine.get_alerts(unacknowledged_only=True, limit=50)
    if not alerts:
        log.info("  No pending alerts.")
        return
    log.info("  %d unacknowledged alerts:", len(alerts))
    for alert in alerts:
        log.info("  #%-4d [%s] %s (claim #%d)",
                 alert.id, alert.severity.upper(), alert.title, alert.claim_id)


def run_lifecycle_report(claim_id: int):
    """Generate lifecycle report for a claim (or system if 0)."""
    from src.graph.lifecycle_report import LifecycleReport
    report = LifecycleReport()
    if claim_id == 0:
        print(report.generate())
    else:
        print(report.generate(claim_id=claim_id))


def run_quick_lifecycle(claim_id: int):
    """One-line lifecycle summary."""
    from src.graph.lifecycle_report import LifecycleReport
    report = LifecycleReport()
    print(report.quick_lifecycle(claim_id))


# ── Phase VI: Source Intelligence & Network Forensics ────────────────────

def run_source_reputation(source_id: int):
    """Snapshot reputation for a source (or all if 0)."""
    log.info("=" * 60)
    log.info("SOURCE REPUTATION – SNAPSHOT")
    log.info("=" * 60)

    from src.graph.source_reputation import SourceReputationEngine
    engine = SourceReputationEngine()
    if source_id == 0:
        snaps = engine.snapshot_all()
        log.info("  Snapshotted %d sources.", len(snaps))
    else:
        snap = engine.snapshot_source(source_id)
        log.info("  Source #%d: reliability=%.4f ema=%.4f trend=%s",
                 source_id, snap.reliability, snap.ema_credibility, snap.trend_direction)


def run_source_profile(source_id: int):
    """Show full reputation profile for a source."""
    log.info("=" * 60)
    log.info("SOURCE REPUTATION – PROFILE #%d", source_id)
    log.info("=" * 60)

    from src.graph.source_reputation import SourceReputationEngine
    engine = SourceReputationEngine()
    profile = engine.get_profile(source_id)
    log.info("  Title:            %s", profile.source_title)
    log.info("  Reliability idx:  %.4f", profile.reliability_index)
    log.info("  Grade:            %s", profile.grade)
    log.info("  Current EMA:      %.4f", profile.current_ema)
    log.info("  Accuracy rate:    %.4f", profile.accuracy_rate)
    log.info("  Support ratio:    %.4f", profile.support_ratio)
    log.info("  Support/Contra:   %d / %d", profile.support_count, profile.contradict_count)
    log.info("  Trend:            %s (delta=%.6f)", profile.trend_direction, profile.trend_delta)
    log.info("  Snapshots:        %d", profile.snapshot_count)


def run_rank_sources():
    """Rank all sources by reliability index."""
    log.info("=" * 60)
    log.info("SOURCE REPUTATION – RANKINGS")
    log.info("=" * 60)

    from src.graph.source_reputation import SourceReputationEngine
    engine = SourceReputationEngine()
    profiles = engine.rank_sources()
    if not profiles:
        log.info("  No sources to rank.")
        return
    for i, p in enumerate(profiles, 1):
        log.info("  %2d. [%s] %-40s idx=%.4f ema=%.4f claims=%d",
                 i, p.grade, p.source_title[:40], p.reliability_index,
                 p.current_ema, p.total_claims)


def run_build_influence():
    """Build source influence edges."""
    log.info("=" * 60)
    log.info("INFLUENCE NETWORK – BUILD EDGES")
    log.info("=" * 60)

    from src.graph.influence_network import InfluenceNetworkEngine
    engine = InfluenceNetworkEngine()
    edges = engine.build_edges()
    log.info("  Built %d influence edges.", len(edges))


def run_analyze_network():
    """Analyze the source influence network."""
    log.info("=" * 60)
    log.info("INFLUENCE NETWORK – ANALYSIS")
    log.info("=" * 60)

    from src.graph.influence_network import InfluenceNetworkEngine
    engine = InfluenceNetworkEngine()
    profile = engine.analyze_network()
    log.info("  Sources:     %d", profile.total_sources)
    log.info("  Edges:       %d", profile.total_edges)
    log.info("  Density:     %.4f", profile.density)
    log.info("  Components:  %d", profile.components)
    if profile.gateways:
        log.info("  Gateways:")
        for gw in profile.gateways[:5]:
            log.info("    Source #%d: betweenness=%.4f (%s)",
                     gw["source_id"], gw["betweenness"], gw.get("title", ""))
    if profile.bottlenecks:
        log.info("  Bottlenecks:")
        for bn in profile.bottlenecks[:5]:
            log.info("    Source #%d: removal -> %d components",
                     bn["source_id"], bn["components_if_removed"])
    if profile.top_amplifiers:
        log.info("  Top amplifiers:")
        for amp in profile.top_amplifiers[:5]:
            log.info("    Source #%d: amplification=%.4f (%s)",
                     amp["source_id"], amp["amplification_total"], amp.get("title", ""))


def run_coordination_scan(window: float):
    """Scan for coordinated source behavior."""
    log.info("=" * 60)
    log.info("COORDINATION DETECTOR – SCAN (window=%.1fh)", window)
    log.info("=" * 60)

    from src.graph.coordination_detector import CoordinationDetector
    detector = CoordinationDetector()
    events = detector.scan(window_hours=window)
    log.info("  Detected %d coordination events.", len(events))
    for ev in events[:10]:
        log.info("  [%s] score=%.4f sources=%d pattern=%s",
                 ev.cluster_id[:8], ev.coordination_score,
                 ev.source_count, ev.pattern_type)


def run_coordination_summary():
    """Show coordination detection summary."""
    log.info("=" * 60)
    log.info("COORDINATION DETECTOR – SUMMARY")
    log.info("=" * 60)

    from src.graph.coordination_detector import CoordinationDetector
    detector = CoordinationDetector()
    summary = detector.get_summary()
    log.info("  Total events:      %d", summary.total_events)
    log.info("  Unique clusters:   %d", summary.total_clusters)
    log.info("  Highest score:     %.4f", summary.highest_score)
    log.info("  Mean score:        %.4f", summary.mean_score)
    if summary.pattern_distribution:
        for pat, count in summary.pattern_distribution.items():
            log.info("    %s: %d", pat, count)


def run_provenance_trace(claim_id: int):
    """Trace deep provenance for a claim (or all if 0)."""
    log.info("=" * 60)
    log.info("DEEP PROVENANCE – TRACE")
    log.info("=" * 60)

    from src.graph.provenance_deep import DeepProvenanceEngine
    engine = DeepProvenanceEngine()
    if claim_id == 0:
        traces = engine.trace_all()
        log.info("  Traced %d claims.", len(traces))
    else:
        trace = engine.trace(claim_id)
        log.info("  Claim #%d: origin=%s depth=%d confidence=%.4f source=\"%s\"",
                 claim_id, trace.origin_type, trace.chain_depth,
                 trace.confidence, trace.origin_source[:40])


def run_provenance_summary():
    """Show deep provenance summary."""
    log.info("=" * 60)
    log.info("DEEP PROVENANCE – SUMMARY")
    log.info("=" * 60)

    from src.graph.provenance_deep import DeepProvenanceEngine
    engine = DeepProvenanceEngine()
    summary = engine.get_summary()
    log.info("  Traced claims:   %d", summary.total_traced)
    log.info("  Avg depth:       %.2f", summary.avg_chain_depth)
    log.info("  Max depth:       %d", summary.max_chain_depth)
    log.info("  Avg confidence:  %.4f", summary.avg_confidence)
    log.info("  Orphans:         %d", summary.orphan_count)
    if summary.origin_distribution:
        for origin, count in summary.origin_distribution.items():
            log.info("    %s: %d", origin, count)


def run_source_forensics(source_id: int):
    """Generate source forensics report."""
    from src.graph.source_forensics_report import SourceForensicsReportEngine
    engine = SourceForensicsReportEngine()
    print(engine.generate(source_id=source_id))


def run_quick_source(source_id: int):
    """One-line source intelligence summary."""
    from src.graph.source_forensics_report import SourceForensicsReportEngine
    engine = SourceForensicsReportEngine()
    print(engine.quick_source(source_id))


def run_all(pdf_path: str = ""):
    """Execute the complete research pipeline."""
    log.info("=" * 60)
    log.info("PROJECT ANCHOR – FULL PIPELINE")
    log.info("=" * 60)

    init_db()
    run_collection()
    run_academic_search()
    run_government_crossref()

    if pdf_path:
        run_pdf_analysis(pdf_path)

    run_physics()
    run_nlp()
    run_graph()
    run_reports()
    run_static_report()

    log.info("=" * 60)
    log.info("PIPELINE COMPLETE")
    log.info("=" * 60)


def main():
    parser = argparse.ArgumentParser(
        description="Project Anchor – Forensic Research Aggregation System",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("--all", action="store_true", help="Run complete pipeline")
    parser.add_argument("--collect", action="store_true", help="Data collection only")
    parser.add_argument("--academic", action="store_true", help="Academic search only")
    parser.add_argument("--government", action="store_true", help="Government cross-ref only")
    parser.add_argument("--analyze-pdf", type=str, help="Analyze a specific PDF file")
    parser.add_argument("--physics", action="store_true", help="Run physics computations")
    parser.add_argument("--waves", action="store_true", help="Run wave science computations")
    parser.add_argument("--nlp", action="store_true", help="Run NLP analysis")
    parser.add_argument("--graph", action="store_true", help="Build propagation graph")
    parser.add_argument("--report", action="store_true", help="Generate all reports")
    parser.add_argument("--static-report", action="store_true", help="Generate static HTML report")
    parser.add_argument("--dashboard", action="store_true", help="Launch interactive dashboard")
    parser.add_argument("--init-db", action="store_true", help="Initialize database only")

    # IPFS commands
    parser.add_argument("--ipfs-status", action="store_true", help="Show IPFS node status & archive stats")
    parser.add_argument("--ipfs-archive", action="store_true", help="Archive all evidence to IPFS")
    parser.add_argument("--ipfs-pin", type=str, help="Pin a specific file to IPFS")
    parser.add_argument("--ipfs-verify", action="store_true", help="Verify IPFS proof chain integrity")

    # Taxonomy & extended search commands
    parser.add_argument("--taxonomy", action="store_true", help="Load taxonomy knowledge base into DB")
    parser.add_argument("--taxonomy-search", type=str, help="Search taxonomy entries for TERM")
    parser.add_argument("--taxonomy-export", action="store_true", help="Export taxonomy to JSON")
    parser.add_argument("--arxiv", type=str, help="Search arXiv for TERM")
    parser.add_argument("--extended-search", action="store_true", help="Run all extended terms through scrapers")

    # Phase II commands
    parser.add_argument("--key-generate", action="store_true", help="Generate Ed25519 signing keypair")
    parser.add_argument("--sign-cid", type=str, help="Sign a CID with default key")
    parser.add_argument("--verify-cid", type=str, help="Verify a CID signature")
    parser.add_argument("--snapshot", action="store_true", help="Create Merkle snapshot of database")
    parser.add_argument("--verify-snapshot", action="store_true", help="Verify latest Merkle snapshot")
    parser.add_argument("--ipns-publish", type=str, help="Publish CID to IPNS")
    parser.add_argument("--ipns-resolve", action="store_true", help="Resolve current IPNS pointer")
    parser.add_argument("--generate-audit", action="store_true", help="Generate comprehensive audit report")
    parser.add_argument("--foia-search", type=str, help="Search all FOIA sources for query")
    parser.add_argument("--tesla", action="store_true", help="Run Tesla full investigation")
    parser.add_argument("--load-scientists", action="store_true", help="Load scientist cases into DB")
    parser.add_argument("--search-scientists", type=str, help="Search scientist cases by query")
    parser.add_argument("--gateway-health", action="store_true", help="Check multi-gateway health")

    # ── Phase III: Math Forensics & Claim Graph ──
    parser.add_argument("--parse-equation", type=str, help="Parse a plaintext equation (e.g. 'E = m*c**2')")
    parser.add_argument("--parse-latex", type=str, help="Parse a LaTeX equation string")
    parser.add_argument("--dim-check", type=str, help="Dimensional analysis on a known equation name")
    parser.add_argument("--simplify-eq", type=str, help="Simplify a plaintext expression")
    parser.add_argument("--math-audit", action="store_true", help="Run full math forensics audit on known equations")
    parser.add_argument("--add-claim", type=str, help="Add a claim to the evidence graph")
    parser.add_argument("--add-source", type=str, help="Add a source node (title)")
    parser.add_argument("--link-claim", type=str, help="Link claim→source: 'claim_id,source_id,relationship'")
    parser.add_argument("--claim-stats", action="store_true", help="Show claim graph statistics")
    parser.add_argument("--provenance", type=int, help="Show provenance chain for a claim ID")
    parser.add_argument("--contradictions", action="store_true", help="List all contradictions in claim graph")

    # ── Phase IV: Claim Confidence & Mutation Entropy ──
    parser.add_argument("--score-claim", type=int, help="Score a claim by ID with Bayesian confidence engine")
    parser.add_argument("--score-all", action="store_true", help="Score all claims and rank by confidence")
    parser.add_argument("--mutation-entropy", type=int, help="Analyze mutation entropy for a claim chain")
    parser.add_argument("--citation-density", type=int, help="Analyze citation density for a claim")
    parser.add_argument("--tension-map", action="store_true", help="Show contradiction tension map")
    parser.add_argument("--propagation", type=int, help="Track propagation velocity for a claim")
    parser.add_argument("--claim-report", nargs="?", type=int, const=0, help="Generate epistemic scoring report (optional claim ID)")
    parser.add_argument("--quick-score", type=int, help="One-line epistemic summary for a claim")

    # ── Phase V: Temporal Epistemic Dynamics ──
    parser.add_argument("--conf-snapshot", nargs="?", type=int, const=0, help="Snapshot confidence (optional claim ID, 0=all)")
    parser.add_argument("--conf-trend", type=int, help="Analyze confidence trend for a claim")
    parser.add_argument("--entropy-snapshot", nargs="?", type=int, const=0, help="Snapshot entropy (optional claim ID, 0=all)")
    parser.add_argument("--entropy-trend", type=int, help="Analyze entropy trend for a claim")
    parser.add_argument("--drift-kinematics", type=int, help="Drift kinematics analysis for a claim")
    parser.add_argument("--classify-claim", type=int, help="Classify a claim's stability state")
    parser.add_argument("--classify-all", action="store_true", help="Classify all claims and show distribution")
    parser.add_argument("--alert-scan", nargs="?", type=int, const=0, help="Scan for alerts (optional claim ID, 0=all)")
    parser.add_argument("--alert-list", action="store_true", help="List pending alerts")
    parser.add_argument("--lifecycle", nargs="?", type=int, const=0, help="Lifecycle report (optional claim ID, 0=system)")
    parser.add_argument("--quick-lifecycle", type=int, help="One-line lifecycle summary for a claim")

    # ── Phase VI: Source Intelligence & Network Forensics ──
    parser.add_argument("--source-snapshot", nargs="?", type=int, const=0, help="Snapshot source reputation (optional source ID, 0=all)")
    parser.add_argument("--source-profile", type=int, help="Full reputation profile for a source")
    parser.add_argument("--source-rank", action="store_true", help="Rank all sources by reliability index")
    parser.add_argument("--influence-build", action="store_true", help="Build source influence edges")
    parser.add_argument("--influence-network", action="store_true", help="Analyze the source influence network")
    parser.add_argument("--coord-scan", nargs="?", type=float, const=24.0, help="Scan for coordination (optional window hours, default=24)")
    parser.add_argument("--coord-summary", action="store_true", help="Coordination detection summary")
    parser.add_argument("--provenance-trace", nargs="?", type=int, const=0, help="Trace deep provenance (optional claim ID, 0=all)")
    parser.add_argument("--provenance-summary", action="store_true", help="Deep provenance summary")
    parser.add_argument("--source-report", nargs="?", type=int, const=0, help="Source forensics report (optional source ID, 0=ecosystem)")
    parser.add_argument("--quick-source", type=int, help="One-line source intelligence summary")

    args = parser.parse_args()

    # Always init DB
    init_db()

    if args.all:
        run_all(pdf_path=args.analyze_pdf or "")
    elif args.collect:
        run_collection()
    elif args.academic:
        run_academic_search()
    elif args.government:
        run_government_crossref()
    elif args.analyze_pdf:
        run_pdf_analysis(args.analyze_pdf)
    elif args.physics:
        run_physics()
    elif args.waves:
        run_waves()
    elif args.nlp:
        run_nlp()
    elif args.graph:
        run_graph()
    elif args.report:
        run_reports()
    elif args.static_report:
        run_static_report()
    elif args.dashboard:
        run_dashboard()
    elif args.init_db:
        log.info("Database initialized.")
    elif args.ipfs_status:
        run_ipfs_status()
    elif args.ipfs_archive:
        run_ipfs_archive()
    elif args.ipfs_pin:
        run_ipfs_pin_file(args.ipfs_pin)
    elif args.ipfs_verify:
        run_ipfs_verify()
    elif args.taxonomy:
        run_taxonomy_load()
    elif args.taxonomy_search:
        run_taxonomy_search(args.taxonomy_search)
    elif args.taxonomy_export:
        run_taxonomy_export()
    elif args.arxiv:
        run_arxiv_search(args.arxiv)
    elif args.extended_search:
        run_extended_search()
    elif args.key_generate:
        run_key_generate()
    elif args.sign_cid:
        run_sign_cid(args.sign_cid)
    elif args.verify_cid:
        run_verify_cid(args.verify_cid)
    elif args.snapshot:
        run_snapshot()
    elif args.verify_snapshot:
        run_verify_snapshot()
    elif args.ipns_publish:
        run_ipns_publish(args.ipns_publish)
    elif args.ipns_resolve:
        run_ipns_resolve()
    elif args.generate_audit:
        run_generate_audit()
    elif args.foia_search:
        run_foia_search(args.foia_search)
    elif args.tesla:
        run_tesla_investigation()
    elif args.load_scientists:
        run_load_scientist_cases()
    elif args.search_scientists:
        run_search_scientists(args.search_scientists)
    elif args.gateway_health:
        run_gateway_health()
    elif args.parse_equation:
        run_parse_equation(args.parse_equation)
    elif args.parse_latex:
        run_parse_latex(args.parse_latex)
    elif args.dim_check:
        run_dim_check(args.dim_check)
    elif args.simplify_eq:
        run_simplify_equation(args.simplify_eq)
    elif args.math_audit:
        run_math_audit()
    elif args.add_claim:
        run_add_claim(args.add_claim)
    elif args.add_source:
        run_add_source(args.add_source)
    elif args.link_claim:
        run_link_claim(args.link_claim)
    elif args.claim_stats:
        run_claim_stats()
    elif args.provenance:
        run_provenance(args.provenance)
    elif args.contradictions:
        run_contradictions()
    elif args.score_claim:
        run_score_claim(args.score_claim)
    elif args.score_all:
        run_score_all()
    elif args.mutation_entropy:
        run_mutation_entropy(args.mutation_entropy)
    elif args.citation_density:
        run_citation_density(args.citation_density)
    elif args.tension_map:
        run_tension_map()
    elif args.propagation:
        run_propagation_velocity(args.propagation)
    elif args.claim_report is not None:
        run_claim_report(args.claim_report)
    elif args.quick_score:
        run_quick_score(args.quick_score)
    elif args.conf_snapshot is not None:
        run_confidence_snapshot(args.conf_snapshot)
    elif args.conf_trend:
        run_confidence_trend(args.conf_trend)
    elif args.entropy_snapshot is not None:
        run_entropy_snapshot(args.entropy_snapshot)
    elif args.entropy_trend:
        run_entropy_trend(args.entropy_trend)
    elif args.drift_kinematics:
        run_drift_kinematics(args.drift_kinematics)
    elif args.classify_claim:
        run_classify_claim(args.classify_claim)
    elif args.classify_all:
        run_classify_all()
    elif args.alert_scan is not None:
        run_alert_scan(args.alert_scan)
    elif args.alert_list:
        run_alert_list()
    elif args.lifecycle is not None:
        run_lifecycle_report(args.lifecycle)
    elif args.quick_lifecycle:
        run_quick_lifecycle(args.quick_lifecycle)
    # ── Phase VI dispatch ──
    elif args.source_snapshot is not None:
        run_source_reputation(args.source_snapshot)
    elif args.source_profile:
        run_source_profile(args.source_profile)
    elif args.source_rank:
        run_rank_sources()
    elif args.influence_build:
        run_build_influence()
    elif args.influence_network:
        run_analyze_network()
    elif args.coord_scan is not None:
        run_coordination_scan(args.coord_scan)
    elif args.coord_summary:
        run_coordination_summary()
    elif args.provenance_trace is not None:
        run_provenance_trace(args.provenance_trace)
    elif args.provenance_summary:
        run_provenance_summary()
    elif args.source_report is not None:
        run_source_forensics(args.source_report)
    elif args.quick_source:
        run_quick_source(args.quick_source)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
