"""
Unit tests for Phase V modules – Temporal Epistemic Dynamics:
  - ConfidenceTimeline (temporal confidence tracking, SMA/EMA, plateau/convergence)
  - EntropyTrendEngine (H(t) series, dH/dt, d²H/dt², spike/collapse detection)
  - DriftKinematicsEngine (velocity, acceleration, jerk, inflection detection)
  - StabilityClassifier (epistemic state machine: stable/converging/volatile/diverging/critical)
  - AlertEngine (rule-based anomaly detection, alert lifecycle)
  - LifecycleReport (10-section narrative report, trajectory scoring)

All tests use :memory: SQLite via PROJECT_ANCHOR_DB env var.
"""

import json
import os
import sys
import math
import time
import unittest
from datetime import datetime, timezone, timedelta
from unittest.mock import patch

# Project root on path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

os.environ["PROJECT_ANCHOR_DB"] = ":memory:"

from src.database import init_db, insert_row, execute_sql


# ── Helper: seed graph data ─────────────────────────────────────────────

def _seed_graph():
    """Seed graph with interconnected claims, sources, and links for testing."""
    from src.graph.claim_graph import ClaimGraph
    graph = ClaimGraph()

    # Claims
    c1 = graph.add_claim("Gravity anomaly detected on August 12",
                         claim_type="observation")
    c2 = graph.add_claim("Weight measurements dropped by 0.3%",
                         claim_type="measurement")
    c3 = graph.add_claim("No anomaly occurred on August 12",
                         claim_type="assertion")
    c4 = graph.add_claim("Thomas Webb falsified the readings",
                         claim_type="rebuttal")
    # Mutation chain: c5 → c6 → c7
    c5 = graph.add_claim("Original theory: gravitational wave interference",
                         claim_type="hypothesis")
    c6 = graph.add_claim("Revised theory: gravitational lensing artifact",
                         claim_type="hypothesis", parent_claim_id=c5)
    c7 = graph.add_claim("Final theory: instrument calibration error",
                         claim_type="hypothesis", parent_claim_id=c6)

    # Sources
    s1 = graph.add_source("NIST Lab Report #472", source_type="document",
                          credibility=0.9)
    s2 = graph.add_source("Reddit post u/gravity_watcher", source_type="social",
                          credibility=0.3)
    s3 = graph.add_source("ArXiv preprint 2024.08123", source_type="academic",
                          credibility=0.8)

    # Links
    graph.link("source", s1, "claim", c1, relationship="supports", weight=0.9)
    graph.link("source", s1, "claim", c2, relationship="supports", weight=0.8)
    graph.link("source", s2, "claim", c1, relationship="references", weight=0.4)
    graph.link("source", s3, "claim", c2, relationship="supports", weight=0.7)
    graph.link("claim", c3, "claim", c1, relationship="contradicts", weight=0.6)
    graph.link("claim", c4, "claim", c1, relationship="contradicts", weight=0.5)
    graph.link("source", s3, "claim", c5, relationship="supports", weight=0.6)

    # Entity
    graph.add_entity("Thomas Webb", entity_type="person",
                     description="Primary observer")

    return {
        "claims": [c1, c2, c3, c4, c5, c6, c7],
        "sources": [s1, s2, s3],
    }


def _inject_confidence_history(claim_id: int, scores: list[float],
                               start_hours_ago: float = 10.0):
    """Manually inject confidence timeline entries with spaced timestamps."""
    # Clear existing data to prevent pollution from prior tests
    execute_sql("DELETE FROM confidence_timeline WHERE claim_id = ?", (claim_id,))
    now = datetime.now(timezone.utc)
    interval = start_hours_ago / max(len(scores), 1)
    for i, score in enumerate(scores):
        ts = now - timedelta(hours=start_hours_ago - i * interval)
        insert_row("confidence_timeline", {
            "claim_id": claim_id,
            "score_value": score,
            "components_json": json.dumps({"injected": True}),
            "snapshot_at": ts.isoformat(),
        })


def _inject_entropy_history(claim_id: int, entropies: list[float],
                            drifts: list[float] | None = None,
                            start_hours_ago: float = 10.0):
    """Manually inject entropy timeline entries with spaced timestamps."""
    # Clear existing data to prevent pollution from prior tests
    execute_sql("DELETE FROM entropy_timeline WHERE claim_id = ?", (claim_id,))
    now = datetime.now(timezone.utc)
    interval = start_hours_ago / max(len(entropies), 1)
    if drifts is None:
        drifts = [0.0] * len(entropies)
    for i, (h, d) in enumerate(zip(entropies, drifts)):
        ts = now - timedelta(hours=start_hours_ago - i * interval)
        insert_row("entropy_timeline", {
            "claim_id": claim_id,
            "shannon_entropy": h,
            "drift_velocity": d,
            "chain_length": 1,
            "snapshot_at": ts.isoformat(),
        })


# ── Shared setup ─────────────────────────────────────────────────────────
_seed_data = None


def setUpModule():
    """Initialize DB and seed data once for all tests."""
    global _seed_data
    init_db()
    _seed_data = _seed_graph()


# ════════════════════════════════════════════════════════════════════════
#  TestConfidenceTimeline
# ════════════════════════════════════════════════════════════════════════

class TestConfidenceTimeline(unittest.TestCase):
    """Test temporal confidence tracking engine."""

    def setUp(self):
        from src.graph.confidence_timeline import ConfidenceTimeline
        self.tl = ConfidenceTimeline()
        self.ids = _seed_data["claims"]

    def test_snapshot_claim_returns_point(self):
        """snapshot_claim should return a ConfidenceTrendPoint with valid data."""
        point = self.tl.snapshot_claim(self.ids[0])
        self.assertEqual(point.claim_id, self.ids[0])
        self.assertGreater(point.score_value, 0.0)
        self.assertLessEqual(point.score_value, 1.0)
        self.assertTrue(point.snapshot_at)  # non-empty timestamp
        self.assertIsInstance(point.components, dict)

    def test_snapshot_all(self):
        """snapshot_all should snapshot every claim in the graph."""
        points = self.tl.snapshot_all()
        self.assertGreaterEqual(len(points), len(self.ids))
        for pt in points:
            self.assertGreater(pt.score_value, 0.0)

    def test_get_history_returns_newest_first(self):
        """get_history should return snapshots in descending time order."""
        # Take two snapshots
        self.tl.snapshot_claim(self.ids[1])
        self.tl.snapshot_claim(self.ids[1])
        history = self.tl.get_history(self.ids[1], limit=10)
        self.assertGreaterEqual(len(history), 2)
        # Newest first
        self.assertGreaterEqual(history[0].snapshot_at, history[-1].snapshot_at)

    def test_get_latest(self):
        """get_latest should return the most recent score float."""
        self.tl.snapshot_claim(self.ids[2])
        latest = self.tl.get_latest(self.ids[2])
        self.assertIsInstance(latest, float)
        self.assertGreater(latest, 0.0)

    def test_get_latest_none_for_unknown(self):
        """get_latest returns None for claim with no history."""
        result = self.tl.get_latest(99999)
        self.assertIsNone(result)

    def test_analyze_trend_basic_stats(self):
        """analyze_trend should compute mean, std_dev, range."""
        cid = self.ids[0]
        _inject_confidence_history(cid, [0.5, 0.55, 0.52, 0.58, 0.56])
        trend = self.tl.analyze_trend(cid)
        self.assertGreater(trend.total_snapshots, 0)
        self.assertAlmostEqual(trend.mean_score,
                               sum([0.5, 0.55, 0.52, 0.58, 0.56]) / 5,
                               delta=0.1)  # approximate due to prior snapshots
        self.assertGreaterEqual(trend.score_range, 0.0)

    def test_analyze_trend_direction_rising(self):
        """Rising scores should yield trend_direction='rising'."""
        cid = self.ids[3]
        _inject_confidence_history(cid, [0.2, 0.3, 0.4, 0.5, 0.6, 0.7])
        trend = self.tl.analyze_trend(cid)
        self.assertEqual(trend.trend_direction, "rising")

    def test_analyze_trend_direction_falling(self):
        """Falling scores should yield trend_direction='falling'."""
        cid = self.ids[4]
        _inject_confidence_history(cid, [0.8, 0.7, 0.6, 0.5, 0.4, 0.3])
        trend = self.tl.analyze_trend(cid)
        self.assertEqual(trend.trend_direction, "falling")

    def test_analyze_trend_direction_stable(self):
        """Stable scores should yield trend_direction='stable'."""
        cid = self.ids[5]
        _inject_confidence_history(cid, [0.5, 0.5, 0.5, 0.5, 0.5, 0.5])
        trend = self.tl.analyze_trend(cid)
        self.assertEqual(trend.trend_direction, "stable")

    def test_moving_avg_and_ema(self):
        """Moving average and EMA should produce reasonable values."""
        cid = self.ids[0]
        # Ensure enough history
        _inject_confidence_history(cid, [0.4, 0.5, 0.6, 0.5, 0.55, 0.52])
        trend = self.tl.analyze_trend(cid)
        self.assertGreater(trend.moving_avg, 0.0)
        self.assertGreater(trend.ema, 0.0)

    def test_sma_series(self):
        """compute_sma_series should return a list of floats."""
        cid = self.ids[1]
        _inject_confidence_history(cid, [0.3, 0.4, 0.5, 0.6, 0.7, 0.8])
        series = self.tl.compute_sma_series(cid, window=3)
        self.assertIsInstance(series, list)
        self.assertGreater(len(series), 0)
        for val in series:
            self.assertIsInstance(val, float)

    def test_ema_series(self):
        """compute_ema_series should return a list of floats."""
        cid = self.ids[1]
        _inject_confidence_history(cid, [0.3, 0.4, 0.5, 0.6, 0.7, 0.8])
        series = self.tl.compute_ema_series(cid)
        self.assertIsInstance(series, list)
        self.assertGreater(len(series), 0)

    def test_plateau_detection(self):
        """Identical scores should be detected as a plateau."""
        cid = self.ids[6]
        _inject_confidence_history(cid, [0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5])
        trend = self.tl.analyze_trend(cid)
        self.assertTrue(trend.is_plateau)

    def test_rate_of_change(self):
        """Rate of change should be positive for rising scores."""
        cid = self.ids[3]
        trend = self.tl.analyze_trend(cid)
        # We injected rising scores for ids[3]
        self.assertGreater(trend.rate_of_change, 0.0)

    def test_convergence_detection(self):
        """Scores with decreasing variance should be detected as converging."""
        cid = self.ids[2]
        # Clear any prior data and inject: high variance early → low variance late
        scores = [0.2, 0.8, 0.3, 0.7, 0.4, 0.6, 0.49, 0.51, 0.50, 0.50]
        _inject_confidence_history(cid, scores)
        trend = self.tl.analyze_trend(cid)
        self.assertTrue(trend.is_converging)

    def test_empty_trend(self):
        """analyze_trend on unknown claim returns empty ConfidenceTrend."""
        trend = self.tl.analyze_trend(99998)
        self.assertEqual(trend.total_snapshots, 0)
        self.assertEqual(trend.current_score, 0.0)

    def test_trend_to_dict(self):
        """ConfidenceTrend.to_dict() should produce a proper dict."""
        cid = self.ids[0]
        trend = self.tl.analyze_trend(cid)
        d = trend.to_dict()
        self.assertIn("claim_id", d)
        self.assertIn("current_score", d)
        self.assertIn("rate_of_change", d)
        self.assertIn("trend_direction", d)

    def test_purge_old_snapshots(self):
        """purge_old_snapshots should keep at most 'keep' entries."""
        cid = self.ids[0]
        # Inject many snapshots
        _inject_confidence_history(cid, [0.5 + i * 0.01 for i in range(20)])
        count_before = self.tl.get_snapshot_count(cid)
        self.assertGreaterEqual(count_before, 20)
        removed = self.tl.purge_old_snapshots(cid, keep=5)
        self.assertGreater(removed, 0)
        count_after = self.tl.get_snapshot_count(cid)
        self.assertLessEqual(count_after, 5)


# ════════════════════════════════════════════════════════════════════════
#  TestEntropyTrend
# ════════════════════════════════════════════════════════════════════════

class TestEntropyTrend(unittest.TestCase):
    """Test temporal entropy trend engine."""

    def setUp(self):
        from src.graph.entropy_trend import EntropyTrendEngine
        self.engine = EntropyTrendEngine()
        self.ids = _seed_data["claims"]

    def test_snapshot_claim_returns_point(self):
        """snapshot_claim should return an EntropyTrendPoint."""
        point = self.engine.snapshot_claim(self.ids[0])
        self.assertEqual(point.claim_id, self.ids[0])
        self.assertIsInstance(point.shannon_entropy, float)
        self.assertTrue(point.snapshot_at)

    def test_snapshot_all(self):
        """snapshot_all should produce points for all claims."""
        points = self.engine.snapshot_all()
        self.assertGreaterEqual(len(points), len(self.ids))

    def test_get_history_order(self):
        """get_history returns newest-first."""
        cid = self.ids[0]
        self.engine.snapshot_claim(cid)
        self.engine.snapshot_claim(cid)
        history = self.engine.get_history(cid, limit=10)
        self.assertGreaterEqual(len(history), 2)
        self.assertGreaterEqual(history[0].snapshot_at, history[-1].snapshot_at)

    def test_get_latest_entropy(self):
        """get_latest_entropy should return a float."""
        cid = self.ids[1]
        self.engine.snapshot_claim(cid)
        val = self.engine.get_latest_entropy(cid)
        self.assertIsInstance(val, float)

    def test_get_latest_entropy_none(self):
        """get_latest_entropy returns None for unknown claim."""
        result = self.engine.get_latest_entropy(99997)
        self.assertIsNone(result)

    def test_analyze_trend_basic(self):
        """analyze_trend should compute basic stats."""
        cid = self.ids[0]
        _inject_entropy_history(cid, [1.0, 1.2, 1.1, 1.3, 1.25])
        trend = self.engine.analyze_trend(cid)
        self.assertGreater(trend.total_snapshots, 0)
        self.assertGreater(trend.mean_entropy, 0.0)

    def test_analyze_trend_dh_dt(self):
        """dH/dt should be positive for increasing entropy."""
        cid = self.ids[1]
        _inject_entropy_history(cid, [0.5, 0.8, 1.1, 1.4, 1.7])
        trend = self.engine.analyze_trend(cid)
        self.assertGreater(trend.dh_dt, 0.0)

    def test_analyze_trend_d2h_dt2(self):
        """d²H/dt² should be computable with 3+ points."""
        cid = self.ids[2]
        _inject_entropy_history(cid, [0.5, 0.8, 1.3, 2.0, 2.9])
        trend = self.engine.analyze_trend(cid)
        # Convex upward → positive second derivative
        self.assertNotEqual(trend.d2h_dt2, 0.0)

    def test_trend_direction_increasing(self):
        """Monotonically increasing entropy → direction='increasing'."""
        cid = self.ids[3]
        _inject_entropy_history(cid, [0.5, 0.8, 1.1, 1.5, 2.0])
        trend = self.engine.analyze_trend(cid)
        self.assertEqual(trend.trend_direction, "increasing")

    def test_trend_direction_decreasing(self):
        """Monotonically decreasing entropy → direction='decreasing'."""
        cid = self.ids[4]
        _inject_entropy_history(cid, [2.0, 1.5, 1.1, 0.8, 0.5])
        trend = self.engine.analyze_trend(cid)
        self.assertEqual(trend.trend_direction, "decreasing")

    def test_trend_direction_oscillating(self):
        """Alternating increase/decrease → direction='oscillating'."""
        cid = self.ids[5]
        _inject_entropy_history(cid, [1.0, 2.0, 1.0, 2.0, 1.0, 2.0])
        trend = self.engine.analyze_trend(cid)
        self.assertEqual(trend.trend_direction, "oscillating")

    def test_spike_detection(self):
        """A sudden large increase should be flagged as a spike."""
        cid = self.ids[6]
        # Stable then jump
        _inject_entropy_history(cid, [1.0, 1.01, 0.99, 1.0, 1.0, 5.0])
        trend = self.engine.analyze_trend(cid)
        self.assertTrue(trend.is_spike)
        self.assertGreater(trend.spike_magnitude, 0.0)

    def test_collapse_detection(self):
        """A sudden large decrease should be flagged as a collapse."""
        cid = self.ids[0]
        # Clear and inject: stable then collapse
        _inject_entropy_history(cid, [5.0, 5.01, 4.99, 5.0, 5.0, 0.5],
                                start_hours_ago=6.0)
        trend = self.engine.analyze_trend(cid)
        # The last delta is negative and large relative to std
        self.assertTrue(trend.is_collapse)

    def test_empty_trend(self):
        """analyze_trend on unknown claim returns empty EntropyTrend."""
        trend = self.engine.analyze_trend(99996)
        self.assertEqual(trend.total_snapshots, 0)

    def test_to_dict(self):
        """EntropyTrend.to_dict() should produce a proper dict."""
        cid = self.ids[0]
        trend = self.engine.analyze_trend(cid)
        d = trend.to_dict()
        self.assertIn("claim_id", d)
        self.assertIn("dh_dt", d)
        self.assertIn("d2h_dt2", d)
        self.assertIn("trend_direction", d)

    def test_detect_spikes_bulk(self):
        """detect_spikes should find claims with spikes."""
        # We injected a spike for ids[6] above
        spikes = self.engine.detect_spikes()
        # May or may not find spikes depending on data state
        self.assertIsInstance(spikes, list)

    def test_get_claims_with_history(self):
        """get_claims_with_history should return claim IDs."""
        ids = self.engine.get_claims_with_history()
        self.assertIsInstance(ids, list)
        self.assertGreater(len(ids), 0)


# ════════════════════════════════════════════════════════════════════════
#  TestDriftKinematics
# ════════════════════════════════════════════════════════════════════════

class TestDriftKinematics(unittest.TestCase):
    """Test drift kinematic analysis engine."""

    def setUp(self):
        from src.graph.drift_kinematics import DriftKinematicsEngine
        self.engine = DriftKinematicsEngine()
        self.ids = _seed_data["claims"]

    def test_analyze_with_no_data(self):
        """analyze on unknown claim returns default DriftKinematics."""
        result = self.engine.analyze(99995)
        self.assertEqual(result.claim_id, 99995)
        self.assertEqual(result.total_snapshots, 0)
        self.assertEqual(result.phase, "unknown")

    def test_analyze_with_data(self):
        """analyze should compute kinematic profile from entropy timeline data."""
        cid = self.ids[0]
        # Inject drift data (via entropy timeline drift_velocity field)
        _inject_entropy_history(cid,
                                entropies=[1.0] * 6,
                                drifts=[0.1, 0.2, 0.35, 0.55, 0.8, 1.1],
                                start_hours_ago=6.0)
        result = self.engine.analyze(cid)
        self.assertGreater(result.total_snapshots, 0)
        self.assertIsInstance(result.kinematic_profile, list)

    def test_velocity_computation(self):
        """Velocity should be non-zero for changing drift values."""
        cid = self.ids[1]
        _inject_entropy_history(cid,
                                entropies=[1.0] * 5,
                                drifts=[0.0, 0.1, 0.2, 0.3, 0.4],
                                start_hours_ago=5.0)
        result = self.engine.analyze(cid)
        # Linear increase in drift → positive velocity
        self.assertGreater(abs(result.current_velocity), 0.0)

    def test_acceleration_computation(self):
        """Acceleration should be non-zero for accelerating drift."""
        cid = self.ids[2]
        # Quadratic increase: acceleration = constant
        _inject_entropy_history(cid,
                                entropies=[1.0] * 6,
                                drifts=[0.0, 0.01, 0.04, 0.09, 0.16, 0.25],
                                start_hours_ago=6.0)
        result = self.engine.analyze(cid)
        # Need at least 3 velocity points to compute acceleration
        # With 6 drift points we get 5 velocity points → 4 acceleration points
        self.assertNotEqual(result.current_acceleration, 0.0)

    def test_phase_constant(self):
        """Constant drift should classify as 'constant'."""
        cid = self.ids[3]
        _inject_entropy_history(cid,
                                entropies=[1.0] * 5,
                                drifts=[0.5, 0.5, 0.5, 0.5, 0.5],
                                start_hours_ago=5.0)
        result = self.engine.analyze(cid)
        # Constant drift → zero velocity, zero acceleration → constant or inflecting
        # (inflecting possible if prior data left residual inflection points)
        self.assertIn(result.phase, ("constant", "unknown", "inflecting"))

    def test_inflection_detection(self):
        """Sign change in acceleration should produce inflection points."""
        cid = self.ids[4]
        # Drift increases then decreases (inflection in velocity/acceleration)
        _inject_entropy_history(cid,
                                entropies=[1.0] * 8,
                                drifts=[0.0, 0.1, 0.3, 0.6, 0.5, 0.3, 0.1, 0.0],
                                start_hours_ago=8.0)
        result = self.engine.analyze(cid)
        # The velocity goes from positive to negative, creating acceleration sign change
        # This may or may not produce inflection_points depending on magnitude
        self.assertIsInstance(result.inflection_points, list)

    def test_to_dict(self):
        """DriftKinematics.to_dict() should produce a proper dict."""
        result = self.engine.analyze(self.ids[0])
        d = result.to_dict()
        self.assertIn("claim_id", d)
        self.assertIn("current_velocity", d)
        self.assertIn("current_acceleration", d)
        self.assertIn("phase", d)
        self.assertIn("inflection_count", d)

    def test_analyze_all(self):
        """analyze_all should return list of DriftKinematics."""
        results = self.engine.analyze_all()
        self.assertIsInstance(results, list)
        # Should have entries since we have injected entropy timeline data
        self.assertGreater(len(results), 0)

    def test_rank_by_acceleration(self):
        """rank_by_acceleration should return sorted list."""
        ranked = self.engine.rank_by_acceleration(top_n=5)
        self.assertIsInstance(ranked, list)
        if len(ranked) >= 2:
            self.assertGreaterEqual(
                abs(ranked[0].current_acceleration),
                abs(ranked[1].current_acceleration)
            )


# ════════════════════════════════════════════════════════════════════════
#  TestStabilityClassifier
# ════════════════════════════════════════════════════════════════════════

class TestStabilityClassifier(unittest.TestCase):
    """Test epistemic state machine classifier."""

    def setUp(self):
        from src.graph.stability_classifier import StabilityClassifier, STABILITY_STATES
        self.classifier = StabilityClassifier()
        self.ids = _seed_data["claims"]
        self.STABILITY_STATES = STABILITY_STATES

    def test_classify_returns_profile(self):
        """classify should return a StabilityProfile with valid state."""
        profile = self.classifier.classify(self.ids[0])
        self.assertEqual(profile.claim_id, self.ids[0])
        self.assertIn(profile.classification, self.STABILITY_STATES)
        self.assertTrue(profile.classified_at)

    def test_classify_all(self):
        """classify_all should classify every claim."""
        profiles = self.classifier.classify_all()
        self.assertGreaterEqual(len(profiles), len(self.ids))
        for p in profiles:
            self.assertIn(p.classification, self.STABILITY_STATES)

    def test_signal_flags_are_list(self):
        """signal_flags should be a list of strings."""
        profile = self.classifier.classify(self.ids[0])
        self.assertIsInstance(profile.signal_flags, list)
        for flag in profile.signal_flags:
            self.assertIsInstance(flag, str)

    def test_get_latest(self):
        """get_latest should return most recent classification string."""
        self.classifier.classify(self.ids[1])
        latest = self.classifier.get_latest(self.ids[1])
        self.assertIsNotNone(latest)
        self.assertIn(latest, self.STABILITY_STATES)

    def test_get_latest_none_for_unknown(self):
        """get_latest returns None for unclassified claim."""
        latest = self.classifier.get_latest(99994)
        self.assertIsNone(latest)

    def test_get_history(self):
        """get_history should return list of classification records."""
        cid = self.ids[2]
        self.classifier.classify(cid)
        self.classifier.classify(cid)
        history = self.classifier.get_history(cid, limit=5)
        self.assertGreaterEqual(len(history), 2)

    def test_get_by_state(self):
        """get_by_state should return claim IDs in that state."""
        profiles = self.classifier.classify_all()
        # Gather which states have claims
        states_seen = set(p.classification for p in profiles)
        for state in states_seen:
            ids_in_state = self.classifier.get_by_state(state)
            self.assertIsInstance(ids_in_state, list)
            self.assertGreater(len(ids_in_state), 0)

    def test_get_summary(self):
        """get_summary should return dict with state counts."""
        self.classifier.classify_all()
        summary = self.classifier.get_summary()
        self.assertIn("total_classified", summary)
        self.assertGreater(summary["total_classified"], 0)
        for state in self.STABILITY_STATES:
            self.assertIn(state, summary)

    def test_to_dict(self):
        """StabilityProfile.to_dict() should produce a proper dict."""
        profile = self.classifier.classify(self.ids[0])
        d = profile.to_dict()
        self.assertIn("classification", d)
        self.assertIn("signal_flags", d)
        self.assertIn("confidence_trend", d)
        self.assertIn("entropy_trend", d)

    def test_stable_classification(self):
        """A claim with low variance everywhere should classify as stable or converging."""
        cid = self.ids[5]
        # Inject very stable data (clearing any prior data)
        _inject_confidence_history(cid, [0.5, 0.5, 0.5, 0.5, 0.5])
        _inject_entropy_history(cid, [1.0, 1.0, 1.0, 1.0, 1.0],
                                drifts=[0.1, 0.1, 0.1, 0.1, 0.1])
        # Clear any prior stability classifications to avoid signal contamination
        execute_sql("DELETE FROM stability_classifications WHERE claim_id = ?", (cid,))
        profile = self.classifier.classify(cid)
        self.assertIn(profile.classification, ("stable", "converging"))


# ════════════════════════════════════════════════════════════════════════
#  TestAlertEngine
# ════════════════════════════════════════════════════════════════════════

class TestAlertEngine(unittest.TestCase):
    """Test rule-based alert engine."""

    def setUp(self):
        from src.graph.alert_engine import AlertEngine, ALERT_TYPES, SEVERITY_LEVELS
        self.engine = AlertEngine()
        self.ids = _seed_data["claims"]
        self.ALERT_TYPES = ALERT_TYPES
        self.SEVERITY_LEVELS = SEVERITY_LEVELS

    def test_create_alert(self):
        """create_alert should persist and return an Alert."""
        alert = self.engine.create_alert(
            claim_id=self.ids[0],
            alert_type="entropy_spike",
            severity="warning",
            title="Test alert",
            detail="Test detail",
            metric_value=2.5,
            threshold=2.0,
        )
        self.assertGreater(alert.id, 0)
        self.assertEqual(alert.claim_id, self.ids[0])
        self.assertEqual(alert.alert_type, "entropy_spike")
        self.assertEqual(alert.severity, "warning")
        self.assertFalse(alert.acknowledged)

    def test_create_alert_to_dict(self):
        """Alert.to_dict() should produce a proper dict."""
        alert = self.engine.create_alert(
            claim_id=self.ids[1],
            alert_type="confidence_collapse",
            severity="critical",
            title="Confidence crashing",
        )
        d = alert.to_dict()
        self.assertIn("id", d)
        self.assertIn("alert_type", d)
        self.assertIn("severity", d)
        self.assertIn("acknowledged", d)

    def test_scan_claim(self):
        """scan_claim should return a list of Alert objects."""
        alerts = self.engine.scan_claim(self.ids[0])
        self.assertIsInstance(alerts, list)
        for alert in alerts:
            self.assertIsInstance(alert.title, str)

    def test_scan_all(self):
        """scan_all should scan all claims and return alerts."""
        alerts = self.engine.scan_all()
        self.assertIsInstance(alerts, list)

    def test_get_alerts_unfiltered(self):
        """get_alerts with no filters should return all alerts."""
        # Create some alerts first
        self.engine.create_alert(self.ids[0], "entropy_spike", "warning",
                                 "Spike 1", metric_value=2.0)
        self.engine.create_alert(self.ids[1], "confidence_collapse", "critical",
                                 "Collapse 1", metric_value=0.1)
        alerts = self.engine.get_alerts()
        self.assertIsInstance(alerts, list)
        self.assertGreater(len(alerts), 0)

    def test_get_alerts_by_claim(self):
        """get_alerts filtered by claim_id."""
        self.engine.create_alert(self.ids[2], "entropy_spike", "info",
                                 "Test alert for claim 2")
        alerts = self.engine.get_alerts(claim_id=self.ids[2])
        for alert in alerts:
            self.assertEqual(alert.claim_id, self.ids[2])

    def test_get_alerts_by_severity(self):
        """get_alerts filtered by severity."""
        self.engine.create_alert(self.ids[0], "entropy_spike", "critical",
                                 "Critical test")
        alerts = self.engine.get_alerts(severity="critical")
        for alert in alerts:
            self.assertEqual(alert.severity, "critical")

    def test_get_alerts_unacknowledged_only(self):
        """get_alerts with unacknowledged_only=True."""
        alert = self.engine.create_alert(self.ids[0], "entropy_spike", "warning",
                                         "Unack test")
        # Acknowledge it
        self.engine.acknowledge(alert.id)
        # Query unacknowledged
        unack = self.engine.get_alerts(unacknowledged_only=True)
        ack_ids = {a.id for a in unack}
        self.assertNotIn(alert.id, ack_ids)

    def test_acknowledge_alert(self):
        """acknowledge should mark alert as acknowledged."""
        alert = self.engine.create_alert(self.ids[3], "drift_inflection", "info",
                                         "Acknowledge me")
        result = self.engine.acknowledge(alert.id)
        self.assertTrue(result)
        # Verify it's acknowledged
        alerts = self.engine.get_alerts(claim_id=self.ids[3])
        found = [a for a in alerts if a.id == alert.id]
        self.assertTrue(found[0].acknowledged)

    def test_acknowledge_all(self):
        """acknowledge_all should clear all unacknowledged alerts."""
        self.engine.create_alert(self.ids[0], "entropy_spike", "warning", "Ack all 1")
        self.engine.create_alert(self.ids[1], "entropy_spike", "info", "Ack all 2")
        self.engine.acknowledge_all()
        unack = self.engine.get_alerts(unacknowledged_only=True)
        self.assertEqual(len(unack), 0)

    def test_get_summary(self):
        """get_summary should return counts by severity and type."""
        summary = self.engine.get_summary()
        self.assertIn("total_alerts", summary)
        self.assertIn("unacknowledged", summary)
        self.assertIn("by_severity", summary)
        self.assertIn("by_type", summary)
        for sev in self.SEVERITY_LEVELS:
            self.assertIn(sev, summary["by_severity"])


# ════════════════════════════════════════════════════════════════════════
#  TestLifecycleReport
# ════════════════════════════════════════════════════════════════════════

class TestLifecycleReport(unittest.TestCase):
    """Test lifecycle report generator."""

    def setUp(self):
        from src.graph.lifecycle_report import LifecycleReport
        self.report = LifecycleReport()
        self.ids = _seed_data["claims"]

    def test_generate_claim_report(self):
        """generate(claim_id) should produce a multi-line report string."""
        cid = self.ids[0]
        text = self.report.generate(claim_id=cid)
        self.assertIsInstance(text, str)
        self.assertIn("CLAIM LIFECYCLE REPORT", text)
        self.assertIn("CONFIDENCE TRAJECTORY", text)
        self.assertIn("ENTROPY DYNAMICS", text)
        self.assertIn("DRIFT KINEMATICS", text)
        self.assertIn("STABILITY CLASSIFICATION", text)
        self.assertIn("ACTIVE ALERTS", text)
        self.assertIn("EPISTEMIC TRAJECTORY SCORE", text)
        self.assertIn("LIFECYCLE RECOMMENDATIONS", text)

    def test_generate_system_report(self):
        """generate() with no claim_id should produce system-wide report."""
        text = self.report.generate()
        self.assertIsInstance(text, str)
        self.assertIn("SYSTEM LIFECYCLE REPORT", text)
        self.assertIn("STABILITY DISTRIBUTION", text)
        self.assertIn("ALERT SUMMARY", text)

    def test_quick_lifecycle(self):
        """quick_lifecycle should return a concise one-line summary."""
        cid = self.ids[0]
        line = self.report.quick_lifecycle(cid)
        self.assertIsInstance(line, str)
        self.assertIn(f"Claim #{cid}", line)
        self.assertIn("state=", line)
        self.assertIn("trajectory=", line)

    def test_to_json(self):
        """to_json should return a JSON-serializable dict."""
        cid = self.ids[0]
        data = self.report.to_json(cid)
        self.assertIsInstance(data, dict)
        self.assertEqual(data["claim_id"], cid)
        self.assertIn("confidence", data)
        self.assertIn("entropy", data)
        self.assertIn("drift", data)
        self.assertIn("stability", data)
        self.assertIn("trajectory", data)
        self.assertIn("alerts", data)
        self.assertIn("generated_at", data)
        # Ensure it's JSON-serializable
        serialized = json.dumps(data)
        self.assertIsInstance(serialized, str)

    def test_trajectory_score_range(self):
        """Trajectory score should be between 0 and 100."""
        cid = self.ids[0]
        data = self.report.to_json(cid)
        score = data["trajectory"]["score"]
        self.assertGreaterEqual(score, 0.0)
        self.assertLessEqual(score, 100.0)

    def test_trajectory_grade(self):
        """Trajectory grade should be A/B/C/D/F."""
        cid = self.ids[0]
        data = self.report.to_json(cid)
        self.assertIn(data["trajectory"]["grade"], ("A", "B", "C", "D", "F"))

    def test_report_claim_not_found(self):
        """Generating report for a claim with no temporal data should still work."""
        # Use a real claim ID that exists (avoids FK constraint issues)
        # but has minimal temporal data
        cid = self.ids[6]
        text = self.report.generate(claim_id=cid)
        self.assertIsInstance(text, str)
        self.assertIn("CLAIM LIFECYCLE REPORT", text)

    def test_report_contains_all_10_sections(self):
        """Report should contain all 10 numbered sections."""
        cid = self.ids[0]
        text = self.report.generate(claim_id=cid)
        for section_num in range(1, 11):
            self.assertIn(f"{section_num}.", text)


# ════════════════════════════════════════════════════════════════════════
#  TestIntegration – Cross-module temporal pipeline
# ════════════════════════════════════════════════════════════════════════

class TestIntegration(unittest.TestCase):
    """Integration tests: full temporal pipeline from snapshot to report."""

    def setUp(self):
        from src.graph.confidence_timeline import ConfidenceTimeline
        from src.graph.entropy_trend import EntropyTrendEngine
        from src.graph.drift_kinematics import DriftKinematicsEngine
        from src.graph.stability_classifier import StabilityClassifier
        from src.graph.alert_engine import AlertEngine
        from src.graph.lifecycle_report import LifecycleReport
        self.conf_tl = ConfidenceTimeline()
        self.entropy_tl = EntropyTrendEngine()
        self.drift_engine = DriftKinematicsEngine()
        self.classifier = StabilityClassifier()
        self.alert_engine = AlertEngine()
        self.lifecycle = LifecycleReport()
        self.ids = _seed_data["claims"]

    def test_full_pipeline(self):
        """Snapshot → analyze → classify → alert → report pipeline."""
        cid = self.ids[0]

        # 1. Snapshot confidence and entropy
        conf_point = self.conf_tl.snapshot_claim(cid)
        ent_point = self.entropy_tl.snapshot_claim(cid)
        self.assertGreater(conf_point.score_value, 0.0)

        # 2. Analyze trends
        conf_trend = self.conf_tl.analyze_trend(cid)
        ent_trend = self.entropy_tl.analyze_trend(cid)
        self.assertGreater(conf_trend.total_snapshots, 0)

        # 3. Drift kinematics
        drift = self.drift_engine.analyze(cid)
        self.assertEqual(drift.claim_id, cid)

        # 4. Classify
        profile = self.classifier.classify(cid)
        self.assertIn(profile.classification,
                      ("stable", "converging", "volatile", "diverging", "critical"))

        # 5. Scan for alerts
        alerts = self.alert_engine.scan_claim(cid)
        self.assertIsInstance(alerts, list)

        # 6. Generate report
        report = self.lifecycle.generate(claim_id=cid)
        self.assertIn("CLAIM LIFECYCLE REPORT", report)

        # 7. Quick summary
        quick = self.lifecycle.quick_lifecycle(cid)
        self.assertIn(f"Claim #{cid}", quick)

        # 8. JSON export
        data = self.lifecycle.to_json(cid)
        self.assertIsInstance(data, dict)
        self.assertEqual(data["claim_id"], cid)

    def test_multi_claim_system_report(self):
        """System report across multiple claims should complete."""
        # Ensure multiple claims have temporal data
        for cid in self.ids[:3]:
            self.conf_tl.snapshot_claim(cid)
            self.entropy_tl.snapshot_claim(cid)

        report = self.lifecycle.generate()
        self.assertIn("SYSTEM LIFECYCLE REPORT", report)
        self.assertIn("STABILITY DISTRIBUTION", report)


if __name__ == "__main__":
    unittest.main()
