"""
Stability Classifier – Epistemic State Machine

Classifies claims into stability states based on temporal signals:
  - stable:      low variance, low drift, consistent confidence
  - converging:  decreasing variance, narrowing oscillation
  - volatile:    high variance, frequent direction changes
  - diverging:   increasing variance, accelerating drift
  - critical:    extreme metrics, multiple anomaly signals

Uses inputs from:
  - ConfidenceTimeline (confidence trends)
  - EntropyTrendEngine (entropy dynamics)
  - DriftKinematicsEngine (kinematic profiles)

Results stored in stability_classifications table.
"""

import json
from datetime import datetime, timezone
from dataclasses import dataclass, field

from src.database import insert_row, execute_sql
from src.graph.claim_graph import ClaimGraph
from src.graph.confidence_timeline import ConfidenceTimeline, ConfidenceTrend
from src.graph.entropy_trend import EntropyTrendEngine, EntropyTrend
from src.graph.drift_kinematics import DriftKinematicsEngine, DriftKinematics
from src.logger import get_logger

log = get_logger(__name__)


# ── Classification Constants ─────────────────────────────────────────────
STABILITY_STATES = ("stable", "converging", "volatile", "diverging", "critical")


@dataclass
class StabilityProfile:
    """Complete stability classification with supporting signals."""
    claim_id: int = 0
    classification: str = "stable"
    confidence_trend: float = 0.0    # rate of change of confidence
    entropy_trend: float = 0.0       # dH/dt
    drift_accel: float = 0.0         # d²d/dt²
    confidence_std: float = 0.0
    entropy_std: float = 0.0
    is_converging: bool = False
    is_plateau: bool = False
    is_spike: bool = False
    has_inflection: bool = False
    signal_flags: list = field(default_factory=list)
    classified_at: str = ""

    def to_dict(self) -> dict:
        return {
            "claim_id": self.claim_id,
            "classification": self.classification,
            "confidence_trend": round(self.confidence_trend, 6),
            "entropy_trend": round(self.entropy_trend, 6),
            "drift_accel": round(self.drift_accel, 6),
            "confidence_std": round(self.confidence_std, 6),
            "entropy_std": round(self.entropy_std, 6),
            "is_converging": self.is_converging,
            "is_plateau": self.is_plateau,
            "is_spike": self.is_spike,
            "has_inflection": self.has_inflection,
            "signal_flags": self.signal_flags,
            "classified_at": self.classified_at,
        }


class StabilityClassifier:
    """
    Classifies claims into epistemic stability states.

    Combines signals from confidence, entropy, and drift systems
    into a single classification with supporting evidence.
    """

    # ── Thresholds ───────────────────────────────────────────────────────
    # Confidence volatility threshold
    CONF_VOLATILE_STD = 0.10
    # Entropy volatility threshold
    ENTROPY_VOLATILE_STD = 0.5
    # Drift acceleration threshold for diverging
    DRIFT_DIVERGING_ACCEL = 0.005
    # Confidence convergence std threshold
    CONVERGENCE_STD = 0.03
    # Critical: number of simultaneous anomaly flags
    CRITICAL_FLAG_COUNT = 3

    def __init__(self):
        self.graph = ClaimGraph()
        self.confidence_tl = ConfidenceTimeline()
        self.entropy_tl = EntropyTrendEngine()
        self.drift_engine = DriftKinematicsEngine()

    # ── Core Classification ──────────────────────────────────────────────

    def classify(self, claim_id: int) -> StabilityProfile:
        """
        Classify a claim's epistemic stability state.

        Gathers signals from all temporal engines and produces
        a single classification with supporting evidence.
        """
        profile = StabilityProfile(claim_id=claim_id)
        now = datetime.now(timezone.utc).isoformat()
        profile.classified_at = now

        # Gather temporal signals
        conf_trend = self.confidence_tl.analyze_trend(claim_id)
        ent_trend = self.entropy_tl.analyze_trend(claim_id)
        drift_kin = self.drift_engine.analyze(claim_id)

        # Extract key metrics
        profile.confidence_trend = conf_trend.rate_of_change
        profile.entropy_trend = ent_trend.dh_dt
        profile.drift_accel = drift_kin.current_acceleration
        profile.confidence_std = conf_trend.std_dev
        profile.entropy_std = ent_trend.std_dev
        profile.is_converging = conf_trend.is_converging
        profile.is_plateau = conf_trend.is_plateau
        profile.is_spike = ent_trend.is_spike
        profile.has_inflection = len(drift_kin.inflection_points) > 0

        # Collect signal flags
        flags = self._collect_flags(profile, conf_trend, ent_trend, drift_kin)
        profile.signal_flags = flags

        # Classify based on signals
        profile.classification = self._determine_classification(profile, flags)

        # Persist
        self._save(profile)

        log.info("Classified claim #%d → %s (%d flags)",
                 claim_id, profile.classification, len(flags))
        return profile

    def classify_all(self) -> list[StabilityProfile]:
        """Classify all claims in the graph."""
        claims = self.graph.get_all_claims()
        profiles = []
        for claim in claims:
            profile = self.classify(claim.id)
            profiles.append(profile)
        log.info("Classified %d claims.", len(profiles))
        return profiles

    # ── Signal Collection ────────────────────────────────────────────────

    def _collect_flags(self, profile: StabilityProfile,
                       conf_trend: ConfidenceTrend,
                       ent_trend: EntropyTrend,
                       drift_kin: DriftKinematics) -> list[str]:
        """Collect anomaly/signal flags from all temporal sources."""
        flags = []

        # Confidence signals
        if conf_trend.is_converging:
            flags.append("confidence_converging")
        if conf_trend.is_plateau:
            flags.append("confidence_plateau")
        if conf_trend.std_dev > self.CONF_VOLATILE_STD:
            flags.append("confidence_volatile")
        if conf_trend.trend_direction == "falling":
            flags.append("confidence_falling")
        if conf_trend.trend_direction == "rising":
            flags.append("confidence_rising")

        # Entropy signals
        if ent_trend.is_spike:
            flags.append("entropy_spike")
        if ent_trend.is_collapse:
            flags.append("entropy_collapse")
        if ent_trend.std_dev > self.ENTROPY_VOLATILE_STD:
            flags.append("entropy_volatile")
        if ent_trend.trend_direction == "increasing":
            flags.append("entropy_increasing")
        if ent_trend.trend_direction == "oscillating":
            flags.append("entropy_oscillating")

        # Drift signals
        if drift_kin.phase == "accelerating":
            flags.append("drift_accelerating")
        if drift_kin.phase == "inflecting":
            flags.append("drift_inflecting")
        if abs(drift_kin.current_acceleration) > self.DRIFT_DIVERGING_ACCEL:
            flags.append("drift_high_acceleration")
        if drift_kin.inflection_points:
            flags.append("drift_inflection_detected")

        return flags

    # ── Classification Logic ─────────────────────────────────────────────

    def _determine_classification(self, profile: StabilityProfile,
                                  flags: list[str]) -> str:
        """
        Determine the stability classification based on signal flags.

        Priority order (highest to lowest):
          critical → diverging → volatile → converging → stable
        """
        # Critical: too many simultaneous anomaly signals
        anomaly_flags = [f for f in flags if f in (
            "entropy_spike", "entropy_volatile", "confidence_volatile",
            "drift_high_acceleration", "confidence_falling", "entropy_increasing",
        )]
        if len(anomaly_flags) >= self.CRITICAL_FLAG_COUNT:
            return "critical"

        # Diverging: accelerating drift + increasing entropy
        if ("drift_accelerating" in flags or "drift_high_acceleration" in flags) and \
           ("entropy_increasing" in flags or "entropy_spike" in flags):
            return "diverging"

        # Volatile: high variance in either confidence or entropy
        if "confidence_volatile" in flags or "entropy_volatile" in flags or \
           "entropy_oscillating" in flags:
            return "volatile"

        # Converging: confidence is converging and/or entropy decreasing
        if profile.is_converging or profile.is_plateau:
            return "converging"

        if "confidence_rising" in flags and profile.confidence_std < self.CONVERGENCE_STD:
            return "converging"

        # Default: stable
        return "stable"

    # ── Persistence ──────────────────────────────────────────────────────

    def _save(self, profile: StabilityProfile) -> int:
        """Save classification to the database."""
        return insert_row("stability_classifications", {
            "claim_id": profile.claim_id,
            "classification": profile.classification,
            "confidence_trend": profile.confidence_trend,
            "entropy_trend": profile.entropy_trend,
            "drift_accel": profile.drift_accel,
            "signal_summary": json.dumps(profile.signal_flags),
            "classified_at": profile.classified_at,
        })

    # ── Query ────────────────────────────────────────────────────────────

    def get_latest(self, claim_id: int) -> str | None:
        """Get the most recent classification for a claim."""
        rows = execute_sql(
            "SELECT classification FROM stability_classifications "
            "WHERE claim_id = ? ORDER BY classified_at DESC LIMIT 1",
            (claim_id,),
        )
        return rows[0]["classification"] if rows else None

    def get_history(self, claim_id: int, limit: int = 50) -> list[dict]:
        """Get classification history for a claim."""
        rows = execute_sql(
            "SELECT * FROM stability_classifications "
            "WHERE claim_id = ? ORDER BY classified_at DESC LIMIT ?",
            (claim_id, limit),
        )
        return rows

    def get_by_state(self, state: str) -> list[int]:
        """
        Get claim IDs currently in a given state.
        Uses the most recent classification for each claim.
        """
        rows = execute_sql(
            "SELECT claim_id, classification FROM stability_classifications "
            "WHERE id IN ("
            "  SELECT MAX(id) FROM stability_classifications GROUP BY claim_id"
            ") AND classification = ?",
            (state,),
        )
        return [r["claim_id"] for r in rows]

    def get_summary(self) -> dict:
        """Summary of stability classifications across all claims."""
        rows = execute_sql(
            "SELECT classification, COUNT(*) as cnt FROM ("
            "  SELECT claim_id, classification FROM stability_classifications "
            "  WHERE id IN ("
            "    SELECT MAX(id) FROM stability_classifications GROUP BY claim_id"
            "  )"
            ") GROUP BY classification"
        )
        summary = {state: 0 for state in STABILITY_STATES}
        for row in rows:
            summary[row["classification"]] = row["cnt"]
        summary["total_classified"] = sum(summary.values())
        return summary
