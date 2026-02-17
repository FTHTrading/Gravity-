"""
Unit tests for the physics consistency module.
Validates computations against known values.
"""

import math
import sys
import os
import unittest

# Ensure project root is on path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.database import init_db
from src.physics.gravity_engine import (
    GravityPhysicsEngine,
    G, c, M_SUN, M_EARTH, R_EARTH, g_SURFACE,
)


class TestGravityPhysicsEngine(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        # Use in-memory or temp DB
        init_db()
        cls.engine = GravityPhysicsEngine()

    def test_gravitational_binding_energy_order_of_magnitude(self):
        """Earth's binding energy should be ~2e32 J."""
        result = self.engine.gravitational_binding_energy()
        self.assertAlmostEqual(math.log10(result.value), 32, delta=1)
        self.assertEqual(result.units, "joules")

    def test_energy_to_nullify_gravity(self):
        """Should be a very large number of joules."""
        result = self.engine.energy_to_nullify_gravity()
        self.assertGreater(result.value, 1e30)
        self.assertEqual(result.units, "joules")

    def test_gw_strain_gw150914(self):
        """GW150914-like strain should be ~1e-21 order of magnitude."""
        result = self.engine.gravitational_wave_strain(
            m1_solar=36.0, m2_solar=29.0, distance_mpc=410.0
        )
        log_h = math.log10(result.value)
        self.assertAlmostEqual(log_h, -21, delta=2)

    def test_tidal_acceleration_negligible(self):
        """Tidal acceleration from GW at Earth should be negligible vs g."""
        result = self.engine.tidal_acceleration_from_gw(strain=1e-21, frequency=250)
        self.assertLess(result.value, 1e-5)  # far less than g=9.8

    def test_ratio_gw_to_gravity_tiny(self):
        """Ratio should be an astronomically small number."""
        result = self.engine.ratio_gw_to_surface_gravity(strain=1e-21, frequency=250)
        self.assertLess(result.value, 1e-6)

    def test_required_distance_for_cancellation(self):
        """Distance should be within solar system scale for 1M solar mass BH."""
        result = self.engine.required_distance_for_cancellation(bh_mass_solar=1e6)
        r_au = result.value / 1.496e11
        self.assertGreater(r_au, 0.01)
        self.assertLess(r_au, 100)

    def test_merger_energy_output(self):
        """GW150914 radiated ~5.4e47 J."""
        result = self.engine.merger_energy_output(mass_radiated_solar=3.0)
        log_e = math.log10(result.value)
        self.assertAlmostEqual(log_e, 47, delta=1)

    def test_full_comparison_returns_all(self):
        """Full suite should return 25 results (7 original + 14 extended + 4 Planck)."""
        results = self.engine.run_full_comparison()
        self.assertGreaterEqual(len(results), 25)
        for r in results:
            self.assertIn("description", r)
            self.assertIn("equation", r)
            self.assertIn("value", r)
            self.assertIn("units", r)

    def test_constants_sanity(self):
        """Verify physical constants are reasonable."""
        self.assertAlmostEqual(G, 6.674e-11, delta=1e-13)
        self.assertAlmostEqual(c, 2.998e8, delta=1e5)
        self.assertAlmostEqual(g_SURFACE, 9.80665, places=3)
        self.assertAlmostEqual(M_EARTH, 5.972e24, delta=1e22)


if __name__ == "__main__":
    unittest.main()
