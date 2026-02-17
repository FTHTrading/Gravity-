"""
Unit tests for Phase VI modules – Source Intelligence & Network Forensics:
  - SourceReputationEngine (EMA credibility, reliability index, grading, trends)
  - InfluenceNetworkEngine (edge construction, network analysis, gateways)
  - CoordinationDetector (temporal clustering, pattern classification, scoring)
  - DeepProvenanceEngine (mutation chains, origin classification, confidence decay)
  - SourceForensicsReportEngine (narrative reports, ecosystem health, quick summary)

All tests use :memory: SQLite via PROJECT_ANCHOR_DB env var.
"""

import json
import os
import sys
import math
import unittest
from datetime import datetime, timezone, timedelta

# Project root on path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

os.environ["PROJECT_ANCHOR_DB"] = ":memory:"

from src.database import init_db, insert_row, execute_sql, query_rows


# ── Helper: seed graph data ─────────────────────────────────────────────

def _seed_graph():
    """Seed graph with claims, sources, and links for Phase VI testing."""
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
    # Mutation chain: c5 -> c6 -> c7
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

    # Links: s1 and s3 both reference c1 (shared claim = influence edge)
    graph.link("source", s1, "claim", c1, relationship="supports", weight=0.9)
    graph.link("source", s1, "claim", c2, relationship="supports", weight=0.8)
    graph.link("source", s2, "claim", c1, relationship="references", weight=0.4)
    graph.link("source", s3, "claim", c2, relationship="supports", weight=0.7)
    graph.link("claim", c3, "claim", c1, relationship="contradicts", weight=0.6)
    graph.link("claim", c4, "claim", c1, relationship="contradicts", weight=0.5)
    graph.link("source", s3, "claim", c5, relationship="supports", weight=0.6)
    graph.link("source", s2, "claim", c3, relationship="supports", weight=0.3)

    # Entity
    graph.add_entity("Thomas Webb", entity_type="person",
                     description="Primary observer")

    return {
        "claims": [c1, c2, c3, c4, c5, c6, c7],
        "sources": [s1, s2, s3],
    }


def _clear_phase6_tables():
    """Clear Phase VI tables between tests to avoid data pollution."""
    for table in ("source_reputation", "influence_edges",
                  "coordination_events", "provenance_traces"):
        execute_sql(f"DELETE FROM {table}")


# ═══════════════════════════════════════════════════════════════════════
# 1. SourceReputationEngine
# ═══════════════════════════════════════════════════════════════════════

class TestSourceReputationSnapshot(unittest.TestCase):
    """Test reputation snapshotting."""

    def setUp(self):
        init_db()
        self.data = _seed_graph()
        _clear_phase6_tables()

    def test_snapshot_single_source(self):
        from src.graph.source_reputation import SourceReputationEngine
        engine = SourceReputationEngine()
        snap = engine.snapshot_source(self.data["sources"][0])
        self.assertGreater(snap.source_id, 0)
        self.assertGreaterEqual(snap.reliability, 0.0)
        self.assertLessEqual(snap.reliability, 1.0)
        self.assertIn(snap.trend_direction, ("flat", "improving", "degrading"))
        self.assertTrue(snap.computed_at)

    def test_snapshot_returns_correct_source_id(self):
        from src.graph.source_reputation import SourceReputationEngine
        engine = SourceReputationEngine()
        s1 = self.data["sources"][0]
        snap = engine.snapshot_source(s1)
        self.assertEqual(snap.source_id, s1)

    def test_snapshot_all_covers_all_sources(self):
        from src.graph.source_reputation import SourceReputationEngine
        engine = SourceReputationEngine()
        snaps = engine.snapshot_all()
        self.assertEqual(len(snaps), len(self.data["sources"]))

    def test_snapshot_persisted_to_db(self):
        from src.graph.source_reputation import SourceReputationEngine
        engine = SourceReputationEngine()
        s1 = self.data["sources"][0]
        engine.snapshot_source(s1)
        rows = query_rows("source_reputation", "source_id = ?", (s1,))
        self.assertEqual(len(rows), 1)

    def test_snapshot_accuracy_rate_bounded(self):
        from src.graph.source_reputation import SourceReputationEngine
        engine = SourceReputationEngine()
        for sid in self.data["sources"]:
            snap = engine.snapshot_source(sid)
            self.assertGreaterEqual(snap.accuracy_rate, 0.0)
            self.assertLessEqual(snap.accuracy_rate, 1.0)

    def test_snapshot_ema_initial_equals_reliability(self):
        """First snapshot: EMA should equal reliability."""
        from src.graph.source_reputation import SourceReputationEngine
        engine = SourceReputationEngine()
        s1 = self.data["sources"][0]
        snap = engine.snapshot_source(s1)
        self.assertAlmostEqual(snap.ema_credibility, snap.reliability, places=4)

    def test_snapshot_ema_smoothing_on_repeat(self):
        """Second snapshot: EMA should blend old and new."""
        from src.graph.source_reputation import SourceReputationEngine
        engine = SourceReputationEngine()
        s1 = self.data["sources"][0]
        snap1 = engine.snapshot_source(s1)
        snap2 = engine.snapshot_source(s1)
        # EMA2 = alpha * reliability2 + (1-alpha) * EMA1
        expected = 0.3 * snap2.reliability + 0.7 * snap1.ema_credibility
        self.assertAlmostEqual(snap2.ema_credibility, expected, places=4)

    def test_snapshot_to_dict(self):
        from src.graph.source_reputation import SourceReputationEngine
        engine = SourceReputationEngine()
        snap = engine.snapshot_source(self.data["sources"][0])
        d = snap.to_dict()
        self.assertIn("source_id", d)
        self.assertIn("reliability", d)
        self.assertIn("ema_credibility", d)
        self.assertIn("trend_direction", d)

    def test_laplace_smoothing(self):
        """With no links, reliability should be 0.5 (Laplace: 1/(0+2))."""
        from src.graph.source_reputation import SourceReputationEngine
        engine = SourceReputationEngine()
        # Create an isolated source with no links
        from src.graph.claim_graph import ClaimGraph
        g = ClaimGraph()
        s_new = g.add_source("Isolated Source", source_type="unknown", credibility=0.5)
        snap = engine.snapshot_source(s_new)
        self.assertAlmostEqual(snap.reliability, 0.5, places=4)


class TestSourceReputationProfile(unittest.TestCase):
    """Test reputation profiles and ranking."""

    def setUp(self):
        init_db()
        self.data = _seed_graph()
        _clear_phase6_tables()

    def test_profile_before_snapshot(self):
        """Profile with no snapshots should return defaults."""
        from src.graph.source_reputation import SourceReputationEngine
        engine = SourceReputationEngine()
        profile = engine.get_profile(self.data["sources"][0])
        self.assertEqual(profile.snapshot_count, 0)
        self.assertEqual(profile.grade, "C")

    def test_profile_after_snapshot(self):
        from src.graph.source_reputation import SourceReputationEngine
        engine = SourceReputationEngine()
        s1 = self.data["sources"][0]
        engine.snapshot_source(s1)
        profile = engine.get_profile(s1)
        self.assertEqual(profile.snapshot_count, 1)
        self.assertEqual(profile.source_id, s1)
        self.assertGreater(profile.reliability_index, 0)

    def test_profile_source_title(self):
        from src.graph.source_reputation import SourceReputationEngine
        engine = SourceReputationEngine()
        s1 = self.data["sources"][0]
        engine.snapshot_source(s1)
        profile = engine.get_profile(s1)
        self.assertIn("NIST", profile.source_title)

    def test_profile_to_dict(self):
        from src.graph.source_reputation import SourceReputationEngine
        engine = SourceReputationEngine()
        s1 = self.data["sources"][0]
        engine.snapshot_source(s1)
        d = engine.get_profile(s1).to_dict()
        self.assertIn("reliability_index", d)
        self.assertIn("grade", d)
        self.assertIn("trend_direction", d)

    def test_rank_sources_ordering(self):
        from src.graph.source_reputation import SourceReputationEngine
        engine = SourceReputationEngine()
        engine.snapshot_all()
        ranked = engine.rank_sources()
        self.assertEqual(len(ranked), len(self.data["sources"]))
        # Verify descending order
        for i in range(len(ranked) - 1):
            self.assertGreaterEqual(ranked[i].reliability_index,
                                    ranked[i + 1].reliability_index)

    def test_get_all_profiles(self):
        from src.graph.source_reputation import SourceReputationEngine
        engine = SourceReputationEngine()
        engine.snapshot_all()
        profiles = engine.get_all_profiles()
        self.assertEqual(len(profiles), len(self.data["sources"]))

    def test_grade_boundaries(self):
        from src.graph.source_reputation import SourceReputationEngine
        self.assertEqual(SourceReputationEngine._grade(0.95), "A")
        self.assertEqual(SourceReputationEngine._grade(0.90), "A")
        self.assertEqual(SourceReputationEngine._grade(0.80), "B")
        self.assertEqual(SourceReputationEngine._grade(0.75), "B")
        self.assertEqual(SourceReputationEngine._grade(0.65), "C")
        self.assertEqual(SourceReputationEngine._grade(0.60), "C")
        self.assertEqual(SourceReputationEngine._grade(0.50), "D")
        self.assertEqual(SourceReputationEngine._grade(0.40), "D")
        self.assertEqual(SourceReputationEngine._grade(0.30), "F")
        self.assertEqual(SourceReputationEngine._grade(0.0), "F")

    def test_reliability_index_bounded(self):
        from src.graph.source_reputation import SourceReputationEngine
        engine = SourceReputationEngine()
        engine.snapshot_all()
        for p in engine.get_all_profiles():
            self.assertGreaterEqual(p.reliability_index, 0.0)
            self.assertLessEqual(p.reliability_index, 1.0)


class TestSourceReputationHistory(unittest.TestCase):
    """Test reputation history."""

    def setUp(self):
        init_db()
        self.data = _seed_graph()
        _clear_phase6_tables()

    def test_history_empty(self):
        from src.graph.source_reputation import SourceReputationEngine
        engine = SourceReputationEngine()
        history = engine.get_history(self.data["sources"][0])
        self.assertEqual(len(history), 0)

    def test_history_grows(self):
        from src.graph.source_reputation import SourceReputationEngine
        engine = SourceReputationEngine()
        s1 = self.data["sources"][0]
        engine.snapshot_source(s1)
        engine.snapshot_source(s1)
        engine.snapshot_source(s1)
        history = engine.get_history(s1)
        self.assertEqual(len(history), 3)

    def test_history_chronological(self):
        from src.graph.source_reputation import SourceReputationEngine
        engine = SourceReputationEngine()
        s1 = self.data["sources"][0]
        engine.snapshot_source(s1)
        engine.snapshot_source(s1)
        history = engine.get_history(s1)
        self.assertLessEqual(history[0].computed_at, history[1].computed_at)

    def test_trend_flat_with_few_snapshots(self):
        from src.graph.source_reputation import SourceReputationEngine
        engine = SourceReputationEngine()
        s1 = self.data["sources"][0]
        snap1 = engine.snapshot_source(s1)
        # With only 1 snapshot, trend should be flat (needs MIN_CLAIMS_FOR_TREND=3)
        self.assertEqual(snap1.trend_direction, "flat")

    def test_trend_after_sufficient_snapshots(self):
        from src.graph.source_reputation import SourceReputationEngine
        engine = SourceReputationEngine()
        s1 = self.data["sources"][0]
        # Multiple snapshots of same data = same reliability = flat trend
        for _ in range(4):
            snap = engine.snapshot_source(s1)
        self.assertEqual(snap.trend_direction, "flat")


# ═══════════════════════════════════════════════════════════════════════
# 2. InfluenceNetworkEngine
# ═══════════════════════════════════════════════════════════════════════

class TestInfluenceEdgeConstruction(unittest.TestCase):
    """Test influence edge building."""

    def setUp(self):
        init_db()
        self.data = _seed_graph()
        _clear_phase6_tables()

    def test_build_edges_returns_list(self):
        from src.graph.influence_network import InfluenceNetworkEngine
        engine = InfluenceNetworkEngine()
        edges = engine.build_edges()
        self.assertIsInstance(edges, list)

    def test_build_edges_finds_shared_claims(self):
        """s1 and s2 both link to c1; s1 and s3 both link to c2."""
        from src.graph.influence_network import InfluenceNetworkEngine
        engine = InfluenceNetworkEngine()
        edges = engine.build_edges()
        self.assertGreater(len(edges), 0)

    def test_edge_persisted_to_db(self):
        from src.graph.influence_network import InfluenceNetworkEngine
        engine = InfluenceNetworkEngine()
        edges = engine.build_edges()
        rows = query_rows("influence_edges", "1=1")
        self.assertEqual(len(rows), len(edges))

    def test_edge_attributes(self):
        from src.graph.influence_network import InfluenceNetworkEngine
        engine = InfluenceNetworkEngine()
        edges = engine.build_edges()
        for edge in edges:
            self.assertGreater(edge.from_source_id, 0)
            self.assertGreater(edge.to_source_id, 0)
            self.assertGreater(edge.shared_claims, 0)
            self.assertGreaterEqual(edge.amplification, 0.0)
            self.assertEqual(edge.relationship, "amplifies")

    def test_edge_to_dict(self):
        from src.graph.influence_network import InfluenceNetworkEngine
        engine = InfluenceNetworkEngine()
        edges = engine.build_edges()
        if edges:
            d = edges[0].to_dict()
            self.assertIn("from_source_id", d)
            self.assertIn("shared_claims", d)
            self.assertIn("amplification", d)

    def test_no_self_edges(self):
        from src.graph.influence_network import InfluenceNetworkEngine
        engine = InfluenceNetworkEngine()
        edges = engine.build_edges()
        for edge in edges:
            self.assertNotEqual(edge.from_source_id, edge.to_source_id)


class TestInfluenceNetworkAnalysis(unittest.TestCase):
    """Test full network analysis."""

    def setUp(self):
        init_db()
        self.data = _seed_graph()
        _clear_phase6_tables()

    def test_analyze_empty_network(self):
        from src.graph.influence_network import InfluenceNetworkEngine
        engine = InfluenceNetworkEngine()
        # No edges built yet
        profile = engine.analyze_network()
        self.assertEqual(profile.total_edges, 0)
        self.assertGreater(profile.total_sources, 0)

    def test_analyze_with_edges(self):
        from src.graph.influence_network import InfluenceNetworkEngine
        engine = InfluenceNetworkEngine()
        engine.build_edges()
        profile = engine.analyze_network()
        self.assertGreater(profile.total_edges, 0)
        self.assertGreater(profile.total_sources, 0)
        self.assertGreaterEqual(profile.density, 0.0)
        self.assertGreater(profile.components, 0)

    def test_network_profile_to_dict(self):
        from src.graph.influence_network import InfluenceNetworkEngine
        engine = InfluenceNetworkEngine()
        engine.build_edges()
        d = engine.analyze_network().to_dict()
        self.assertIn("total_sources", d)
        self.assertIn("total_edges", d)
        self.assertIn("density", d)
        self.assertIn("components", d)

    def test_density_bounded(self):
        from src.graph.influence_network import InfluenceNetworkEngine
        engine = InfluenceNetworkEngine()
        engine.build_edges()
        profile = engine.analyze_network()
        self.assertGreaterEqual(profile.density, 0.0)
        self.assertLessEqual(profile.density, 1.0)

    def test_gateways_are_list(self):
        from src.graph.influence_network import InfluenceNetworkEngine
        engine = InfluenceNetworkEngine()
        engine.build_edges()
        profile = engine.analyze_network()
        self.assertIsInstance(profile.gateways, list)

    def test_top_amplifiers_are_list(self):
        from src.graph.influence_network import InfluenceNetworkEngine
        engine = InfluenceNetworkEngine()
        engine.build_edges()
        profile = engine.analyze_network()
        self.assertIsInstance(profile.top_amplifiers, list)


class TestInfluenceNeighbors(unittest.TestCase):
    """Test source neighbor queries."""

    def setUp(self):
        init_db()
        self.data = _seed_graph()
        _clear_phase6_tables()

    def test_get_influence_on_empty(self):
        from src.graph.influence_network import InfluenceNetworkEngine
        engine = InfluenceNetworkEngine()
        result = engine.get_influence_on(self.data["sources"][0])
        self.assertEqual(len(result), 0)

    def test_get_influence_on_with_edges(self):
        from src.graph.influence_network import InfluenceNetworkEngine
        engine = InfluenceNetworkEngine()
        engine.build_edges()
        # At least one source should have outgoing influence
        all_out = []
        for sid in self.data["sources"]:
            all_out.extend(engine.get_influence_on(sid))
        self.assertGreater(len(all_out), 0)

    def test_get_influenced_by_with_edges(self):
        from src.graph.influence_network import InfluenceNetworkEngine
        engine = InfluenceNetworkEngine()
        engine.build_edges()
        all_in = []
        for sid in self.data["sources"]:
            all_in.extend(engine.get_influenced_by(sid))
        self.assertGreater(len(all_in), 0)


# ═══════════════════════════════════════════════════════════════════════
# 3. CoordinationDetector
# ═══════════════════════════════════════════════════════════════════════

class TestCoordinationScan(unittest.TestCase):
    """Test coordination scanning."""

    def setUp(self):
        init_db()
        self.data = _seed_graph()
        _clear_phase6_tables()

    def test_scan_returns_list(self):
        from src.graph.coordination_detector import CoordinationDetector
        detector = CoordinationDetector()
        events = detector.scan()
        self.assertIsInstance(events, list)

    def test_scan_detects_shared_claim_coordination(self):
        """Claims c1 and c2 have multiple sources -> should detect events."""
        from src.graph.coordination_detector import CoordinationDetector
        detector = CoordinationDetector()
        events = detector.scan()
        # With timestamps close together in test data, should find coordination
        self.assertGreater(len(events), 0)

    def test_scan_events_persisted(self):
        from src.graph.coordination_detector import CoordinationDetector
        detector = CoordinationDetector()
        events = detector.scan()
        rows = query_rows("coordination_events", "1=1")
        self.assertEqual(len(rows), len(events))

    def test_scan_event_attributes(self):
        from src.graph.coordination_detector import CoordinationDetector
        detector = CoordinationDetector()
        events = detector.scan()
        for ev in events:
            self.assertTrue(ev.cluster_id)
            self.assertGreaterEqual(ev.source_count, 2)
            self.assertGreaterEqual(ev.coordination_score, 0.0)
            self.assertLessEqual(ev.coordination_score, 1.0)
            self.assertIn(ev.pattern_type, ("simultaneous", "cascade", "burst"))

    def test_scan_with_custom_window(self):
        from src.graph.coordination_detector import CoordinationDetector
        detector = CoordinationDetector()
        events_wide = detector.scan(window_hours=1000.0)
        _clear_phase6_tables()
        events_narrow = detector.scan(window_hours=0.001)
        # Wide window should capture at least as many events
        self.assertGreaterEqual(len(events_wide), len(events_narrow))

    def test_scan_claim_single(self):
        from src.graph.coordination_detector import CoordinationDetector
        detector = CoordinationDetector()
        c1 = self.data["claims"][0]
        events = detector.scan_claim(c1)
        # c1 has s1 and s2 linking to it
        self.assertGreater(len(events), 0)

    def test_scan_claim_no_sources(self):
        from src.graph.coordination_detector import CoordinationDetector
        detector = CoordinationDetector()
        # c4 has no source links, only claim-to-claim
        c4 = self.data["claims"][3]
        events = detector.scan_claim(c4)
        self.assertEqual(len(events), 0)

    def test_coordination_event_to_dict(self):
        from src.graph.coordination_detector import CoordinationDetector
        detector = CoordinationDetector()
        events = detector.scan()
        if events:
            d = events[0].to_dict()
            self.assertIn("cluster_id", d)
            self.assertIn("coordination_score", d)
            self.assertIn("pattern_type", d)
            self.assertIn("source_ids", d)


class TestCoordinationScoring(unittest.TestCase):
    """Test coordination scoring math."""

    def test_score_bounded(self):
        from src.graph.coordination_detector import CoordinationDetector
        score = CoordinationDetector._compute_coordination_score(
            source_count=5, spread_hours=2.0,
            window_hours=24.0, temporal_density=2.5
        )
        self.assertGreaterEqual(score, 0.0)
        self.assertLessEqual(score, 1.0)

    def test_tighter_clustering_higher_score(self):
        from src.graph.coordination_detector import CoordinationDetector
        score_tight = CoordinationDetector._compute_coordination_score(
            source_count=3, spread_hours=0.5,
            window_hours=24.0, temporal_density=6.0
        )
        score_loose = CoordinationDetector._compute_coordination_score(
            source_count=3, spread_hours=20.0,
            window_hours=24.0, temporal_density=0.15
        )
        self.assertGreater(score_tight, score_loose)

    def test_more_sources_higher_score(self):
        from src.graph.coordination_detector import CoordinationDetector
        score_few = CoordinationDetector._compute_coordination_score(
            source_count=2, spread_hours=1.0,
            window_hours=24.0, temporal_density=2.0
        )
        score_many = CoordinationDetector._compute_coordination_score(
            source_count=10, spread_hours=1.0,
            window_hours=24.0, temporal_density=10.0
        )
        self.assertGreater(score_many, score_few)

    def test_zero_spread_score(self):
        from src.graph.coordination_detector import CoordinationDetector
        score = CoordinationDetector._compute_coordination_score(
            source_count=3, spread_hours=0.0,
            window_hours=24.0, temporal_density=30.0
        )
        self.assertGreater(score, 0.0)


class TestCoordinationPatternClassification(unittest.TestCase):
    """Test pattern classification logic."""

    def test_simultaneous_pattern(self):
        from src.graph.coordination_detector import CoordinationDetector
        pattern = CoordinationDetector._classify_pattern(
            cluster_sources=[(1, "t1"), (2, "t2")],
            spread_hours=0.5,
            window_hours=24.0
        )
        self.assertEqual(pattern, "simultaneous")

    def test_cascade_pattern(self):
        from src.graph.coordination_detector import CoordinationDetector
        # spread = 3.0, window = 24.0, ratio = 0.125 < 0.3
        pattern = CoordinationDetector._classify_pattern(
            cluster_sources=[(1, "t1"), (2, "t2")],
            spread_hours=3.0,
            window_hours=24.0
        )
        self.assertEqual(pattern, "cascade")

    def test_burst_pattern(self):
        from src.graph.coordination_detector import CoordinationDetector
        # spread = 20.0, window = 24.0, ratio = 0.83 > 0.3
        pattern = CoordinationDetector._classify_pattern(
            cluster_sources=[(1, "t1"), (2, "t2")],
            spread_hours=20.0,
            window_hours=24.0
        )
        self.assertEqual(pattern, "burst")


class TestCoordinationSummary(unittest.TestCase):
    """Test coordination summary."""

    def setUp(self):
        init_db()
        self.data = _seed_graph()
        _clear_phase6_tables()

    def test_summary_empty(self):
        from src.graph.coordination_detector import CoordinationDetector
        detector = CoordinationDetector()
        summary = detector.get_summary()
        self.assertEqual(summary.total_events, 0)
        self.assertEqual(summary.total_clusters, 0)

    def test_summary_after_scan(self):
        from src.graph.coordination_detector import CoordinationDetector
        detector = CoordinationDetector()
        detector.scan()
        summary = detector.get_summary()
        self.assertGreater(summary.total_events, 0)
        self.assertGreater(summary.total_clusters, 0)
        self.assertGreater(summary.highest_score, 0.0)

    def test_summary_to_dict(self):
        from src.graph.coordination_detector import CoordinationDetector
        detector = CoordinationDetector()
        detector.scan()
        d = detector.get_summary().to_dict()
        self.assertIn("total_events", d)
        self.assertIn("pattern_distribution", d)
        self.assertIn("highest_score", d)

    def test_get_events_filtered(self):
        from src.graph.coordination_detector import CoordinationDetector
        detector = CoordinationDetector()
        detector.scan()
        all_ev = detector.get_events(min_score=0.0)
        high_ev = detector.get_events(min_score=0.9)
        self.assertGreaterEqual(len(all_ev), len(high_ev))

    def test_cluster_id_deterministic(self):
        from src.graph.coordination_detector import CoordinationDetector
        id1 = CoordinationDetector._make_cluster_id(1, [2, 3])
        id2 = CoordinationDetector._make_cluster_id(1, [3, 2])
        self.assertEqual(id1, id2)  # sorted source IDs → same hash

    def test_cluster_id_unique_per_claim(self):
        from src.graph.coordination_detector import CoordinationDetector
        id1 = CoordinationDetector._make_cluster_id(1, [2, 3])
        id2 = CoordinationDetector._make_cluster_id(2, [2, 3])
        self.assertNotEqual(id1, id2)


# ═══════════════════════════════════════════════════════════════════════
# 4. DeepProvenanceEngine
# ═══════════════════════════════════════════════════════════════════════

class TestProvenanceTrace(unittest.TestCase):
    """Test deep provenance tracing."""

    def setUp(self):
        init_db()
        self.data = _seed_graph()
        _clear_phase6_tables()

    def test_trace_single_claim(self):
        from src.graph.provenance_deep import DeepProvenanceEngine
        engine = DeepProvenanceEngine()
        c1 = self.data["claims"][0]
        trace = engine.trace(c1)
        self.assertEqual(trace.claim_id, c1)
        self.assertIn(trace.origin_type, ("original", "derived", "mutated",
                                           "amplified", "orphan"))

    def test_trace_original_claim(self):
        """c1 has no mutation parent and has sources -> original."""
        from src.graph.provenance_deep import DeepProvenanceEngine
        engine = DeepProvenanceEngine()
        c1 = self.data["claims"][0]
        trace = engine.trace(c1)
        self.assertEqual(trace.origin_type, "original")

    def test_trace_derived_claim(self):
        """c7 has mutation chain c5 -> c6 -> c7."""
        from src.graph.provenance_deep import DeepProvenanceEngine
        engine = DeepProvenanceEngine()
        c7 = self.data["claims"][6]
        trace = engine.trace(c7)
        self.assertIn(trace.origin_type, ("derived", "mutated"))
        self.assertGreater(trace.chain_depth, 0)

    def test_trace_chain_depth_correct(self):
        """c7 has depth 2 in mutation chain (c5 -> c6 -> c7)."""
        from src.graph.provenance_deep import DeepProvenanceEngine
        engine = DeepProvenanceEngine()
        c7 = self.data["claims"][6]
        trace = engine.trace(c7)
        self.assertGreaterEqual(trace.chain_depth, 2)

    def test_trace_persisted_to_db(self):
        from src.graph.provenance_deep import DeepProvenanceEngine
        engine = DeepProvenanceEngine()
        c1 = self.data["claims"][0]
        engine.trace(c1)
        rows = query_rows("provenance_traces", "claim_id = ?", (c1,))
        self.assertEqual(len(rows), 1)

    def test_trace_all(self):
        from src.graph.provenance_deep import DeepProvenanceEngine
        engine = DeepProvenanceEngine()
        traces = engine.trace_all()
        self.assertEqual(len(traces), len(self.data["claims"]))

    def test_trace_confidence_decay(self):
        """Deeper chains should have lower confidence."""
        from src.graph.provenance_deep import DeepProvenanceEngine
        engine = DeepProvenanceEngine()
        c1 = self.data["claims"][0]  # depth 0
        c7 = self.data["claims"][6]  # depth 2+
        t1 = engine.trace(c1)
        t7 = engine.trace(c7)
        if t1.confidence > 0 and t7.confidence > 0:
            self.assertGreaterEqual(t1.confidence, t7.confidence)

    def test_trace_confidence_bounded(self):
        from src.graph.provenance_deep import DeepProvenanceEngine
        engine = DeepProvenanceEngine()
        for cid in self.data["claims"]:
            trace = engine.trace(cid)
            self.assertGreaterEqual(trace.confidence, 0.0)
            self.assertLessEqual(trace.confidence, 1.0)

    def test_trace_chain_path_is_list(self):
        from src.graph.provenance_deep import DeepProvenanceEngine
        engine = DeepProvenanceEngine()
        c7 = self.data["claims"][6]
        trace = engine.trace(c7)
        self.assertIsInstance(trace.chain_path, list)
        self.assertGreater(len(trace.chain_path), 0)

    def test_trace_to_dict(self):
        from src.graph.provenance_deep import DeepProvenanceEngine
        engine = DeepProvenanceEngine()
        c1 = self.data["claims"][0]
        d = engine.trace(c1).to_dict()
        self.assertIn("origin_type", d)
        self.assertIn("chain_depth", d)
        self.assertIn("confidence", d)
        self.assertIn("chain_path", d)


class TestProvenanceMutationChain(unittest.TestCase):
    """Test mutation chain traversal specifically."""

    def setUp(self):
        init_db()
        self.data = _seed_graph()
        _clear_phase6_tables()

    def test_mutation_chain_root_claim(self):
        """Root claim (no parent) should have chain of length 1."""
        from src.graph.provenance_deep import DeepProvenanceEngine
        engine = DeepProvenanceEngine()
        chain = engine._trace_mutation_chain(self.data["claims"][0])
        self.assertEqual(len(chain), 1)
        self.assertEqual(chain[0], self.data["claims"][0])

    def test_mutation_chain_derived(self):
        """c7 chain should be [c5, c6, c7]."""
        from src.graph.provenance_deep import DeepProvenanceEngine
        engine = DeepProvenanceEngine()
        c5, c6, c7 = self.data["claims"][4:7]
        chain = engine._trace_mutation_chain(c7)
        self.assertEqual(chain, [c5, c6, c7])

    def test_mutation_chain_no_cycles(self):
        from src.graph.provenance_deep import DeepProvenanceEngine
        engine = DeepProvenanceEngine()
        for cid in self.data["claims"]:
            chain = engine._trace_mutation_chain(cid)
            self.assertEqual(len(chain), len(set(chain)))  # no duplicates


class TestProvenanceSummary(unittest.TestCase):
    """Test provenance summary."""

    def setUp(self):
        init_db()
        self.data = _seed_graph()
        _clear_phase6_tables()

    def test_summary_empty(self):
        from src.graph.provenance_deep import DeepProvenanceEngine
        engine = DeepProvenanceEngine()
        summary = engine.get_summary()
        self.assertEqual(summary.total_traced, 0)

    def test_summary_after_trace_all(self):
        from src.graph.provenance_deep import DeepProvenanceEngine
        engine = DeepProvenanceEngine()
        engine.trace_all()
        summary = engine.get_summary()
        self.assertEqual(summary.total_traced, len(self.data["claims"]))
        self.assertGreater(summary.max_chain_depth, 0)
        self.assertGreater(summary.avg_chain_depth, 0)
        self.assertIsInstance(summary.origin_distribution, dict)

    def test_summary_to_dict(self):
        from src.graph.provenance_deep import DeepProvenanceEngine
        engine = DeepProvenanceEngine()
        engine.trace_all()
        d = engine.get_summary().to_dict()
        self.assertIn("total_traced", d)
        self.assertIn("origin_distribution", d)
        self.assertIn("avg_chain_depth", d)

    def test_get_trace_history(self):
        from src.graph.provenance_deep import DeepProvenanceEngine
        engine = DeepProvenanceEngine()
        c1 = self.data["claims"][0]
        engine.trace(c1)
        traces = engine.get_trace(c1)
        self.assertEqual(len(traces), 1)
        self.assertEqual(traces[0].claim_id, c1)


class TestProvenanceTextSimilarity(unittest.TestCase):
    """Test text similarity helper."""

    def test_identical_text(self):
        from src.graph.provenance_deep import DeepProvenanceEngine
        sim = DeepProvenanceEngine._text_similarity("hello world", "hello world")
        self.assertAlmostEqual(sim, 1.0)

    def test_completely_different(self):
        from src.graph.provenance_deep import DeepProvenanceEngine
        sim = DeepProvenanceEngine._text_similarity("hello world", "foo bar baz")
        self.assertAlmostEqual(sim, 0.0)

    def test_partial_overlap(self):
        from src.graph.provenance_deep import DeepProvenanceEngine
        sim = DeepProvenanceEngine._text_similarity("hello world foo", "hello world bar")
        self.assertGreater(sim, 0.0)
        self.assertLess(sim, 1.0)

    def test_empty_text(self):
        from src.graph.provenance_deep import DeepProvenanceEngine
        sim = DeepProvenanceEngine._text_similarity("", "hello")
        self.assertAlmostEqual(sim, 0.0)

    def test_case_insensitive(self):
        from src.graph.provenance_deep import DeepProvenanceEngine
        sim = DeepProvenanceEngine._text_similarity("Hello World", "hello world")
        self.assertAlmostEqual(sim, 1.0)


# ═══════════════════════════════════════════════════════════════════════
# 5. SourceForensicsReportEngine
# ═══════════════════════════════════════════════════════════════════════

class TestSourceForensicsSingleReport(unittest.TestCase):
    """Test single-source forensics reports."""

    def setUp(self):
        init_db()
        self.data = _seed_graph()
        _clear_phase6_tables()

    def test_generate_single_narrative(self):
        from src.graph.source_forensics_report import SourceForensicsReportEngine
        engine = SourceForensicsReportEngine()
        s1 = self.data["sources"][0]
        report = engine.generate(source_id=s1)
        self.assertIsInstance(report, str)
        self.assertIn("SOURCE FORENSICS REPORT", report)
        self.assertIn("SOURCE IDENTITY", report)
        self.assertIn("REPUTATION PROFILE", report)

    def test_generate_single_dict(self):
        from src.graph.source_forensics_report import SourceForensicsReportEngine
        engine = SourceForensicsReportEngine()
        s1 = self.data["sources"][0]
        d = engine.generate_dict(source_id=s1)
        self.assertIn("source_id", d)
        self.assertIn("reputation", d)
        self.assertIn("influence", d)
        self.assertIn("coordination", d)
        self.assertIn("provenance", d)

    def test_single_report_sections(self):
        from src.graph.source_forensics_report import SourceForensicsReportEngine
        engine = SourceForensicsReportEngine()
        s1 = self.data["sources"][0]
        report = engine.generate(source_id=s1)
        for section in ("SOURCE IDENTITY", "REPUTATION PROFILE",
                        "INFLUENCE ANALYSIS", "COORDINATION FLAGS",
                        "PROVENANCE"):
            self.assertIn(section, report)

    def test_single_report_title(self):
        from src.graph.source_forensics_report import SourceForensicsReportEngine
        engine = SourceForensicsReportEngine()
        s1 = self.data["sources"][0]
        d = engine.generate_dict(source_id=s1)
        self.assertEqual(d["title"], "NIST Lab Report #472")


class TestSourceForensicsEcosystemReport(unittest.TestCase):
    """Test ecosystem-level forensics reports."""

    def setUp(self):
        init_db()
        self.data = _seed_graph()
        _clear_phase6_tables()

    def test_generate_ecosystem_narrative(self):
        from src.graph.source_forensics_report import SourceForensicsReportEngine
        engine = SourceForensicsReportEngine()
        report = engine.generate(source_id=0)
        self.assertIsInstance(report, str)
        self.assertIn("ECOSYSTEM ANALYSIS", report)

    def test_generate_ecosystem_dict(self):
        from src.graph.source_forensics_report import SourceForensicsReportEngine
        engine = SourceForensicsReportEngine()
        d = engine.generate_dict(source_id=0)
        self.assertIn("source_count", d)
        self.assertIn("ecosystem_health", d)
        self.assertIn("ecosystem_grade", d)

    def test_ecosystem_sections(self):
        from src.graph.source_forensics_report import SourceForensicsReportEngine
        engine = SourceForensicsReportEngine()
        report = engine.generate(source_id=0)
        for section in ("ECOSYSTEM OVERVIEW", "REPUTATION DISTRIBUTION",
                        "INFLUENCE NETWORK", "COORDINATION ANALYSIS",
                        "PROVENANCE ANALYSIS"):
            self.assertIn(section, report)

    def test_ecosystem_health_bounded(self):
        from src.graph.source_forensics_report import SourceForensicsReportEngine
        engine = SourceForensicsReportEngine()
        d = engine.generate_dict(source_id=0)
        self.assertGreaterEqual(d["ecosystem_health"], 0.0)
        self.assertLessEqual(d["ecosystem_health"], 1.0)

    def test_ecosystem_grade_valid(self):
        from src.graph.source_forensics_report import SourceForensicsReportEngine
        engine = SourceForensicsReportEngine()
        d = engine.generate_dict(source_id=0)
        self.assertIn(d["ecosystem_grade"], ("A", "B", "C", "D", "F"))

    def test_ecosystem_source_count(self):
        from src.graph.source_forensics_report import SourceForensicsReportEngine
        engine = SourceForensicsReportEngine()
        d = engine.generate_dict(source_id=0)
        self.assertEqual(d["source_count"], len(self.data["sources"]))


class TestSourceForensicsQuickSummary(unittest.TestCase):
    """Test quick source summary."""

    def setUp(self):
        init_db()
        self.data = _seed_graph()
        _clear_phase6_tables()

    def test_quick_source_returns_string(self):
        from src.graph.source_forensics_report import SourceForensicsReportEngine
        engine = SourceForensicsReportEngine()
        s1 = self.data["sources"][0]
        result = engine.quick_source(s1)
        self.assertIsInstance(result, str)
        self.assertIn(f"Source #{s1}", result)

    def test_quick_source_contains_key_metrics(self):
        from src.graph.source_forensics_report import SourceForensicsReportEngine
        engine = SourceForensicsReportEngine()
        s1 = self.data["sources"][0]
        result = engine.quick_source(s1)
        self.assertIn("reliability=", result)
        self.assertIn("trend=", result)

    def test_quick_source_nonexistent(self):
        """Nonexistent source should not crash."""
        from src.graph.source_forensics_report import SourceForensicsReportEngine
        engine = SourceForensicsReportEngine()
        result = engine.quick_source(99999)
        self.assertIsInstance(result, str)


class TestEcosystemHealth(unittest.TestCase):
    """Test ecosystem health computation."""

    def test_health_all_zeros(self):
        from src.graph.source_forensics_report import SourceForensicsReportEngine
        health = SourceForensicsReportEngine._compute_ecosystem_health({})
        self.assertGreaterEqual(health, 0.0)
        self.assertLessEqual(health, 1.0)

    def test_health_with_reputation(self):
        from src.graph.source_forensics_report import SourceForensicsReportEngine
        data = {
            "source_count": 10,
            "reputation_summary": {"mean_reliability": 0.9},
            "provenance": {"total_traced": 10, "orphan_count": 0},
            "network": {"components": 1},
            "coordination": {"highest_score": 0.0},
        }
        health = SourceForensicsReportEngine._compute_ecosystem_health(data)
        self.assertGreater(health, 0.5)

    def test_grade_boundaries(self):
        from src.graph.source_forensics_report import SourceForensicsReportEngine
        self.assertEqual(SourceForensicsReportEngine._grade(0.95), "A")
        self.assertEqual(SourceForensicsReportEngine._grade(0.80), "B")
        self.assertEqual(SourceForensicsReportEngine._grade(0.65), "C")
        self.assertEqual(SourceForensicsReportEngine._grade(0.50), "D")
        self.assertEqual(SourceForensicsReportEngine._grade(0.30), "F")


# ═══════════════════════════════════════════════════════════════════════
# INTEGRATION
# ═══════════════════════════════════════════════════════════════════════

class TestPhase6Integration(unittest.TestCase):
    """End-to-end integration tests across all Phase VI modules."""

    def setUp(self):
        init_db()
        self.data = _seed_graph()
        _clear_phase6_tables()

    def test_full_pipeline(self):
        """Run the complete Phase VI pipeline in sequence."""
        from src.graph.source_reputation import SourceReputationEngine
        from src.graph.influence_network import InfluenceNetworkEngine
        from src.graph.coordination_detector import CoordinationDetector
        from src.graph.provenance_deep import DeepProvenanceEngine
        from src.graph.source_forensics_report import SourceForensicsReportEngine

        # Step 1: Reputation snapshots
        rep = SourceReputationEngine()
        rep.snapshot_all()
        profiles = rep.rank_sources()
        self.assertEqual(len(profiles), 3)

        # Step 2: Influence edges
        inf = InfluenceNetworkEngine()
        edges = inf.build_edges()
        self.assertGreater(len(edges), 0)
        network = inf.analyze_network()
        self.assertGreater(network.total_edges, 0)

        # Step 3: Coordination detection
        coord = CoordinationDetector()
        events = coord.scan()
        self.assertGreater(len(events), 0)
        summary = coord.get_summary()
        self.assertGreater(summary.total_events, 0)

        # Step 4: Deep provenance
        prov = DeepProvenanceEngine()
        traces = prov.trace_all()
        self.assertEqual(len(traces), 7)
        prov_summary = prov.get_summary()
        self.assertGreater(prov_summary.max_chain_depth, 0)

        # Step 5: Forensics reports
        report = SourceForensicsReportEngine()
        ecosystem = report.generate(source_id=0)
        self.assertIn("ECOSYSTEM ANALYSIS", ecosystem)
        single = report.generate(source_id=self.data["sources"][0])
        self.assertIn("SOURCE FORENSICS REPORT", single)

    def test_ecosystem_health_after_pipeline(self):
        """Verify ecosystem health is computed correctly after full pipeline."""
        from src.graph.source_reputation import SourceReputationEngine
        from src.graph.influence_network import InfluenceNetworkEngine
        from src.graph.coordination_detector import CoordinationDetector
        from src.graph.provenance_deep import DeepProvenanceEngine
        from src.graph.source_forensics_report import SourceForensicsReportEngine

        SourceReputationEngine().snapshot_all()
        InfluenceNetworkEngine().build_edges()
        CoordinationDetector().scan()
        DeepProvenanceEngine().trace_all()

        report = SourceForensicsReportEngine()
        d = report.generate_dict(source_id=0)
        self.assertGreater(d["ecosystem_health"], 0.0)
        self.assertIn(d["ecosystem_grade"], ("A", "B", "C", "D", "F"))

    def test_all_modules_import(self):
        """Verify all Phase VI modules import without error."""
        from src.graph.source_reputation import SourceReputationEngine, ReputationSnapshot, ReputationProfile
        from src.graph.influence_network import InfluenceNetworkEngine, InfluenceEdge, NetworkProfile
        from src.graph.coordination_detector import CoordinationDetector, CoordinationEvent, CoordinationSummary
        from src.graph.provenance_deep import DeepProvenanceEngine, ProvenanceTrace, ProvenanceSummary
        from src.graph.source_forensics_report import SourceForensicsReportEngine, SourceForensicsReport

    def test_dataclass_defaults(self):
        """All dataclasses should instantiate with defaults."""
        from src.graph.source_reputation import ReputationSnapshot, ReputationProfile
        from src.graph.influence_network import InfluenceEdge, NetworkProfile
        from src.graph.coordination_detector import CoordinationEvent, CoordinationSummary
        from src.graph.provenance_deep import ProvenanceTrace, ProvenanceSummary

        self.assertIsNotNone(ReputationSnapshot())
        self.assertIsNotNone(ReputationProfile())
        self.assertIsNotNone(InfluenceEdge())
        self.assertIsNotNone(NetworkProfile())
        self.assertIsNotNone(CoordinationEvent())
        self.assertIsNotNone(CoordinationSummary())
        self.assertIsNotNone(ProvenanceTrace())
        self.assertIsNotNone(ProvenanceSummary())


if __name__ == "__main__":
    unittest.main()
