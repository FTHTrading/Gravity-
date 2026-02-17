"""
Phase VII – Scientific Registry Tests

Tests for:
  - ScientificRegistry (lookup, domain filtering, equation linking)
  - Default contributors loaded
  - SHA-256 hashing of registry entries
  - DB persistence
"""

import os
import unittest

os.environ["PROJECT_ANCHOR_DB"] = ":memory:"

from src.database import init_db
from src.taxonomy.scientific_registry import (
    ScientificRegistry, ScientificContributor, DEFAULT_CONTRIBUTORS,
    SCIENTIFIC_DOMAINS,
)


class TestScientificRegistry(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        init_db()
        cls.reg = ScientificRegistry()

    def test_defaults_loaded(self):
        all_contribs = self.reg.list_all()
        self.assertTrue(len(all_contribs) >= 10)

    def test_get_newton(self):
        c = self.reg.get("Isaac Newton")
        self.assertIsNotNone(c)
        self.assertEqual(c.domain, "Physics")
        self.assertIn("newton_gravity", c.key_equations)

    def test_get_einstein(self):
        c = self.reg.get("Albert Einstein")
        self.assertIsNotNone(c)
        self.assertIn("einstein_energy", c.key_equations)

    def test_get_shannon(self):
        c = self.reg.get("Claude Shannon")
        self.assertIsNotNone(c)
        self.assertEqual(c.domain, "Information Theory")

    def test_get_nonexistent(self):
        c = self.reg.get("Nonexistent Person")
        self.assertIsNone(c)

    def test_list_by_domain(self):
        physics = self.reg.list_by_domain("Physics")
        self.assertTrue(len(physics) >= 3)

    def test_find_by_equation(self):
        contribs = self.reg.find_by_equation("newton_gravity")
        names = [c.name for c in contribs]
        self.assertIn("Isaac Newton", names)

    def test_all_have_hashes(self):
        for c in self.reg.list_all():
            self.assertTrue(len(c.sha256_hash) == 64,
                            f"{c.name} missing hash")

    def test_deterministic_hash(self):
        c1 = self.reg.get("Isaac Newton")
        c2 = ScientificContributor(
            name="Isaac Newton",
            domain="Physics",
            birth_year=1643,
            death_year=1727,
            nationality="English",
            core_contributions=[
                "Laws of motion",
                "Universal gravitation",
                "Calculus (co-inventor)",
                "Optics",
            ],
            key_equations=["newton_gravity", "kinetic_energy"],
            publications=["Principia Mathematica (1687)", "Opticks (1704)"],
            modern_applications=[
                "Orbital mechanics",
                "Celestial navigation",
                "Structural engineering",
            ],
        )
        c2.compute_hash()
        self.assertEqual(c1.sha256_hash, c2.sha256_hash)

    def test_register_new(self):
        new_contrib = ScientificContributor(
            name="Test Scientist",
            domain="Physics",
            core_contributions=["Test contribution"],
        )
        self.reg.register(new_contrib)
        found = self.reg.get("Test Scientist")
        self.assertIsNotNone(found)
        self.assertEqual(found.domain, "Physics")

    def test_link_claim(self):
        self.reg.link_claim("Isaac Newton", 42)
        c = self.reg.get("Isaac Newton")
        self.assertIn(42, c.linked_claim_ids)

    def test_link_equation(self):
        self.reg.link_equation("Isaac Newton", 99)
        c = self.reg.get("Isaac Newton")
        self.assertIn(99, c.linked_equation_ids)

    def test_save_all_to_db(self):
        saved = self.reg.save_all_to_db()
        self.assertTrue(saved >= 10)

    def test_save_one_to_db(self):
        row_id = self.reg.save_one_to_db("Albert Einstein")
        self.assertIsNotNone(row_id)

    def test_summary(self):
        summary = self.reg.summary()
        self.assertIn("total_contributors", summary)
        self.assertIn("domains", summary)
        self.assertTrue(summary["total_contributors"] >= 10)

    def test_scientific_domains(self):
        self.assertIn("Physics", SCIENTIFIC_DOMAINS)
        self.assertIn("Mathematics", SCIENTIFIC_DOMAINS)
        self.assertIn("Information Theory", SCIENTIFIC_DOMAINS)

    def test_default_contributors_count(self):
        self.assertTrue(len(DEFAULT_CONTRIBUTORS) >= 10)


if __name__ == "__main__":
    unittest.main()
