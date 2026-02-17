"""
Source Reputation Engine – Temporal Source Credibility Intelligence

Tracks source reliability over time using:
  - Support / contradiction ratio across linked claims
  - Exponential moving average (EMA) of credibility
  - Accuracy rate (fraction of claims that are supported/confirmed)
  - Trend direction (improving / degrading / flat)
  - Reliability index (composite of accuracy + consistency + longevity)

DB tables used: source_reputation, source_nodes, evidence_links, claim_nodes
"""

import json
import math
from datetime import datetime, timezone
from dataclasses import dataclass, field

from src.database import insert_row, query_rows, execute_sql, get_connection
from src.logger import get_logger

log = get_logger(__name__)

# ── Constants ────────────────────────────────────────────────────────────
EMA_ALPHA = 0.3          # Smoothing factor for EMA credibility
MIN_CLAIMS_FOR_TREND = 3  # Minimum reputation snapshots before trend
TREND_THRESHOLD = 0.02    # Minimum |delta| to classify as improving/degrading


@dataclass
class ReputationSnapshot:
    """A single credibility measurement for a source."""
    id: int = 0
    source_id: int = 0
    reliability: float = 0.5
    accuracy_rate: float = 0.0
    support_count: int = 0
    contradict_count: int = 0
    total_claims: int = 0
    ema_credibility: float = 0.5
    trend_direction: str = "flat"
    computed_at: str = ""

    def to_dict(self) -> dict:
        return {
            "source_id": self.source_id,
            "reliability": round(self.reliability, 4),
            "accuracy_rate": round(self.accuracy_rate, 4),
            "support_count": self.support_count,
            "contradict_count": self.contradict_count,
            "total_claims": self.total_claims,
            "ema_credibility": round(self.ema_credibility, 4),
            "trend_direction": self.trend_direction,
            "computed_at": self.computed_at,
        }


@dataclass
class ReputationProfile:
    """Full reputation profile for a source."""
    source_id: int = 0
    source_title: str = ""
    source_type: str = ""
    current_reliability: float = 0.5
    current_ema: float = 0.5
    accuracy_rate: float = 0.0
    support_ratio: float = 0.0
    trend_direction: str = "flat"
    trend_delta: float = 0.0
    total_claims: int = 0
    support_count: int = 0
    contradict_count: int = 0
    snapshot_count: int = 0
    mean_reliability: float = 0.5
    std_reliability: float = 0.0
    reliability_index: float = 0.0
    grade: str = "C"

    def to_dict(self) -> dict:
        return {
            "source_id": self.source_id,
            "source_title": self.source_title,
            "source_type": self.source_type,
            "current_reliability": round(self.current_reliability, 4),
            "current_ema": round(self.current_ema, 4),
            "accuracy_rate": round(self.accuracy_rate, 4),
            "support_ratio": round(self.support_ratio, 4),
            "trend_direction": self.trend_direction,
            "trend_delta": round(self.trend_delta, 6),
            "total_claims": self.total_claims,
            "support_count": self.support_count,
            "contradict_count": self.contradict_count,
            "snapshot_count": self.snapshot_count,
            "mean_reliability": round(self.mean_reliability, 4),
            "std_reliability": round(self.std_reliability, 4),
            "reliability_index": round(self.reliability_index, 4),
            "grade": self.grade,
        }


class SourceReputationEngine:
    """Compute and track source credibility over time."""

    # ── Snapshot ─────────────────────────────────────────────────────────

    def snapshot_source(self, source_id: int) -> ReputationSnapshot:
        """
        Compute a reputation snapshot for a single source.

        Examines all evidence_links from this source → claims,
        tallies support vs contradiction, computes EMA.
        """
        now = datetime.now(timezone.utc).isoformat()

        # Count relationships
        links = query_rows(
            "evidence_links",
            "from_type = ? AND from_id = ? AND to_type = ?",
            ("source", source_id, "claim"),
        )
        # Also count links where claims point to this source
        links_inbound = query_rows(
            "evidence_links",
            "to_type = ? AND to_id = ? AND from_type = ?",
            ("source", source_id, "claim"),
        )
        all_links = links + links_inbound

        support_count = 0
        contradict_count = 0
        total = len(all_links)

        for link in all_links:
            rel = link.get("relationship", "")
            if rel in ("supports", "references", "derives_from"):
                support_count += 1
            elif rel in ("contradicts", "supersedes"):
                contradict_count += 1

        # Accuracy rate
        accuracy = support_count / total if total > 0 else 0.0

        # Raw reliability: support fraction with Laplace smoothing
        reliability = (support_count + 1) / (total + 2)

        # EMA credibility from previous snapshot
        prev_rows = query_rows(
            "source_reputation",
            "source_id = ? ORDER BY computed_at DESC LIMIT 1",
            (source_id,),
        )
        if prev_rows:
            prev_ema = prev_rows[0]["ema_credibility"]
            ema = EMA_ALPHA * reliability + (1 - EMA_ALPHA) * prev_ema
        else:
            ema = reliability

        # Trend direction
        trend = self._compute_trend(source_id, reliability)

        snap = ReputationSnapshot(
            source_id=source_id,
            reliability=reliability,
            accuracy_rate=accuracy,
            support_count=support_count,
            contradict_count=contradict_count,
            total_claims=total,
            ema_credibility=ema,
            trend_direction=trend,
            computed_at=now,
        )

        snap.id = insert_row("source_reputation", {
            "source_id": source_id,
            "reliability": reliability,
            "accuracy_rate": accuracy,
            "support_count": support_count,
            "contradict_count": contradict_count,
            "total_claims": total,
            "ema_credibility": ema,
            "trend_direction": trend,
            "computed_at": now,
        })

        log.info("Source #%d reputation: reliability=%.4f ema=%.4f trend=%s",
                 source_id, reliability, ema, trend)
        return snap

    def snapshot_all(self) -> list[ReputationSnapshot]:
        """Snapshot reputation for all sources."""
        sources = query_rows("source_nodes", "1=1")
        results = []
        for src in sources:
            snap = self.snapshot_source(src["id"])
            results.append(snap)
        log.info("Snapshotted %d sources.", len(results))
        return results

    # ── Profile ──────────────────────────────────────────────────────────

    def get_profile(self, source_id: int) -> ReputationProfile:
        """
        Build a full reputation profile from snapshot history.
        """
        profile = ReputationProfile(source_id=source_id)

        # Source metadata
        source_rows = query_rows("source_nodes", "id = ?", (source_id,))
        if source_rows:
            profile.source_title = source_rows[0].get("source_title", "")
            profile.source_type = source_rows[0].get("source_type", "")

        # Snapshot history
        snapshots = query_rows(
            "source_reputation",
            "source_id = ? ORDER BY computed_at ASC",
            (source_id,),
        )
        profile.snapshot_count = len(snapshots)

        if not snapshots:
            return profile

        # Latest values
        latest = snapshots[-1]
        profile.current_reliability = latest["reliability"]
        profile.current_ema = latest["ema_credibility"]
        profile.accuracy_rate = latest["accuracy_rate"]
        profile.support_count = latest["support_count"]
        profile.contradict_count = latest["contradict_count"]
        profile.total_claims = latest["total_claims"]
        profile.trend_direction = latest["trend_direction"]

        # Support ratio
        total = profile.support_count + profile.contradict_count
        profile.support_ratio = profile.support_count / total if total > 0 else 0.0

        # Statistics across snapshots
        reliabilities = [s["reliability"] for s in snapshots]
        profile.mean_reliability = sum(reliabilities) / len(reliabilities)
        if len(reliabilities) > 1:
            variance = sum((r - profile.mean_reliability) ** 2 for r in reliabilities) / len(reliabilities)
            profile.std_reliability = math.sqrt(variance)

        # Trend delta (latest - first)
        if len(snapshots) >= 2:
            profile.trend_delta = snapshots[-1]["reliability"] - snapshots[0]["reliability"]

        # Reliability index: composite score
        profile.reliability_index = self._compute_reliability_index(profile)
        profile.grade = self._grade(profile.reliability_index)

        return profile

    def get_all_profiles(self) -> list[ReputationProfile]:
        """Get reputation profiles for all sources."""
        sources = query_rows("source_nodes", "1=1")
        return [self.get_profile(src["id"]) for src in sources]

    def rank_sources(self) -> list[ReputationProfile]:
        """Return all source profiles ranked by reliability index."""
        profiles = self.get_all_profiles()
        profiles.sort(key=lambda p: p.reliability_index, reverse=True)
        return profiles

    # ── History ──────────────────────────────────────────────────────────

    def get_history(self, source_id: int) -> list[ReputationSnapshot]:
        """Get chronological reputation history for a source."""
        rows = query_rows(
            "source_reputation",
            "source_id = ? ORDER BY computed_at ASC",
            (source_id,),
        )
        return [self._row_to_snapshot(r) for r in rows]

    # ── Internal ─────────────────────────────────────────────────────────

    def _compute_trend(self, source_id: int, current: float) -> str:
        """Determine trend direction from snapshot history."""
        rows = query_rows(
            "source_reputation",
            "source_id = ? ORDER BY computed_at DESC LIMIT ?",
            (source_id, MIN_CLAIMS_FOR_TREND),
        )
        if len(rows) < MIN_CLAIMS_FOR_TREND:
            return "flat"

        # Compare current to oldest in window
        oldest = rows[-1]["reliability"]
        delta = current - oldest
        if delta > TREND_THRESHOLD:
            return "improving"
        elif delta < -TREND_THRESHOLD:
            return "degrading"
        return "flat"

    def _compute_reliability_index(self, profile: ReputationProfile) -> float:
        """
        Composite reliability index (0.0 – 1.0):
          - 40% accuracy rate
          - 30% EMA credibility
          - 20% consistency (1 - std_reliability)
          - 10% volume bonus (log-scaled claim count)
        """
        accuracy_component = profile.accuracy_rate * 0.40
        ema_component = profile.current_ema * 0.30
        consistency_component = max(0, 1.0 - profile.std_reliability * 3) * 0.20
        volume_bonus = min(1.0, math.log1p(profile.total_claims) / 3.0) * 0.10

        index = accuracy_component + ema_component + consistency_component + volume_bonus
        return max(0.0, min(1.0, index))

    @staticmethod
    def _grade(index: float) -> str:
        """Letter grade from reliability index."""
        if index >= 0.90:
            return "A"
        if index >= 0.75:
            return "B"
        if index >= 0.60:
            return "C"
        if index >= 0.40:
            return "D"
        return "F"

    @staticmethod
    def _row_to_snapshot(row) -> ReputationSnapshot:
        return ReputationSnapshot(
            id=row["id"],
            source_id=row["source_id"],
            reliability=row["reliability"],
            accuracy_rate=row["accuracy_rate"],
            support_count=row["support_count"],
            contradict_count=row["contradict_count"],
            total_claims=row["total_claims"],
            ema_credibility=row["ema_credibility"],
            trend_direction=row["trend_direction"],
            computed_at=row["computed_at"],
        )
