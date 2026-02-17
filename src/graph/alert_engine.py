"""
Alert Engine – Epistemic Anomaly Detection & Notification

Rule-based + threshold trigger system for detecting:
  - Entropy spikes (sudden mutation bursts)
  - Confidence collapse (rapid score decline)
  - Drift acceleration (inflection points)
  - Cluster tension surges (conflict escalation)
  - Stability transitions (state changes)

Alerts stored in epistemic_alerts table with severity levels:
  info, warning, critical

Provides:
  - Automatic alert generation from temporal analysis
  - Alert querying and acknowledgement
  - Alert summary and dashboard data
"""

import json
from datetime import datetime, timezone
from dataclasses import dataclass, field

from src.database import insert_row, execute_sql
from src.graph.claim_graph import ClaimGraph
from src.graph.confidence_timeline import ConfidenceTimeline, ConfidenceTrend
from src.graph.entropy_trend import EntropyTrendEngine, EntropyTrend
from src.graph.drift_kinematics import DriftKinematicsEngine, DriftKinematics
from src.graph.contradiction_analyzer import ContradictionAnalyzer
from src.logger import get_logger

log = get_logger(__name__)


# ── Alert Types ──────────────────────────────────────────────────────────
ALERT_TYPES = (
    "entropy_spike",
    "entropy_collapse",
    "confidence_collapse",
    "confidence_surge",
    "drift_acceleration",
    "drift_inflection",
    "tension_surge",
    "stability_transition",
    "critical_state",
)

SEVERITY_LEVELS = ("info", "warning", "critical")


@dataclass
class Alert:
    """Single epistemic alert."""
    id: int = 0
    claim_id: int = 0
    alert_type: str = ""
    severity: str = "info"
    title: str = ""
    detail: str = ""
    metric_value: float = 0.0
    threshold: float = 0.0
    acknowledged: bool = False
    created_at: str = ""

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "claim_id": self.claim_id,
            "alert_type": self.alert_type,
            "severity": self.severity,
            "title": self.title,
            "detail": self.detail,
            "metric_value": round(self.metric_value, 6),
            "threshold": round(self.threshold, 6),
            "acknowledged": self.acknowledged,
            "created_at": self.created_at,
        }


class AlertEngine:
    """
    Monitors temporal epistemic signals and generates alerts
    when anomalies or significant state changes are detected.
    """

    # ── Thresholds ───────────────────────────────────────────────────────
    # Entropy spike: spike_magnitude > this
    ENTROPY_SPIKE_THRESHOLD = 2.0
    # Confidence collapse: dC/dt < this (negative = falling)
    CONFIDENCE_COLLAPSE_RATE = -0.05
    # Confidence surge: dC/dt > this
    CONFIDENCE_SURGE_RATE = 0.05
    # Drift acceleration: |d²d/dt²| > this
    DRIFT_ACCEL_THRESHOLD = 0.005
    # Tension surge: tension value > this
    TENSION_THRESHOLD = 0.5

    def __init__(self):
        self.graph = ClaimGraph()
        self.confidence_tl = ConfidenceTimeline()
        self.entropy_tl = EntropyTrendEngine()
        self.drift_engine = DriftKinematicsEngine()
        self.contradiction = ContradictionAnalyzer()

    # ── Alert Creation ───────────────────────────────────────────────────

    def create_alert(self, claim_id: int, alert_type: str,
                     severity: str, title: str,
                     detail: str = "", metric_value: float = 0.0,
                     threshold: float = 0.0) -> Alert:
        """Create and persist an alert."""
        now = datetime.now(timezone.utc).isoformat()
        alert_id = insert_row("epistemic_alerts", {
            "claim_id": claim_id,
            "alert_type": alert_type,
            "severity": severity,
            "title": title,
            "detail": detail,
            "metric_value": metric_value,
            "threshold": threshold,
            "acknowledged": 0,
            "created_at": now,
        })

        alert = Alert(
            id=alert_id,
            claim_id=claim_id,
            alert_type=alert_type,
            severity=severity,
            title=title,
            detail=detail,
            metric_value=metric_value,
            threshold=threshold,
            acknowledged=False,
            created_at=now,
        )
        log.info("Alert [%s] %s: %s (claim #%d, value=%.4f)",
                 severity.upper(), alert_type, title, claim_id, metric_value)
        return alert

    # ── Automatic Scanning ───────────────────────────────────────────────

    def scan_claim(self, claim_id: int) -> list[Alert]:
        """
        Scan a single claim for all alert conditions.
        Returns list of new alerts generated.
        """
        alerts = []

        # Check entropy
        alerts.extend(self._check_entropy(claim_id))

        # Check confidence
        alerts.extend(self._check_confidence(claim_id))

        # Check drift
        alerts.extend(self._check_drift(claim_id))

        # Check tension
        alerts.extend(self._check_tension(claim_id))

        return alerts

    def scan_all(self) -> list[Alert]:
        """Scan all claims for alert conditions."""
        claims = self.graph.get_all_claims()
        all_alerts = []
        for claim in claims:
            alerts = self.scan_claim(claim.id)
            all_alerts.extend(alerts)
        log.info("Scan complete: %d alerts across %d claims.",
                 len(all_alerts), len(claims))
        return all_alerts

    # ── Entropy Checks ───────────────────────────────────────────────────

    def _check_entropy(self, claim_id: int) -> list[Alert]:
        """Check for entropy anomalies."""
        alerts = []
        trend = self.entropy_tl.analyze_trend(claim_id)

        if trend.is_spike and trend.spike_magnitude >= self.ENTROPY_SPIKE_THRESHOLD:
            severity = "critical" if trend.spike_magnitude > 3.0 else "warning"
            alerts.append(self.create_alert(
                claim_id=claim_id,
                alert_type="entropy_spike",
                severity=severity,
                title=f"Entropy spike detected (magnitude={trend.spike_magnitude:.2f})",
                detail=f"Current entropy: {trend.current_entropy:.4f}, "
                       f"Mean: {trend.mean_entropy:.4f}, "
                       f"Std: {trend.std_dev:.4f}",
                metric_value=trend.spike_magnitude,
                threshold=self.ENTROPY_SPIKE_THRESHOLD,
            ))

        if trend.is_collapse:
            alerts.append(self.create_alert(
                claim_id=claim_id,
                alert_type="entropy_collapse",
                severity="warning",
                title=f"Entropy collapse detected",
                detail=f"Entropy dropped to {trend.current_entropy:.4f} "
                       f"from mean {trend.mean_entropy:.4f}",
                metric_value=trend.spike_magnitude,
                threshold=self.ENTROPY_SPIKE_THRESHOLD,
            ))

        return alerts

    # ── Confidence Checks ────────────────────────────────────────────────

    def _check_confidence(self, claim_id: int) -> list[Alert]:
        """Check for confidence anomalies."""
        alerts = []
        trend = self.confidence_tl.analyze_trend(claim_id)

        if trend.rate_of_change < self.CONFIDENCE_COLLAPSE_RATE:
            severity = "critical" if trend.rate_of_change < 2 * self.CONFIDENCE_COLLAPSE_RATE else "warning"
            alerts.append(self.create_alert(
                claim_id=claim_id,
                alert_type="confidence_collapse",
                severity=severity,
                title=f"Confidence collapsing (rate={trend.rate_of_change:.4f}/hr)",
                detail=f"Current: {trend.current_score:.4f}, "
                       f"Mean: {trend.mean_score:.4f}, "
                       f"Direction: {trend.trend_direction}",
                metric_value=trend.rate_of_change,
                threshold=self.CONFIDENCE_COLLAPSE_RATE,
            ))

        if trend.rate_of_change > self.CONFIDENCE_SURGE_RATE:
            alerts.append(self.create_alert(
                claim_id=claim_id,
                alert_type="confidence_surge",
                severity="info",
                title=f"Confidence surging (rate={trend.rate_of_change:.4f}/hr)",
                detail=f"Current: {trend.current_score:.4f}, "
                       f"Direction: {trend.trend_direction}",
                metric_value=trend.rate_of_change,
                threshold=self.CONFIDENCE_SURGE_RATE,
            ))

        return alerts

    # ── Drift Checks ─────────────────────────────────────────────────────

    def _check_drift(self, claim_id: int) -> list[Alert]:
        """Check for drift kinematic anomalies."""
        alerts = []
        kinematics = self.drift_engine.analyze(claim_id)

        if abs(kinematics.current_acceleration) > self.DRIFT_ACCEL_THRESHOLD:
            severity = "warning"
            if abs(kinematics.current_acceleration) > 2 * self.DRIFT_ACCEL_THRESHOLD:
                severity = "critical"
            alerts.append(self.create_alert(
                claim_id=claim_id,
                alert_type="drift_acceleration",
                severity=severity,
                title=f"Drift acceleration detected (a={kinematics.current_acceleration:.6f})",
                detail=f"Phase: {kinematics.phase}, "
                       f"Velocity: {kinematics.current_velocity:.6f}, "
                       f"Inflection points: {len(kinematics.inflection_points)}",
                metric_value=abs(kinematics.current_acceleration),
                threshold=self.DRIFT_ACCEL_THRESHOLD,
            ))

        if kinematics.inflection_points:
            alerts.append(self.create_alert(
                claim_id=claim_id,
                alert_type="drift_inflection",
                severity="info",
                title=f"Drift inflection point ({len(kinematics.inflection_points)} detected)",
                detail=f"Latest inflection: {kinematics.inflection_points[-1]}",
                metric_value=float(len(kinematics.inflection_points)),
                threshold=1.0,
            ))

        return alerts

    # ── Tension Checks ───────────────────────────────────────────────────

    def _check_tension(self, claim_id: int) -> list[Alert]:
        """Check for contradiction tension anomalies."""
        alerts = []
        profile = self.contradiction.profile_claim(claim_id)
        if not profile:
            return alerts

        if profile.tension_score > self.TENSION_THRESHOLD:
            severity = "critical" if profile.tension_score > 0.8 else "warning"
            alerts.append(self.create_alert(
                claim_id=claim_id,
                alert_type="tension_surge",
                severity=severity,
                title=f"High tension detected (score={profile.tension_score:.4f})",
                detail=f"Contradictions: {profile.contradiction_count}, "
                       f"Contested: {profile.is_contested}",
                metric_value=profile.tension_score,
                threshold=self.TENSION_THRESHOLD,
            ))

        return alerts

    # ── Alert Queries ────────────────────────────────────────────────────

    def get_alerts(self, claim_id: int | None = None,
                   severity: str | None = None,
                   alert_type: str | None = None,
                   unacknowledged_only: bool = False,
                   limit: int = 100) -> list[Alert]:
        """Query alerts with optional filters."""
        conditions = []
        params = []

        if claim_id is not None:
            conditions.append("claim_id = ?")
            params.append(claim_id)
        if severity:
            conditions.append("severity = ?")
            params.append(severity)
        if alert_type:
            conditions.append("alert_type = ?")
            params.append(alert_type)
        if unacknowledged_only:
            conditions.append("acknowledged = 0")

        where = " AND ".join(conditions) if conditions else "1=1"
        sql = f"SELECT * FROM epistemic_alerts WHERE {where} ORDER BY created_at DESC LIMIT ?"
        params.append(limit)

        rows = execute_sql(sql, tuple(params))
        return [self._row_to_alert(r) for r in rows]

    def acknowledge(self, alert_id: int) -> bool:
        """Mark an alert as acknowledged."""
        execute_sql(
            "UPDATE epistemic_alerts SET acknowledged = 1 WHERE id = ?",
            (alert_id,),
        )
        log.info("Alert #%d acknowledged.", alert_id)
        return True

    def acknowledge_all(self, claim_id: int | None = None) -> int:
        """Acknowledge all unacknowledged alerts. Optionally filter by claim."""
        if claim_id is not None:
            execute_sql(
                "UPDATE epistemic_alerts SET acknowledged = 1 "
                "WHERE claim_id = ? AND acknowledged = 0",
                (claim_id,),
            )
        else:
            execute_sql(
                "UPDATE epistemic_alerts SET acknowledged = 1 WHERE acknowledged = 0"
            )
        # Return count of total unacknowledged (now 0 for the scope)
        return 0

    # ── Summary ──────────────────────────────────────────────────────────

    def get_summary(self) -> dict:
        """Get alert summary statistics."""
        rows = execute_sql(
            "SELECT severity, COUNT(*) as cnt FROM epistemic_alerts "
            "GROUP BY severity"
        )
        by_severity = {s: 0 for s in SEVERITY_LEVELS}
        for row in rows:
            by_severity[row["severity"]] = row["cnt"]

        rows2 = execute_sql(
            "SELECT alert_type, COUNT(*) as cnt FROM epistemic_alerts "
            "GROUP BY alert_type"
        )
        by_type = {}
        for row in rows2:
            by_type[row["alert_type"]] = row["cnt"]

        unack = execute_sql(
            "SELECT COUNT(*) as cnt FROM epistemic_alerts WHERE acknowledged = 0"
        )
        unacknowledged = unack[0]["cnt"] if unack else 0

        total = execute_sql("SELECT COUNT(*) as cnt FROM epistemic_alerts")
        total_count = total[0]["cnt"] if total else 0

        return {
            "total_alerts": total_count,
            "unacknowledged": unacknowledged,
            "by_severity": by_severity,
            "by_type": by_type,
        }

    # ── Helpers ──────────────────────────────────────────────────────────

    def _row_to_alert(self, row: dict) -> Alert:
        """Convert a database row to an Alert object."""
        return Alert(
            id=row.get("id", 0),
            claim_id=row.get("claim_id", 0),
            alert_type=row.get("alert_type", ""),
            severity=row.get("severity", "info"),
            title=row.get("title", ""),
            detail=row.get("detail", ""),
            metric_value=row.get("metric_value", 0.0),
            threshold=row.get("threshold", 0.0),
            acknowledged=bool(row.get("acknowledged", 0)),
            created_at=row.get("created_at", ""),
        )
