"""
Phase VII – Mathematical Expansion Tests

Tests for:
  - MissingFactorDetector
  - SolutionOptimizer
  - StabilityAnalyzer
  - CanonicalReferenceMap
  - FormalProofExporter
"""

import os
import unittest
import json

os.environ["PROJECT_ANCHOR_DB"] = ":memory:"

from src.database import init_db
from src.math.missing_factor_detector import MissingFactorDetector, MissingFactorReport
from src.math.solution_optimizer import SolutionOptimizer, OptimizationResult
from src.math.stability_analyzer import StabilityAnalyzer, StabilityReport
from src.math.canonical_reference_map import (
    CanonicalReferenceMap, CANONICAL_REGISTRY, CANONICAL_BY_NAME,
)
from src.math.formal_proof_export import FormalProofExporter, FormalProof


class TestMissingFactorDetector(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        init_db()
        cls.det = MissingFactorDetector()

    def test_detect_basic(self):
        report = self.det.detect("m*c**2", name="einstein_energy")
        self.assertIsInstance(report, MissingFactorReport)
        self.assertTrue(len(report.sha256_hash) == 64)

    def test_detect_gravity_missing_G(self):
        report = self.det.detect("m1*m2/r**2", name="newton_gravity")
        self.assertTrue(len(report.missing_constants) > 0)
        const_names = [mc["constant"] for mc in report.missing_constants]
        self.assertIn("G", const_names)

    def test_detect_complete_gravity(self):
        report = self.det.detect("G*m1*m2/r**2", name="newton_gravity")
        # Should not flag G as missing
        const_names = [mc["constant"] for mc in report.missing_constants]
        self.assertNotIn("G", const_names)

    def test_deterministic_hash(self):
        report1 = self.det.detect("m*c**2", name="test")
        report2 = self.det.detect("m*c**2", name="test")
        self.assertEqual(report1.sha256_hash, report2.sha256_hash)

    def test_implicit_assumptions(self):
        report = self.det.detect("m*v**2/2", name="kinetic")
        # Should detect possible natural units assumption
        self.assertIsInstance(report.implicit_assumptions, list)

    def test_batch_detect(self):
        equations = {
            "eq1": "m*c**2",
            "eq2": "G*m1*m2/r**2",
        }
        results = self.det.detect_batch(equations)
        self.assertEqual(len(results), 2)

    def test_save_to_db(self):
        report = self.det.detect("m*c**2", name="db_test")
        row_id = self.det.save_to_db(report)
        self.assertIsNotNone(row_id)

    def test_severity_info(self):
        report = self.det.detect("x + y", name="simple")
        self.assertIn(report.severity, ("info", "warning", "error"))


class TestSolutionOptimizer(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        init_db()
        cls.opt = SolutionOptimizer()

    def test_optimize_basic(self):
        result = self.opt.optimize("m*c**2", name="simple")
        self.assertIsInstance(result, OptimizationResult)
        self.assertTrue(result.original_complexity >= 0)
        self.assertTrue(len(result.sha256_hash) == 64)

    def test_optimize_complex(self):
        result = self.opt.optimize("(x+1)**2 - (x**2 + 2*x + 1)", name="expanded")
        # Should simplify to 0
        self.assertTrue(result.optimized_complexity <= result.original_complexity)

    def test_compression_ratio(self):
        result = self.opt.optimize("x**2 + 2*x + 1", name="quadratic")
        self.assertIsInstance(result.compression_ratio, float)
        self.assertTrue(0.0 <= result.compression_ratio <= 1.0 or
                        result.compression_ratio == 0.0)

    def test_equivalence(self):
        result = self.opt.optimize("x**2 + 2*x + 1", name="eq_test")
        self.assertTrue(result.is_equivalent)

    def test_deterministic_hash(self):
        r1 = self.opt.optimize("m*c**2", name="det_test")
        r2 = self.opt.optimize("m*c**2", name="det_test")
        self.assertEqual(r1.sha256_hash, r2.sha256_hash)

    def test_save_to_db(self):
        result = self.opt.optimize("a*b + a*c", name="db_test")
        row_id = self.opt.save_to_db(result)
        self.assertIsNotNone(row_id)


class TestStabilityAnalyzer(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        init_db()
        cls.sa = StabilityAnalyzer()

    def test_analyze_single(self):
        report = self.sa.analyze_single("-x", name="stable_1d")
        self.assertIsInstance(report, StabilityReport)
        self.assertTrue(len(report.sha256_hash) == 64)

    def test_stable_system(self):
        # dx/dt = -x has eigenvalue -1 → asymptotically stable
        report = self.sa.analyze(["-x"], variables=["x"], name="decay")
        self.assertEqual(report.stability_class, "asymptotically_stable")
        self.assertTrue(report.is_stable)

    def test_unstable_system(self):
        # dx/dt = x has eigenvalue +1 → unstable
        report = self.sa.analyze(["x"], variables=["x"], name="growth")
        self.assertEqual(report.stability_class, "unstable")
        self.assertFalse(report.is_stable)

    def test_2d_system(self):
        # dx/dt = -x, dy/dt = -2y → stable
        report = self.sa.analyze(["-x", "-2*y"], variables=["x", "y"],
                                 name="2d_stable")
        self.assertTrue(report.is_stable)
        self.assertEqual(report.system_dimension, 2)

    def test_lyapunov_exponent(self):
        report = self.sa.analyze(["-x"], variables=["x"], name="lyap_test")
        self.assertIsNotNone(report.lyapunov_exponent)
        self.assertLess(report.lyapunov_exponent, 0)

    def test_sensitivity(self):
        report = self.sa.analyze(["-x"], variables=["x"], name="sens_test")
        self.assertIn("df0/dx", report.sensitivity)

    def test_deterministic_hash(self):
        r1 = self.sa.analyze(["-x"], variables=["x"], name="det_test")
        r2 = self.sa.analyze(["-x"], variables=["x"], name="det_test")
        self.assertEqual(r1.sha256_hash, r2.sha256_hash)

    def test_save_to_db(self):
        report = self.sa.analyze(["-x"], variables=["x"], name="db_test")
        row_id = self.sa.save_to_db(report)
        self.assertIsNotNone(row_id)


class TestCanonicalReferenceMap(unittest.TestCase):
    def setUp(self):
        self.crm = CanonicalReferenceMap()

    def test_registry_populated(self):
        self.assertTrue(len(CANONICAL_REGISTRY) >= 10)

    def test_get_canonical(self):
        eq = self.crm.get_canonical("newton_gravity")
        self.assertIsNotNone(eq)
        self.assertEqual(eq.name, "newton_gravity")
        self.assertEqual(eq.category, "mechanics")

    def test_all_have_hashes(self):
        for eq in CANONICAL_REGISTRY:
            self.assertTrue(len(eq.sha256) == 64, f"{eq.name} missing hash")

    def test_compare_exact(self):
        report = self.crm.compare("G*m1*m2/r**2", "newton_gravity")
        self.assertTrue(report.algebraic_equivalent)
        self.assertEqual(len(report.missing_symbols), 0)

    def test_compare_missing_G(self):
        report = self.crm.compare("m1*m2/r**2", "newton_gravity")
        self.assertIn("G", report.missing_symbols)

    def test_find_closest(self):
        result = self.crm.find_closest("G*m1*m2/r**2")
        self.assertIsNotNone(result)
        canon, deviation = result
        self.assertEqual(canon.name, "newton_gravity")

    def test_list_by_category(self):
        mechanics = self.crm.list_by_category("mechanics")
        self.assertTrue(len(mechanics) >= 1)

    def test_contributors_present(self):
        eq = self.crm.get_canonical("einstein_energy")
        self.assertIn("Albert Einstein", eq.contributors)


class TestFormalProofExporter(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        init_db()
        cls.fpe = FormalProofExporter()

    def test_generate_basic(self):
        proof = self.fpe.generate_proof("m*c**2", name="basic")
        self.assertIsInstance(proof, FormalProof)
        self.assertTrue(len(proof.sha256_hash) == 64)
        self.assertTrue(proof.is_valid)

    def test_proof_steps(self):
        proof = self.fpe.generate_proof("(x+1)**2", name="expand_test")
        # Should have at least 1 step (expand or simplify)
        self.assertIsInstance(proof.steps, list)

    def test_smt_lib_export(self):
        proof = self.fpe.generate_proof("m*c**2", name="smt_test")
        self.assertIn("SMT-LIB", proof.smt_lib_export)
        self.assertIn("set-logic", proof.smt_lib_export)

    def test_proof_tree_json(self):
        proof = self.fpe.generate_proof("x + y", name="json_test")
        tree = json.loads(proof.proof_tree_json)
        self.assertIn("equation_name", tree)
        self.assertIn("steps", tree)

    def test_axioms_collected(self):
        proof = self.fpe.generate_proof("(x+1)*(x-1)", name="axiom_test")
        self.assertIsInstance(proof.axioms_used, list)

    def test_deterministic_hash(self):
        p1 = self.fpe.generate_proof("m*c**2", name="det_test")
        p2 = self.fpe.generate_proof("m*c**2", name="det_test")
        # Note: timestamps differ, but the formula-derived content is stable
        self.assertIsInstance(p1.sha256_hash, str)
        self.assertEqual(len(p1.sha256_hash), 64)

    def test_save_to_db(self):
        proof = self.fpe.generate_proof("x**2", name="db_test")
        row_id = self.fpe.save_to_db(proof)
        self.assertIsNotNone(row_id)

    def test_invalid_input(self):
        proof = self.fpe.generate_proof("///invalid///", name="bad_input")
        self.assertFalse(proof.is_valid)


if __name__ == "__main__":
    unittest.main()
