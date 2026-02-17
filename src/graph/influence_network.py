"""
Influence Network Engine – Source Amplification & Gateway Analysis

Analyses how sources amplify each other through shared claims:
  - Source-to-source influence edges (who amplifies whom)
  - Gateway detection (sources that bridge disparate claim clusters)
  - Bottleneck identification (single points of failure in info flow)
  - Amplification factor (how much a source magnifies reach)
  - Network centrality metrics (degree, betweenness, PageRank)
  - Cluster analysis (communities of sources that co-reference)

DB tables used: influence_edges, source_nodes, evidence_links, claim_nodes
"""

import json
import math
from datetime import datetime, timezone
from dataclasses import dataclass, field
from collections import defaultdict

from src.database import insert_row, query_rows, execute_sql, get_connection
from src.logger import get_logger

log = get_logger(__name__)


@dataclass
class InfluenceEdge:
    """A directed influence relationship between two sources."""
    id: int = 0
    from_source_id: int = 0
    to_source_id: int = 0
    shared_claims: int = 0
    amplification: float = 0.0
    relationship: str = "amplifies"
    first_seen: str = ""
    last_seen: str = ""
    created_at: str = ""

    def to_dict(self) -> dict:
        return {
            "from_source_id": self.from_source_id,
            "to_source_id": self.to_source_id,
            "shared_claims": self.shared_claims,
            "amplification": round(self.amplification, 4),
            "relationship": self.relationship,
            "first_seen": self.first_seen,
            "last_seen": self.last_seen,
        }


@dataclass
class NetworkProfile:
    """Network-level analysis of source influence."""
    total_sources: int = 0
    total_edges: int = 0
    density: float = 0.0
    components: int = 0
    gateways: list = field(default_factory=list)
    bottlenecks: list = field(default_factory=list)
    top_amplifiers: list = field(default_factory=list)
    centrality: dict = field(default_factory=dict)
    clusters: list = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "total_sources": self.total_sources,
            "total_edges": self.total_edges,
            "density": round(self.density, 4),
            "components": self.components,
            "gateways": self.gateways,
            "bottlenecks": self.bottlenecks,
            "top_amplifiers": self.top_amplifiers[:10],
            "clusters": [list(c) for c in self.clusters[:10]],
        }


class InfluenceNetworkEngine:
    """Build and analyze source-level influence networks."""

    # ── Edge Construction ────────────────────────────────────────────────

    def build_edges(self) -> list[InfluenceEdge]:
        """
        Discover influence relationships between sources.

        Two sources are linked if they both connect to the same claim
        via evidence_links. The directionality is determined by which
        source's link was created first (earlier source → later source).
        """
        now = datetime.now(timezone.utc).isoformat()

        # Map: claim_id → list of (source_id, created_at, relationship)
        claim_sources = defaultdict(list)

        source_claim_links = query_rows(
            "evidence_links",
            "(from_type = 'source' AND to_type = 'claim') OR "
            "(from_type = 'claim' AND to_type = 'source')",
        )

        for link in source_claim_links:
            if link["from_type"] == "source":
                claim_sources[link["to_id"]].append((
                    link["from_id"], link["created_at"], link["relationship"]
                ))
            else:
                claim_sources[link["from_id"]].append((
                    link["to_id"], link["created_at"], link["relationship"]
                ))

        # Build pairwise edges
        pair_data = defaultdict(lambda: {
            "shared_claims": 0,
            "first_seen": "",
            "last_seen": "",
        })

        for claim_id, sources in claim_sources.items():
            if len(sources) < 2:
                continue

            # Sort by created_at for directionality
            sources_sorted = sorted(sources, key=lambda x: x[1] if x[1] else "")

            for i, (src_a, time_a, _) in enumerate(sources_sorted):
                for src_b, time_b, _ in sources_sorted[i + 1:]:
                    if src_a == src_b:
                        continue

                    key = (src_a, src_b)  # earlier → later = influence direction
                    data = pair_data[key]
                    data["shared_claims"] += 1
                    if not data["first_seen"] or (time_a and time_a < data["first_seen"]):
                        data["first_seen"] = time_a or ""
                    if time_b and (not data["last_seen"] or time_b > data["last_seen"]):
                        data["last_seen"] = time_b or ""

        # Persist edges
        results = []
        for (from_id, to_id), data in pair_data.items():
            # Amplification: shared claims normalized by total claims of source
            from_links = query_rows(
                "evidence_links",
                "(from_type = 'source' AND from_id = ?) OR "
                "(to_type = 'source' AND to_id = ?)",
                (from_id, from_id),
            )
            total_from = max(len(from_links), 1)
            amplification = data["shared_claims"] / total_from

            edge_id = insert_row("influence_edges", {
                "from_source_id": from_id,
                "to_source_id": to_id,
                "shared_claims": data["shared_claims"],
                "amplification": amplification,
                "relationship": "amplifies",
                "first_seen": data["first_seen"],
                "last_seen": data["last_seen"],
                "created_at": now,
            })

            edge = InfluenceEdge(
                id=edge_id,
                from_source_id=from_id,
                to_source_id=to_id,
                shared_claims=data["shared_claims"],
                amplification=amplification,
                first_seen=data["first_seen"],
                last_seen=data["last_seen"],
                created_at=now,
            )
            results.append(edge)

        log.info("Built %d influence edges from %d claim-source mappings.",
                 len(results), len(claim_sources))
        return results

    # ── Network Analysis ─────────────────────────────────────────────────

    def analyze_network(self) -> NetworkProfile:
        """
        Full network analysis using stored influence edges.
        Uses NetworkX for centrality and community detection.
        """
        profile = NetworkProfile()

        edges = query_rows("influence_edges", "1=1")
        sources = query_rows("source_nodes", "1=1")
        profile.total_sources = len(sources)
        profile.total_edges = len(edges)

        if not edges or profile.total_sources < 2:
            return profile

        # Density
        max_edges = profile.total_sources * (profile.total_sources - 1)
        profile.density = len(edges) / max_edges if max_edges > 0 else 0

        try:
            import networkx as nx
        except ImportError:
            log.warning("NetworkX not installed – skipping graph analysis")
            return profile

        G = nx.DiGraph()

        # Build graph
        for src in sources:
            G.add_node(src["id"], title=src.get("source_title", ""),
                       stype=src.get("source_type", ""))

        for edge in edges:
            G.add_edge(
                edge["from_source_id"],
                edge["to_source_id"],
                weight=edge["shared_claims"],
                amplification=edge["amplification"],
            )

        # Connected components (weakly)
        profile.components = nx.number_weakly_connected_components(G)

        # Betweenness centrality → gateways
        if len(G.nodes) >= 2:
            betweenness = nx.betweenness_centrality(G)
            sorted_btw = sorted(betweenness.items(), key=lambda x: x[1], reverse=True)
            profile.gateways = [
                {"source_id": sid, "betweenness": round(val, 4),
                 "title": G.nodes[sid].get("title", "")}
                for sid, val in sorted_btw[:5] if val > 0
            ]

            # Bottlenecks: nodes whose removal increases components
            for sid, val in sorted_btw[:10]:
                if val > 0:
                    H = G.copy()
                    H.remove_node(sid)
                    new_comp = nx.number_weakly_connected_components(H)
                    if new_comp > profile.components:
                        profile.bottlenecks.append({
                            "source_id": sid,
                            "betweenness": round(val, 4),
                            "components_if_removed": new_comp,
                            "title": G.nodes[sid].get("title", ""),
                        })

        # Top amplifiers: highest out-degree weighted by amplification
        amp_scores = {}
        for edge in edges:
            fid = edge["from_source_id"]
            amp_scores[fid] = amp_scores.get(fid, 0) + edge["amplification"]

        sorted_amp = sorted(amp_scores.items(), key=lambda x: x[1], reverse=True)
        for sid, score in sorted_amp[:10]:
            title = ""
            for src in sources:
                if src["id"] == sid:
                    title = src.get("source_title", "")
                    break
            profile.top_amplifiers.append({
                "source_id": sid,
                "amplification_total": round(score, 4),
                "title": title,
            })

        # Centrality metrics
        if len(G.nodes) >= 2:
            try:
                pagerank = nx.pagerank(G, weight="weight")
                profile.centrality = {
                    sid: round(val, 6) for sid, val in
                    sorted(pagerank.items(), key=lambda x: x[1], reverse=True)[:10]
                }
            except Exception:
                profile.centrality = {}

        # Cluster detection (weakly connected components as communities)
        components = list(nx.weakly_connected_components(G))
        profile.clusters = [list(c) for c in components]

        log.info("Network: %d sources, %d edges, density=%.4f, %d components",
                 profile.total_sources, profile.total_edges,
                 profile.density, profile.components)
        return profile

    # ── Source Neighbors ─────────────────────────────────────────────────

    def get_influence_on(self, source_id: int) -> list[InfluenceEdge]:
        """Get all sources that this source influences (outgoing edges)."""
        rows = query_rows(
            "influence_edges",
            "from_source_id = ?",
            (source_id,),
        )
        return [self._row_to_edge(r) for r in rows]

    def get_influenced_by(self, source_id: int) -> list[InfluenceEdge]:
        """Get all sources that influence this source (incoming edges)."""
        rows = query_rows(
            "influence_edges",
            "to_source_id = ?",
            (source_id,),
        )
        return [self._row_to_edge(r) for r in rows]

    # ── Row Converter ────────────────────────────────────────────────────

    @staticmethod
    def _row_to_edge(row) -> InfluenceEdge:
        return InfluenceEdge(
            id=row["id"],
            from_source_id=row["from_source_id"],
            to_source_id=row["to_source_id"],
            shared_claims=row["shared_claims"],
            amplification=row["amplification"],
            relationship=row.get("relationship", "amplifies"),
            first_seen=row.get("first_seen", ""),
            last_seen=row.get("last_seen", ""),
            created_at=row.get("created_at", ""),
        )
