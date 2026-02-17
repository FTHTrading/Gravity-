"""
Deep Provenance Engine – Multi-Layer Origin Tracing

Traces claims to their ultimate origin through:
  - Mutation chain traversal (claim → parent → grandparent → root)
  - Source chain traversal (source → sources it references → origin source)
  - Cross-graph tracing (claim ↔ source ↔ entity networks)
  - Origin classification (original, derived, amplified, mutated, orphan)
  - Confidence decay along provenance chains
  - Full provenance trace persistence for forensic audit

DB tables used: provenance_traces, claim_nodes, source_nodes, evidence_links
"""

import json
import math
from datetime import datetime, timezone
from dataclasses import dataclass, field
from collections import defaultdict

from src.database import insert_row, query_rows, execute_sql, get_connection
from src.logger import get_logger

log = get_logger(__name__)

# ── Constants ────────────────────────────────────────────────────────────
MAX_TRACE_DEPTH = 20
CONFIDENCE_DECAY_PER_HOP = 0.85  # Multiply confidence by this per chain hop

ORIGIN_TYPES = {
    "original",      # No predecessor — root claim
    "derived",       # Has mutation_parent chain
    "amplified",     # Multiple sources reference same text
    "mutated",       # Significant text drift from parent
    "orphan",        # No sources linked
}


@dataclass
class ProvenanceTrace:
    """Full provenance trace for a claim."""
    id: int = 0
    claim_id: int = 0
    origin_type: str = "orphan"
    origin_id: int = 0
    chain_depth: int = 0
    chain_path: list = field(default_factory=list)
    origin_source: str = ""
    confidence: float = 0.0
    traced_at: str = ""

    def to_dict(self) -> dict:
        return {
            "claim_id": self.claim_id,
            "origin_type": self.origin_type,
            "origin_id": self.origin_id,
            "chain_depth": self.chain_depth,
            "chain_path": self.chain_path,
            "origin_source": self.origin_source,
            "confidence": round(self.confidence, 4),
            "traced_at": self.traced_at,
        }


@dataclass
class ProvenanceSummary:
    """Summary of provenance analysis across all claims."""
    total_traced: int = 0
    origin_distribution: dict = field(default_factory=dict)
    avg_chain_depth: float = 0.0
    max_chain_depth: int = 0
    avg_confidence: float = 0.0
    orphan_count: int = 0
    deepest_chains: list = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "total_traced": self.total_traced,
            "origin_distribution": self.origin_distribution,
            "avg_chain_depth": round(self.avg_chain_depth, 2),
            "max_chain_depth": self.max_chain_depth,
            "avg_confidence": round(self.avg_confidence, 4),
            "orphan_count": self.orphan_count,
            "deepest_chains": self.deepest_chains[:10],
        }


class DeepProvenanceEngine:
    """Trace claims to their ultimate origins through mutation + source chains."""

    # ── Trace ────────────────────────────────────────────────────────────

    def trace(self, claim_id: int) -> ProvenanceTrace:
        """
        Trace a claim to its ultimate origin.

        Strategy:
          1. Follow mutation_parent chain to find root claim
          2. Follow source evidence links from root
          3. Classify origin type
          4. Compute chain confidence (decayed per hop)
        """
        now = datetime.now(timezone.utc).isoformat()

        # Step 1: Mutation chain traversal
        mutation_chain = self._trace_mutation_chain(claim_id)
        root_claim_id = mutation_chain[0] if mutation_chain else claim_id
        chain_depth = len(mutation_chain) - 1 if mutation_chain else 0

        # Step 2: Source chain from root
        source_chain = self._trace_source_chain(root_claim_id)

        # Step 3: Build full path
        full_path = []
        for cid in mutation_chain:
            full_path.append({"type": "claim", "id": cid})
        for sid in source_chain:
            full_path.append({"type": "source", "id": sid})

        total_depth = chain_depth + len(source_chain)

        # Step 4: Classify origin
        origin_type = self._classify_origin(
            claim_id, mutation_chain, source_chain
        )

        # Step 5: Origin source label
        origin_source = ""
        if source_chain:
            src_rows = query_rows("source_nodes", "id = ?", (source_chain[-1],))
            if src_rows:
                origin_source = src_rows[0].get("source_title", "")

        # Step 6: Confidence decay
        claim_rows = query_rows("claim_nodes", "id = ?", (root_claim_id,))
        base_confidence = claim_rows[0]["confidence"] if claim_rows else 0.0
        decayed_confidence = base_confidence * (CONFIDENCE_DECAY_PER_HOP ** total_depth)

        trace = ProvenanceTrace(
            claim_id=claim_id,
            origin_type=origin_type,
            origin_id=root_claim_id,
            chain_depth=total_depth,
            chain_path=full_path,
            origin_source=origin_source,
            confidence=decayed_confidence,
            traced_at=now,
        )

        trace.id = insert_row("provenance_traces", {
            "claim_id": claim_id,
            "origin_type": origin_type,
            "origin_id": root_claim_id,
            "chain_depth": total_depth,
            "chain_path_json": json.dumps(full_path),
            "origin_source": origin_source,
            "confidence": decayed_confidence,
            "traced_at": now,
        })

        log.info("Traced claim #%d: origin=%s depth=%d confidence=%.4f",
                 claim_id, origin_type, total_depth, decayed_confidence)
        return trace

    def trace_all(self) -> list[ProvenanceTrace]:
        """Trace provenance for all claims."""
        claims = query_rows("claim_nodes", "1=1")
        results = []
        for claim in claims:
            trace = self.trace(claim["id"])
            results.append(trace)
        log.info("Traced provenance for %d claims.", len(results))
        return results

    # ── Summary ──────────────────────────────────────────────────────────

    def get_summary(self) -> ProvenanceSummary:
        """Summarize provenance analysis results."""
        rows = query_rows("provenance_traces", "1=1")
        summary = ProvenanceSummary()
        summary.total_traced = len(rows)

        if not rows:
            return summary

        # Origin distribution
        dist = defaultdict(int)
        for r in rows:
            dist[r["origin_type"]] += 1
        summary.origin_distribution = dict(dist)

        # Depth stats
        depths = [r["chain_depth"] for r in rows]
        summary.avg_chain_depth = sum(depths) / len(depths)
        summary.max_chain_depth = max(depths)

        # Confidence stats
        confs = [r["confidence"] for r in rows]
        summary.avg_confidence = sum(confs) / len(confs)

        # Orphan count
        summary.orphan_count = dist.get("orphan", 0)

        # Deepest chains
        sorted_rows = sorted(rows, key=lambda r: r["chain_depth"], reverse=True)
        summary.deepest_chains = [
            {"claim_id": r["claim_id"], "depth": r["chain_depth"],
             "origin": r["origin_type"]}
            for r in sorted_rows[:10]
        ]

        return summary

    # ── History ──────────────────────────────────────────────────────────

    def get_trace(self, claim_id: int) -> list[ProvenanceTrace]:
        """Get stored provenance traces for a claim."""
        rows = query_rows(
            "provenance_traces",
            "claim_id = ? ORDER BY traced_at DESC",
            (claim_id,),
        )
        return [self._row_to_trace(r) for r in rows]

    # ── Internal ─────────────────────────────────────────────────────────

    def _trace_mutation_chain(self, claim_id: int) -> list[int]:
        """
        Follow mutation_parent links back to root.
        Returns [root_id, ..., parent_id, claim_id].
        """
        chain = []
        visited = set()
        current = claim_id

        while current and current not in visited and len(chain) < MAX_TRACE_DEPTH:
            visited.add(current)
            chain.append(current)
            rows = query_rows("claim_nodes", "id = ?", (current,))
            if not rows:
                break
            parent = rows[0].get("mutation_parent")
            if parent:
                current = parent
            else:
                break

        chain.reverse()
        return chain

    def _trace_source_chain(self, claim_id: int) -> list[int]:
        """
        Find sources linked to a claim, then trace those sources'
        own references to find the deepest origin source.
        Returns list of source_ids from claim → deepest source.
        """
        # Direct sources
        links = query_rows(
            "evidence_links",
            "(from_type = 'source' AND to_type = 'claim' AND to_id = ?) OR "
            "(from_type = 'claim' AND to_type = 'source' AND from_id = ?)",
            (claim_id, claim_id),
        )

        source_ids = set()
        for link in links:
            if link["from_type"] == "source":
                source_ids.add(link["from_id"])
            else:
                source_ids.add(link["to_id"])

        if not source_ids:
            return []

        # Find the most credible direct source
        best_source = None
        best_cred = -1
        for sid in source_ids:
            src_rows = query_rows("source_nodes", "id = ?", (sid,))
            if src_rows:
                cred = src_rows[0].get("credibility", 0.0)
                if cred > best_cred:
                    best_cred = cred
                    best_source = sid

        if best_source is None:
            return list(source_ids)[:1]

        # Trace further: follow source-to-source references
        chain = [best_source]
        visited = {best_source}
        current = best_source

        while len(chain) < MAX_TRACE_DEPTH:
            # Find sources that this source references
            ref_links = query_rows(
                "evidence_links",
                "from_type = 'source' AND from_id = ? AND to_type = 'source' "
                "AND relationship IN ('references', 'derives_from')",
                (current,),
            )

            next_source = None
            for link in ref_links:
                if link["to_id"] not in visited:
                    next_source = link["to_id"]
                    break

            if next_source is None:
                break

            visited.add(next_source)
            chain.append(next_source)
            current = next_source

        return chain

    def _classify_origin(
        self,
        claim_id: int,
        mutation_chain: list[int],
        source_chain: list[int],
    ) -> str:
        """
        Classify the origin type of a claim.
        """
        # If no mutation parent and has sources → original
        if len(mutation_chain) <= 1 and source_chain:
            return "original"

        # If mutation chain exists, check for significant drift
        if len(mutation_chain) > 1:
            root_id = mutation_chain[0]
            root_rows = query_rows("claim_nodes", "id = ?", (root_id,))
            claim_rows = query_rows("claim_nodes", "id = ?", (claim_id,))

            if root_rows and claim_rows:
                root_text = root_rows[0]["claim_text"]
                claim_text = claim_rows[0]["claim_text"]
                if root_text and claim_text and root_text != claim_text:
                    # Significant mutation
                    similarity = self._text_similarity(root_text, claim_text)
                    if similarity < 0.5:
                        return "mutated"
                    return "derived"

            return "derived"

        # No sources at all → orphan
        if not source_chain:
            # Check if multiple sources reference same text (amplified)
            links = query_rows(
                "evidence_links",
                "to_type = 'claim' AND to_id = ?",
                (claim_id,),
            )
            if len(links) >= 2:
                return "amplified"
            return "orphan"

        return "original"

    @staticmethod
    def _text_similarity(text_a: str, text_b: str) -> float:
        """Simple Jaccard similarity between word sets."""
        words_a = set(text_a.lower().split())
        words_b = set(text_b.lower().split())
        if not words_a or not words_b:
            return 0.0
        intersection = words_a & words_b
        union = words_a | words_b
        return len(intersection) / len(union) if union else 0.0

    @staticmethod
    def _row_to_trace(row) -> ProvenanceTrace:
        chain_path = []
        try:
            chain_path = json.loads(row["chain_path_json"])
        except (json.JSONDecodeError, TypeError):
            pass

        return ProvenanceTrace(
            id=row["id"],
            claim_id=row["claim_id"],
            origin_type=row["origin_type"],
            origin_id=row.get("origin_id", 0),
            chain_depth=row["chain_depth"],
            chain_path=chain_path,
            origin_source=row.get("origin_source", ""),
            confidence=row["confidence"],
            traced_at=row["traced_at"],
        )
