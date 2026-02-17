"""
Canonical Reference Map – Reference library of fundamental physics equations
with structural metadata for comparison and deviation detection.

Phase VII-A: Mathematical Expansion

Provides:
  - Canonical equations from fundamental physics
  - SHA-256 fingerprints for each canonical form
  - Dimensional vectors
  - Reference metadata and linked contributors
  - Structural deviation detection against user-supplied equations
"""

import hashlib
import json
from dataclasses import dataclass, field
from typing import Optional

import sympy
from sympy import symbols, Symbol, latex, srepr, simplify, count_ops
from sympy.parsing.sympy_parser import (
    parse_expr, standard_transformations,
    implicit_multiplication_application, convert_xor,
)

from src.logger import get_logger

log = get_logger(__name__)

SAFE_TRANSFORMS = standard_transformations + (
    implicit_multiplication_application,
    convert_xor,
)


@dataclass
class CanonicalEquation:
    """A canonical physics equation with metadata."""
    name: str
    category: str
    plaintext: str
    latex_form: str = ""
    sympy_repr: str = ""
    dimension: str = ""
    domain: str = "physics"
    contributors: list = field(default_factory=list)
    sha256: str = ""
    symbol_count: int = 0
    operation_count: int = 0
    references: list = field(default_factory=list)
    modern_applications: list = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "category": self.category,
            "plaintext": self.plaintext,
            "latex_form": self.latex_form,
            "dimension": self.dimension,
            "domain": self.domain,
            "contributors": self.contributors,
            "sha256": self.sha256,
            "symbol_count": self.symbol_count,
            "operation_count": self.operation_count,
            "references": self.references,
            "modern_applications": self.modern_applications,
        }


@dataclass
class DeviationReport:
    """Report comparing an equation against its canonical form."""
    equation_name: str
    canonical_name: str
    is_structurally_equivalent: bool = False
    missing_symbols: list = field(default_factory=list)
    extra_symbols: list = field(default_factory=list)
    complexity_difference: int = 0
    algebraic_equivalent: bool = False
    notes: list = field(default_factory=list)
    sha256_hash: str = ""

    def to_dict(self) -> dict:
        return {
            "equation_name": self.equation_name,
            "canonical_name": self.canonical_name,
            "is_structurally_equivalent": self.is_structurally_equivalent,
            "missing_symbols": self.missing_symbols,
            "extra_symbols": self.extra_symbols,
            "complexity_difference": self.complexity_difference,
            "algebraic_equivalent": self.algebraic_equivalent,
            "notes": self.notes,
            "sha256_hash": self.sha256_hash,
        }


# ── Canonical Equations Registry ─────────────────────────────────────────────

def _build_canonical(name, category, plaintext, dimension, domain,
                     contributors, refs=None, apps=None):
    """Build a CanonicalEquation with computed metadata."""
    eq = CanonicalEquation(
        name=name,
        category=category,
        plaintext=plaintext,
        dimension=dimension,
        domain=domain,
        contributors=contributors,
        references=refs or [],
        modern_applications=apps or [],
    )
    # Parse and compute metadata
    local_dict = {}
    for s in ["G", "c", "h", "hbar", "k_B", "e", "m_e", "m_p",
              "epsilon_0", "mu_0", "g", "M", "m", "r", "F", "E", "V",
              "T", "P", "L", "v", "a", "t", "x", "y", "z", "q",
              "rho", "sigma", "omega", "nu", "lambda_", "theta", "phi",
              "m1", "m2", "q1", "q2", "R", "S", "H", "U", "W",
              "A", "B", "n", "pi", "k", "alpha", "mu",
              "a_dot", "partial_mu", "gamma"]:
        local_dict[s] = Symbol(s.rstrip("_"))
    local_dict["pi"] = sympy.pi

    try:
        expr = parse_expr(plaintext, local_dict=local_dict,
                          transformations=SAFE_TRANSFORMS, evaluate=False)
        eq.sympy_repr = srepr(expr)
        eq.latex_form = latex(expr)
        eq.symbol_count = len(expr.free_symbols)
        eq.operation_count = int(count_ops(expr, visual=False))
        eq.sha256 = hashlib.sha256(eq.sympy_repr.encode("utf-8")).hexdigest()
    except Exception as exc:
        log.debug("Failed to parse canonical '%s': %s", name, exc)
        eq.sha256 = hashlib.sha256(plaintext.encode("utf-8")).hexdigest()

    return eq


CANONICAL_REGISTRY: list[CanonicalEquation] = [
    _build_canonical(
        "newton_gravity", "mechanics",
        "G*m1*m2/r**2",
        "M L T^-2 (force)", "physics",
        ["Isaac Newton"],
        refs=["Principia Mathematica, 1687"],
        apps=["Orbital mechanics", "Celestial navigation", "Satellite dynamics"],
    ),
    _build_canonical(
        "einstein_energy", "relativity",
        "m*c**2",
        "M L^2 T^-2 (energy)", "physics",
        ["Albert Einstein"],
        refs=["Annalen der Physik, 1905"],
        apps=["Nuclear energy", "Particle physics", "PET scans"],
    ),
    _build_canonical(
        "einstein_field_coupling", "relativity",
        "8*pi*G/c**4",
        "coupling constant", "physics",
        ["Albert Einstein"],
        refs=["Annalen der Physik, 1915"],
        apps=["Gravitational wave detection", "Black hole physics", "Cosmology"],
    ),
    _build_canonical(
        "maxwell_gauss_electric", "electromagnetism",
        "rho/epsilon_0",
        "field divergence", "physics",
        ["James Clerk Maxwell", "Carl Friedrich Gauss"],
        refs=["A Treatise on Electricity and Magnetism, 1873"],
        apps=["Electrostatics", "Capacitor design", "Semiconductor physics"],
    ),
    _build_canonical(
        "schrodinger_energy", "quantum_mechanics",
        "hbar*omega",
        "M L^2 T^-2 (energy)", "physics",
        ["Erwin Schrödinger"],
        refs=["Annalen der Physik, 1926"],
        apps=["Quantum computing", "Semiconductor design", "MRI"],
    ),
    _build_canonical(
        "dirac_equation_coupling", "quantum_mechanics",
        "m*c",
        "M L T^-1 (momentum)", "physics",
        ["Paul Dirac"],
        refs=["Proc. Royal Society A, 1928"],
        apps=["Antimatter prediction", "Quantum field theory", "Spintronics"],
    ),
    _build_canonical(
        "coulomb_force", "electromagnetism",
        "q1*q2/(4*pi*epsilon_0*r**2)",
        "M L T^-2 (force)", "physics",
        ["Charles-Augustin de Coulomb"],
        refs=["Histoire de l'Académie Royale des Sciences, 1785"],
        apps=["Electrostatics", "Molecular chemistry", "Plasma physics"],
    ),
    _build_canonical(
        "gravitational_potential", "mechanics",
        "-G*M*m/r",
        "M L^2 T^-2 (energy)", "physics",
        ["Isaac Newton"],
        apps=["Orbital energy", "Escape velocity calculations"],
    ),
    _build_canonical(
        "kinetic_energy", "mechanics",
        "m*v**2/2",
        "M L^2 T^-2 (energy)", "physics",
        ["Gottfried Wilhelm Leibniz", "Émilie du Châtelet"],
        apps=["Classical mechanics", "Engineering dynamics"],
    ),
    _build_canonical(
        "planck_einstein", "quantum_mechanics",
        "h*nu",
        "M L^2 T^-2 (energy)", "physics",
        ["Max Planck", "Albert Einstein"],
        refs=["Verhandlungen der Deutschen Physikalischen Gesellschaft, 1900"],
        apps=["Spectroscopy", "Laser physics", "Photovoltaics"],
    ),
    _build_canonical(
        "de_broglie_wavelength", "quantum_mechanics",
        "h/(m*v)",
        "L (length)", "physics",
        ["Louis de Broglie"],
        refs=["Annales de Physique, 1925"],
        apps=["Electron microscopy", "Neutron diffraction"],
    ),
    _build_canonical(
        "friedmann_expansion", "cosmology",
        "8*pi*G*rho/3",
        "T^-2", "physics",
        ["Alexander Friedmann"],
        refs=["Zeitschrift für Physik, 1922"],
        apps=["Big Bang cosmology", "Dark energy models"],
    ),
    _build_canonical(
        "noether_current", "theoretical_physics",
        "L",
        "action density", "physics",
        ["Emmy Noether"],
        refs=["Nachrichten von der Gesellschaft der Wissenschaften, 1918"],
        apps=["Conservation laws", "Gauge theory", "Particle physics"],
    ),
    _build_canonical(
        "shannon_entropy", "information_theory",
        "-n*k*x",
        "information measure", "mathematics",
        ["Claude Shannon"],
        refs=["Bell System Technical Journal, 1948"],
        apps=["Data compression", "Cryptography", "Machine learning"],
    ),
    _build_canonical(
        "boltzmann_entropy", "thermodynamics",
        "k_B*n",
        "M L^2 T^-2 K^-1 (entropy)", "physics",
        ["Ludwig Boltzmann"],
        refs=["Vorlesungen über Gastheorie, 1896"],
        apps=["Statistical mechanics", "Thermodynamics", "Materials science"],
    ),
]


# Build lookup dict
CANONICAL_BY_NAME = {eq.name: eq for eq in CANONICAL_REGISTRY}
CANONICAL_BY_CATEGORY = {}
for eq in CANONICAL_REGISTRY:
    CANONICAL_BY_CATEGORY.setdefault(eq.category, []).append(eq)


class CanonicalReferenceMap:
    """
    Compare equations against the canonical reference library.
    """

    def __init__(self):
        self.registry = CANONICAL_REGISTRY
        self.by_name = CANONICAL_BY_NAME

    def get_canonical(self, name: str) -> Optional[CanonicalEquation]:
        """Look up a canonical equation by name."""
        return self.by_name.get(name)

    def list_all(self) -> list[CanonicalEquation]:
        """Return all canonical equations."""
        return list(self.registry)

    def list_by_category(self, category: str) -> list[CanonicalEquation]:
        """Return canonical equations in a given category."""
        return CANONICAL_BY_CATEGORY.get(category, [])

    def compare(self, equation_str: str, canonical_name: str,
                name: str = "comparison") -> DeviationReport:
        """
        Compare a user-supplied equation against a canonical form.

        Args:
            equation_str: Plain text equation to compare
            canonical_name: Name of the canonical equation
            name: Label for this comparison

        Returns:
            DeviationReport with structural deviation analysis
        """
        report = DeviationReport(
            equation_name=name,
            canonical_name=canonical_name,
        )

        canonical = self.by_name.get(canonical_name)
        if canonical is None:
            report.notes.append(f"Unknown canonical equation: {canonical_name}")
            report.sha256_hash = hashlib.sha256(
                name.encode("utf-8")
            ).hexdigest()
            return report

        # Parse both
        local_dict = {}
        for s in ["G", "c", "h", "hbar", "k_B", "e", "m_e", "m_p",
                   "epsilon_0", "mu_0", "g", "M", "m", "r", "F", "E", "V",
                   "T", "P", "L", "v", "a", "t", "x", "y", "z", "q",
                   "rho", "sigma", "omega", "nu", "lambda_", "theta",
                   "m1", "m2", "q1", "q2", "n", "pi", "k",
                   "mu", "alpha", "beta", "gamma", "delta"]:
            local_dict[s] = Symbol(s.rstrip("_"))
        local_dict["pi"] = sympy.pi

        try:
            user_expr = parse_expr(equation_str, local_dict=local_dict,
                                   transformations=SAFE_TRANSFORMS, evaluate=False)
            canon_expr = parse_expr(canonical.plaintext, local_dict=local_dict,
                                    transformations=SAFE_TRANSFORMS, evaluate=False)

            # Symbol comparison
            user_syms = {str(s) for s in user_expr.free_symbols}
            canon_syms = {str(s) for s in canon_expr.free_symbols}
            report.missing_symbols = sorted(canon_syms - user_syms)
            report.extra_symbols = sorted(user_syms - canon_syms)

            # Structural equivalence (same symbol set)
            report.is_structurally_equivalent = (
                user_syms == canon_syms
            )

            # Algebraic equivalence
            try:
                diff_expr = simplify(user_expr - canon_expr)
                report.algebraic_equivalent = (diff_expr == 0)
            except Exception:
                report.algebraic_equivalent = False

            # Complexity difference
            user_ops = int(count_ops(user_expr, visual=False))
            canon_ops = int(count_ops(canon_expr, visual=False))
            report.complexity_difference = user_ops - canon_ops

            if report.missing_symbols:
                report.notes.append(
                    f"Missing symbols from canonical: {report.missing_symbols}"
                )
            if report.extra_symbols:
                report.notes.append(
                    f"Extra symbols not in canonical: {report.extra_symbols}"
                )

        except Exception as exc:
            report.notes.append(f"Comparison error: {exc}")

        canonical_str = json.dumps(report.to_dict(), sort_keys=True, default=str)
        report.sha256_hash = hashlib.sha256(
            canonical_str.encode("utf-8")
        ).hexdigest()

        return report

    def find_closest(self, equation_str: str) -> Optional[tuple]:
        """
        Find the canonical equation most similar to the given expression.

        Returns:
            (CanonicalEquation, DeviationReport) or None
        """
        best_match = None
        best_score = -1

        for canon in self.registry:
            report = self.compare(equation_str, canon.name)
            # Score: fewer missing + fewer extra = better match
            total_diff = len(report.missing_symbols) + len(report.extra_symbols)
            if report.algebraic_equivalent:
                score = 1000  # Perfect match
            else:
                score = max(0, 20 - total_diff - abs(report.complexity_difference))

            if score > best_score:
                best_score = score
                best_match = (canon, report)

        return best_match
