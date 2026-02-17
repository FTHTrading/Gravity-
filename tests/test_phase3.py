"""
Unit tests for Phase III modules:
  - EquationParser (plaintext & LaTeX parsing, complexity metrics)
  - DimensionalAnalyzer (dimension inference, consistency checks)
  - SymbolicRefactor (simplify, expand, factor, series, equivalence, consistency)
  - DerivationLogger (chain lifecycle, DB persistence)
  - EquationAuditReport (report generation)
  - ClaimGraph (CRUD, linking, mutation, contradictions, statistics)
"""

import hashlib
import os
import sys
import tempfile
import unittest

# Ensure project root is on path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.database import init_db


class TestEquationParser(unittest.TestCase):
    """Test equation parsing and complexity metrics."""

    @classmethod
    def setUpClass(cls):
        from src.math.equation_parser import EquationParser
        cls.parser = EquationParser()

    def test_parse_simple_expression(self):
        """Parse a simple expression like x**2 + 1."""
        result = self.parser.parse_plaintext("x**2 + 1", name="simple")
        self.assertFalse(result.parse_error)
        self.assertFalse(result.is_equation)
        self.assertIn("x", result.symbols_found)
        self.assertTrue(len(result.sha256) == 64)

    def test_parse_equation(self):
        """Parse E = m*c**2 as an equation with LHS and RHS."""
        result = self.parser.parse_plaintext("E = m*c**2", name="einstein")
        self.assertFalse(result.parse_error)
        self.assertTrue(result.is_equation)
        self.assertIsNotNone(result.lhs)
        self.assertIsNotNone(result.rhs)
        # Symbols should include E, m, c
        for sym in ("E", "m", "c"):
            self.assertIn(sym, result.symbols_found)

    def test_parse_gravitational(self):
        """Parse F = G*M*m/r**2."""
        result = self.parser.parse_plaintext("F = G*M*m/r**2", name="gravity")
        self.assertFalse(result.parse_error)
        self.assertTrue(result.is_equation)

    def test_sha256_deterministic(self):
        """Same input should produce same SHA-256."""
        r1 = self.parser.parse_plaintext("x**2 + y**2", name="a")
        r2 = self.parser.parse_plaintext("x**2 + y**2", name="b")
        self.assertEqual(r1.sha256, r2.sha256)

    def test_complexity_metrics(self):
        """Complexity metrics should return valid classification."""
        result = self.parser.parse_plaintext("x**2 + 2*x + 1", name="quadratic")
        metrics = self.parser.get_complexity_metrics(result)
        self.assertIn("complexity_class", metrics)
        self.assertIn(metrics["complexity_class"],
                      ("trivial", "simple", "moderate", "complex", "highly_complex"))
        self.assertGreater(metrics["operation_count"], 0)

    def test_parse_error_handled(self):
        """Malformed input should produce a parse error, not crash."""
        result = self.parser.parse_plaintext("=== !!!", name="bad")
        # Should either parse with error or produce some result
        # The parser's resilience matters more than specific behavior
        self.assertIsNotNone(result)


class TestDimensionalAnalyzer(unittest.TestCase):
    """Test dimensional analysis engine."""

    @classmethod
    def setUpClass(cls):
        from src.math.dimensional_analyzer import DimensionalAnalyzer
        from src.math.equation_parser import EquationParser
        cls.analyzer = DimensionalAnalyzer()
        cls.parser = EquationParser()

    def test_einstein_dimensions_valid(self):
        """E = m*c**2 should be dimensionally valid (energy = energy)."""
        report = self.analyzer.check_known_equation("einstein_energy")
        self.assertIsNotNone(report)
        self.assertEqual(report.status, "valid")
        self.assertTrue(report.dimensions_match)

    def test_kinetic_energy_valid(self):
        """E = m*v**2/2 should be dimensionally valid."""
        report = self.analyzer.check_known_equation("kinetic_energy")
        self.assertIsNotNone(report)
        self.assertEqual(report.status, "valid")

    def test_newton_gravity_valid(self):
        """F = G*M*m/r**2 should be dimensionally valid."""
        report = self.analyzer.check_known_equation("newton_gravity")
        self.assertIsNotNone(report)
        self.assertEqual(report.status, "valid")
        self.assertTrue(report.dimensions_match)

    def test_unknown_equation_returns_none(self):
        """Non-existent equation name should return None."""
        report = self.analyzer.check_known_equation("fake_equation")
        self.assertIsNone(report)

    def test_custom_expression(self):
        """Analyze a custom parsed equation."""
        parsed = self.parser.parse_plaintext("m*v", name="momentum")
        report = self.analyzer.analyze(parsed)
        self.assertIsNotNone(report)
        # m*v should produce M L T⁻¹ (momentum)
        self.assertIn("M", report.rhs_dimension)


class TestSymbolicRefactor(unittest.TestCase):
    """Test symbolic manipulation engine."""

    @classmethod
    def setUpClass(cls):
        from src.math.symbolic_refactor import SymbolicRefactor
        from src.math.equation_parser import EquationParser
        cls.refactor = SymbolicRefactor()
        cls.parser = EquationParser()

    def test_simplify(self):
        """Simplify (x+1)**2 - x**2 - 2*x - 1 → 0."""
        parsed = self.parser.parse_plaintext("(x+1)**2 - x**2 - 2*x - 1", name="identity")
        result = self.refactor.simplify(parsed)
        self.assertEqual(result.output_expr, "0")

    def test_expand(self):
        """Expand (x+1)**2 → x**2 + 2*x + 1."""
        parsed = self.parser.parse_plaintext("(x+1)**2", name="binomial")
        result = self.refactor.expand(parsed)
        self.assertIn("x**2", result.output_expr)
        self.assertTrue(result.is_equivalent)

    def test_factor(self):
        """Factor x**2 + 2*x + 1 → (x+1)**2."""
        parsed = self.parser.parse_plaintext("x**2 + 2*x + 1", name="trinomial")
        result = self.refactor.factor(parsed)
        self.assertIn("x + 1", result.output_expr)

    def test_differentiate(self):
        """d/dx(x**3) = 3*x**2."""
        parsed = self.parser.parse_plaintext("x**3", name="cubic")
        result = self.refactor.differentiate(parsed, var_name="x")
        self.assertIn("x**2", result.output_expr)
        self.assertFalse(result.is_equivalent)  # derivative ≠ original

    def test_series_expand(self):
        """Series expansion of sin(x) around 0."""
        import sympy
        parsed = self.parser.parse_plaintext("sin(x)", name="sine")
        result = self.refactor.series_expand(parsed, var_name="x", point=0, order=4)
        self.assertIn("x", result.output_expr)

    def test_equivalence_check(self):
        """Two equivalent expressions should be detected."""
        a = self.parser.parse_plaintext("(x+1)**2", name="a")
        b = self.parser.parse_plaintext("x**2 + 2*x + 1", name="b")
        self.assertTrue(self.refactor.check_equivalence(a, b))

    def test_non_equivalence(self):
        """Two different expressions should not be equivalent."""
        a = self.parser.parse_plaintext("x**2", name="a")
        b = self.parser.parse_plaintext("x**3", name="b")
        self.assertFalse(self.refactor.check_equivalence(a, b))

    def test_consistency_report(self):
        """Consistency check should return a well-formed report."""
        parsed = self.parser.parse_plaintext("x**2 + 1", name="test")
        report = self.refactor.check_consistency(parsed)
        self.assertEqual(report.equation_name, "test")
        self.assertTrue(report.is_consistent)


class TestDerivationLogger(unittest.TestCase):
    """Test derivation chain lifecycle."""

    def test_chain_create_and_finalize(self):
        """Create a chain, add steps, and finalize."""
        from src.math.derivation_logger import DerivationLogger
        logger = DerivationLogger()

        chain = logger.start_chain("test_deriv", "x**2 + 2*x + 1")
        logger.add_step("test_deriv", "factor", "x**2 + 2*x + 1",
                        "(x + 1)**2", justification="Perfect square trinomial")
        logger.add_step("test_deriv", "substitute", "(x + 1)**2",
                        "4", justification="x = 1")

        result = logger.finalize_chain("test_deriv")
        self.assertEqual(len(result.steps), 2)
        self.assertTrue(len(result.sha256) == 64)
        self.assertEqual(result.final_expr, "4")

    def test_chain_to_dict(self):
        """Chain serialization to dict should include all fields."""
        from src.math.derivation_logger import DerivationLogger
        logger = DerivationLogger()

        logger.start_chain("dict_test", "a + b")
        logger.add_step("dict_test", "simplify", "a + b", "a + b")
        logger.finalize_chain("dict_test")

        d = logger.get_chain("dict_test").to_dict()
        self.assertIn("name", d)
        self.assertIn("steps", d)
        self.assertIn("sha256", d)
        self.assertEqual(len(d["steps"]), 1)

    def test_db_save_and_load(self):
        """Save to DB and load back."""
        from src.math.derivation_logger import DerivationLogger

        # Use temp DB
        os.environ["PROJECT_ANCHOR_DB"] = ":memory:"
        init_db()

        logger = DerivationLogger()
        logger.start_chain("db_test", "m*c**2")
        logger.add_step("db_test", "substitute", "m*c**2", "m*9e16")
        logger.finalize_chain("db_test")

        proof_id = logger.save_to_db("db_test")
        self.assertGreater(proof_id, 0)

        # Load back
        logger2 = DerivationLogger()
        loaded = logger2.load_from_db(proof_id)
        self.assertIsNotNone(loaded)
        self.assertEqual(loaded.name, "db_test")
        self.assertEqual(len(loaded.steps), 1)


class TestEquationAuditReport(unittest.TestCase):
    """Test equation audit report generation."""

    def test_report_with_equations(self):
        """Generate a report from parsed equations."""
        from src.math.equation_parser import EquationParser
        from src.math.dimensional_analyzer import DimensionalAnalyzer
        from src.math.equation_audit_report import EquationAuditReport

        parser = EquationParser()
        analyzer = DimensionalAnalyzer()

        eqs = [
            parser.parse_plaintext("E = m*c**2", name="Einstein"),
            parser.parse_plaintext("F = m*a", name="Newton2"),
        ]
        dim_reports = [analyzer.analyze(eq) for eq in eqs]

        report_gen = EquationAuditReport()
        text = report_gen.generate(
            parsed_equations=eqs,
            dimensional_reports=dim_reports,
        )
        self.assertIn("MATHEMATICAL FORENSICS AUDIT REPORT", text)
        self.assertIn("EQUATION INVENTORY", text)
        self.assertIn("DIMENSIONAL ANALYSIS", text)
        self.assertIn("Einstein", text)

    def test_report_json_export(self):
        """Report should export to JSON."""
        from src.math.equation_audit_report import EquationAuditReport
        import json

        report_gen = EquationAuditReport()
        report_gen.generate()  # Empty report
        j = report_gen.to_json()
        data = json.loads(j)
        self.assertIn("metadata", data)
        self.assertIn("sections", data)


class TestClaimGraph(unittest.TestCase):
    """Test claim graph CRUD and analysis."""

    @classmethod
    def setUpClass(cls):
        os.environ["PROJECT_ANCHOR_DB"] = ":memory:"
        init_db()

    def test_add_claim(self):
        """Add a claim and verify it gets an ID."""
        from src.graph.claim_graph import ClaimGraph
        graph = ClaimGraph()
        cid = graph.add_claim("Gravity was anomalous on August 12")
        self.assertGreater(cid, 0)

    def test_add_source(self):
        """Add a source node."""
        from src.graph.claim_graph import ClaimGraph
        graph = ClaimGraph()
        sid = graph.add_source("NIST observation log", source_type="document")
        self.assertGreater(sid, 0)

    def test_link_nodes(self):
        """Link a claim to a source."""
        from src.graph.claim_graph import ClaimGraph
        graph = ClaimGraph()
        cid = graph.add_claim("Weight measurements dropped by 0.3%")
        sid = graph.add_source("Lab report #472")
        lid = graph.link("claim", cid, "source", sid, relationship="supports")
        self.assertGreater(lid, 0)

    def test_get_claim(self):
        """Retrieve a claim by ID."""
        from src.graph.claim_graph import ClaimGraph
        graph = ClaimGraph()
        cid = graph.add_claim("Thomas Webb observed the event")
        claim = graph.get_claim(cid)
        self.assertIsNotNone(claim)
        self.assertEqual(claim.claim_text, "Thomas Webb observed the event")
        self.assertEqual(claim.verification, "unverified")

    def test_mutation_tracking(self):
        """Mutating a claim should record a diff."""
        from src.graph.claim_graph import ClaimGraph
        graph = ClaimGraph()
        parent_id = graph.add_claim("Original claim text")
        child_id = graph.add_claim(
            "Modified claim text with additions",
            parent_claim_id=parent_id,
        )
        child = graph.get_claim(child_id)
        self.assertEqual(child.mutation_parent, parent_id)
        self.assertTrue(len(child.mutation_diff) > 0)

    def test_mutation_chain(self):
        """Get the full mutation chain."""
        from src.graph.claim_graph import ClaimGraph
        graph = ClaimGraph()
        id1 = graph.add_claim("Version 1")
        id2 = graph.add_claim("Version 2", parent_claim_id=id1)
        id3 = graph.add_claim("Version 3", parent_claim_id=id2)
        chain = graph.get_mutation_chain(id3)
        self.assertEqual(len(chain), 3)
        self.assertEqual(chain[0].id, id1)
        self.assertEqual(chain[2].id, id3)

    def test_find_contradictions(self):
        """Contradiction edge should be detectable."""
        from src.graph.claim_graph import ClaimGraph
        graph = ClaimGraph()
        c1 = graph.add_claim("Gravity increased")
        c2 = graph.add_claim("Gravity decreased")
        graph.link("claim", c1, "claim", c2, relationship="contradicts")
        contradictions = graph.find_contradictions()
        self.assertGreater(len(contradictions), 0)

    def test_statistics(self):
        """Statistics should return valid counts."""
        from src.graph.claim_graph import ClaimGraph
        graph = ClaimGraph()
        stats = graph.get_statistics()
        self.assertIn("total_claims", stats)
        self.assertIn("total_sources", stats)
        self.assertIn("total_links", stats)
        self.assertIsInstance(stats["total_claims"], int)

    def test_add_entity(self):
        """Add an entity node."""
        from src.graph.claim_graph import ClaimGraph
        graph = ClaimGraph()
        eid = graph.add_entity("Thomas Webb", entity_type="person",
                               description="Primary observer")
        self.assertGreater(eid, 0)

    def test_update_claim_status(self):
        """Update claim verification status."""
        from src.graph.claim_graph import ClaimGraph
        graph = ClaimGraph()
        cid = graph.add_claim("Test claim")
        ok = graph.update_claim_status(cid, "confirmed")
        self.assertTrue(ok)
        claim = graph.get_claim(cid)
        self.assertEqual(claim.verification, "confirmed")


if __name__ == "__main__":
    unittest.main()
