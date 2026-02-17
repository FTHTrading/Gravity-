"""
Contradiction Analyzer – Tension Mapping & Conflict Cluster Detection

Extends the basic find_contradictions() from ClaimGraph with:
  - Contradiction frequency scoring per claim
  - Weighted tension scores (how contested is each claim?)
  - Conflict cluster detection (groups of mutually contradicting claims)
  - Tension heat map data for visualization
  - Contradiction lineage tracking (do contradictions propagate through mutations?)
"""

import math
from collections import defaultdict
from datetime import datetime, timezone
from dataclasses import dataclass, field

from src.database import query_rows
from src.graph.claim_graph import ClaimGraph, ClaimNode, EvidenceLink
from src.logger import get_logger

log = get_logger(__name__)


@dataclass
class ContradictionProfile:
    """Contradiction analysis for a single claim."""
    claim_id: int = 0
    claim_text: str = ""
    contradiction_count: int = 0
    tension_score: float = 0.0
    contradicting_claims: list = field(default_factory=list)
    tension_by_type: dict = field(default_factory=dict)
    is_contested: bool = False

    def to_dict(self) -> dict:
        return {
            "claim_id": self.claim_id,
            "claim_text": self.claim_text[:100],
            "contradiction_count": self.contradiction_count,
            "tension_score": round(self.tension_score, 4),
            "contradicting_claims": self.contradicting_claims,
            "is_contested": self.is_contested,
        }


@dataclass
class ConflictCluster:
    """A group of mutually contradicting claims."""
    cluster_id: int = 0
    claim_ids: list = field(default_factory=list)
    total_tension: float = 0.0
    center_claim_id: int = 0
    size: int = 0

    def to_dict(self) -> dict:
        return {
            "cluster_id": self.cluster_id,
            "claim_ids": self.claim_ids,
            "total_tension": round(self.total_tension, 4),
            "center_claim_id": self.center_claim_id,
            "size": self.size,
        }


class ContradictionAnalyzer:
    """
    Deep contradiction analysis for the claim graph.
    Quantifies epistemic tension and detects conflict clusters.
    """

    def __init__(self):
        self.graph = ClaimGraph()

    # ── Per-Claim Contradiction Profile ──────────────────────────────────

    def profile_claim(self, claim_id: int) -> ContradictionProfile:
        """
        Build a full contradiction profile for a single claim.
        """
        claim = self.graph.get_claim(claim_id)
        if not claim:
            return ContradictionProfile(claim_id=claim_id)

        profile = ContradictionProfile(
            claim_id=claim_id,
            claim_text=claim.claim_text,
        )

        # Find all contradiction edges
        outbound = self.graph.get_links_from("claim", claim_id)
        inbound = self.graph.get_links_to("claim", claim_id)

        contradictions = []
        for link in outbound:
            if link.relationship == "contradicts" and link.to_type == "claim":
                contradictions.append((link.to_id, link.weight))
        for link in inbound:
            if link.relationship == "contradicts" and link.from_type == "claim":
                contradictions.append((link.from_id, link.weight))

        profile.contradiction_count = len(contradictions)

        # Build detailed list
        for other_id, weight in contradictions:
            other = self.graph.get_claim(other_id)
            if other:
                profile.contradicting_claims.append({
                    "id": other.id,
                    "text": other.claim_text[:100],
                    "type": other.claim_type,
                    "weight": weight,
                    "verification": other.verification,
                })

        # Tension score: sum of contradiction weights, log-scaled
        total_weight = sum(w for _, w in contradictions)
        profile.tension_score = math.log1p(total_weight) if total_weight > 0 else 0.0

        # Tension by opponent type
        for item in profile.contradicting_claims:
            ct = item["type"]
            profile.tension_by_type[ct] = profile.tension_by_type.get(ct, 0) + 1

        # A claim is "contested" if it has 2+ contradictions or high tension
        profile.is_contested = (
            profile.contradiction_count >= 2 or profile.tension_score > 1.0
        )

        log.info("Contradiction profile for claim #%d: count=%d tension=%.4f contested=%s",
                 claim_id, profile.contradiction_count,
                 profile.tension_score, profile.is_contested)

        return profile

    def profile_all_claims(self) -> list[ContradictionProfile]:
        """Build contradiction profiles for every claim."""
        claims = self.graph.get_all_claims()
        profiles = [self.profile_claim(c.id) for c in claims]
        contested = sum(1 for p in profiles if p.is_contested)
        log.info("Profiled %d claims, %d contested", len(profiles), contested)
        return profiles

    # ── Conflict Cluster Detection ───────────────────────────────────────

    def find_conflict_clusters(self) -> list[ConflictCluster]:
        """
        Detect groups of mutually contradicting claims using
        union-find on contradiction edges.
        """
        # Build adjacency from contradiction edges
        contradictions = query_rows("evidence_links", "relationship = ?", ("contradicts",))
        if not contradictions:
            return []

        # Union-Find
        parent = {}

        def find(x):
            if x not in parent:
                parent[x] = x
            while parent[x] != x:
                parent[x] = parent[parent[x]]
                x = parent[x]
            return x

        def union(a, b):
            ra, rb = find(a), find(b)
            if ra != rb:
                parent[ra] = rb

        # Process contradiction edges
        edge_weights = defaultdict(float)
        for row in contradictions:
            if row["from_type"] == "claim" and row["to_type"] == "claim":
                a, b = row["from_id"], row["to_id"]
                union(a, b)
                edge_weights[(min(a, b), max(a, b))] += row["weight"]

        # Group into clusters
        clusters_dict = defaultdict(set)
        for node in parent:
            root = find(node)
            clusters_dict[root].add(node)

        # Build ConflictCluster objects
        clusters = []
        for idx, (root, members) in enumerate(clusters_dict.items()):
            if len(members) < 2:
                continue

            # Total tension: sum of edge weights within cluster
            total_tension = 0.0
            for (a, b), w in edge_weights.items():
                if a in members and b in members:
                    total_tension += w

            # Center: claim with most contradiction edges
            edge_counts = defaultdict(int)
            for (a, b), _ in edge_weights.items():
                if a in members and b in members:
                    edge_counts[a] += 1
                    edge_counts[b] += 1
            center = max(edge_counts, key=edge_counts.get) if edge_counts else root

            cluster = ConflictCluster(
                cluster_id=idx + 1,
                claim_ids=sorted(members),
                total_tension=total_tension,
                center_claim_id=center,
                size=len(members),
            )
            clusters.append(cluster)

        clusters.sort(key=lambda c: c.total_tension, reverse=True)
        log.info("Found %d conflict clusters", len(clusters))
        return clusters

    # ── Tension Heat Map ─────────────────────────────────────────────────

    def tension_map(self) -> list[dict]:
        """
        Generate tension heat map data: list of {claim_id, tension_score, text}.
        Sorted by tension score descending.
        """
        profiles = self.profile_all_claims()
        heat_data = []
        for p in profiles:
            if p.tension_score > 0:
                heat_data.append({
                    "claim_id": p.claim_id,
                    "text": p.claim_text[:80],
                    "tension": round(p.tension_score, 4),
                    "count": p.contradiction_count,
                    "contested": p.is_contested,
                })
        heat_data.sort(key=lambda x: x["tension"], reverse=True)
        return heat_data

    # ── Mutation Contradiction Lineage ───────────────────────────────────

    def contradiction_lineage(self, claim_id: int) -> list[dict]:
        """
        Check if contradictions propagate through a claim's mutation chain.
        Returns list of {step, claim_id, contradiction_count, tension}.
        """
        chain = self.graph.get_mutation_chain(claim_id)
        lineage = []
        for i, claim in enumerate(chain):
            profile = self.profile_claim(claim.id)
            lineage.append({
                "step": i,
                "claim_id": claim.id,
                "text": claim.claim_text[:60],
                "contradiction_count": profile.contradiction_count,
                "tension": round(profile.tension_score, 4),
            })
        return lineage

    # ── Summary Statistics ───────────────────────────────────────────────

    def get_summary(self) -> dict:
        """Aggregate contradiction statistics for the entire graph."""
        profiles = self.profile_all_claims()
        clusters = self.find_conflict_clusters()

        total_contradictions = sum(p.contradiction_count for p in profiles) // 2
        contested = [p for p in profiles if p.is_contested]
        avg_tension = (
            sum(p.tension_score for p in profiles) / len(profiles)
            if profiles else 0.0
        )
        max_tension = max(
            (p.tension_score for p in profiles), default=0.0
        )

        return {
            "total_claims": len(profiles),
            "total_contradictions": total_contradictions,
            "contested_claims": len(contested),
            "conflict_clusters": len(clusters),
            "avg_tension": round(avg_tension, 4),
            "max_tension": round(max_tension, 4),
            "most_contested": (
                contested[0].to_dict() if contested else None
            ),
        }
