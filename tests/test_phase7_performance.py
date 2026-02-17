"""
Phase VII – Performance & Optimization Tests

Tests for:
  - SolvabilityIndex
  - ModelEfficiencyScore
  - CompressionRatio
  - AsyncExecutor
  - CacheManager
  - BenchmarkSuite
"""

import os
import unittest

os.environ["PROJECT_ANCHOR_DB"] = ":memory:"

from src.database import init_db
from src.optimization.solvability_index import SolvabilityIndex, SolvabilityResult
from src.optimization.model_efficiency_score import ModelEfficiencyScore, EfficiencyResult
from src.optimization.compression_ratio import CompressionRatio, CompressionResult
from src.performance.async_executor import AsyncExecutor, BatchResult
from src.performance.cache_manager import CacheManager
from src.performance.benchmark_suite import BenchmarkSuite


class TestSolvabilityIndex(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        init_db()
        cls.si = SolvabilityIndex()

    def test_compute_basic(self):
        result = self.si.compute("m*c**2", name="emc2")
        self.assertIsInstance(result, SolvabilityResult)
        self.assertTrue(0.0 <= result.solvability_index <= 1.0)
        self.assertTrue(len(result.sha256_hash) == 64)

    def test_highly_tractable(self):
        # 1 variable, 1 constraint, stable, complete dims → high SI
        result = self.si.compute("x", name="simple", constraints=2,
                                 stability_factor=0.0,
                                 dimensional_completeness=1.0)
        self.assertGreater(result.solvability_index, 0.5)

    def test_intractable(self):
        # Many variables, unstable → low SI
        result = self.si.compute("a*b*c*d*e*f*g*h*i*j", name="complex",
                                 constraints=1, stability_factor=0.9,
                                 dimensional_completeness=0.3)
        self.assertLess(result.solvability_index, 0.1)

    def test_from_stability_class(self):
        result = self.si.compute_from_stability(
            "m*c**2", name="stable_test",
            stability_class="asymptotically_stable",
        )
        self.assertEqual(result.stability_factor, 0.0)

    def test_unstable_class(self):
        result = self.si.compute_from_stability(
            "m*c**2", name="unstable_test",
            stability_class="unstable",
        )
        self.assertEqual(result.stability_factor, 0.9)

    def test_deterministic_hash(self):
        r1 = self.si.compute("m*c**2", name="det_test")
        r2 = self.si.compute("m*c**2", name="det_test")
        self.assertEqual(r1.sha256_hash, r2.sha256_hash)

    def test_save_to_db(self):
        result = self.si.compute("x + y", name="db_test")
        row_id = self.si.save_to_db(result)
        self.assertIsNotNone(row_id)

    def test_interpretation(self):
        result = self.si.compute("x", name="interp_test")
        self.assertTrue(len(result.interpretation) > 0)


class TestModelEfficiencyScore(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        init_db()
        cls.mes = ModelEfficiencyScore()

    def test_compute_basic(self):
        result = self.mes.compute("m*c**2", name="emc2")
        self.assertIsInstance(result, EfficiencyResult)
        self.assertTrue(result.operation_count >= 0)
        self.assertTrue(0.0 < result.efficiency_score <= 1.0)

    def test_simple_more_efficient(self):
        r1 = self.mes.compute("x", name="simple")
        r2 = self.mes.compute("a*b*c + d*e*f + g*h*i", name="complex")
        self.assertGreater(r1.efficiency_score, r2.efficiency_score)

    def test_tree_depth(self):
        result = self.mes.compute("x**2 + y**2 + z**2", name="depth_test")
        self.assertTrue(result.tree_depth >= 1)

    def test_deterministic_hash(self):
        r1 = self.mes.compute("m*c**2", name="det_test")
        r2 = self.mes.compute("m*c**2", name="det_test")
        self.assertEqual(r1.sha256_hash, r2.sha256_hash)

    def test_save_to_db(self):
        result = self.mes.compute("x + y", name="db_test")
        row_id = self.mes.save_to_db(result)
        self.assertIsNotNone(row_id)


class TestCompressionRatio(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        init_db()
        cls.cr = CompressionRatio()

    def test_compute_basic(self):
        result = self.cr.compute("x**2 + 2*x + 1", name="quadratic")
        self.assertIsInstance(result, CompressionResult)
        self.assertTrue(len(result.sha256_hash) == 64)

    def test_already_simple(self):
        result = self.cr.compute("x + y", name="simple")
        self.assertEqual(result.compression_ratio, 0.0)

    def test_strategy_results(self):
        result = self.cr.compute("x**2 + 2*x + 1", name="strat_test")
        self.assertTrue(len(result.strategy_results) >= 3)

    def test_deterministic_hash(self):
        r1 = self.cr.compute("x**2 + 2*x + 1", name="det_test")
        r2 = self.cr.compute("x**2 + 2*x + 1", name="det_test")
        self.assertEqual(r1.sha256_hash, r2.sha256_hash)

    def test_save_to_db(self):
        result = self.cr.compute("x + y", name="db_test")
        row_id = self.cr.save_to_db(result)
        self.assertIsNotNone(row_id)


class TestAsyncExecutor(unittest.TestCase):
    def test_run_batch(self):
        executor = AsyncExecutor(max_workers=2)
        result = executor.run_batch(
            [1, 2, 3, 4, 5],
            lambda x: x * 2,
            label="double",
        )
        self.assertIsInstance(result, BatchResult)
        self.assertEqual(result.total, 5)
        self.assertEqual(result.completed, 5)
        self.assertEqual(result.failed, 0)
        self.assertEqual(result.results, [2, 4, 6, 8, 10])

    def test_batch_with_errors(self):
        def may_fail(x):
            if x == 3:
                raise ValueError("test error")
            return x

        executor = AsyncExecutor(max_workers=2)
        result = executor.run_batch([1, 2, 3, 4], may_fail, label="errors")
        self.assertEqual(result.completed, 3)
        self.assertEqual(result.failed, 1)
        self.assertEqual(len(result.errors), 1)

    def test_run_sequential(self):
        executor = AsyncExecutor()
        result = executor.run_sequential(
            [1, 2, 3],
            lambda x: x ** 2,
            label="squares",
        )
        self.assertEqual(result.results, [1, 4, 9])
        self.assertEqual(result.completed, 3)

    def test_deterministic_order(self):
        executor = AsyncExecutor(max_workers=4)
        result = executor.run_batch(
            list(range(20)),
            lambda x: x * 10,
            label="order_test",
        )
        expected = [x * 10 for x in range(20)]
        self.assertEqual(result.results, expected)

    def test_elapsed_time(self):
        executor = AsyncExecutor()
        result = executor.run_batch([1], lambda x: x, label="time")
        self.assertGreater(result.elapsed_sec, 0)


class TestCacheManager(unittest.TestCase):
    def test_put_get(self):
        cache = CacheManager(max_size=10)
        key = CacheManager.make_key("test", "input")
        cache.put(key, {"result": 42})
        self.assertEqual(cache.get(key)["result"], 42)

    def test_miss(self):
        cache = CacheManager(max_size=10)
        self.assertIsNone(cache.get("nonexistent"))

    def test_lru_eviction(self):
        cache = CacheManager(max_size=3)
        for i in range(5):
            cache.put(str(i), i)
        # First two should be evicted
        self.assertIsNone(cache.get("0"))
        self.assertIsNone(cache.get("1"))
        self.assertEqual(cache.get("4"), 4)

    def test_invalidate(self):
        cache = CacheManager(max_size=10)
        cache.put("key1", "val1")
        cache.invalidate("key1")
        self.assertIsNone(cache.get("key1"))

    def test_invalidate_all(self):
        cache = CacheManager(max_size=10)
        cache.put("a", 1)
        cache.put("b", 2)
        cache.invalidate_all()
        self.assertIsNone(cache.get("a"))
        self.assertIsNone(cache.get("b"))

    def test_stats(self):
        cache = CacheManager(max_size=10)
        cache.put("x", 1)
        cache.get("x")  # hit
        cache.get("y")  # miss
        stats = cache.stats
        self.assertEqual(stats.hits, 1)
        self.assertEqual(stats.misses, 1)

    def test_make_key_deterministic(self):
        k1 = CacheManager.make_key("a", "b", "c")
        k2 = CacheManager.make_key("a", "b", "c")
        self.assertEqual(k1, k2)
        self.assertEqual(len(k1), 64)

    def test_contains(self):
        cache = CacheManager(max_size=10)
        cache.put("key", "val")
        self.assertTrue(cache.contains("key"))
        self.assertFalse(cache.contains("other"))


class TestBenchmarkSuite(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        init_db()

    def test_measure(self):
        suite = BenchmarkSuite()
        with suite.measure("test_op"):
            _ = sum(range(1000))
        self.assertEqual(len(suite.records), 1)
        self.assertEqual(suite.records[0].operation, "test_op")
        self.assertGreater(suite.records[0].duration_sec, 0)

    def test_time_function(self):
        suite = BenchmarkSuite()
        result, record = suite.time_function("add", lambda a, b: a + b, 3, 4)
        self.assertEqual(result, 7)
        self.assertEqual(record.operation, "add")

    def test_summary(self):
        suite = BenchmarkSuite()
        with suite.measure("op1"):
            pass
        with suite.measure("op2"):
            pass
        summary = suite.summary()
        self.assertEqual(summary["total_records"], 2)
        self.assertIn("avg_time_sec", summary)

    def test_save_to_db(self):
        suite = BenchmarkSuite()
        with suite.measure("db_test"):
            pass
        saved = suite.save_to_db()
        self.assertEqual(saved, 1)

    def test_clear(self):
        suite = BenchmarkSuite()
        with suite.measure("clear_test"):
            pass
        suite.clear()
        self.assertEqual(len(suite.records), 0)

    def test_empty_summary(self):
        suite = BenchmarkSuite()
        summary = suite.summary()
        self.assertEqual(summary["total_records"], 0)


if __name__ == "__main__":
    unittest.main()
