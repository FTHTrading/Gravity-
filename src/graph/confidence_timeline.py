"""
Confidence Timeline – Temporal Confidence Tracking Engine

Records and queries confidence scores over time for each claim,
enabling trend analysis, moving averages, plateau detection,
and convergence identification.

Stored in confidence_timeline table.
Key capabilities:
  - Snapshot current confidence to timeline
  - Compute moving averages (simple, exponential)
  - Detect plateau / convergence windows
  - Rate of change (dC/dt)
  - Historical comparison and delta reporting
"""

import math
import json
from datetime import datetime, timezone, timedelta
from dataclasses import dataclass, field

from src.database import insert_row, execute_sql
from src.graph.claim_graph import ClaimGraph
from src.graph.confidence_scorer import ConfidenceScorer, ScoreBreakdown
from src.logger import get_logger

log = get_logger(__name__)


@dataclass
class ConfidenceTrendPoint:
    """Single point on the confidence timeline."""
    claim_id: int = 0
    score_value: float = 0.0
    snapshot_at: str = ""
    components: dict = field(default_factory=dict)


@dataclass
class ConfidenceTrend:
    """Aggregated confidence trend analysis for a claim."""
    claim_id: int = 0
    current_score: float = 0.0
    mean_score: float = 0.0
    std_dev: float = 0.0
    min_score: float = 0.0
    max_score: float = 0.0
    score_range: float = 0.0
    total_snapshots: int = 0
    moving_avg: float = 0.0
    ema: float = 0.0
    rate_of_change: float = 0.0       # dC/dt (per hour)
    is_converging: bool = False
    is_plateau: bool = False
    plateau_duration_hours: float = 0.0
    trend_direction: str = "stable"    # rising, falling, stable
    history: list = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "claim_id": self.claim_id,
            "current_score": round(self.current_score, 6),
            "mean_score": round(self.mean_score, 6),
            "std_dev": round(self.std_dev, 6),
            "min_score": round(self.min_score, 6),
            "max_score": round(self.max_score, 6),
            "score_range": round(self.score_range, 6),
            "total_snapshots": self.total_snapshots,
            "moving_avg": round(self.moving_avg, 6),
            "ema": round(self.ema, 6),
            "rate_of_change": round(self.rate_of_change, 6),
            "is_converging": self.is_converging,
            "is_plateau": self.is_plateau,
            "plateau_duration_hours": round(self.plateau_duration_hours, 2),
            "trend_direction": self.trend_direction,
        }


class ConfidenceTimeline:
    """
    Tracks confidence scores over time for claims.

    Provides moving averages, convergence detection, and plateau analysis.
    """

    # Plateau threshold: if std_dev of last N scores < this, it's a plateau
    PLATEAU_THRESHOLD = 0.02
    # Convergence: if std_dev is shrinking across windows
    CONVERGENCE_WINDOW = 5
    # Moving average window
    MA_WINDOW = 5
    # EMA smoothing factor
    EMA_ALPHA = 0.3
    # Rate of change significance threshold (per hour)
    ROC_THRESHOLD = 0.01

    def __init__(self):
        self.graph = ClaimGraph()
        self.scorer = ConfidenceScorer()

    # ── Snapshot Operations ──────────────────────────────────────────────

    def snapshot_claim(self, claim_id: int) -> ConfidenceTrendPoint:
        """
        Score a claim and record the result on the timeline.
        Returns the trend point created.
        """
        score = self.scorer.score_claim(claim_id)
        now = datetime.now(timezone.utc).isoformat()

        insert_row("confidence_timeline", {
            "claim_id": claim_id,
            "score_value": score.composite,
            "components_json": json.dumps(score.to_dict()),
            "snapshot_at": now,
        })

        point = ConfidenceTrendPoint(
            claim_id=claim_id,
            score_value=score.composite,
            snapshot_at=now,
            components=score.to_dict(),
        )
        log.info("Confidence snapshot: claim #%d → %.4f", claim_id, score.composite)
        return point

    def snapshot_all(self) -> list[ConfidenceTrendPoint]:
        """Snapshot confidence for every claim in the graph."""
        claims = self.graph.get_all_claims()
        points = []
        for claim in claims:
            point = self.snapshot_claim(claim.id)
            points.append(point)
        log.info("Snapshotted %d claims to confidence timeline.", len(points))
        return points

    # ── Query Operations ─────────────────────────────────────────────────

    def get_history(self, claim_id: int, limit: int = 100) -> list[ConfidenceTrendPoint]:
        """Get the confidence history for a claim, newest first."""
        rows = execute_sql(
            "SELECT claim_id, score_value, snapshot_at, components_json "
            "FROM confidence_timeline WHERE claim_id = ? "
            "ORDER BY snapshot_at DESC LIMIT ?",
            (claim_id, limit),
        )
        points = []
        for row in rows:
            comps = {}
            if row.get("components_json"):
                try:
                    comps = json.loads(row["components_json"])
                except (json.JSONDecodeError, TypeError):
                    pass
            points.append(ConfidenceTrendPoint(
                claim_id=row["claim_id"],
                score_value=row["score_value"],
                snapshot_at=row["snapshot_at"],
                components=comps,
            ))
        return points

    def get_latest(self, claim_id: int) -> float | None:
        """Get the most recent confidence score from the timeline."""
        rows = execute_sql(
            "SELECT score_value FROM confidence_timeline "
            "WHERE claim_id = ? ORDER BY snapshot_at DESC LIMIT 1",
            (claim_id,),
        )
        if rows:
            return rows[0]["score_value"]
        return None

    # ── Trend Analysis ───────────────────────────────────────────────────

    def analyze_trend(self, claim_id: int) -> ConfidenceTrend:
        """
        Full trend analysis for a claim's confidence history.

        Computes: mean, std_dev, moving average, EMA, rate of change,
        plateau and convergence detection, trend direction.
        """
        history = self.get_history(claim_id, limit=200)

        trend = ConfidenceTrend(claim_id=claim_id)

        if not history:
            return trend

        # History is newest-first; reverse for chronological analysis
        chronological = list(reversed(history))
        scores = [p.score_value for p in chronological]
        trend.total_snapshots = len(scores)
        trend.current_score = scores[-1]
        trend.history = [{"score": p.score_value, "at": p.snapshot_at} for p in chronological]

        # Basic statistics
        trend.mean_score = sum(scores) / len(scores)
        trend.min_score = min(scores)
        trend.max_score = max(scores)
        trend.score_range = trend.max_score - trend.min_score

        if len(scores) > 1:
            variance = sum((s - trend.mean_score) ** 2 for s in scores) / len(scores)
            trend.std_dev = math.sqrt(variance)
        else:
            trend.std_dev = 0.0

        # Moving average (last MA_WINDOW points)
        window = scores[-self.MA_WINDOW:]
        trend.moving_avg = sum(window) / len(window)

        # Exponential moving average
        trend.ema = self._compute_ema(scores)

        # Rate of change (dC/dt)
        trend.rate_of_change = self._compute_rate_of_change(chronological)

        # Trend direction
        if len(scores) >= 3:
            recent_avg = sum(scores[-3:]) / 3
            earlier_avg = sum(scores[:min(3, len(scores))]) / min(3, len(scores))
            diff = recent_avg - earlier_avg
            if diff > self.ROC_THRESHOLD:
                trend.trend_direction = "rising"
            elif diff < -self.ROC_THRESHOLD:
                trend.trend_direction = "falling"
            else:
                trend.trend_direction = "stable"

        # Plateau detection
        trend.is_plateau, trend.plateau_duration_hours = self._detect_plateau(
            chronological
        )

        # Convergence detection
        trend.is_converging = self._detect_convergence(scores)

        return trend

    # ── Moving Averages ──────────────────────────────────────────────────

    def _compute_ema(self, scores: list[float]) -> float:
        """Exponential moving average with alpha smoothing."""
        if not scores:
            return 0.0
        ema = scores[0]
        for s in scores[1:]:
            ema = self.EMA_ALPHA * s + (1 - self.EMA_ALPHA) * ema
        return ema

    def compute_sma_series(self, claim_id: int, window: int = 5) -> list[float]:
        """Compute a simple moving average series for a claim."""
        history = self.get_history(claim_id, limit=500)
        scores = [p.score_value for p in reversed(history)]
        if len(scores) < window:
            return scores
        sma = []
        for i in range(len(scores)):
            if i < window - 1:
                sma.append(sum(scores[:i+1]) / (i + 1))
            else:
                sma.append(sum(scores[i - window + 1:i + 1]) / window)
        return sma

    def compute_ema_series(self, claim_id: int) -> list[float]:
        """Compute full EMA series for a claim."""
        history = self.get_history(claim_id, limit=500)
        scores = [p.score_value for p in reversed(history)]
        if not scores:
            return []
        ema_series = [scores[0]]
        for s in scores[1:]:
            ema_series.append(self.EMA_ALPHA * s + (1 - self.EMA_ALPHA) * ema_series[-1])
        return ema_series

    # ── Rate of Change ───────────────────────────────────────────────────

    def _compute_rate_of_change(self, chronological: list[ConfidenceTrendPoint]) -> float:
        """
        Compute dC/dt in score-units per hour.
        Uses first and last points in the timeline.
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
            return (last.score_value - first.score_value) / dt_hours
        except (ValueError, TypeError):
            return 0.0

    # ── Plateau Detection ────────────────────────────────────────────────

    def _detect_plateau(self, chronological: list[ConfidenceTrendPoint]) -> tuple[bool, float]:
        """
        Detect if the score has plateaued.
        Returns (is_plateau, duration_in_hours).
        """
        if len(chronological) < self.MA_WINDOW:
            return False, 0.0

        recent = [p.score_value for p in chronological[-self.MA_WINDOW:]]
        mean = sum(recent) / len(recent)
        variance = sum((s - mean) ** 2 for s in recent) / len(recent)
        std = math.sqrt(variance)

        if std < self.PLATEAU_THRESHOLD:
            # Calculate duration of plateau
            try:
                t_start = datetime.fromisoformat(chronological[-self.MA_WINDOW].snapshot_at)
                t_end = datetime.fromisoformat(chronological[-1].snapshot_at)
                hours = (t_end - t_start).total_seconds() / 3600.0
                return True, hours
            except (ValueError, TypeError):
                return True, 0.0

        return False, 0.0

    # ── Convergence Detection ────────────────────────────────────────────

    def _detect_convergence(self, scores: list[float]) -> bool:
        """
        Detect if scores are converging by checking whether
        the standard deviation of successive windows is decreasing.
        """
        if len(scores) < self.CONVERGENCE_WINDOW * 2:
            return False

        window = self.CONVERGENCE_WINDOW

        def window_std(data: list[float]) -> float:
            mean = sum(data) / len(data)
            return math.sqrt(sum((x - mean) ** 2 for x in data) / len(data))

        # Compare std of earlier window vs later window
        earlier = scores[-(2 * window):-window]
        later = scores[-window:]
        std_earlier = window_std(earlier)
        std_later = window_std(later)

        # Converging if variance is shrinking
        return std_later < std_earlier * 0.8

    # ── Helpers ──────────────────────────────────────────────────────────

    def get_claims_with_history(self) -> list[int]:
        """Get all claim IDs that have timeline entries."""
        rows = execute_sql(
            "SELECT DISTINCT claim_id FROM confidence_timeline "
            "ORDER BY claim_id"
        )
        return [r["claim_id"] for r in rows]

    def get_snapshot_count(self, claim_id: int) -> int:
        """Count how many timeline snapshots exist for a claim."""
        rows = execute_sql(
            "SELECT COUNT(*) as cnt FROM confidence_timeline WHERE claim_id = ?",
            (claim_id,),
        )
        return rows[0]["cnt"] if rows else 0

    def purge_old_snapshots(self, claim_id: int, keep: int = 100) -> int:
        """Remove oldest snapshots beyond the keep limit. Returns count removed."""
        total = self.get_snapshot_count(claim_id)
        if total <= keep:
            return 0
        to_remove = total - keep
        execute_sql(
            "DELETE FROM confidence_timeline WHERE id IN ("
            "  SELECT id FROM confidence_timeline "
            "  WHERE claim_id = ? ORDER BY snapshot_at ASC LIMIT ?"
            ")",
            (claim_id, to_remove),
        )
        log.info("Purged %d old snapshots for claim #%d", to_remove, claim_id)
        return to_remove
