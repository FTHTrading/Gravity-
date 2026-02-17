"""
Equation Audit Report – Forensic Analysis Report Generator for Mathematical Proofs

Produces comprehensive reports covering:
  - Equation parse fidelity
  - Dimensional consistency
  - Symbolic simplification history
  - Derivation chain integrity
  - IPFS anchoring status
  - Cryptographic signature status
"""

import json
from datetime import datetime, timezone
from typing import Optional

from src.database import query_rows
from src.logger import get_logger

log = get_logger(__name__)


class EquationAuditReport:
    """Generates forensic audit reports for mathematical proof chains."""

    def __init__(self):
        self.sections: list[dict] = []
        self.metadata = {
            "generated_at": "",
            "equation_count": 0,
            "derivation_count": 0,
            "dimensional_checks": 0,
            "ipfs_anchored": 0,
            "signed": 0,
        }

    def generate(
        self,
        parsed_equations: list = None,
        dimensional_reports: list = None,
        derivation_chains: list = None,
        refactor_results: list = None,
    ) -> str:
        """
        Generate a full audit report.

        Args:
            parsed_equations: list of ParsedEquation objects
            dimensional_reports: list of DimensionalReport objects
            derivation_chains: list of DerivationChain objects
            refactor_results: list of RefactorResult objects

        Returns:
            Formatted report string
        """
        self.metadata["generated_at"] = datetime.now(timezone.utc).isoformat()
        self.sections = []

        # Section 1: Header
        self._add_header()

        # Section 2: Equation Inventory
        if parsed_equations:
            self._add_equation_inventory(parsed_equations)

        # Section 3: Dimensional Analysis
        if dimensional_reports:
            self._add_dimensional_analysis(dimensional_reports)

        # Section 4: Symbolic Refactoring
        if refactor_results:
            self._add_refactoring_summary(refactor_results)

        # Section 5: Derivation Chains
        if derivation_chains:
            self._add_derivation_chains(derivation_chains)

        # Section 6: Integrity Summary
        self._add_integrity_summary(
            parsed_equations or [],
            dimensional_reports or [],
            derivation_chains or [],
        )

        # Section 7: Database Proofs
        self._add_database_proofs()

        # Section 8: Recommendations
        self._add_recommendations(dimensional_reports or [])

        return self._render()

    def _add_header(self):
        self.sections.append({
            "title": "MATHEMATICAL FORENSICS AUDIT REPORT",
            "content": [
                f"Generated: {self.metadata['generated_at']}",
                "System: Project Anchor – Mathematical Integrity Layer",
                "Protocol: Phase III – Equation Forensics Engine",
                "=" * 72,
            ],
        })

    def _add_equation_inventory(self, equations: list):
        lines = [f"Total equations analyzed: {len(equations)}", ""]
        self.metadata["equation_count"] = len(equations)

        for i, eq in enumerate(equations, 1):
            lines.append(f"  [{i}] {eq.name}")
            lines.append(f"      Input: {eq.original_input[:80]}")
            lines.append(f"      Format: {eq.input_format}")
            if eq.parse_error:
                lines.append(f"      ⚠ PARSE ERROR: {eq.parse_error}")
            else:
                lines.append(f"      Symbols: {', '.join(eq.symbols_found)}")
                lines.append(f"      SHA-256: {eq.sha256[:32]}…")
                if eq.is_equation:
                    lines.append(f"      LHS: {eq.lhs}")
                    lines.append(f"      RHS: {eq.rhs}")
            lines.append("")

        self.sections.append({
            "title": "EQUATION INVENTORY",
            "content": lines,
        })

    def _add_dimensional_analysis(self, reports: list):
        lines = [f"Equations checked: {len(reports)}", ""]
        self.metadata["dimensional_checks"] = len(reports)

        valid = sum(1 for r in reports if r.status == "valid")
        invalid = sum(1 for r in reports if r.status == "invalid")
        partial = sum(1 for r in reports if r.status == "partial")

        lines.append(f"  Valid:   {valid}")
        lines.append(f"  Invalid: {invalid}")
        lines.append(f"  Partial: {partial}")
        lines.append("")

        for r in reports:
            status_icon = {"valid": "✓", "invalid": "✗", "partial": "~"}.get(r.status, "?")
            lines.append(f"  [{status_icon}] {r.equation_name}")
            if r.lhs_dimension:
                lines.append(f"      LHS dimension: {r.lhs_dimension}")
            if r.rhs_dimension:
                lines.append(f"      RHS dimension: {r.rhs_dimension}")
            if r.errors:
                for err in r.errors:
                    lines.append(f"      ERROR: {err}")
            if r.warnings:
                for warn in r.warnings:
                    lines.append(f"      WARN: {warn}")
            if r.unknown_symbols:
                lines.append(f"      Unknown symbols: {', '.join(r.unknown_symbols)}")
            lines.append("")

        self.sections.append({
            "title": "DIMENSIONAL ANALYSIS",
            "content": lines,
        })

    def _add_refactoring_summary(self, results: list):
        lines = [f"Operations performed: {len(results)}", ""]

        for r in results:
            equiv_mark = "≡" if r.is_equivalent else "≠"
            lines.append(f"  [{r.operation}] {r.input_expr[:50]}")
            lines.append(f"    → {r.output_expr[:50]}")
            lines.append(f"    Equivalence: {equiv_mark}")
            lines.append(f"    Complexity: {r.complexity_before} → {r.complexity_after}")
            if r.notes:
                for note in r.notes:
                    lines.append(f"    Note: {note}")
            lines.append("")

        self.sections.append({
            "title": "SYMBOLIC REFACTORING",
            "content": lines,
        })

    def _add_derivation_chains(self, chains: list):
        lines = [f"Derivations recorded: {len(chains)}", ""]
        self.metadata["derivation_count"] = len(chains)

        for chain in chains:
            lines.append(f"  ▸ {chain.name}")
            lines.append(f"    Steps: {len(chain.steps)}")
            lines.append(f"    Start: {chain.starting_expr[:60]}")
            lines.append(f"    Final: {chain.final_expr[:60]}")
            if chain.sha256:
                lines.append(f"    SHA-256: {chain.sha256[:32]}…")
            if chain.ipfs_cid:
                lines.append(f"    IPFS CID: {chain.ipfs_cid}")
                self.metadata["ipfs_anchored"] += 1
            if chain.signature_hex:
                lines.append(f"    Signed: {chain.signature_hex[:32]}…")
                self.metadata["signed"] += 1
            lines.append("")

            # Detail each step
            for step in chain.steps:
                valid_mark = "✓" if step.is_valid else "✗"
                lines.append(f"      Step {step.step_number} [{valid_mark}] {step.operation}")
                lines.append(f"        In:  {step.input_expr[:60]}")
                lines.append(f"        Out: {step.output_expr[:60]}")
                if step.justification:
                    lines.append(f"        Why: {step.justification[:60]}")
            lines.append("")

        self.sections.append({
            "title": "DERIVATION CHAINS",
            "content": lines,
        })

    def _add_integrity_summary(self, equations, dim_reports, chains):
        lines = []

        total_eq = len(equations)
        parse_ok = sum(1 for e in equations if not e.parse_error)
        dim_valid = sum(1 for r in dim_reports if r.status == "valid")
        anchored = sum(1 for c in chains if c.ipfs_cid)
        signed = sum(1 for c in chains if c.signature_hex)

        lines.append(f"  Equations parsed:       {parse_ok}/{total_eq}")
        lines.append(f"  Dimensionally valid:    {dim_valid}/{len(dim_reports)}")
        lines.append(f"  Derivations recorded:   {len(chains)}")
        lines.append(f"  IPFS anchored:          {anchored}")
        lines.append(f"  Cryptographically signed: {signed}")
        lines.append("")

        # Compute integrity score
        scores = []
        if total_eq > 0:
            scores.append(parse_ok / total_eq)
        if dim_reports:
            scores.append(dim_valid / len(dim_reports))
        if chains:
            scores.append(anchored / len(chains))
            scores.append(signed / len(chains))
        integrity = (sum(scores) / len(scores) * 100) if scores else 0
        lines.append(f"  OVERALL INTEGRITY SCORE: {integrity:.1f}%")

        self.sections.append({
            "title": "INTEGRITY SUMMARY",
            "content": lines,
        })

    def _add_database_proofs(self):
        """Pull equation_proofs from DB for cross-reference."""
        lines = []
        try:
            proofs = query_rows("equation_proofs", "1=1")
            lines.append(f"  Total proofs in database: {len(proofs)}")
            for p in proofs[:20]:  # Limit output
                lines.append(
                    f"    ID={p['id']} | {p['equation_name']} | "
                    f"Status={p.get('verification_status', '?')} | "
                    f"CID={p.get('ipfs_cid', '')[:20] or 'none'}"
                )
        except Exception:
            lines.append("  (No equation_proofs table data available)")

        self.sections.append({
            "title": "DATABASE PROOF RECORDS",
            "content": lines,
        })

    def _add_recommendations(self, dim_reports: list):
        lines = []

        invalid = [r for r in dim_reports if r.status == "invalid"]
        partial = [r for r in dim_reports if r.status == "partial"]

        if invalid:
            lines.append("  ⚠ DIMENSIONAL MISMATCHES DETECTED:")
            for r in invalid:
                lines.append(f"    - {r.equation_name}: {'; '.join(r.errors)}")
            lines.append("")

        if partial:
            lines.append("  ℹ INCOMPLETE DIMENSIONAL ANALYSIS:")
            for r in partial:
                lines.append(
                    f"    - {r.equation_name}: unknown symbols = "
                    f"{', '.join(r.unknown_symbols)}"
                )
            lines.append("    → Register symbol dimensions to complete analysis")
            lines.append("")

        if not invalid and not partial:
            lines.append("  All checked equations are dimensionally consistent.")
            lines.append("")

        lines.append("  General recommendations:")
        lines.append("    1. Run dimensional analysis on ALL submitted equations")
        lines.append("    2. Anchor finalized derivations to IPFS")
        lines.append("    3. Sign all anchored CIDs with Ed25519 key")
        lines.append("    4. Take Merkle snapshot after batch updates")

        self.sections.append({
            "title": "RECOMMENDATIONS",
            "content": lines,
        })

    def _render(self) -> str:
        """Render all sections to a formatted string."""
        lines = []
        for section in self.sections:
            lines.append("")
            lines.append(f"{'─' * 72}")
            lines.append(f"  {section['title']}")
            lines.append(f"{'─' * 72}")
            for line in section["content"]:
                lines.append(line)
        lines.append("")
        lines.append("=" * 72)
        lines.append("  END OF MATHEMATICAL FORENSICS AUDIT REPORT")
        lines.append("=" * 72)
        return "\n".join(lines)

    def to_json(self) -> str:
        """Return the report data as JSON."""
        return json.dumps({
            "metadata": self.metadata,
            "sections": self.sections,
        }, indent=2, default=str)
