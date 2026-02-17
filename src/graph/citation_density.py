"""
Citation Density Analyzer – Cross-Reference Frequency Scoring

Measures how densely a claim is cited / referenced across sources,
other claims, and entity nodes in the evidence graph.

Metrics:
  - Direct citation count (inbound 'supports' / 'references' links)
  - Cross-source density (unique sources referencing the claim)
  - Entity co-occurrence (entities linked to same sources)
  - Citation depth (how many hops of citations support this claim)
  - Density score (normalized composite)
"""

import math
from datetime import datetime, timezone
from dataclasses import dataclass, field

from src.database import query_rows, execute_sql
from src.graph.claim_graph import ClaimGraph, ClaimNode, EvidenceLink
from src.logger import get_logger

log = get_logger(__name__)


@dataclass
class CitationMetrics:
    """Citation density analysis for a single claim."""
    claim_id: int = 0
    direct_citations: int = 0
    unique_sources: int = 0
    supporting_claims: int = 0
    contradicting_claims: int = 0
    entity_co_occurrences: int = 0
    citation_depth: int = 0
    density_score: float = 0.0
    source_details: list = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "claim_id": self.claim_id,
            "direct_citations": self.direct_citations,
            "unique_sources": self.unique_sources,
            "supporting_claims": self.supporting_claims,
            "contradicting_claims": self.contradicting_claims,
            "entity_co_occurrences": self.entity_co_occurrences,
            "citation_depth": self.citation_depth,
            "density_score": round(self.density_score, 4),
        }


class CitationDensity:
    """
    Analyzes citation density in the claim graph.
    Higher density → better-supported claim.
    """

    def __init__(self):
        self.graph = ClaimGraph()

    def analyze_claim(self, claim_id: int) -> CitationMetrics:
        """Full citation density analysis for a single claim."""
        claim = self.graph.get_claim(claim_id)
        if not claim:
            log.warning("Claim #%d not found", claim_id)
            return CitationMetrics(claim_id=claim_id)

        metrics = CitationMetrics(claim_id=claim_id)

        # Get all links involving this claim
        outbound = self.graph.get_links_from("claim", claim_id)
        inbound = self.graph.get_links_to("claim", claim_id)
        all_links = outbound + inbound

        # Count direct citations
        source_ids = set()
        supporting_claim_ids = set()
        contradicting_claim_ids = set()

        for link in all_links:
            # Source citations
            if link.from_type == "source" and link.relationship in ("supports", "references"):
                source_ids.add(link.from_id)
                metrics.direct_citations += 1
            elif link.to_type == "source" and link.relationship in ("supports", "references"):
                source_ids.add(link.to_id)
                metrics.direct_citations += 1

            # Supporting claims
            if link.from_type == "claim" and link.from_id != claim_id:
                if link.relationship == "supports":
                    supporting_claim_ids.add(link.from_id)
                elif link.relationship == "contradicts":
                    contradicting_claim_ids.add(link.from_id)
            if link.to_type == "claim" and link.to_id != claim_id:
                if link.relationship == "supports":
                    supporting_claim_ids.add(link.to_id)
                elif link.relationship == "contradicts":
                    contradicting_claim_ids.add(link.to_id)

        metrics.unique_sources = len(source_ids)
        metrics.supporting_claims = len(supporting_claim_ids)
        metrics.contradicting_claims = len(contradicting_claim_ids)

        # Source details
        for sid in source_ids:
            source = self.graph.get_source(sid)
            if source:
                metrics.source_details.append({
                    "id": source.id,
                    "title": source.source_title,
                    "type": source.source_type,
                    "credibility": source.credibility,
                })

        # Entity co-occurrences: count entities linked to same sources
        entity_ids = set()
        for link in all_links:
            if link.from_type == "entity":
                entity_ids.add(link.from_id)
            if link.to_type == "entity":
                entity_ids.add(link.to_id)
        metrics.entity_co_occurrences = len(entity_ids)

        # Citation depth: BFS from this claim through supporting links
        metrics.citation_depth = self._compute_citation_depth(claim_id)

        # Density score: normalized composite
        metrics.density_score = self._compute_density_score(metrics)

        log.info("Citation density for claim #%d: citations=%d sources=%d "
                 "support=%d contra=%d depth=%d score=%.4f",
                 claim_id, metrics.direct_citations, metrics.unique_sources,
                 metrics.supporting_claims, metrics.contradicting_claims,
                 metrics.citation_depth, metrics.density_score)

        return metrics

    def _compute_citation_depth(self, claim_id: int, max_depth: int = 5) -> int:
        """
        BFS to find the maximum depth of supporting evidence chains.
        Only follows 'supports' and 'references' edges.
        """
        visited = set()
        queue = [(claim_id, 0)]
        max_found = 0

        while queue:
            node_id, depth = queue.pop(0)
            if node_id in visited or depth > max_depth:
                continue
            visited.add(node_id)
            max_found = max(max_found, depth)

            # Follow outbound supports
            links = self.graph.get_links_from("claim", node_id)
            for link in links:
                if link.relationship in ("supports", "references") and link.to_type == "claim":
                    queue.append((link.to_id, depth + 1))

        return max_found

    def _compute_density_score(self, metrics: CitationMetrics) -> float:
        """
        Normalized density score [0, 1].

        Components:
          - Source diversity (0.3 weight): sigmoid of unique_sources
          - Citation volume (0.25 weight): sigmoid of direct_citations
          - Support ratio (0.25 weight): supports / (supports + contradictions)
          - Depth bonus (0.2 weight): depth / (depth + 2)
        """
        # Source diversity: sigmoid
        src_score = 1.0 - 1.0 / (1.0 + metrics.unique_sources)

        # Citation volume: sigmoid
        cite_score = 1.0 - 1.0 / (1.0 + metrics.direct_citations)

        # Support ratio
        total_claims = metrics.supporting_claims + metrics.contradicting_claims
        support_ratio = (
            metrics.supporting_claims / total_claims if total_claims > 0 else 0.5
        )

        # Depth bonus
        depth_score = metrics.citation_depth / (metrics.citation_depth + 2.0)

        score = (
            0.30 * src_score
            + 0.25 * cite_score
            + 0.25 * support_ratio
            + 0.20 * depth_score
        )

        return max(0.0, min(1.0, score))

    def analyze_all_claims(self) -> list[CitationMetrics]:
        """Analyze citation density for every claim."""
        claims = self.graph.get_all_claims()
        results = [self.analyze_claim(c.id) for c in claims]
        log.info("Analyzed citation density for %d claims", len(results))
        return results

    def rank_by_density(self, top_n: int = 20) -> list[tuple[int, float, str]]:
        """
        Return top-N claims ranked by citation density.
        Returns list of (claim_id, density_score, text_snippet).
        """
        all_metrics = self.analyze_all_claims()
        all_metrics.sort(key=lambda m: m.density_score, reverse=True)

        ranked = []
        for m in all_metrics[:top_n]:
            claim = self.graph.get_claim(m.claim_id)
            text = claim.claim_text[:80] if claim else "?"
            ranked.append((m.claim_id, m.density_score, text))
        return ranked

    def get_uncited_claims(self) -> list[ClaimNode]:
        """Find claims with zero citations (potential orphans)."""
        all_metrics = self.analyze_all_claims()
        orphans = []
        for m in all_metrics:
            if m.direct_citations == 0 and m.unique_sources == 0:
                claim = self.graph.get_claim(m.claim_id)
                if claim:
                    orphans.append(claim)
        log.info("Found %d uncited claims", len(orphans))
        return orphans

    def get_cross_source_claims(self, min_sources: int = 2) -> list[CitationMetrics]:
        """Find claims referenced by multiple distinct sources."""
        all_metrics = self.analyze_all_claims()
        multi = [m for m in all_metrics if m.unique_sources >= min_sources]
        log.info("Claims with %d+ sources: %d", min_sources, len(multi))
        return multi
