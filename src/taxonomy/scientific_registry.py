"""
Scientific Registry – Structured registry of scientific contributors
linked to equations, domains, and claims.

Phase VII-B: Scientific Registry

Provides:
  - Contributor profiles (name, domain, core contributions)
  - Key equation linkage
  - Publication references
  - Modern application mapping
  - Citation links to equation_proofs and claim_nodes
  - SHA-256 hashed registry entries
"""

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

from src.logger import get_logger

log = get_logger(__name__)

# ── Scientific Domains ───────────────────────────────────────────────────────

SCIENTIFIC_DOMAINS = [
    "Physics",
    "Mathematics",
    "Chemistry",
    "Engineering",
    "Computer Science",
    "Cryptography",
    "Materials Science",
    "Information Theory",
    "Cosmology",
    "Quantum Mechanics",
    "Electromagnetism",
    "Thermodynamics",
    "Biology",
]


@dataclass
class ScientificContributor:
    """A scientific contributor with equation linkage."""
    name: str
    domain: str
    birth_year: Optional[int] = None
    death_year: Optional[int] = None
    nationality: str = ""
    core_contributions: list = field(default_factory=list)
    key_equations: list = field(default_factory=list)
    publications: list = field(default_factory=list)
    modern_applications: list = field(default_factory=list)
    linked_claim_ids: list = field(default_factory=list)
    linked_equation_ids: list = field(default_factory=list)
    citation_count: int = 0
    sha256_hash: str = ""

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "domain": self.domain,
            "birth_year": self.birth_year,
            "death_year": self.death_year,
            "nationality": self.nationality,
            "core_contributions": self.core_contributions,
            "key_equations": self.key_equations,
            "publications": self.publications,
            "modern_applications": self.modern_applications,
            "linked_claim_ids": self.linked_claim_ids,
            "linked_equation_ids": self.linked_equation_ids,
            "citation_count": self.citation_count,
            "sha256_hash": self.sha256_hash,
        }

    def compute_hash(self):
        """Compute deterministic SHA-256."""
        d = self.to_dict()
        d.pop("sha256_hash", None)
        canonical = json.dumps(d, sort_keys=True, default=str)
        self.sha256_hash = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
        return self.sha256_hash


# ── Default Registry ─────────────────────────────────────────────────────────

DEFAULT_CONTRIBUTORS = [
    ScientificContributor(
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
    ),
    ScientificContributor(
        name="Albert Einstein",
        domain="Physics",
        birth_year=1879,
        death_year=1955,
        nationality="German-American",
        core_contributions=[
            "Special relativity",
            "General relativity",
            "Mass-energy equivalence",
            "Photoelectric effect",
            "Brownian motion",
        ],
        key_equations=["einstein_energy", "einstein_field_coupling"],
        publications=[
            "Annalen der Physik (1905) – Special relativity",
            "Annalen der Physik (1915) – General relativity",
        ],
        modern_applications=[
            "GPS corrections",
            "Nuclear energy",
            "Gravitational wave detection",
            "PET scans",
        ],
    ),
    ScientificContributor(
        name="James Clerk Maxwell",
        domain="Physics",
        birth_year=1831,
        death_year=1879,
        nationality="Scottish",
        core_contributions=[
            "Maxwell's equations",
            "Electromagnetic theory",
            "Kinetic theory of gases",
            "Color theory",
        ],
        key_equations=["maxwell_gauss_electric"],
        publications=["A Treatise on Electricity and Magnetism (1873)"],
        modern_applications=[
            "Radio communications",
            "Optical fiber networks",
            "Antenna design",
            "MRI technology",
        ],
    ),
    ScientificContributor(
        name="Erwin Schrödinger",
        domain="Quantum Mechanics",
        birth_year=1887,
        death_year=1961,
        nationality="Austrian",
        core_contributions=[
            "Schrödinger equation",
            "Wave mechanics",
            "Quantum entanglement concept",
        ],
        key_equations=["schrodinger_energy"],
        publications=["Annalen der Physik (1926)"],
        modern_applications=[
            "Quantum computing",
            "Semiconductor design",
            "Quantum chemistry",
        ],
    ),
    ScientificContributor(
        name="Paul Dirac",
        domain="Quantum Mechanics",
        birth_year=1902,
        death_year=1984,
        nationality="British",
        core_contributions=[
            "Dirac equation",
            "Antimatter prediction",
            "Quantum electrodynamics foundations",
            "Bra-ket notation",
        ],
        key_equations=["dirac_equation_coupling"],
        publications=["Proc. Royal Society A (1928)"],
        modern_applications=[
            "Antimatter research",
            "Spintronics",
            "Quantum field theory",
        ],
    ),
    ScientificContributor(
        name="Emmy Noether",
        domain="Mathematics",
        birth_year=1882,
        death_year=1935,
        nationality="German",
        core_contributions=[
            "Noether's theorem",
            "Abstract algebra foundations",
            "Ring theory",
        ],
        key_equations=["noether_current"],
        publications=[
            "Nachrichten von der Gesellschaft der Wissenschaften (1918)",
        ],
        modern_applications=[
            "Conservation laws in physics",
            "Gauge theory",
            "Particle physics",
        ],
    ),
    ScientificContributor(
        name="Claude Shannon",
        domain="Information Theory",
        birth_year=1916,
        death_year=2001,
        nationality="American",
        core_contributions=[
            "Information theory",
            "Shannon entropy",
            "Channel capacity theorem",
            "Digital circuit design theory",
        ],
        key_equations=["shannon_entropy"],
        publications=["Bell System Technical Journal (1948)"],
        modern_applications=[
            "Data compression",
            "Cryptography",
            "Machine learning",
            "5G telecommunications",
        ],
    ),
    ScientificContributor(
        name="Ludwig Boltzmann",
        domain="Physics",
        birth_year=1844,
        death_year=1906,
        nationality="Austrian",
        core_contributions=[
            "Statistical mechanics",
            "Boltzmann entropy",
            "Boltzmann equation",
            "H-theorem",
        ],
        key_equations=["boltzmann_entropy"],
        publications=["Vorlesungen über Gastheorie (1896)"],
        modern_applications=[
            "Thermodynamics",
            "Material science",
            "Cosmological entropy models",
        ],
    ),
    ScientificContributor(
        name="Max Planck",
        domain="Physics",
        birth_year=1858,
        death_year=1947,
        nationality="German",
        core_contributions=[
            "Quantum theory",
            "Planck constant",
            "Blackbody radiation law",
        ],
        key_equations=["planck_einstein"],
        publications=[
            "Verhandlungen der Deutschen Physikalischen Gesellschaft (1900)",
        ],
        modern_applications=[
            "Photovoltaics",
            "Laser physics",
            "Quantum computing",
        ],
    ),
    ScientificContributor(
        name="Louis de Broglie",
        domain="Quantum Mechanics",
        birth_year=1892,
        death_year=1987,
        nationality="French",
        core_contributions=[
            "Wave-particle duality",
            "de Broglie wavelength",
            "Matter waves",
        ],
        key_equations=["de_broglie_wavelength"],
        publications=["Annales de Physique (1925)"],
        modern_applications=[
            "Electron microscopy",
            "Neutron diffraction",
            "Quantum mechanics foundations",
        ],
    ),
    ScientificContributor(
        name="Alexander Friedmann",
        domain="Cosmology",
        birth_year=1888,
        death_year=1925,
        nationality="Russian",
        core_contributions=[
            "Friedmann equations",
            "Expanding universe model",
        ],
        key_equations=["friedmann_expansion"],
        publications=["Zeitschrift für Physik (1922)"],
        modern_applications=[
            "Big Bang cosmology",
            "Dark energy models",
            "Cosmic microwave background analysis",
        ],
    ),
    ScientificContributor(
        name="Charles-Augustin de Coulomb",
        domain="Physics",
        birth_year=1736,
        death_year=1806,
        nationality="French",
        core_contributions=[
            "Coulomb's law",
            "Electrostatic force measurement",
            "Torsion balance",
        ],
        key_equations=["coulomb_force"],
        publications=[
            "Histoire de l'Académie Royale des Sciences (1785)",
        ],
        modern_applications=[
            "Electrostatics",
            "Molecular chemistry",
            "Plasma physics",
        ],
    ),
]


class ScientificRegistry:
    """
    Registry of scientific contributors linked to equations and claims.
    """

    def __init__(self):
        self._contributors: dict[str, ScientificContributor] = {}
        # Load defaults
        for c in DEFAULT_CONTRIBUTORS:
            c.compute_hash()
            self._contributors[c.name] = c

    def register(self, contributor: ScientificContributor):
        """Add or update a contributor in the registry."""
        contributor.compute_hash()
        self._contributors[contributor.name] = contributor
        log.info("Registered contributor: %s (domain=%s)",
                 contributor.name, contributor.domain)

    def get(self, name: str) -> Optional[ScientificContributor]:
        """Look up a contributor by name."""
        return self._contributors.get(name)

    def list_all(self) -> list[ScientificContributor]:
        """Return all contributors."""
        return list(self._contributors.values())

    def list_by_domain(self, domain: str) -> list[ScientificContributor]:
        """Return contributors in a given domain."""
        return [c for c in self._contributors.values()
                if c.domain.lower() == domain.lower()]

    def find_by_equation(self, equation_name: str) -> list[ScientificContributor]:
        """Find contributors linked to a given equation."""
        return [c for c in self._contributors.values()
                if equation_name in c.key_equations]

    def link_claim(self, contributor_name: str, claim_id: int):
        """Link a claim node ID to a contributor."""
        c = self._contributors.get(contributor_name)
        if c and claim_id not in c.linked_claim_ids:
            c.linked_claim_ids.append(claim_id)
            c.compute_hash()

    def link_equation(self, contributor_name: str, equation_id: int):
        """Link an equation proof ID to a contributor."""
        c = self._contributors.get(contributor_name)
        if c and equation_id not in c.linked_equation_ids:
            c.linked_equation_ids.append(equation_id)
            c.compute_hash()

    def save_all_to_db(self) -> int:
        """Save all contributors to the scientific_registry table."""
        from src.database import insert_row
        saved = 0
        for c in self._contributors.values():
            try:
                insert_row("scientific_registry", {
                    "name": c.name,
                    "domain": c.domain,
                    "birth_year": c.birth_year,
                    "death_year": c.death_year,
                    "nationality": c.nationality,
                    "core_contributions": json.dumps(c.core_contributions),
                    "key_equations": json.dumps(c.key_equations),
                    "publication_links": json.dumps(c.publications),
                    "modern_applications": json.dumps(c.modern_applications),
                    "linked_claim_ids": json.dumps(c.linked_claim_ids),
                    "linked_equation_ids": json.dumps(c.linked_equation_ids),
                    "citation_count": c.citation_count,
                    "sha256_hash": c.sha256_hash,
                    "created_at": datetime.now(timezone.utc).isoformat(),
                })
                saved += 1
            except Exception as exc:
                log.debug("Failed to save contributor '%s': %s", c.name, exc)
        log.info("Saved %d contributors to database", saved)
        return saved

    def save_one_to_db(self, name: str) -> Optional[int]:
        """Save a single contributor to the database."""
        c = self._contributors.get(name)
        if c is None:
            return None
        from src.database import insert_row
        return insert_row("scientific_registry", {
            "name": c.name,
            "domain": c.domain,
            "birth_year": c.birth_year,
            "death_year": c.death_year,
            "nationality": c.nationality,
            "core_contributions": json.dumps(c.core_contributions),
            "key_equations": json.dumps(c.key_equations),
            "publication_links": json.dumps(c.publications),
            "modern_applications": json.dumps(c.modern_applications),
            "linked_claim_ids": json.dumps(c.linked_claim_ids),
            "linked_equation_ids": json.dumps(c.linked_equation_ids),
            "citation_count": c.citation_count,
            "sha256_hash": c.sha256_hash,
            "created_at": datetime.now(timezone.utc).isoformat(),
        })

    def summary(self) -> dict:
        """Return summary statistics."""
        domains = {}
        for c in self._contributors.values():
            domains[c.domain] = domains.get(c.domain, 0) + 1
        return {
            "total_contributors": len(self._contributors),
            "domains": domains,
            "total_equations_linked": sum(
                len(c.key_equations) for c in self._contributors.values()
            ),
        }
