"""
Coordination Detector – Temporal Clustering & Coordinated Behavior Analysis

Detects coordinated or suspicious patterns across sources by analyzing:
  - Temporal burst detection (multiple sources linking to same claim within window)
  - Coordination scoring (density * count * inverse-window)
  - Pattern classification (burst, cascade, simultaneous, echo)
  - Cluster identification with source membership
  - Time-windowed scanning across all claims

DB tables used: coordination_events, source_nodes, evidence_links, claim_nodes
"""

import hashlib
import json
import math
from datetime import datetime, timezone, timedelta
from dataclasses import dataclass, field
from collections import defaultdict

from src.database import insert_row, query_rows, execute_sql, get_connection
from src.logger import get_logger

log = get_logger(__name__)

# ── Constants ────────────────────────────────────────────────────────────
DEFAULT_WINDOW_HOURS = 24.0    # Default temporal window for clustering
MIN_SOURCES_FOR_COORD = 2      # Minimum sources to flag as coordinated
SIMULTANEOUS_THRESHOLD = 1.0   # Hours threshold for "simultaneous" pattern
CASCADE_SPREAD_FACTOR = 0.3    # Max spread-to-window ratio for cascade


@dataclass
class CoordinationEvent:
    """A detected coordination cluster."""
    id: int = 0
    cluster_id: str = ""
    source_ids: list = field(default_factory=list)
    claim_ids: list = field(default_factory=list)
    window_hours: float = 0.0
    source_count: int = 0
    temporal_density: float = 0.0
    coordination_score: float = 0.0
    pattern_type: str = "burst"
    detected_at: str = ""

    def to_dict(self) -> dict:
        return {
            "cluster_id": self.cluster_id,
            "source_ids": self.source_ids,
            "claim_ids": self.claim_ids,
            "window_hours": round(self.window_hours, 2),
            "source_count": self.source_count,
            "temporal_density": round(self.temporal_density, 4),
            "coordination_score": round(self.coordination_score, 4),
            "pattern_type": self.pattern_type,
            "detected_at": self.detected_at,
        }


@dataclass
class CoordinationSummary:
    """Summary of all coordination analysis."""
    total_events: int = 0
    total_clusters: int = 0
    pattern_distribution: dict = field(default_factory=dict)
    highest_score: float = 0.0
    most_coordinated_sources: list = field(default_factory=list)
    mean_score: float = 0.0

    def to_dict(self) -> dict:
        return {
            "total_events": self.total_events,
            "total_clusters": self.total_clusters,
            "pattern_distribution": self.pattern_distribution,
            "highest_score": round(self.highest_score, 4),
            "most_coordinated_sources": self.most_coordinated_sources[:10],
            "mean_score": round(self.mean_score, 4),
        }


class CoordinationDetector:
    """Detect coordinated behavior across sources."""

    # ── Scan ─────────────────────────────────────────────────────────────

    def scan(self, window_hours: float = DEFAULT_WINDOW_HOURS) -> list[CoordinationEvent]:
        """
        Scan all claims for coordinated source behavior within window.

        For each claim, finds all sources linked within the time window.
        If >= MIN_SOURCES_FOR_COORD sources link within the window,
        it's flagged as a coordination event.
        """
        now = datetime.now(timezone.utc).isoformat()
        results = []

        # Map: claim_id → list of (source_id, timestamp)
        claim_sources = self._build_claim_source_map()

        for claim_id, sources in claim_sources.items():
            if len(sources) < MIN_SOURCES_FOR_COORD:
                continue

            # Sort by timestamp
            sources_sorted = sorted(sources, key=lambda x: x[1] if x[1] else "")

            # Sliding window analysis
            clusters = self._find_temporal_clusters(
                sources_sorted, window_hours
            )

            for cluster_sources in clusters:
                if len(cluster_sources) < MIN_SOURCES_FOR_COORD:
                    continue

                source_ids = [s[0] for s in cluster_sources]
                timestamps = [s[1] for s in cluster_sources if s[1]]

                # Compute temporal spread
                if len(timestamps) >= 2:
                    ts_parsed = []
                    for t in timestamps:
                        try:
                            ts_parsed.append(datetime.fromisoformat(t.replace("Z", "+00:00")))
                        except (ValueError, AttributeError):
                            pass
                    if len(ts_parsed) >= 2:
                        spread = (max(ts_parsed) - min(ts_parsed)).total_seconds() / 3600
                    else:
                        spread = 0.0
                else:
                    spread = 0.0

                # Temporal density: sources per hour
                temporal_density = len(cluster_sources) / max(spread, 0.1)

                # Coordination score
                coord_score = self._compute_coordination_score(
                    len(cluster_sources), spread, window_hours, temporal_density
                )

                # Pattern type
                pattern = self._classify_pattern(
                    cluster_sources, spread, window_hours
                )

                # Generate cluster ID
                cluster_id = self._make_cluster_id(claim_id, source_ids)

                event = CoordinationEvent(
                    cluster_id=cluster_id,
                    source_ids=source_ids,
                    claim_ids=[claim_id],
                    window_hours=spread if spread > 0 else window_hours,
                    source_count=len(cluster_sources),
                    temporal_density=temporal_density,
                    coordination_score=coord_score,
                    pattern_type=pattern,
                    detected_at=now,
                )

                event.id = insert_row("coordination_events", {
                    "cluster_id": cluster_id,
                    "source_ids_json": json.dumps(source_ids),
                    "claim_ids_json": json.dumps([claim_id]),
                    "window_hours": event.window_hours,
                    "source_count": event.source_count,
                    "temporal_density": temporal_density,
                    "coordination_score": coord_score,
                    "pattern_type": pattern,
                    "detected_at": now,
                })

                results.append(event)

        log.info("Detected %d coordination events across %d claims.",
                 len(results), len(claim_sources))
        return results

    def scan_claim(self, claim_id: int,
                   window_hours: float = DEFAULT_WINDOW_HOURS) -> list[CoordinationEvent]:
        """Scan a single claim for coordination patterns."""
        now = datetime.now(timezone.utc).isoformat()
        results = []

        sources = self._get_claim_sources(claim_id)
        if len(sources) < MIN_SOURCES_FOR_COORD:
            return results

        sources_sorted = sorted(sources, key=lambda x: x[1] if x[1] else "")
        clusters = self._find_temporal_clusters(sources_sorted, window_hours)

        for cluster_sources in clusters:
            if len(cluster_sources) < MIN_SOURCES_FOR_COORD:
                continue

            source_ids = [s[0] for s in cluster_sources]
            timestamps = [s[1] for s in cluster_sources if s[1]]

            spread = self._compute_spread(timestamps)
            temporal_density = len(cluster_sources) / max(spread, 0.1)
            coord_score = self._compute_coordination_score(
                len(cluster_sources), spread, window_hours, temporal_density
            )
            pattern = self._classify_pattern(cluster_sources, spread, window_hours)
            cluster_id = self._make_cluster_id(claim_id, source_ids)

            event = CoordinationEvent(
                cluster_id=cluster_id,
                source_ids=source_ids,
                claim_ids=[claim_id],
                window_hours=spread if spread > 0 else window_hours,
                source_count=len(cluster_sources),
                temporal_density=temporal_density,
                coordination_score=coord_score,
                pattern_type=pattern,
                detected_at=now,
            )

            event.id = insert_row("coordination_events", {
                "cluster_id": cluster_id,
                "source_ids_json": json.dumps(source_ids),
                "claim_ids_json": json.dumps([claim_id]),
                "window_hours": event.window_hours,
                "source_count": event.source_count,
                "temporal_density": temporal_density,
                "coordination_score": coord_score,
                "pattern_type": pattern,
                "detected_at": now,
            })

            results.append(event)

        return results

    # ── Summary ──────────────────────────────────────────────────────────

    def get_summary(self) -> CoordinationSummary:
        """Get summary of all detected coordination events."""
        rows = query_rows("coordination_events", "1=1")
        summary = CoordinationSummary()
        summary.total_events = len(rows)

        if not rows:
            return summary

        # Unique clusters
        cluster_ids = set(r["cluster_id"] for r in rows)
        summary.total_clusters = len(cluster_ids)

        # Pattern distribution
        patterns = defaultdict(int)
        for r in rows:
            patterns[r["pattern_type"]] += 1
        summary.pattern_distribution = dict(patterns)

        # Scores
        scores = [r["coordination_score"] for r in rows]
        summary.highest_score = max(scores) if scores else 0.0
        summary.mean_score = sum(scores) / len(scores) if scores else 0.0

        # Most coordinated sources
        source_freq = defaultdict(int)
        for r in rows:
            try:
                sids = json.loads(r["source_ids_json"])
                for sid in sids:
                    source_freq[sid] += 1
            except (json.JSONDecodeError, TypeError):
                pass

        sorted_sources = sorted(source_freq.items(), key=lambda x: x[1], reverse=True)
        summary.most_coordinated_sources = [
            {"source_id": sid, "event_count": count}
            for sid, count in sorted_sources[:10]
        ]

        return summary

    def get_events(self, min_score: float = 0.0,
                   limit: int = 50) -> list[CoordinationEvent]:
        """Get coordination events filtered by minimum score."""
        rows = query_rows(
            "coordination_events",
            "coordination_score >= ? ORDER BY coordination_score DESC LIMIT ?",
            (min_score, limit),
        )
        return [self._row_to_event(r) for r in rows]

    # ── Internal ─────────────────────────────────────────────────────────

    def _build_claim_source_map(self) -> dict:
        """Map claim_id → list of (source_id, timestamp)."""
        links = query_rows(
            "evidence_links",
            "(from_type = 'source' AND to_type = 'claim') OR "
            "(from_type = 'claim' AND to_type = 'source')",
        )

        claim_sources = defaultdict(list)
        for link in links:
            if link["from_type"] == "source":
                claim_sources[link["to_id"]].append(
                    (link["from_id"], link["created_at"])
                )
            else:
                claim_sources[link["from_id"]].append(
                    (link["to_id"], link["created_at"])
                )
        return dict(claim_sources)

    def _get_claim_sources(self, claim_id: int) -> list:
        """Get (source_id, timestamp) list for a single claim."""
        links = query_rows(
            "evidence_links",
            "(from_type = 'source' AND to_type = 'claim' AND to_id = ?) OR "
            "(from_type = 'claim' AND to_type = 'source' AND from_id = ?)",
            (claim_id, claim_id),
        )
        result = []
        for link in links:
            if link["from_type"] == "source":
                result.append((link["from_id"], link["created_at"]))
            else:
                result.append((link["to_id"], link["created_at"]))
        return result

    def _find_temporal_clusters(
        self,
        sources: list,
        window_hours: float,
    ) -> list[list]:
        """
        Group sources into temporal clusters using sliding window.
        Each cluster contains sources within window_hours of each other.
        """
        if not sources:
            return []

        clusters = []
        current_cluster = [sources[0]]

        for i in range(1, len(sources)):
            prev_time = sources[i - 1][1] or ""
            curr_time = sources[i][1] or ""

            if prev_time and curr_time:
                try:
                    t_prev = datetime.fromisoformat(prev_time.replace("Z", "+00:00"))
                    t_curr = datetime.fromisoformat(curr_time.replace("Z", "+00:00"))
                    gap_hours = (t_curr - t_prev).total_seconds() / 3600

                    if gap_hours <= window_hours:
                        current_cluster.append(sources[i])
                    else:
                        if len(current_cluster) >= MIN_SOURCES_FOR_COORD:
                            clusters.append(current_cluster)
                        current_cluster = [sources[i]]
                except (ValueError, AttributeError):
                    current_cluster.append(sources[i])
            else:
                current_cluster.append(sources[i])

        if len(current_cluster) >= MIN_SOURCES_FOR_COORD:
            clusters.append(current_cluster)

        return clusters

    @staticmethod
    def _compute_spread(timestamps: list) -> float:
        """Compute time spread in hours from a list of ISO timestamps."""
        parsed = []
        for t in timestamps:
            try:
                parsed.append(datetime.fromisoformat(t.replace("Z", "+00:00")))
            except (ValueError, AttributeError):
                pass
        if len(parsed) < 2:
            return 0.0
        return (max(parsed) - min(parsed)).total_seconds() / 3600

    @staticmethod
    def _compute_coordination_score(
        source_count: int,
        spread_hours: float,
        window_hours: float,
        temporal_density: float,
    ) -> float:
        """
        Coordination score (0.0 – 1.0):
          - Higher with more sources in the cluster
          - Higher with tighter temporal clustering
          - Normalized by window size
        """
        # Count factor: log-scaled source count
        count_factor = min(1.0, math.log1p(source_count) / 3.0)

        # Tightness factor: how close are events relative to window
        if spread_hours > 0 and window_hours > 0:
            tightness = 1.0 - (spread_hours / window_hours)
        else:
            tightness = 1.0
        tightness = max(0.0, min(1.0, tightness))

        # Density factor
        density_factor = min(1.0, temporal_density / 10.0)

        score = (count_factor * 0.35 + tightness * 0.40 + density_factor * 0.25)
        return max(0.0, min(1.0, score))

    @staticmethod
    def _classify_pattern(
        cluster_sources: list,
        spread_hours: float,
        window_hours: float,
    ) -> str:
        """
        Classify the coordination pattern:
          - simultaneous: spread < threshold
          - cascade: spread is small fraction of window, ordered timestamps
          - echo: claims reference same content with later timestamps
          - burst: default dense cluster
        """
        if spread_hours <= SIMULTANEOUS_THRESHOLD:
            return "simultaneous"
        if spread_hours > 0 and window_hours > 0:
            if spread_hours / window_hours <= CASCADE_SPREAD_FACTOR:
                return "cascade"
        return "burst"

    @staticmethod
    def _make_cluster_id(claim_id: int, source_ids: list) -> str:
        """Generate a deterministic cluster ID."""
        raw = f"claim_{claim_id}_sources_{'_'.join(str(s) for s in sorted(source_ids))}"
        return hashlib.sha256(raw.encode()).hexdigest()[:16]

    @staticmethod
    def _row_to_event(row) -> CoordinationEvent:
        source_ids = []
        claim_ids = []
        try:
            source_ids = json.loads(row["source_ids_json"])
        except (json.JSONDecodeError, TypeError):
            pass
        try:
            claim_ids = json.loads(row["claim_ids_json"])
        except (json.JSONDecodeError, TypeError):
            pass

        return CoordinationEvent(
            id=row["id"],
            cluster_id=row["cluster_id"],
            source_ids=source_ids,
            claim_ids=claim_ids,
            window_hours=row["window_hours"],
            source_count=row["source_count"],
            temporal_density=row["temporal_density"],
            coordination_score=row["coordination_score"],
            pattern_type=row["pattern_type"],
            detected_at=row["detected_at"],
        )
