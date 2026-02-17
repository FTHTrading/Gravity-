"""
Lifecycle Report – Temporal Narrative Report Generator

Produces comprehensive lifecycle reports for claims combining all
temporal epistemic signals:

Sections:
  1. Claim Identity
  2. Confidence Trajectory
  3. Entropy Dynamics
  4. Drift Kinematics
  5. Stability Classification
  6. Active Alerts
  7. Phase Transitions
  8. Anomaly Timeline
  9. Epistemic Trajectory Score (0-100%)
  10. Lifecycle Recommendations
"""

import json
from datetime import datetime, timezone
from dataclasses import dataclass, field

from src.graph.claim_graph import ClaimGraph
from src.graph.confidence_timeline import ConfidenceTimeline, ConfidenceTrend
from src.graph.entropy_trend import EntropyTrendEngine, EntropyTrend
from src.graph.drift_kinematics import DriftKinematicsEngine, DriftKinematics
from src.graph.stability_classifier import StabilityClassifier, StabilityProfile
from src.graph.alert_engine import AlertEngine
from src.logger import get_logger

log = get_logger(__name__)


class LifecycleReport:
    """
    Generates temporal epistemic lifecycle reports.

    Combines signals from all Phase V engines into a narrative
    summary with trajectory scores and recommendations.
    """

    def __init__(self):
        self.graph = ClaimGraph()
        self.confidence_tl = ConfidenceTimeline()
        self.entropy_tl = EntropyTrendEngine()
        self.drift_engine = DriftKinematicsEngine()
        self.classifier = StabilityClassifier()
        self.alert_engine = AlertEngine()

    # ── Report Generation ────────────────────────────────────────────────

    def generate(self, claim_id: int | None = None) -> str:
        """
        Generate a lifecycle report.

        If claim_id is provided, generates for that claim.
        Otherwise generates a system-wide lifecycle summary.
        """
        if claim_id:
            return self._generate_claim_report(claim_id)
        return self._generate_system_report()

    def _generate_claim_report(self, claim_id: int) -> str:
        """Generate detailed lifecycle report for a single claim."""
        lines = []
        now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

        # Gather all data
        claim = self.graph.get_claim(claim_id)
        conf_trend = self.confidence_tl.analyze_trend(claim_id)
        ent_trend = self.entropy_tl.analyze_trend(claim_id)
        drift_kin = self.drift_engine.analyze(claim_id)
        stability = self.classifier.classify(claim_id)
        alerts = self.alert_engine.get_alerts(claim_id=claim_id, limit=20)

        # ── Header ───────────────────────────────────────────────────────
        lines.append("=" * 72)
        lines.append("  CLAIM LIFECYCLE REPORT")
        lines.append(f"  Generated: {now}")
        lines.append("=" * 72)
        lines.append("")

        # ── 1. Claim Identity ────────────────────────────────────────────
        lines.append("─" * 72)
        lines.append("  1. CLAIM IDENTITY")
        lines.append("─" * 72)
        if claim:
            lines.append(f"  ID:            #{claim_id}")
            lines.append(f"  Text:          {claim.claim_text[:80]}")
            lines.append(f"  Type:          {claim.claim_type}")
            lines.append(f"  Verification:  {claim.verification}")
            lines.append(f"  Confidence:    {claim.confidence:.4f}")
            lines.append(f"  Created:       {claim.created_at}")
        else:
            lines.append(f"  Claim #{claim_id} not found.")
        lines.append("")

        # ── 2. Confidence Trajectory ─────────────────────────────────────
        lines.append("─" * 72)
        lines.append("  2. CONFIDENCE TRAJECTORY")
        lines.append("─" * 72)
        lines.append(f"  Current score:    {conf_trend.current_score:.4f}")
        lines.append(f"  Mean:             {conf_trend.mean_score:.4f}")
        lines.append(f"  Std deviation:    {conf_trend.std_dev:.4f}")
        lines.append(f"  Range:            [{conf_trend.min_score:.4f}, {conf_trend.max_score:.4f}]")
        lines.append(f"  Moving avg (5):   {conf_trend.moving_avg:.4f}")
        lines.append(f"  EMA:              {conf_trend.ema:.4f}")
        lines.append(f"  Rate of change:   {conf_trend.rate_of_change:.6f} /hr")
        lines.append(f"  Direction:        {conf_trend.trend_direction}")
        lines.append(f"  Converging:       {'Yes' if conf_trend.is_converging else 'No'}")
        lines.append(f"  Plateau:          {'Yes' if conf_trend.is_plateau else 'No'}")
        if conf_trend.is_plateau:
            lines.append(f"  Plateau duration: {conf_trend.plateau_duration_hours:.2f} hours")
        lines.append(f"  Snapshots:        {conf_trend.total_snapshots}")
        lines.append("")

        # ── 3. Entropy Dynamics ──────────────────────────────────────────
        lines.append("─" * 72)
        lines.append("  3. ENTROPY DYNAMICS")
        lines.append("─" * 72)
        lines.append(f"  Current H:        {ent_trend.current_entropy:.4f}")
        lines.append(f"  Mean H:           {ent_trend.mean_entropy:.4f}")
        lines.append(f"  Std deviation:    {ent_trend.std_dev:.4f}")
        lines.append(f"  dH/dt:            {ent_trend.dh_dt:.6f} /hr")
        lines.append(f"  d²H/dt²:          {ent_trend.d2h_dt2:.6f} /hr²")
        lines.append(f"  Trend:            {ent_trend.trend_direction}")
        if ent_trend.is_spike:
            lines.append(f"  ⚠ SPIKE:          magnitude={ent_trend.spike_magnitude:.2f}")
        if ent_trend.is_collapse:
            lines.append(f"  ⚠ COLLAPSE:       magnitude={ent_trend.spike_magnitude:.2f}")
        lines.append(f"  Snapshots:        {ent_trend.total_snapshots}")
        lines.append("")

        # ── 4. Drift Kinematics ──────────────────────────────────────────
        lines.append("─" * 72)
        lines.append("  4. DRIFT KINEMATICS")
        lines.append("─" * 72)
        lines.append(f"  Current drift:    {drift_kin.current_drift:.6f}")
        lines.append(f"  Velocity (dd/dt): {drift_kin.current_velocity:.6f}")
        lines.append(f"  Acceleration:     {drift_kin.current_acceleration:.6f}")
        lines.append(f"  Jerk:             {drift_kin.current_jerk:.6f}")
        lines.append(f"  Mean velocity:    {drift_kin.mean_velocity:.6f}")
        lines.append(f"  Max velocity:     {drift_kin.max_velocity:.6f}")
        lines.append(f"  Phase:            {drift_kin.phase}")
        lines.append(f"  Inflections:      {len(drift_kin.inflection_points)}")
        if drift_kin.inflection_points:
            for i, ip in enumerate(drift_kin.inflection_points[-3:], 1):
                lines.append(f"    #{i}: at {ip['timestamp'][:19]}  "
                             f"accel {ip['from_acceleration']:.6f} → {ip['to_acceleration']:.6f}")
        lines.append("")

        # ── 5. Stability Classification ──────────────────────────────────
        lines.append("─" * 72)
        lines.append("  5. STABILITY CLASSIFICATION")
        lines.append("─" * 72)
        lines.append(f"  State:            {stability.classification.upper()}")
        lines.append(f"  Signal flags:     {len(stability.signal_flags)}")
        for flag in stability.signal_flags:
            lines.append(f"    • {flag}")
        lines.append("")

        # ── 6. Active Alerts ─────────────────────────────────────────────
        lines.append("─" * 72)
        lines.append("  6. ACTIVE ALERTS")
        lines.append("─" * 72)
        if alerts:
            for alert in alerts:
                ack = "✓" if alert.acknowledged else "○"
                lines.append(f"  [{ack}] [{alert.severity.upper():8s}] {alert.title}")
                if alert.detail:
                    lines.append(f"      {alert.detail[:70]}")
        else:
            lines.append("  No alerts.")
        lines.append("")

        # ── 7. Phase Transitions ─────────────────────────────────────────
        lines.append("─" * 72)
        lines.append("  7. PHASE TRANSITIONS")
        lines.append("─" * 72)
        class_history = self.classifier.get_history(claim_id, limit=10)
        if class_history:
            prev_state = None
            for row in reversed(class_history):
                state = row["classification"]
                if state != prev_state:
                    lines.append(f"    {row['classified_at'][:19]}  → {state.upper()}")
                    prev_state = state
        else:
            lines.append("  No classification history.")
        lines.append("")

        # ── 8. Anomaly Timeline ──────────────────────────────────────────
        lines.append("─" * 72)
        lines.append("  8. ANOMALY TIMELINE")
        lines.append("─" * 72)
        anomaly_alerts = [a for a in alerts if a.severity in ("warning", "critical")]
        if anomaly_alerts:
            for alert in anomaly_alerts:
                lines.append(f"    {alert.created_at[:19]}  [{alert.severity.upper()}] {alert.alert_type}")
        else:
            lines.append("  No anomalies detected.")
        lines.append("")

        # ── 9. Epistemic Trajectory Score ────────────────────────────────
        lines.append("─" * 72)
        lines.append("  9. EPISTEMIC TRAJECTORY SCORE")
        lines.append("─" * 72)
        trajectory = self._compute_trajectory_score(conf_trend, ent_trend, drift_kin, stability)
        lines.append(f"  Score:  {trajectory['score']:.1f}%")
        lines.append(f"  Grade:  {trajectory['grade']}")
        for component, value in trajectory["components"].items():
            lines.append(f"    {component:25s} {value:.4f}")
        lines.append("")

        # ── 10. Recommendations ──────────────────────────────────────────
        lines.append("─" * 72)
        lines.append("  10. LIFECYCLE RECOMMENDATIONS")
        lines.append("─" * 72)
        recs = self._generate_recommendations(stability, conf_trend, ent_trend, drift_kin, alerts)
        for i, rec in enumerate(recs, 1):
            lines.append(f"  {i}. {rec}")
        lines.append("")
        lines.append("=" * 72)

        return "\n".join(lines)

    def _generate_system_report(self) -> str:
        """Generate system-wide lifecycle summary."""
        lines = []
        now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

        claims = self.graph.get_all_claims()

        lines.append("=" * 72)
        lines.append("  SYSTEM LIFECYCLE REPORT")
        lines.append(f"  Generated: {now}")
        lines.append(f"  Total claims: {len(claims)}")
        lines.append("=" * 72)
        lines.append("")

        # Classify all claims
        profiles = []
        for claim in claims:
            profile = self.classifier.classify(claim.id)
            profiles.append(profile)

        # State distribution
        lines.append("─" * 72)
        lines.append("  STABILITY DISTRIBUTION")
        lines.append("─" * 72)
        state_counts = {}
        for p in profiles:
            state_counts[p.classification] = state_counts.get(p.classification, 0) + 1
        for state in ("stable", "converging", "volatile", "diverging", "critical"):
            count = state_counts.get(state, 0)
            bar = "█" * count
            lines.append(f"  {state:12s}  {count:3d}  {bar}")
        lines.append("")

        # Alert summary
        alert_summary = self.alert_engine.get_summary()
        lines.append("─" * 72)
        lines.append("  ALERT SUMMARY")
        lines.append("─" * 72)
        lines.append(f"  Total:          {alert_summary['total_alerts']}")
        lines.append(f"  Unacknowledged: {alert_summary['unacknowledged']}")
        for sev, cnt in alert_summary["by_severity"].items():
            lines.append(f"    {sev:10s}  {cnt}")
        lines.append("")

        # Top concerns
        lines.append("─" * 72)
        lines.append("  TOP CONCERNS")
        lines.append("─" * 72)
        critical = [p for p in profiles if p.classification == "critical"]
        diverging = [p for p in profiles if p.classification == "diverging"]
        volatile = [p for p in profiles if p.classification == "volatile"]

        if critical:
            for p in critical[:5]:
                claim = self.graph.get_claim(p.claim_id)
                text = claim.claim_text[:50] if claim else "?"
                lines.append(f"  ⚠ CRITICAL  #{p.claim_id}: {text}")
        if diverging:
            for p in diverging[:5]:
                claim = self.graph.get_claim(p.claim_id)
                text = claim.claim_text[:50] if claim else "?"
                lines.append(f"  △ DIVERGING #{p.claim_id}: {text}")
        if volatile:
            for p in volatile[:5]:
                claim = self.graph.get_claim(p.claim_id)
                text = claim.claim_text[:50] if claim else "?"
                lines.append(f"  ~ VOLATILE  #{p.claim_id}: {text}")
        if not (critical or diverging or volatile):
            lines.append("  No concerns. All claims stable or converging.")
        lines.append("")

        # System trajectory
        lines.append("─" * 72)
        lines.append("  SYSTEM TRAJECTORY")
        lines.append("─" * 72)
        stable_pct = (state_counts.get("stable", 0) + state_counts.get("converging", 0)) / max(len(profiles), 1) * 100
        lines.append(f"  System health:  {stable_pct:.1f}% stable/converging")
        lines.append(f"  At risk:        {len(critical) + len(diverging)} claims")
        lines.append("")
        lines.append("=" * 72)

        return "\n".join(lines)

    # ── Trajectory Score ─────────────────────────────────────────────────

    def _compute_trajectory_score(self, conf: ConfidenceTrend,
                                  ent: EntropyTrend,
                                  drift: DriftKinematics,
                                  stability: StabilityProfile) -> dict:
        """
        Compute an epistemic trajectory score (0-100%).

        Components:
          - Confidence stability (low std_dev = good)      weight: 0.30
          - Entropy stability (low dH/dt = good)           weight: 0.25
          - Drift stability (low acceleration = good)      weight: 0.20
          - Classification bonus (stable/converging bonus) weight: 0.15
          - Alert penalty (fewer alerts = better)           weight: 0.10
        """
        # Confidence stability: 1 - min(std_dev/0.5, 1)
        conf_stability = max(0, 1 - min(conf.std_dev / 0.5, 1.0))

        # Entropy stability: 1 - min(|dH/dt|/1.0, 1)
        ent_stability = max(0, 1 - min(abs(ent.dh_dt) / 1.0, 1.0))

        # Drift stability: 1 - min(|accel|/0.01, 1)
        drift_stability = max(0, 1 - min(abs(drift.current_acceleration) / 0.01, 1.0))

        # Classification bonus
        class_bonus = {
            "stable": 1.0,
            "converging": 0.8,
            "volatile": 0.4,
            "diverging": 0.2,
            "critical": 0.0,
        }.get(stability.classification, 0.5)

        # Alert penalty: fewer anomaly flags = better
        alert_score = max(0, 1 - len(stability.signal_flags) / 6.0)

        # Weighted composite
        weights = {
            "confidence_stability": 0.30,
            "entropy_stability": 0.25,
            "drift_stability": 0.20,
            "classification_bonus": 0.15,
            "alert_score": 0.10,
        }
        components = {
            "confidence_stability": conf_stability,
            "entropy_stability": ent_stability,
            "drift_stability": drift_stability,
            "classification_bonus": class_bonus,
            "alert_score": alert_score,
        }

        score = sum(components[k] * weights[k] for k in components) * 100

        # Grade
        if score >= 90:
            grade = "A"
        elif score >= 75:
            grade = "B"
        elif score >= 60:
            grade = "C"
        elif score >= 40:
            grade = "D"
        else:
            grade = "F"

        return {
            "score": score,
            "grade": grade,
            "components": components,
        }

    # ── Recommendations ──────────────────────────────────────────────────

    def _generate_recommendations(self, stability: StabilityProfile,
                                  conf: ConfidenceTrend,
                                  ent: EntropyTrend,
                                  drift: DriftKinematics,
                                  alerts: list) -> list[str]:
        """Generate actionable recommendations based on lifecycle analysis."""
        recs = []

        # State-based recommendations
        if stability.classification == "critical":
            recs.append("URGENT: Claim is in critical state. Investigate immediately.")
            recs.append("Review mutation chain for signs of coordinated manipulation.")

        elif stability.classification == "diverging":
            recs.append("Claim is diverging. Monitor drift acceleration closely.")
            recs.append("Check for new contradictions or source credibility changes.")

        elif stability.classification == "volatile":
            recs.append("Claim shows volatility. Wait for stabilization before anchoring.")

        elif stability.classification == "converging":
            recs.append("Claim is converging. Good candidate for anchoring when plateau is reached.")

        elif stability.classification == "stable":
            recs.append("Claim is stable. Suitable for cryptographic anchoring.")

        # Signal-specific recommendations
        if "entropy_spike" in stability.signal_flags:
            recs.append("Entropy spike detected. Review recent mutations for semantic integrity.")

        if "confidence_falling" in stability.signal_flags:
            recs.append("Confidence declining. Check for new contradicting evidence.")

        if "drift_accelerating" in stability.signal_flags:
            recs.append("Drift is accelerating. Narrative divergence may be underway.")

        # Insufficient data
        if conf.total_snapshots < 3:
            recs.append("Insufficient confidence history. Take more snapshots for reliable trends.")

        if ent.total_snapshots < 3:
            recs.append("Insufficient entropy history. Take more snapshots for trend analysis.")

        # Alert-based
        critical_alerts = [a for a in alerts if a.severity == "critical" and not a.acknowledged]
        if critical_alerts:
            recs.append(f"Acknowledge {len(critical_alerts)} critical alert(s) pending review.")

        return recs if recs else ["No specific recommendations. Continue monitoring."]

    # ── Quick Summary ────────────────────────────────────────────────────

    def quick_lifecycle(self, claim_id: int) -> str:
        """One-line lifecycle summary for a claim."""
        stability = self.classifier.classify(claim_id)
        conf = self.confidence_tl.analyze_trend(claim_id)
        ent = self.entropy_tl.analyze_trend(claim_id)
        drift = self.drift_engine.analyze(claim_id)

        trajectory = self._compute_trajectory_score(conf, ent, drift, stability)

        return (
            f"Claim #{claim_id}: "
            f"state={stability.classification.upper()} "
            f"trajectory={trajectory['score']:.0f}% ({trajectory['grade']}) "
            f"conf={conf.current_score:.3f}({conf.trend_direction}) "
            f"H={ent.current_entropy:.3f}(dH/dt={ent.dh_dt:.4f}) "
            f"drift_phase={drift.phase} "
            f"flags={len(stability.signal_flags)}"
        )

    # ── JSON Export ──────────────────────────────────────────────────────

    def to_json(self, claim_id: int) -> dict:
        """Export full lifecycle data as JSON-serializable dict."""
        conf_trend = self.confidence_tl.analyze_trend(claim_id)
        ent_trend = self.entropy_tl.analyze_trend(claim_id)
        drift_kin = self.drift_engine.analyze(claim_id)
        stability = self.classifier.classify(claim_id)
        alerts = self.alert_engine.get_alerts(claim_id=claim_id, limit=50)
        trajectory = self._compute_trajectory_score(conf_trend, ent_trend, drift_kin, stability)

        return {
            "claim_id": claim_id,
            "confidence": conf_trend.to_dict(),
            "entropy": ent_trend.to_dict(),
            "drift": drift_kin.to_dict(),
            "stability": stability.to_dict(),
            "trajectory": trajectory,
            "alerts": [a.to_dict() for a in alerts],
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }
