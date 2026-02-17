"""
Claim Scoring Report – Aggregate Epistemics Report Generator

Combines all Phase IV scoring modules into a single forensic report:
  - Bayesian Confidence analysis
  - Mutation Entropy & drift profiling
  - Citation Density metrics
  - Contradiction Tension mapping
  - Propagation Velocity tracking
  - Overall epistemic integrity score

Produces both human-readable and JSON output.
"""

import json
import math
from datetime import datetime, timezone
from typing import Optional

from src.graph.confidence_scorer import ConfidenceScorer
from src.graph.mutation_entropy import MutationEntropy
from src.graph.citation_density import CitationDensity
from src.graph.contradiction_analyzer import ContradictionAnalyzer
from src.graph.propagation_tracker import PropagationTracker
from src.graph.claim_graph import ClaimGraph
from src.logger import get_logger

log = get_logger(__name__)


class ClaimScoringReport:
    """Generates aggregate epistemic scoring reports for the claim graph."""

    def __init__(self):
        self.graph = ClaimGraph()
        self.scorer = ConfidenceScorer()
        self.entropy = MutationEntropy()
        self.density = CitationDensity()
        self.contradictions = ContradictionAnalyzer()
        self.propagation = PropagationTracker()

        self.sections: list[dict] = []
        self.metadata: dict = {}
        self._claim_data: list[dict] = []

    # ── Main Report ──────────────────────────────────────────────────────

    def generate(self, claim_ids: list[int] | None = None) -> str:
        """
        Generate full epistemic scoring report.

        Args:
            claim_ids: Specific claims to report on, or None for all.

        Returns:
            Formatted report string.
        """
        now = datetime.now(timezone.utc).isoformat()
        self.metadata = {
            "generated_at": now,
            "protocol": "Phase IV – Claim Confidence & Mutation Entropy Engine",
            "system": "Project Anchor – Quantitative Epistemics Layer",
        }
        self.sections = []
        self._claim_data = []

        # Determine scope
        if claim_ids:
            claims = [self.graph.get_claim(cid) for cid in claim_ids]
            claims = [c for c in claims if c is not None]
        else:
            claims = self.graph.get_all_claims()

        if not claims:
            self._add_header()
            self.sections.append({
                "title": "NO CLAIMS FOUND",
                "content": ["  No claims in the evidence graph to analyze."],
            })
            return self._render()

        self.metadata["claim_count"] = len(claims)

        # Collect per-claim data
        for claim in claims:
            data = self._analyze_claim(claim.id)
            self._claim_data.append(data)

        # Build report sections
        self._add_header()
        self._add_overview()
        self._add_confidence_section()
        self._add_entropy_section()
        self._add_citation_section()
        self._add_contradiction_section()
        self._add_propagation_section()
        self._add_epistemic_integrity_score()
        self._add_risk_flags()
        self._add_recommendations()

        report = self._render()
        log.info("Generated claim scoring report for %d claims", len(claims))
        return report

    def _analyze_claim(self, claim_id: int) -> dict:
        """Run all scoring engines on a single claim."""
        claim = self.graph.get_claim(claim_id)
        data = {
            "claim_id": claim_id,
            "claim_text": claim.claim_text if claim else "?",
            "claim_type": claim.claim_type if claim else "?",
        }

        # Confidence
        try:
            score = self.scorer.score_claim(claim_id)
            data["confidence"] = score
        except Exception:
            data["confidence"] = None

        # Entropy
        try:
            chain = self.graph.get_mutation_chain(claim_id)
            if len(chain) >= 2:
                metrics = self.entropy.analyze_chain(claim_id)
                data["entropy"] = metrics
            else:
                data["entropy"] = None
        except Exception:
            data["entropy"] = None

        # Citation density
        try:
            cite = self.density.analyze_claim(claim_id)
            data["citation"] = cite
        except Exception:
            data["citation"] = None

        # Contradiction profile
        try:
            profile = self.contradictions.profile_claim(claim_id)
            data["contradiction"] = profile
        except Exception:
            data["contradiction"] = None

        # Propagation
        try:
            prop = self.propagation.analyze_propagation(claim_id)
            data["propagation"] = prop
        except Exception:
            data["propagation"] = None

        return data

    # ── Section Builders ─────────────────────────────────────────────────

    def _add_header(self):
        self.sections.append({
            "title": "CLAIM CONFIDENCE & EPISTEMIC SCORING REPORT",
            "content": [
                f"Generated: {self.metadata['generated_at']}",
                f"System: {self.metadata.get('system', '')}",
                f"Protocol: {self.metadata.get('protocol', '')}",
                "=" * 72,
            ],
        })

    def _add_overview(self):
        lines = [
            f"Total claims analyzed: {len(self._claim_data)}",
            "",
        ]

        # Type distribution
        type_counts: dict[str, int] = {}
        for d in self._claim_data:
            t = d.get("claim_type", "unknown")
            type_counts[t] = type_counts.get(t, 0) + 1

        for t, count in sorted(type_counts.items()):
            lines.append(f"  {t:20s} {count}")

        self.sections.append({"title": "OVERVIEW", "content": lines})

    def _add_confidence_section(self):
        lines = []
        scored = [d for d in self._claim_data if d.get("confidence")]

        if not scored:
            lines.append("  No confidence scores computed.")
            self.sections.append({"title": "BAYESIAN CONFIDENCE", "content": lines})
            return

        scores = [d["confidence"].composite for d in scored]
        avg_score = sum(scores) / len(scores)
        lines.append(f"  Claims scored: {len(scored)}")
        lines.append(f"  Average confidence: {avg_score:.4f}")
        lines.append(f"  Min: {min(scores):.4f}  Max: {max(scores):.4f}")
        lines.append("")

        # Top 10 by confidence
        ranked = sorted(scored, key=lambda d: d["confidence"].composite,
                         reverse=True)
        lines.append("  Top claims by confidence:")
        for d in ranked[:10]:
            s = d["confidence"]
            text = d["claim_text"][:50]
            lines.append(f"    #{d['claim_id']:4d}  {s.composite:.4f}  {text}")

        lines.append("")

        # Bottom 5 (weakest claims)
        lines.append("  Weakest claims:")
        for d in ranked[-5:]:
            s = d["confidence"]
            text = d["claim_text"][:50]
            lines.append(f"    #{d['claim_id']:4d}  {s.composite:.4f}  {text}")

        self.sections.append({"title": "BAYESIAN CONFIDENCE", "content": lines})

    def _add_entropy_section(self):
        lines = []
        with_entropy = [d for d in self._claim_data if d.get("entropy")]

        if not with_entropy:
            lines.append("  No mutation chains to analyze.")
            self.sections.append(
                {"title": "MUTATION ENTROPY & DRIFT", "content": lines}
            )
            return

        entropies = [d["entropy"].shannon_entropy for d in with_entropy]
        drifts = [d["entropy"].drift_velocity for d in with_entropy]

        lines.append(f"  Claims with mutation chains: {len(with_entropy)}")
        lines.append(f"  Avg Shannon entropy: {sum(entropies)/len(entropies):.4f}")
        lines.append(f"  Avg drift velocity: {sum(drifts)/len(drifts):.4f}")
        lines.append("")

        # High entropy claims
        high_ent = sorted(with_entropy,
                          key=lambda d: d["entropy"].shannon_entropy,
                          reverse=True)
        lines.append("  Highest entropy claims (most content volatility):")
        for d in high_ent[:5]:
            e = d["entropy"]
            lines.append(
                f"    #{d['claim_id']:4d}  H={e.shannon_entropy:.4f}  "
                f"drift={e.drift_velocity:.4f}  stability={e.semantic_stability:.4f}"
            )

        self.sections.append(
            {"title": "MUTATION ENTROPY & DRIFT", "content": lines}
        )

    def _add_citation_section(self):
        lines = []
        with_cite = [d for d in self._claim_data if d.get("citation")]

        if not with_cite:
            lines.append("  No citation data available.")
            self.sections.append(
                {"title": "CITATION DENSITY", "content": lines}
            )
            return

        densities = [d["citation"].density_score for d in with_cite]
        avg_density = sum(densities) / len(densities)

        lines.append(f"  Claims with citation data: {len(with_cite)}")
        lines.append(f"  Average density score: {avg_density:.4f}")
        lines.append("")

        # Top cited
        ranked = sorted(with_cite,
                        key=lambda d: d["citation"].density_score,
                        reverse=True)
        lines.append("  Most densely cited claims:")
        for d in ranked[:10]:
            c = d["citation"]
            lines.append(
                f"    #{d['claim_id']:4d}  density={c.density_score:.4f}  "
                f"sources={c.unique_sources}  depth={c.citation_depth}"
            )

        lines.append("")

        # Uncited
        uncited = [d for d in with_cite if d["citation"].direct_citations == 0]
        if uncited:
            lines.append(f"  ⚠ Uncited claims: {len(uncited)}")
            for d in uncited[:5]:
                lines.append(f"    #{d['claim_id']:4d}  {d['claim_text'][:50]}")

        self.sections.append({"title": "CITATION DENSITY", "content": lines})

    def _add_contradiction_section(self):
        lines = []
        with_contra = [d for d in self._claim_data if d.get("contradiction")]

        if not with_contra:
            lines.append("  No contradiction data available.")
            self.sections.append(
                {"title": "CONTRADICTION TENSION MAP", "content": lines}
            )
            return

        contested = [d for d in with_contra
                      if d["contradiction"].is_contested]
        tensions = [d["contradiction"].tension_score for d in with_contra]
        avg_tension = sum(tensions) / len(tensions) if tensions else 0

        lines.append(f"  Claims analyzed: {len(with_contra)}")
        lines.append(f"  Contested claims: {len(contested)}")
        lines.append(f"  Average tension: {avg_tension:.4f}")
        lines.append("")

        # Conflict clusters
        try:
            clusters = self.contradictions.find_conflict_clusters()
            if clusters:
                lines.append(f"  Conflict clusters detected: {len(clusters)}")
                for i, cluster in enumerate(clusters[:5], 1):
                    members = ", ".join(f"#{m}" for m in cluster.claim_ids[:8])
                    lines.append(
                        f"    Cluster {i}: size={cluster.size}  "
                        f"tension={cluster.total_tension:.2f}  [{members}]"
                    )
                lines.append("")
        except Exception:
            pass

        # Highest tension
        if contested:
            lines.append("  Highest tension claims:")
            ranked = sorted(contested,
                            key=lambda d: d["contradiction"].tension_score,
                            reverse=True)
            for d in ranked[:5]:
                c = d["contradiction"]
                lines.append(
                    f"    #{d['claim_id']:4d}  tension={c.tension_score:.4f}  "
                    f"contradictions={c.contradiction_count}  "
                    f"{d['claim_text'][:40]}"
                )

        self.sections.append(
            {"title": "CONTRADICTION TENSION MAP", "content": lines}
        )

    def _add_propagation_section(self):
        lines = []
        with_prop = [d for d in self._claim_data if d.get("propagation")]

        if not with_prop:
            lines.append("  No propagation data available.")
            self.sections.append(
                {"title": "PROPAGATION VELOCITY", "content": lines}
            )
            return

        velocities = [d["propagation"].velocity for d in with_prop]
        spreads = [d["propagation"].total_spread for d in with_prop]
        amps = [d["propagation"].amplification_factor for d in with_prop]

        lines.append(f"  Claims tracked: {len(with_prop)}")
        lines.append(f"  Avg velocity: {sum(velocities)/len(velocities):.4f} events/hr")
        lines.append(f"  Avg spread: {sum(spreads)/len(spreads):.2f}")
        lines.append(f"  Avg amplification: {sum(amps)/len(amps):.4f}")
        lines.append("")

        # Fastest spreading
        ranked = sorted(with_prop,
                        key=lambda d: d["propagation"].velocity,
                        reverse=True)
        lines.append("  Fastest spreading claims:")
        for d in ranked[:5]:
            p = d["propagation"]
            lines.append(
                f"    #{d['claim_id']:4d}  vel={p.velocity:.4f}  "
                f"spread={p.total_spread}  amp={p.amplification_factor:.2f}"
            )

        self.sections.append(
            {"title": "PROPAGATION VELOCITY", "content": lines}
        )

    def _add_epistemic_integrity_score(self):
        """
        Compute aggregate epistemic integrity score (0–100).

        Weighted combination:
          - avg_confidence × 0.30
          - avg_citation_density × 0.20
          - inverse avg_tension × 0.20
          - avg_semantic_stability × 0.15
          - citation coverage × 0.15
        """
        lines = []

        components = {}

        # Confidence component
        scored = [d for d in self._claim_data if d.get("confidence")]
        if scored:
            avg_conf = sum(d["confidence"].composite for d in scored) / len(scored)
            components["confidence"] = avg_conf
        else:
            components["confidence"] = 0.0

        # Citation density component
        with_cite = [d for d in self._claim_data if d.get("citation")]
        if with_cite:
            avg_dense = sum(
                d["citation"].density_score for d in with_cite
            ) / len(with_cite)
            components["citation_density"] = avg_dense
        else:
            components["citation_density"] = 0.0

        # Inverse tension component
        with_contra = [d for d in self._claim_data if d.get("contradiction")]
        if with_contra:
            avg_tension = sum(
                d["contradiction"].tension_score for d in with_contra
            ) / len(with_contra)
            # Inverse: lower tension = better
            components["inverse_tension"] = 1.0 / (1.0 + avg_tension)
        else:
            components["inverse_tension"] = 1.0

        # Semantic stability component
        with_ent = [d for d in self._claim_data if d.get("entropy")]
        if with_ent:
            avg_stab = sum(
                d["entropy"].semantic_stability for d in with_ent
            ) / len(with_ent)
            components["semantic_stability"] = max(avg_stab, 0.0)
        else:
            components["semantic_stability"] = 1.0  # no mutations = stable

        # Citation coverage
        total = len(self._claim_data)
        cited = sum(
            1 for d in self._claim_data
            if d.get("citation") and d["citation"].direct_citations > 0
        )
        coverage = cited / total if total > 0 else 0.0
        components["citation_coverage"] = coverage

        # Weighted composite
        weights = {
            "confidence": 0.30,
            "citation_density": 0.20,
            "inverse_tension": 0.20,
            "semantic_stability": 0.15,
            "citation_coverage": 0.15,
        }
        composite = sum(
            components[k] * weights[k] for k in weights
        )
        integrity_pct = min(composite * 100, 100.0)

        self.metadata["epistemic_integrity_score"] = round(integrity_pct, 2)

        lines.append(f"  EPISTEMIC INTEGRITY SCORE: {integrity_pct:.1f}%")
        lines.append("")
        lines.append("  Component breakdown:")
        for k in weights:
            val = components[k]
            w = weights[k]
            lines.append(f"    {k:25s} {val:.4f} × {w:.2f} = {val*w:.4f}")
        lines.append(f"    {'':25s} {'─'*24}")
        lines.append(f"    {'Composite':25s} {composite:.4f}  ({integrity_pct:.1f}%)")

        self.sections.append(
            {"title": "EPISTEMIC INTEGRITY SCORE", "content": lines}
        )

    def _add_risk_flags(self):
        """Flag high-risk claims: low confidence + high tension + low citation."""
        lines = []
        flags = []

        for d in self._claim_data:
            reasons = []
            conf = d.get("confidence")
            if conf and conf.composite < 0.25:
                reasons.append(f"low confidence ({conf.composite:.2f})")

            contra = d.get("contradiction")
            if contra and contra.is_contested:
                reasons.append(f"contested (tension={contra.tension_score:.2f})")

            cite = d.get("citation")
            if cite and cite.direct_citations == 0:
                reasons.append("uncited")

            ent = d.get("entropy")
            if ent and ent.semantic_stability < 0.3:
                reasons.append(f"high drift (stability={ent.semantic_stability:.2f})")

            if reasons:
                flags.append((d["claim_id"], d["claim_text"][:50], reasons))

        if flags:
            lines.append(f"  ⚠ Risk flags raised: {len(flags)}")
            lines.append("")
            for cid, text, reasons in flags[:15]:
                lines.append(f"  #{cid:4d}  {text}")
                for r in reasons:
                    lines.append(f"         → {r}")
                lines.append("")
        else:
            lines.append("  No risk flags. All claims within acceptable parameters.")

        self.sections.append({"title": "RISK FLAGS", "content": lines})

    def _add_recommendations(self):
        lines = []

        # Analyze patterns
        uncited = sum(
            1 for d in self._claim_data
            if d.get("citation") and d["citation"].direct_citations == 0
        )
        contested = sum(
            1 for d in self._claim_data
            if d.get("contradiction") and d["contradiction"].is_contested
        )
        low_conf = sum(
            1 for d in self._claim_data
            if d.get("confidence") and d["confidence"].composite < 0.3
        )

        if uncited > 0:
            lines.append(f"  1. {uncited} claims lack citations — add source references")
        if contested > 0:
            lines.append(f"  2. {contested} claims are contested — resolve contradictions")
        if low_conf > 0:
            lines.append(f"  3. {low_conf} claims have low confidence — add supporting evidence")

        lines.append("")
        lines.append("  General recommendations:")
        lines.append("    - Link all claims to at least one source")
        lines.append("    - Review mutation chains for semantic drift")
        lines.append("    - Anchor finalized claim states to IPFS")
        lines.append("    - Log propagation events for temporal analysis")
        lines.append("    - Re-score periodically as new evidence arrives")

        self.sections.append({"title": "RECOMMENDATIONS", "content": lines})

    # ── Rendering ────────────────────────────────────────────────────────

    def _render(self) -> str:
        """Render all sections to formatted string."""
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
        lines.append("  END OF EPISTEMIC SCORING REPORT")
        lines.append("=" * 72)
        return "\n".join(lines)

    def to_json(self) -> str:
        """Return structured JSON with all scoring data."""
        claim_records = []
        for d in self._claim_data:
            record = {
                "claim_id": d["claim_id"],
                "claim_text": d["claim_text"],
                "claim_type": d["claim_type"],
            }
            if d.get("confidence"):
                record["confidence"] = {
                    "composite": d["confidence"].composite,
                    "components": d["confidence"].components,
                }
            if d.get("entropy"):
                record["entropy"] = d["entropy"].to_dict()
            if d.get("citation"):
                record["citation"] = d["citation"].to_dict()
            if d.get("contradiction"):
                record["contradiction"] = d["contradiction"].to_dict()
            if d.get("propagation"):
                record["propagation"] = d["propagation"].to_dict()

            claim_records.append(record)

        return json.dumps({
            "metadata": self.metadata,
            "claims": claim_records,
        }, indent=2, default=str)

    # ── Quick Score ──────────────────────────────────────────────────────

    def quick_score(self, claim_id: int) -> str:
        """One-line summary of a single claim's epistemic standing."""
        data = self._analyze_claim(claim_id)

        parts = [f"Claim #{claim_id}:"]

        conf = data.get("confidence")
        if conf:
            parts.append(f"conf={conf.composite:.3f}")

        ent = data.get("entropy")
        if ent:
            parts.append(f"H={ent.shannon_entropy:.3f}")

        cite = data.get("citation")
        if cite:
            parts.append(f"cite={cite.density_score:.3f}")

        contra = data.get("contradiction")
        if contra:
            parts.append(f"tension={contra.tension_score:.3f}")

        prop = data.get("propagation")
        if prop:
            parts.append(f"vel={prop.velocity:.3f}")

        return "  ".join(parts)
