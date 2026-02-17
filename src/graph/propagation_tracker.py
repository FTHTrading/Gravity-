"""
Propagation Tracker – Temporal Claim Spread & Amplification Metrics

Tracks how claims propagate through the evidence graph over time:
  - Propagation velocity (claims per time unit)
  - Amplification factor (branching ratio of supports/references)
  - Temporal spread distribution
  - Source cascade paths
  - Event logging for claim lifecycle

Events are stored in propagation_events table.
"""

import json
import math
from collections import defaultdict
from datetime import datetime, timezone, timedelta
from dataclasses import dataclass, field
from dateutil import parser as dateparser

from src.database import insert_row, query_rows, execute_sql
from src.graph.claim_graph import ClaimGraph, ClaimNode
from src.logger import get_logger

log = get_logger(__name__)


@dataclass
class PropagationMetrics:
    """Propagation analysis for a single claim."""
    claim_id: int = 0
    total_spread: int = 0
    unique_sources: int = 0
    amplification_factor: float = 0.0
    velocity: float = 0.0
    time_span_hours: float = 0.0
    first_seen: str = ""
    last_seen: str = ""
    cascade_depth: int = 0
    event_timeline: list = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "claim_id": self.claim_id,
            "total_spread": self.total_spread,
            "unique_sources": self.unique_sources,
            "amplification_factor": round(self.amplification_factor, 4),
            "velocity": round(self.velocity, 4),
            "time_span_hours": round(self.time_span_hours, 2),
            "first_seen": self.first_seen,
            "last_seen": self.last_seen,
            "cascade_depth": self.cascade_depth,
        }


class PropagationTracker:
    """
    Tracks temporal propagation patterns of claims through
    the evidence graph.
    """

    def __init__(self):
        self.graph = ClaimGraph()

    # ── Event Logging ────────────────────────────────────────────────────

    def log_event(self, claim_id: int, event_type: str,
                  source_id: int | None = None,
                  timestamp: str | None = None,
                  metadata: dict | None = None) -> int:
        """
        Log a propagation event.

        event_type: 'first_seen', 'repost', 'citation', 'mutation',
                    'amplification', 'retraction', 'archive'
        """
        now = datetime.now(timezone.utc).isoformat()
        event_id = insert_row("propagation_events", {
            "claim_id": claim_id,
            "event_type": event_type,
            "source_id": source_id,
            "timestamp": timestamp or now,
            "metadata_json": json.dumps(metadata) if metadata else None,
            "created_at": now,
        })
        log.debug("Logged propagation event #%d: claim=%d type=%s",
                  event_id, claim_id, event_type)
        return event_id

    def get_events(self, claim_id: int) -> list[dict]:
        """Get all propagation events for a claim, ordered by timestamp."""
        rows = execute_sql(
            "SELECT * FROM propagation_events "
            "WHERE claim_id = ? ORDER BY timestamp ASC",
            (claim_id,),
        )
        return rows

    # ── Propagation Analysis ─────────────────────────────────────────────

    def analyze_propagation(self, claim_id: int) -> PropagationMetrics:
        """
        Full propagation analysis for a claim.
        Uses evidence links + propagation events for temporal data.
        """
        claim = self.graph.get_claim(claim_id)
        if not claim:
            return PropagationMetrics(claim_id=claim_id)

        metrics = PropagationMetrics(claim_id=claim_id)

        # Count total spread via evidence links
        outbound = self.graph.get_links_from("claim", claim_id)
        inbound = self.graph.get_links_to("claim", claim_id)
        all_links = outbound + inbound

        spread_nodes = set()
        source_set = set()

        for link in all_links:
            if link.relationship in ("supports", "references", "derives_from"):
                if link.from_type == "source":
                    source_set.add(link.from_id)
                if link.to_type == "source":
                    source_set.add(link.to_id)
                spread_nodes.add((link.to_type, link.to_id))
                spread_nodes.add((link.from_type, link.from_id))

        # Count mutations as spread
        mutations = query_rows("claim_nodes", "mutation_parent = ?", (claim_id,))
        metrics.total_spread = len(spread_nodes) + len(mutations)
        metrics.unique_sources = len(source_set)

        # Amplification factor: outbound support links / (inbound + 1)
        outbound_supports = sum(1 for l in outbound
                                if l.relationship in ("supports", "references"))
        inbound_supports = sum(1 for l in inbound
                               if l.relationship in ("supports", "references"))
        metrics.amplification_factor = (
            outbound_supports / (inbound_supports + 1)
        )

        # Cascade depth: BFS through support chains
        metrics.cascade_depth = self._cascade_depth(claim_id)

        # Temporal analysis from events
        events = self.get_events(claim_id)
        if events:
            metrics.event_timeline = [
                {"type": e["event_type"], "time": e["timestamp"]}
                for e in events
            ]
            metrics.first_seen = events[0]["timestamp"]
            metrics.last_seen = events[-1]["timestamp"]

            # Velocity: events per hour
            try:
                t_first = dateparser.parse(events[0]["timestamp"])
                t_last = dateparser.parse(events[-1]["timestamp"])
                if t_first and t_last:
                    span = (t_last - t_first).total_seconds() / 3600.0
                    metrics.time_span_hours = max(span, 0.001)
                    metrics.velocity = len(events) / metrics.time_span_hours
            except (ValueError, TypeError):
                pass
        else:
            # Fallback: use claim created_at
            metrics.first_seen = claim.created_at
            metrics.last_seen = claim.created_at

        log.info("Propagation for claim #%d: spread=%d sources=%d amp=%.2f "
                 "velocity=%.2f depth=%d",
                 claim_id, metrics.total_spread, metrics.unique_sources,
                 metrics.amplification_factor, metrics.velocity,
                 metrics.cascade_depth)

        return metrics

    def _cascade_depth(self, claim_id: int, max_depth: int = 10) -> int:
        """BFS max depth through support/reference chains outward."""
        visited = set()
        queue = [(claim_id, 0)]
        max_found = 0

        while queue:
            cid, depth = queue.pop(0)
            if cid in visited or depth > max_depth:
                continue
            visited.add(cid)
            max_found = max(max_found, depth)

            # Follow outbound supports to other claims
            links = self.graph.get_links_from("claim", cid)
            for link in links:
                if link.to_type == "claim" and link.relationship in (
                    "supports", "references", "derives_from"
                ):
                    queue.append((link.to_id, depth + 1))

        return max_found

    # ── Batch Analysis ───────────────────────────────────────────────────

    def analyze_all(self) -> list[PropagationMetrics]:
        """Analyze propagation for every claim."""
        claims = self.graph.get_all_claims()
        results = [self.analyze_propagation(c.id) for c in claims]
        log.info("Analyzed propagation for %d claims", len(results))
        return results

    def rank_by_velocity(self, top_n: int = 20) -> list[tuple[int, float, str]]:
        """Rank claims by propagation velocity."""
        all_metrics = self.analyze_all()
        all_metrics.sort(key=lambda m: m.velocity, reverse=True)
        ranked = []
        for m in all_metrics[:top_n]:
            claim = self.graph.get_claim(m.claim_id)
            text = claim.claim_text[:80] if claim else "?"
            ranked.append((m.claim_id, m.velocity, text))
        return ranked

    def rank_by_amplification(self, top_n: int = 20) -> list[tuple[int, float, str]]:
        """Rank claims by amplification factor."""
        all_metrics = self.analyze_all()
        all_metrics.sort(key=lambda m: m.amplification_factor, reverse=True)
        ranked = []
        for m in all_metrics[:top_n]:
            claim = self.graph.get_claim(m.claim_id)
            text = claim.claim_text[:80] if claim else "?"
            ranked.append((m.claim_id, m.amplification_factor, text))
        return ranked

    # ── Auto-Logging ─────────────────────────────────────────────────────

    def auto_log_from_graph(self) -> int:
        """
        Scan the evidence graph and auto-generate propagation events
        from existing evidence links and mutations.
        Returns count of events logged.
        """
        count = 0
        claims = self.graph.get_all_claims()

        for claim in claims:
            # Log first_seen
            existing = self.get_events(claim.id)
            if not existing:
                self.log_event(
                    claim.id, "first_seen",
                    timestamp=claim.created_at,
                    metadata={"source": "auto_scan"},
                )
                count += 1

            # Log mutations
            mutations = query_rows(
                "claim_nodes", "mutation_parent = ?", (claim.id,)
            )
            for mut in mutations:
                self.log_event(
                    claim.id, "mutation",
                    timestamp=mut["created_at"],
                    metadata={
                        "child_id": mut["id"],
                        "source": "auto_scan",
                    },
                )
                count += 1

            # Log citations from sources
            links = self.graph.get_links_to("claim", claim.id)
            for link in links:
                if link.from_type == "source" and link.relationship in (
                    "supports", "references"
                ):
                    self.log_event(
                        claim.id, "citation",
                        source_id=link.from_id,
                        timestamp=link.created_at,
                        metadata={"source": "auto_scan"},
                    )
                    count += 1

        log.info("Auto-logged %d propagation events", count)
        return count

    # ── Summary ──────────────────────────────────────────────────────────

    def get_summary(self) -> dict:
        """Aggregate propagation statistics."""
        all_metrics = self.analyze_all()
        if not all_metrics:
            return {"total_claims": 0}

        velocities = [m.velocity for m in all_metrics]
        amplifications = [m.amplification_factor for m in all_metrics]
        spreads = [m.total_spread for m in all_metrics]

        return {
            "total_claims": len(all_metrics),
            "avg_velocity": round(sum(velocities) / len(velocities), 4),
            "max_velocity": round(max(velocities), 4),
            "avg_amplification": round(
                sum(amplifications) / len(amplifications), 4
            ),
            "max_amplification": round(max(amplifications), 4),
            "avg_spread": round(sum(spreads) / len(spreads), 2),
            "max_spread": max(spreads),
            "total_events": sum(
                len(self.get_events(m.claim_id)) for m in all_metrics
            ),
        }
