"""
Unit tests for Phase IV modules:
  - ConfidenceScorer (Bayesian scoring, composite, save/load, ranking)
  - MutationEntropy (Shannon entropy, drift velocity, semantic stability)
  - CitationDensity (cross-reference scoring, density composite)
  - ContradictionAnalyzer (tension mapping, conflict clusters)
  - PropagationTracker (event logging, velocity, amplification)
  - ClaimScoringReport (aggregate report generation)

All tests use :memory: SQLite via PROJECT_ANCHOR_DB env var.
"""

import json
import os
import sys
import unittest
from datetime import datetime, timezone, timedelta

# Project root on path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

os.environ["PROJECT_ANCHOR_DB"] = ":memory:"

from src.database import init_db


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


# ── Shared setup ─────────────────────────────────────────────────────────
_seed_data = None


def setUpModule():
    """Initialize DB and seed data once for all tests."""
    global _seed_data
    init_db()
    _seed_data = _seed_graph()


# ── TestConfidenceScorer ─────────────────────────────────────────────────

class TestConfidenceScorer(unittest.TestCase):
    """Test Bayesian confidence scoring engine."""

    def setUp(self):
        from src.graph.confidence_scorer import ConfidenceScorer
        self.scorer = ConfidenceScorer()
        self.ids = _seed_data["claims"]

    def test_score_observation(self):
        """Score an observation claim with linked sources."""
        score = self.scorer.score_claim(self.ids[0])
        self.assertGreater(score.composite, 0.0)
        self.assertLessEqual(score.composite, 1.0)
        self.assertGreater(score.prior, 0.0)
        self.assertGreater(score.source_credibility, 0.0)

    def test_score_components_present(self):
        """All 6 scoring fields must be populated on the breakdown."""
        score = self.scorer.score_claim(self.ids[0])
        # Individual fields on ScoreBreakdown
        self.assertIsInstance(score.prior, float)
        self.assertIsInstance(score.source_credibility, float)
        self.assertIsInstance(score.citation_support, float)
        self.assertIsInstance(score.contradiction_penalty, float)
        self.assertIsInstance(score.verification_bonus, float)
        self.assertIsInstance(score.mutation_decay, float)
        # components dict stores metadata
        self.assertIn("claim_type", score.components)
        self.assertIn("weights", score.components)

    def test_score_claim_type_prior(self):
        """Different claim types should produce different priors."""
        s_obs = self.scorer.score_claim(self.ids[0])   # observation
        s_hyp = self.scorer.score_claim(self.ids[4])   # hypothesis
        # Observation prior (0.60) > hypothesis prior (0.30)
        self.assertGreater(s_obs.prior, s_hyp.prior)

    def test_score_all_claims(self):
        """score_all_claims should return a result for every claim."""
        results = self.scorer.score_all_claims()
        self.assertGreaterEqual(len(results), len(self.ids))

    def test_save_and_load_score(self):
        """Scores should persist to claim_scores table."""
        score = self.scorer.score_claim(self.ids[1])
        self.scorer.save_score(score)
        loaded = self.scorer.get_latest_score(self.ids[1])
        self.assertIsNotNone(loaded)
        self.assertAlmostEqual(loaded, score.composite, places=3)

    def test_rank_claims(self):
        """rank_claims should return sorted (id, score, text) tuples."""
        self.scorer.score_all_claims()
        ranked = self.scorer.rank_claims(top_n=5)
        self.assertGreater(len(ranked), 0)
        # Descending order
        for i in range(len(ranked) - 1):
            self.assertGreaterEqual(ranked[i][1], ranked[i + 1][1])

    def test_contradiction_lowers_score(self):
        """A contradicted claim should score lower than an uncontradicted one."""
        s_contradicted = self.scorer.score_claim(self.ids[0])   # has contradictions
        s_clean = self.scorer.score_claim(self.ids[1])          # no contradictions
        # The contradiction penalty should be higher for the contradicted claim
        self.assertGreaterEqual(
            s_contradicted.contradiction_penalty,
            s_clean.contradiction_penalty,
        )

    def test_to_dict(self):
        """ScoreBreakdown.to_dict should produce serializable output."""
        score = self.scorer.score_claim(self.ids[0])
        d = score.to_dict()
        self.assertIn("composite", d)
        # Should be JSON-serializable
        json.dumps(d)


# ── TestMutationEntropy ──────────────────────────────────────────────────

class TestMutationEntropy(unittest.TestCase):
    """Test Shannon entropy and drift analysis."""

    def setUp(self):
        from src.graph.mutation_entropy import MutationEntropy
        self.engine = MutationEntropy()
        self.ids = _seed_data["claims"]
        # c5 → c6 → c7 is the mutation chain
        self.chain_root = self.ids[4]   # c5
        self.chain_tip = self.ids[6]    # c7

    def test_shannon_entropy_basic(self):
        """Shannon entropy of a known string should be positive."""
        h = self.engine.shannon_entropy("hello world")
        self.assertGreater(h, 0.0)

    def test_shannon_entropy_single_char(self):
        """Entropy of a single repeated character should be 0."""
        h = self.engine.shannon_entropy("aaaaaaaaa")
        self.assertAlmostEqual(h, 0.0, places=6)

    def test_shannon_entropy_empty(self):
        """Entropy of empty string should be 0."""
        h = self.engine.shannon_entropy("")
        self.assertAlmostEqual(h, 0.0, places=6)

    def test_analyze_chain(self):
        """Analyze mutation chain should return valid metrics."""
        metrics = self.engine.analyze_chain(self.chain_tip)
        self.assertIsNotNone(metrics)
        self.assertGreater(metrics.chain_length, 1)
        self.assertGreaterEqual(metrics.shannon_entropy, 0.0)
        self.assertGreaterEqual(metrics.drift_velocity, 0.0)
        self.assertLessEqual(metrics.max_diff_ratio, 1.0)

    def test_semantic_stability(self):
        """Semantic stability should be between 0 and 1 for a chain."""
        metrics = self.engine.analyze_chain(self.chain_tip)
        self.assertIsNotNone(metrics)
        self.assertGreaterEqual(metrics.semantic_stability, 0.0)
        self.assertLessEqual(metrics.semantic_stability, 1.0)

    def test_single_claim_returns_metrics(self):
        """A claim with no mutations should still return metrics with chain_length=1."""
        metrics = self.engine.analyze_chain(self.ids[0])  # no parent
        self.assertIsNotNone(metrics)
        self.assertEqual(metrics.chain_length, 1)
        self.assertAlmostEqual(metrics.drift_velocity, 0.0)
        self.assertEqual(metrics.semantic_stability, 1.0)

    def test_save_metrics(self):
        """Metrics should persist to mutation_metrics table."""
        metrics = self.engine.analyze_chain(self.chain_tip)
        self.assertIsNotNone(metrics)
        self.engine.save_metrics(metrics)
        # Verify via DB
        from src.database import query_rows
        rows = query_rows("mutation_metrics", "claim_id = ?",
                          (self.chain_tip,))
        self.assertGreater(len(rows), 0)

    def test_to_dict(self):
        """MutationMetrics.to_dict should be JSON-serializable."""
        metrics = self.engine.analyze_chain(self.chain_tip)
        self.assertIsNotNone(metrics)
        d = metrics.to_dict()
        json.dumps(d)
        self.assertIn("shannon_entropy", d)


# ── TestCitationDensity ──────────────────────────────────────────────────

class TestCitationDensity(unittest.TestCase):
    """Test citation density scoring."""

    def setUp(self):
        from src.graph.citation_density import CitationDensity
        self.engine = CitationDensity()
        self.ids = _seed_data["claims"]
        self.sids = _seed_data["sources"]

    def test_analyze_well_cited_claim(self):
        """Claim with multiple sources should have density > 0."""
        metrics = self.engine.analyze_claim(self.ids[0])
        self.assertGreater(metrics.direct_citations, 0)
        self.assertGreater(metrics.unique_sources, 0)
        self.assertGreater(metrics.density_score, 0.0)

    def test_analyze_uncited_claim(self):
        """Claim with no citations should have density 0."""
        metrics = self.engine.analyze_claim(self.ids[2])  # c3: no sources linked to it
        self.assertEqual(metrics.density_score, 0.0)

    def test_density_score_range(self):
        """Density score should be in [0, 1]."""
        metrics = self.engine.analyze_claim(self.ids[0])
        self.assertGreaterEqual(metrics.density_score, 0.0)
        self.assertLessEqual(metrics.density_score, 1.0)

    def test_analyze_all_claims(self):
        """analyze_all_claims should return metrics for every claim."""
        results = self.engine.analyze_all_claims()
        self.assertGreaterEqual(len(results), len(self.ids))

    def test_rank_by_density(self):
        """rank_by_density should return sorted tuples."""
        ranked = self.engine.rank_by_density(top_n=5)
        self.assertGreater(len(ranked), 0)
        for i in range(len(ranked) - 1):
            self.assertGreaterEqual(ranked[i][1], ranked[i + 1][1])

    def test_to_dict(self):
        """CitationMetrics.to_dict should be JSON-serializable."""
        metrics = self.engine.analyze_claim(self.ids[0])
        d = metrics.to_dict()
        json.dumps(d)
        self.assertIn("density_score", d)
        self.assertIn("direct_citations", d)


# ── TestContradictionAnalyzer ────────────────────────────────────────────

class TestContradictionAnalyzer(unittest.TestCase):
    """Test tension mapping and conflict cluster detection."""

    def setUp(self):
        from src.graph.contradiction_analyzer import ContradictionAnalyzer
        self.analyzer = ContradictionAnalyzer()
        self.ids = _seed_data["claims"]

    def test_profile_contradicted_claim(self):
        """Claim with contradictions should have tension > 0."""
        profile = self.analyzer.profile_claim(self.ids[0])
        self.assertGreater(profile.contradiction_count, 0)
        self.assertGreater(profile.tension_score, 0.0)
        self.assertTrue(profile.is_contested)

    def test_profile_clean_claim(self):
        """Claim with no contradictions should have tension 0."""
        profile = self.analyzer.profile_claim(self.ids[1])  # c2: no contradictions
        self.assertEqual(profile.contradiction_count, 0)
        self.assertAlmostEqual(profile.tension_score, 0.0)
        self.assertFalse(profile.is_contested)

    def test_profile_all_claims(self):
        """profile_all_claims should return one profile per claim."""
        profiles = self.analyzer.profile_all_claims()
        self.assertGreaterEqual(len(profiles), len(self.ids))

    def test_find_conflict_clusters(self):
        """Should detect at least one conflict cluster."""
        clusters = self.analyzer.find_conflict_clusters()
        # c1 is contradicted by c3 and c4 → should form a cluster
        self.assertGreater(len(clusters), 0)
        # At least one cluster should have size >= 2
        large = [c for c in clusters if c.size >= 2]
        self.assertGreater(len(large), 0)

    def test_tension_map(self):
        """tension_map should return list of dicts with tension data."""
        tmap = self.analyzer.tension_map()
        self.assertIsInstance(tmap, list)
        self.assertGreater(len(tmap), 0)
        # Each entry is a dict with claim_id, tension, etc.
        first = tmap[0]
        self.assertIn("claim_id", first)
        self.assertIn("tension", first)
        self.assertGreater(first["tension"], 0.0)
        # The contradicted claim (ids[0]) should appear
        found = [d for d in tmap if d["claim_id"] == self.ids[0]]
        self.assertEqual(len(found), 1)

    def test_get_summary(self):
        """get_summary should return aggregate stats."""
        summary = self.analyzer.get_summary()
        self.assertIn("total_claims", summary)
        self.assertIn("contested_claims", summary)
        self.assertIn("avg_tension", summary)
        self.assertGreater(summary["contested_claims"], 0)

    def test_to_dict(self):
        """ContradictionProfile.to_dict should be JSON-serializable."""
        profile = self.analyzer.profile_claim(self.ids[0])
        d = profile.to_dict()
        json.dumps(d)
        self.assertIn("tension_score", d)


# ── TestPropagationTracker ───────────────────────────────────────────────

class TestPropagationTracker(unittest.TestCase):
    """Test propagation event logging and velocity analysis."""

    def setUp(self):
        from src.graph.propagation_tracker import PropagationTracker
        self.tracker = PropagationTracker()
        self.ids = _seed_data["claims"]

    def test_log_event(self):
        """Logging an event should return an event ID."""
        eid = self.tracker.log_event(
            self.ids[0], "first_seen",
            metadata={"source": "test"},
        )
        self.assertGreater(eid, 0)

    def test_get_events(self):
        """Events should be retrievable by claim ID."""
        self.tracker.log_event(self.ids[1], "first_seen")
        self.tracker.log_event(self.ids[1], "citation", source_id=1)
        events = self.tracker.get_events(self.ids[1])
        self.assertGreaterEqual(len(events), 2)

    def test_analyze_propagation(self):
        """Propagation analysis should return valid metrics."""
        # Log some events first
        now = datetime.now(timezone.utc)
        t1 = now.isoformat()
        t2 = (now + timedelta(hours=2)).isoformat()
        t3 = (now + timedelta(hours=5)).isoformat()
        self.tracker.log_event(self.ids[0], "first_seen", timestamp=t1)
        self.tracker.log_event(self.ids[0], "citation", timestamp=t2)
        self.tracker.log_event(self.ids[0], "amplification", timestamp=t3)

        metrics = self.tracker.analyze_propagation(self.ids[0])
        self.assertGreater(metrics.total_spread, 0)
        self.assertGreater(metrics.velocity, 0.0)
        self.assertGreater(metrics.time_span_hours, 0.0)
        self.assertIsInstance(metrics.first_seen, str)

    def test_analyze_claim_no_events(self):
        """Claim with no events should still return metrics."""
        # Use a claim unlikely to have events already
        metrics = self.tracker.analyze_propagation(self.ids[3])
        self.assertEqual(metrics.claim_id, self.ids[3])
        # Should still have created_at as first_seen
        self.assertIsInstance(metrics.first_seen, str)

    def test_auto_log_from_graph(self):
        """auto_log_from_graph should create events from evidence links."""
        count = self.tracker.auto_log_from_graph()
        self.assertGreater(count, 0)

    def test_cascade_depth(self):
        """Cascade depth for a well-linked claim should be >= 0."""
        depth = self.tracker._cascade_depth(self.ids[0])
        self.assertGreaterEqual(depth, 0)

    def test_to_dict(self):
        """PropagationMetrics.to_dict should be JSON-serializable."""
        metrics = self.tracker.analyze_propagation(self.ids[0])
        d = metrics.to_dict()
        json.dumps(d)
        self.assertIn("velocity", d)
        self.assertIn("amplification_factor", d)


# ── TestClaimScoringReport ───────────────────────────────────────────────

class TestClaimScoringReport(unittest.TestCase):
    """Test aggregate epistemic scoring report."""

    def setUp(self):
        from src.graph.claim_scoring_report import ClaimScoringReport
        self.report_gen = ClaimScoringReport()
        self.ids = _seed_data["claims"]

    def test_generate_full_report(self):
        """Full report should contain all section headers."""
        report = self.report_gen.generate()
        self.assertIn("CLAIM CONFIDENCE & EPISTEMIC SCORING REPORT", report)
        self.assertIn("BAYESIAN CONFIDENCE", report)
        self.assertIn("CITATION DENSITY", report)
        self.assertIn("CONTRADICTION TENSION MAP", report)
        self.assertIn("EPISTEMIC INTEGRITY SCORE", report)
        self.assertIn("RISK FLAGS", report)
        self.assertIn("RECOMMENDATIONS", report)

    def test_generate_single_claim(self):
        """Report for a single claim should work."""
        report = self.report_gen.generate(claim_ids=[self.ids[0]])
        self.assertIn("EPISTEMIC SCORING REPORT", report)

    def test_generate_empty_graph(self):
        """Report with no matching claims should not crash."""
        report = self.report_gen.generate(claim_ids=[99999])
        self.assertIn("NO CLAIMS FOUND", report)

    def test_to_json(self):
        """JSON export should be valid JSON with expected keys."""
        self.report_gen.generate()
        j = self.report_gen.to_json()
        data = json.loads(j)
        self.assertIn("metadata", data)
        self.assertIn("claims", data)
        self.assertIsInstance(data["claims"], list)

    def test_quick_score(self):
        """Quick score should return a compact summary line."""
        line = self.report_gen.quick_score(self.ids[0])
        self.assertIn(f"Claim #{self.ids[0]}", line)
        self.assertIn("conf=", line)

    def test_epistemic_integrity_score(self):
        """Integrity score should be present in metadata after report."""
        self.report_gen.generate()
        j = json.loads(self.report_gen.to_json())
        self.assertIn("epistemic_integrity_score", j["metadata"])
        score = j["metadata"]["epistemic_integrity_score"]
        self.assertGreaterEqual(score, 0.0)
        self.assertLessEqual(score, 100.0)


if __name__ == "__main__":
    unittest.main()
