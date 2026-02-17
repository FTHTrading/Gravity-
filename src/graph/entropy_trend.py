"""
Entropy Trend Engine – Temporal Shannon Entropy Tracking

Tracks H(t) series per claim chain over time, enabling:
  - dH/dt computation (entropy rate of change)
  - Entropy acceleration (d²H/dt²)
  - Trend detection: increasing, decreasing, oscillating
  - Anomaly detection: sudden entropy spikes or collapses
  - Historical entropy comparison

Results stored in entropy_timeline table.
"""

import math
import json
from datetime import datetime, timezone
from dataclasses import dataclass, field

from src.database import insert_row, execute_sql
from src.graph.claim_graph import ClaimGraph
from src.graph.mutation_entropy import MutationEntropy, MutationMetrics
from src.logger import get_logger

log = get_logger(__name__)


@dataclass
class EntropyTrendPoint:
    """Single point on the entropy timeline."""
    claim_id: int = 0
    shannon_entropy: float = 0.0
    drift_velocity: float = 0.0
    chain_length: int = 0
    snapshot_at: str = ""


@dataclass
class EntropyTrend:
    """Aggregated entropy trend analysis for a claim chain."""
    claim_id: int = 0
    current_entropy: float = 0.0
    mean_entropy: float = 0.0
    std_dev: float = 0.0
    min_entropy: float = 0.0
    max_entropy: float = 0.0
    total_snapshots: int = 0
    dh_dt: float = 0.0                # first derivative: entropy rate (per hour)
    d2h_dt2: float = 0.0              # second derivative: entropy acceleration
    trend_direction: str = "stable"    # increasing, decreasing, stable, oscillating
    is_spike: bool = False             # sudden entropy jump
    is_collapse: bool = False          # sudden entropy drop
    spike_magnitude: float = 0.0
    history: list = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "claim_id": self.claim_id,
            "current_entropy": round(self.current_entropy, 6),
            "mean_entropy": round(self.mean_entropy, 6),
            "std_dev": round(self.std_dev, 6),
            "min_entropy": round(self.min_entropy, 6),
            "max_entropy": round(self.max_entropy, 6),
            "total_snapshots": self.total_snapshots,
            "dh_dt": round(self.dh_dt, 6),
            "d2h_dt2": round(self.d2h_dt2, 6),
            "trend_direction": self.trend_direction,
            "is_spike": self.is_spike,
            "is_collapse": self.is_collapse,
            "spike_magnitude": round(self.spike_magnitude, 6),
        }


class EntropyTrendEngine:
    """
    Tracks Shannon entropy of mutation chains over time.

    Enables detection of:
      - Accelerating entropy (narrative instability growing)
      - Entropy spikes (sudden mutation bursts)
      - Entropy convergence (narrative stabilizing)
    """

    # Spike detection: if change > SPIKE_FACTOR * std_dev
    SPIKE_FACTOR = 2.0
    # Minimum snapshots for meaningful trend analysis
    MIN_TREND_SNAPSHOTS = 3

    def __init__(self):
        self.graph = ClaimGraph()
        self.entropy_engine = MutationEntropy()

    # ── Snapshot Operations ──────────────────────────────────────────────

    def snapshot_claim(self, claim_id: int) -> EntropyTrendPoint:
        """
        Compute mutation entropy now and record on timeline.
        """
        metrics = self.entropy_engine.analyze_chain(claim_id)
        now = datetime.now(timezone.utc).isoformat()

        entropy_val = metrics.shannon_entropy if metrics else 0.0
        drift_val = metrics.drift_velocity if metrics else 0.0
        chain_len = metrics.chain_length if metrics else 0

        insert_row("entropy_timeline", {
            "claim_id": claim_id,
            "shannon_entropy": entropy_val,
            "drift_velocity": drift_val,
            "chain_length": chain_len,
            "snapshot_at": now,
        })

        point = EntropyTrendPoint(
            claim_id=claim_id,
            shannon_entropy=entropy_val,
            drift_velocity=drift_val,
            chain_length=chain_len,
            snapshot_at=now,
        )
        log.info("Entropy snapshot: claim #%d → H=%.4f drift=%.4f",
                 claim_id, entropy_val, drift_val)
        return point

    def snapshot_all(self) -> list[EntropyTrendPoint]:
        """Snapshot entropy for every claim in the graph."""
        claims = self.graph.get_all_claims()
        points = []
        for claim in claims:
            point = self.snapshot_claim(claim.id)
            points.append(point)
        log.info("Snapshotted entropy for %d claims.", len(points))
        return points

    # ── Query Operations ─────────────────────────────────────────────────

    def get_history(self, claim_id: int, limit: int = 100) -> list[EntropyTrendPoint]:
        """Get entropy history for a claim, newest first."""
        rows = execute_sql(
            "SELECT claim_id, shannon_entropy, drift_velocity, chain_length, snapshot_at "
            "FROM entropy_timeline WHERE claim_id = ? "
            "ORDER BY snapshot_at DESC LIMIT ?",
            (claim_id, limit),
        )
        return [
            EntropyTrendPoint(
                claim_id=r["claim_id"],
                shannon_entropy=r["shannon_entropy"],
                drift_velocity=r["drift_velocity"],
                chain_length=r["chain_length"],
                snapshot_at=r["snapshot_at"],
            )
            for r in rows
        ]

    def get_latest_entropy(self, claim_id: int) -> float | None:
        """Get the most recent entropy value from the timeline."""
        rows = execute_sql(
            "SELECT shannon_entropy FROM entropy_timeline "
            "WHERE claim_id = ? ORDER BY snapshot_at DESC LIMIT 1",
            (claim_id,),
        )
        if rows:
            return rows[0]["shannon_entropy"]
        return None

    # ── Trend Analysis ───────────────────────────────────────────────────

    def analyze_trend(self, claim_id: int) -> EntropyTrend:
        """
        Full entropy trend analysis for a claim chain.

        Computes: dH/dt, d²H/dt², spike detection, trend direction.
        """
        history = self.get_history(claim_id, limit=200)
        trend = EntropyTrend(claim_id=claim_id)

        if not history:
            return trend

        # Reverse to chronological order
        chronological = list(reversed(history))
        entropies = [p.shannon_entropy for p in chronological]
        trend.total_snapshots = len(entropies)
        trend.current_entropy = entropies[-1]
        trend.history = [
            {"entropy": p.shannon_entropy, "drift": p.drift_velocity, "at": p.snapshot_at}
            for p in chronological
        ]

        # Basic statistics
        trend.mean_entropy = sum(entropies) / len(entropies)
        trend.min_entropy = min(entropies)
        trend.max_entropy = max(entropies)

        if len(entropies) > 1:
            variance = sum((h - trend.mean_entropy) ** 2 for h in entropies) / len(entropies)
            trend.std_dev = math.sqrt(variance)
        else:
            trend.std_dev = 0.0

        # dH/dt — first derivative
        trend.dh_dt = self._compute_dh_dt(chronological)

        # d²H/dt² — second derivative (entropy acceleration)
        trend.d2h_dt2 = self._compute_d2h_dt2(chronological)

        # Trend direction
        trend.trend_direction = self._classify_trend(entropies)

        # Spike / collapse detection
        if len(entropies) >= self.MIN_TREND_SNAPSHOTS and trend.std_dev > 0:
            last_delta = entropies[-1] - entropies[-2] if len(entropies) >= 2 else 0.0
            magnitude = abs(last_delta) / max(trend.std_dev, 1e-9)
            if magnitude > self.SPIKE_FACTOR:
                trend.spike_magnitude = magnitude
                if last_delta > 0:
                    trend.is_spike = True
                else:
                    trend.is_collapse = True

        return trend

    # ── Derivatives ──────────────────────────────────────────────────────

    def _compute_dh_dt(self, chronological: list[EntropyTrendPoint]) -> float:
        """
        First derivative dH/dt.
        Simple finite-difference using first and last points.
        Returns entropy-units per hour.
        """
        if len(chronological) < 2:
            return 0.0

        first = chronological[0]
        last = chronological[-1]

        try:
            t0 = datetime.fromisoformat(first.snapshot_at)
            t1 = datetime.fromisoformat(last.snapshot_at)
            dt_hours = (t1 - t0).total_seconds() / 3600.0
            if dt_hours < 1e-6:
                return 0.0
            return (last.shannon_entropy - first.shannon_entropy) / dt_hours
        except (ValueError, TypeError):
            return 0.0

    def _compute_d2h_dt2(self, chronological: list[EntropyTrendPoint]) -> float:
        """
        Second derivative d²H/dt².
        Uses three-point finite difference on the first, mid, and last points.
        Returns entropy-units per hour².
        """
        if len(chronological) < 3:
            return 0.0

        first = chronological[0]
        mid_idx = len(chronological) // 2
        mid = chronological[mid_idx]
        last = chronological[-1]

        try:
            t0 = datetime.fromisoformat(first.snapshot_at)
            t1 = datetime.fromisoformat(mid.snapshot_at)
            t2 = datetime.fromisoformat(last.snapshot_at)

            dt1 = (t1 - t0).total_seconds() / 3600.0
            dt2 = (t2 - t1).total_seconds() / 3600.0

            if dt1 < 1e-6 or dt2 < 1e-6:
                return 0.0

            # First derivatives at two points
            dh1 = (mid.shannon_entropy - first.shannon_entropy) / dt1
            dh2 = (last.shannon_entropy - mid.shannon_entropy) / dt2

            # Second derivative
            dt_avg = (dt1 + dt2) / 2.0
            return (dh2 - dh1) / dt_avg

        except (ValueError, TypeError):
            return 0.0

    # ── Trend Classification ─────────────────────────────────────────────

    def _classify_trend(self, entropies: list[float]) -> str:
        """Classify the entropy trend as increasing, decreasing, stable, or oscillating."""
        if len(entropies) < self.MIN_TREND_SNAPSHOTS:
            return "stable"

        # Count direction changes
        increases = 0
        decreases = 0
        for i in range(1, len(entropies)):
            delta = entropies[i] - entropies[i - 1]
            if delta > 1e-6:
                increases += 1
            elif delta < -1e-6:
                decreases += 1

        total_changes = increases + decreases
        if total_changes == 0:
            return "stable"

        # Oscillating: lots of direction changes relative to length
        if increases > 0 and decreases > 0:
            oscillation_ratio = min(increases, decreases) / max(increases, decreases)
            if oscillation_ratio > 0.4:
                return "oscillating"

        # Net direction
        net = entropies[-1] - entropies[0]
        if net > 0.01:
            return "increasing"
        elif net < -0.01:
            return "decreasing"
        return "stable"

    # ── Bulk Analysis ────────────────────────────────────────────────────

    def analyze_all_trends(self) -> list[EntropyTrend]:
        """Analyze entropy trends for all claims with timeline data."""
        claim_ids = self.get_claims_with_history()
        trends = []
        for cid in claim_ids:
            trend = self.analyze_trend(cid)
            trends.append(trend)
        return trends

    def detect_spikes(self, min_magnitude: float = 2.0) -> list[EntropyTrend]:
        """Find claims with recent entropy spikes."""
        trends = self.analyze_all_trends()
        return [t for t in trends if t.is_spike and t.spike_magnitude >= min_magnitude]

    def detect_collapses(self) -> list[EntropyTrend]:
        """Find claims with recent entropy collapses."""
        trends = self.analyze_all_trends()
        return [t for t in trends if t.is_collapse]

    # ── Helpers ──────────────────────────────────────────────────────────

    def get_claims_with_history(self) -> list[int]:
        """Get all claim IDs that have entropy timeline entries."""
        rows = execute_sql(
            "SELECT DISTINCT claim_id FROM entropy_timeline ORDER BY claim_id"
        )
        return [r["claim_id"] for r in rows]

    def get_snapshot_count(self, claim_id: int) -> int:
        """Count how many entropy snapshots exist for a claim."""
        rows = execute_sql(
            "SELECT COUNT(*) as cnt FROM entropy_timeline WHERE claim_id = ?",
            (claim_id,),
        )
        return rows[0]["cnt"] if rows else 0
