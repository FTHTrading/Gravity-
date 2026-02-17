"""
Missing Factor Detector – Detect omitted constants, non-normalized coefficients,
dimensional inconsistencies, and implicit assumptions in equations.

Phase VII-A: Mathematical Expansion

Capabilities:
  - Detect omitted physical constants (G, c, ħ, etc.)
  - Detect non-normalized coefficients
  - Detect dimensional inconsistency
  - Detect implicit assumptions (normalization, unit systems)
  - Compare against canonical reference forms
"""

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

import sympy
from sympy import Symbol, symbols, simplify, Rational

from src.logger import get_logger
from src.math.equation_parser import EquationParser, PHYSICAL_CONSTANTS
from src.math.dimensional_analyzer import (
    DimensionalAnalyzer, SYMBOL_DIMENSIONS, Dimension,
)

log = get_logger(__name__)


# ── Canonical Reference Forms ────────────────────────────────────────────────

CANONICAL_EQUATIONS = {
    "newton_gravity": {
        "expr": "G*m1*m2/r**2",
        "required_constants": ["G"],
        "dimension": "force",
        "description": "Newton's law of universal gravitation",
    },
    "einstein_energy": {
        "expr": "m*c**2",
        "required_constants": ["c"],
        "dimension": "energy",
        "description": "Einstein mass-energy equivalence",
    },
    "einstein_field": {
        "expr": "8*pi*G/c**4",
        "required_constants": ["G", "c"],
        "dimension": "coupling",
        "description": "Einstein field equation coupling constant",
    },
    "maxwell_gauss": {
        "expr": "rho/epsilon_0",
        "required_constants": ["epsilon_0"],
        "dimension": "field_divergence",
        "description": "Gauss's law for electric fields",
    },
    "schrodinger": {
        "expr": "hbar",
        "required_constants": ["hbar"],
        "dimension": "action",
        "description": "Schrödinger equation (reduced Planck constant)",
    },
    "coulomb": {
        "expr": "q1*q2/(4*pi*epsilon_0*r**2)",
        "required_constants": ["epsilon_0"],
        "dimension": "force",
        "description": "Coulomb's law",
    },
    "gravitational_pe": {
        "expr": "-G*M*m/r",
        "required_constants": ["G"],
        "dimension": "energy",
        "description": "Gravitational potential energy",
    },
    "escape_velocity": {
        "expr": "(2*G*M/r)**(1/2)",
        "required_constants": ["G"],
        "dimension": "velocity",
        "description": "Escape velocity",
    },
    "planck_energy": {
        "expr": "h*nu",
        "required_constants": ["h"],
        "dimension": "energy",
        "description": "Planck-Einstein relation",
    },
    "de_broglie": {
        "expr": "h/(m*v)",
        "required_constants": ["h"],
        "dimension": "length",
        "description": "de Broglie wavelength",
    },
    "friedmann": {
        "expr": "8*pi*G*rho/3",
        "required_constants": ["G"],
        "dimension": "inverse_time_squared",
        "description": "Friedmann equation RHS",
    },
}

# Known constant symbols
KNOWN_CONSTANTS = set(PHYSICAL_CONSTANTS.keys())


@dataclass
class MissingFactorReport:
    """Report from missing factor detection analysis."""
    equation_name: str
    original_expr: str
    missing_constants: list = field(default_factory=list)
    redundant_terms: list = field(default_factory=list)
    dimension_mismatch: list = field(default_factory=list)
    scaling_inconsistency: list = field(default_factory=list)
    implicit_assumptions: list = field(default_factory=list)
    non_normalized: list = field(default_factory=list)
    canonical_comparison: Optional[str] = None
    structural_deviation: Optional[str] = None
    severity: str = "info"  # info, warning, error
    sha256_hash: str = ""

    def to_dict(self) -> dict:
        d = {
            "equation_name": self.equation_name,
            "original_expr": self.original_expr,
            "missing_constants": self.missing_constants,
            "redundant_terms": self.redundant_terms,
            "dimension_mismatch": self.dimension_mismatch,
            "scaling_inconsistency": self.scaling_inconsistency,
            "implicit_assumptions": self.implicit_assumptions,
            "non_normalized": self.non_normalized,
            "canonical_comparison": self.canonical_comparison,
            "structural_deviation": self.structural_deviation,
            "severity": self.severity,
            "sha256_hash": self.sha256_hash,
        }
        return d

    def compute_hash(self):
        """Compute deterministic SHA-256 of the report."""
        canonical = json.dumps(self.to_dict(), sort_keys=True, default=str)
        self.sha256_hash = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
        return self.sha256_hash


class MissingFactorDetector:
    """
    Detect omitted constants, non-normalized coefficients, dimensional
    inconsistencies, and implicit assumptions in equations.
    """

    def __init__(self):
        self.parser = EquationParser()
        self.dim_analyzer = DimensionalAnalyzer()

    def detect(self, equation_str: str, name: str = "unnamed",
               expected_dimension: str = None) -> MissingFactorReport:
        """
        Analyze an equation for missing factors.

        Args:
            equation_str: Plain text equation (e.g., 'F = m1*m2/r**2')
            name: Human-readable equation name
            expected_dimension: Expected physical dimension type

        Returns:
            MissingFactorReport with all detected issues
        """
        report = MissingFactorReport(
            equation_name=name,
            original_expr=equation_str,
        )

        # Parse the equation
        parsed = self.parser.parse_plaintext(equation_str, name=name)
        if parsed.parse_error:
            report.severity = "error"
            report.dimension_mismatch.append(
                f"Parse error: {parsed.parse_error}"
            )
            report.compute_hash()
            return report

        equation_symbols = set(parsed.symbols_found)

        # 1. Detect missing constants
        self._detect_missing_constants(report, equation_symbols, name)

        # 2. Detect non-normalized coefficients
        self._detect_non_normalized(report, parsed)

        # 3. Dimensional consistency check
        self._check_dimensions(report, parsed, expected_dimension)

        # 4. Detect implicit assumptions
        self._detect_implicit_assumptions(report, equation_symbols)

        # 5. Compare against canonical form
        self._compare_canonical(report, parsed, name)

        # 6. Detect redundant terms
        self._detect_redundant_terms(report, parsed)

        # Determine severity
        if report.missing_constants or report.dimension_mismatch:
            report.severity = "warning"
        if len(report.missing_constants) > 2 or len(report.dimension_mismatch) > 1:
            report.severity = "error"

        report.compute_hash()
        log.info("Missing factor analysis for '%s': severity=%s, missing=%d, "
                 "mismatch=%d, assumptions=%d",
                 name, report.severity, len(report.missing_constants),
                 len(report.dimension_mismatch), len(report.implicit_assumptions))

        return report

    def detect_batch(self, equations: dict) -> list:
        """
        Analyze multiple equations.

        Args:
            equations: dict of {name: equation_str}

        Returns:
            List of MissingFactorReport
        """
        return [self.detect(expr, name=name) for name, expr in equations.items()]

    def _detect_missing_constants(self, report, equation_symbols, name):
        """Check if expected physical constants are present."""
        # Check against canonical equations
        for canon_name, canon in CANONICAL_EQUATIONS.items():
            if canon_name in name.lower() or name.lower() in canon_name:
                for const in canon["required_constants"]:
                    if const not in equation_symbols:
                        report.missing_constants.append({
                            "constant": const,
                            "description": PHYSICAL_CONSTANTS.get(
                                const, {}
                            ).get("name", const),
                            "canonical_ref": canon_name,
                            "reason": f"Canonical form '{canon_name}' requires {const}",
                        })

        # General heuristic: gravity equations should have G
        gravity_hints = {"gravity", "gravitational", "newton", "kepler"}
        if any(h in name.lower() for h in gravity_hints):
            if "G" not in equation_symbols:
                report.missing_constants.append({
                    "constant": "G",
                    "description": "Gravitational constant",
                    "reason": "Gravity equation without G may assume G=1 normalization",
                })

        # Electrostatic equations should have epsilon_0 or k_e
        em_hints = {"coulomb", "electric", "electromagnetic", "maxwell"}
        if any(h in name.lower() for h in em_hints):
            if "epsilon_0" not in equation_symbols and "k_e" not in equation_symbols:
                report.missing_constants.append({
                    "constant": "epsilon_0",
                    "description": "Vacuum permittivity",
                    "reason": "EM equation without ε₀ may use Gaussian units",
                })

    def _detect_non_normalized(self, report, parsed):
        """Detect coefficients that aren't properly normalized."""
        expr = self.parser.get_expression(parsed)
        if expr is None:
            return

        # Check for large integer coefficients (may indicate missing normalization)
        try:
            for atom in expr.atoms(sympy.Integer):
                val = int(atom)
                if abs(val) > 100 and val not in (0, 1, -1):
                    report.non_normalized.append({
                        "coefficient": str(val),
                        "reason": f"Large integer coefficient {val} may indicate "
                                  "unnormalized expression or embedded constant",
                    })

            # Check for irrational-looking rationals
            for atom in expr.atoms(sympy.Rational):
                if atom.q > 100:
                    report.non_normalized.append({
                        "coefficient": str(atom),
                        "reason": f"Complex rational {atom} may indicate "
                                  "missing normalization factor",
                    })
        except Exception:
            pass

    def _check_dimensions(self, report, parsed, expected_dimension):
        """Run dimensional analysis and report mismatches."""
        try:
            dim_report = self.dim_analyzer.analyze(parsed)
            if dim_report and dim_report.status == "invalid":
                report.dimension_mismatch.append({
                    "lhs_dimension": dim_report.lhs_dimension or "unknown",
                    "rhs_dimension": dim_report.rhs_dimension or "unknown",
                    "errors": dim_report.errors,
                })
            if dim_report and dim_report.unknown_symbols:
                for sym in dim_report.unknown_symbols:
                    if sym not in KNOWN_CONSTANTS:
                        report.scaling_inconsistency.append({
                            "symbol": sym,
                            "reason": f"Symbol '{sym}' has unknown dimensions; "
                                      "cannot verify dimensional consistency",
                        })
        except Exception as exc:
            log.debug("Dimensional check error: %s", exc)

    def _detect_implicit_assumptions(self, report, equation_symbols):
        """Detect implicit assumptions like unit normalization."""
        # Check for natural units (c=1, hbar=1, G=1)
        if "c" not in equation_symbols and "hbar" not in equation_symbols:
            # Could be natural units
            report.implicit_assumptions.append({
                "type": "possible_natural_units",
                "description": "Equation may use natural units (c=1, ℏ=1)",
            })

        # Check for SI vs CGS indicators
        if "epsilon_0" not in equation_symbols and "mu_0" not in equation_symbols:
            if any(s in equation_symbols for s in ["E", "B", "q", "rho"]):
                report.implicit_assumptions.append({
                    "type": "possible_gaussian_units",
                    "description": "EM-like symbols without ε₀/μ₀ may use Gaussian units",
                })

    def _compare_canonical(self, report, parsed, name):
        """Compare against canonical equation forms."""
        for canon_name, canon in CANONICAL_EQUATIONS.items():
            if canon_name in name.lower() or name.lower() in canon_name:
                report.canonical_comparison = canon_name
                try:
                    canon_parsed = self.parser.parse_plaintext(
                        canon["expr"], name=f"canonical_{canon_name}"
                    )
                    # Compare symbol sets
                    input_syms = set(parsed.symbols_found)
                    canon_syms = set(canon_parsed.symbols_found)
                    extra = input_syms - canon_syms
                    missing = canon_syms - input_syms
                    if missing:
                        report.structural_deviation = (
                            f"Missing symbols vs canonical: {missing}; "
                            f"Extra symbols: {extra}"
                        )
                except Exception:
                    pass
                break

    def _detect_redundant_terms(self, report, parsed):
        """Detect algebraically redundant terms."""
        expr = self.parser.get_expression(parsed)
        if expr is None:
            return
        try:
            simplified = simplify(expr)
            original_ops = sympy.count_ops(expr, visual=False)
            simplified_ops = sympy.count_ops(simplified, visual=False)
            if simplified_ops < original_ops * 0.7:
                report.redundant_terms.append({
                    "original_ops": int(original_ops),
                    "simplified_ops": int(simplified_ops),
                    "reason": "Expression can be significantly simplified; "
                              "may contain redundant terms",
                })
        except Exception:
            pass

    def save_to_db(self, report: MissingFactorReport) -> int:
        """Save analysis to equation_optimization table."""
        from src.database import insert_row
        return insert_row("equation_optimization", {
            "equation_name": report.equation_name,
            "original_expr": report.original_expr,
            "missing_factors": json.dumps(report.missing_constants, default=str),
            "dimension_status": report.severity,
            "notes": json.dumps(report.to_dict(), sort_keys=True, default=str),
            "sha256_hash": report.sha256_hash,
            "optimized_at": datetime.now(timezone.utc).isoformat(),
        })
