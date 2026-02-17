"""
Stability Analyzer – Jacobian computation, eigenvalue classification,
sensitivity analysis, and Lyapunov exponent estimation.

Phase VII-A: Mathematical Expansion

Capabilities:
  - Jacobian matrix computation for systems of equations
  - Eigenvalue-based stability classification
  - Sensitivity analysis (partial derivatives)
  - Lyapunov exponent estimation
  - Hash all outputs deterministically
"""

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

import sympy
from sympy import (
    Symbol, symbols, Matrix, simplify, diff,
    Abs, re as sym_re, im as sym_im,
    oo, latex, srepr,
)

from src.logger import get_logger
from src.math.equation_parser import EquationParser

log = get_logger(__name__)


# ── Stability Classifications ────────────────────────────────────────────────
STABILITY_CLASSES = {
    "asymptotically_stable": "All eigenvalues have negative real parts",
    "stable": "All eigenvalues have non-positive real parts",
    "marginally_stable": "At least one eigenvalue on imaginary axis",
    "unstable": "At least one eigenvalue with positive real part",
    "saddle": "Mixed sign eigenvalues",
    "center": "All eigenvalues purely imaginary (non-zero)",
    "unknown": "Cannot determine stability",
}


@dataclass
class StabilityReport:
    """Report from stability analysis."""
    equation_name: str
    system_dimension: int = 0
    jacobian_str: str = ""
    eigenvalues: list = field(default_factory=list)
    eigenvalue_classification: list = field(default_factory=list)
    stability_class: str = "unknown"
    stability_description: str = ""
    sensitivity: dict = field(default_factory=dict)
    lyapunov_exponent: Optional[float] = None
    is_stable: bool = False
    notes: list = field(default_factory=list)
    sha256_hash: str = ""

    def to_dict(self) -> dict:
        return {
            "equation_name": self.equation_name,
            "system_dimension": self.system_dimension,
            "jacobian_str": self.jacobian_str,
            "eigenvalues": [str(e) for e in self.eigenvalues],
            "eigenvalue_classification": self.eigenvalue_classification,
            "stability_class": self.stability_class,
            "stability_description": self.stability_description,
            "sensitivity": {k: str(v) for k, v in self.sensitivity.items()},
            "lyapunov_exponent": self.lyapunov_exponent,
            "is_stable": self.is_stable,
            "notes": self.notes,
            "sha256_hash": self.sha256_hash,
        }

    def compute_hash(self):
        """Compute deterministic SHA-256."""
        canonical = json.dumps(self.to_dict(), sort_keys=True, default=str)
        self.sha256_hash = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
        return self.sha256_hash


class StabilityAnalyzer:
    """
    Analyze mathematical stability of equations and dynamical systems.
    """

    def __init__(self):
        self.parser = EquationParser()

    def analyze(self, expressions: list, variables: list = None,
                name: str = "unnamed") -> StabilityReport:
        """
        Analyze stability of a system of expressions.

        Args:
            expressions: List of SymPy expressions or plain text strings
                         representing dx_i/dt = f_i(x)
            variables: List of state variable names.
                       If None, auto-detected from expressions.
            name: Human-readable name for the system

        Returns:
            StabilityReport with full analysis
        """
        report = StabilityReport(equation_name=name)

        # Parse expressions if given as strings
        sympy_exprs = []
        for expr in expressions:
            if isinstance(expr, str):
                parsed = self.parser.parse_plaintext(expr, name=name)
                e = self.parser.get_expression(parsed)
                if e is not None:
                    sympy_exprs.append(e)
            else:
                sympy_exprs.append(expr)

        if not sympy_exprs:
            report.notes.append("No valid expressions to analyze")
            report.compute_hash()
            return report

        report.system_dimension = len(sympy_exprs)

        # Auto-detect variables if not provided
        if variables is None:
            all_syms = set()
            for e in sympy_exprs:
                all_syms |= e.free_symbols
            variables = sorted([str(s) for s in all_syms])

        sym_vars = [Symbol(v) for v in variables]

        # Compute Jacobian
        jacobian = self._compute_jacobian(sympy_exprs, sym_vars)
        report.jacobian_str = str(jacobian)

        # Compute eigenvalues
        eigenvalues = self._compute_eigenvalues(jacobian)
        report.eigenvalues = eigenvalues

        # Classify eigenvalues
        report.eigenvalue_classification = self._classify_eigenvalues(eigenvalues)

        # Overall stability classification
        report.stability_class = self._classify_stability(eigenvalues)
        report.stability_description = STABILITY_CLASSES.get(
            report.stability_class, "Unknown"
        )
        report.is_stable = report.stability_class in (
            "asymptotically_stable", "stable"
        )

        # Sensitivity analysis
        report.sensitivity = self._sensitivity_analysis(sympy_exprs, sym_vars)

        # Lyapunov exponent (largest real part of eigenvalues)
        report.lyapunov_exponent = self._estimate_lyapunov(eigenvalues)

        report.compute_hash()
        log.info("Stability analysis '%s': class=%s, dim=%d, eigenvalues=%d",
                 name, report.stability_class, report.system_dimension,
                 len(eigenvalues))

        return report

    def analyze_single(self, expr_str: str, name: str = "unnamed") -> StabilityReport:
        """
        Analyze stability of a single expression (1D system).

        For a scalar ODE dx/dt = f(x), stability at equilibrium requires f'(x*) < 0.
        """
        return self.analyze([expr_str], name=name)

    def _compute_jacobian(self, expressions, variables) -> Matrix:
        """Compute the Jacobian matrix J[i,j] = ∂f_i/∂x_j."""
        n = len(expressions)
        m = len(variables)
        J = Matrix(n, m, lambda i, j: diff(expressions[i], variables[j]))
        return J

    def _compute_eigenvalues(self, jacobian: Matrix) -> list:
        """Compute eigenvalues of the Jacobian."""
        try:
            # For symbolic matrices, eigenvals returns {eigenval: multiplicity}
            eig_dict = jacobian.eigenvals()
            eigenvalues = []
            for eig, mult in eig_dict.items():
                for _ in range(mult):
                    eigenvalues.append(eig)
            return eigenvalues
        except Exception as exc:
            log.debug("Eigenvalue computation failed: %s", exc)
            return []

    def _classify_eigenvalues(self, eigenvalues) -> list:
        """Classify each eigenvalue by its characteristics."""
        classifications = []
        for eig in eigenvalues:
            try:
                # Try to get numeric value
                eig_complex = complex(eig)
                real_part = eig_complex.real
                imag_part = eig_complex.imag

                if abs(imag_part) < 1e-12:
                    if real_part < -1e-12:
                        cls = "negative_real"
                    elif real_part > 1e-12:
                        cls = "positive_real"
                    else:
                        cls = "zero"
                else:
                    if real_part < -1e-12:
                        cls = "complex_negative"
                    elif real_part > 1e-12:
                        cls = "complex_positive"
                    else:
                        cls = "purely_imaginary"
            except (TypeError, ValueError):
                # Symbolic eigenvalue
                cls = "symbolic"

            classifications.append({
                "eigenvalue": str(eig),
                "classification": cls,
            })
        return classifications

    def _classify_stability(self, eigenvalues) -> str:
        """Determine overall stability from eigenvalue spectrum."""
        if not eigenvalues:
            return "unknown"

        has_positive = False
        has_negative = False
        has_zero = False
        has_imaginary = False
        all_numeric = True

        for eig in eigenvalues:
            try:
                eig_complex = complex(eig)
                real_part = eig_complex.real
                imag_part = eig_complex.imag

                if abs(real_part) < 1e-12 and abs(imag_part) > 1e-12:
                    has_imaginary = True
                elif real_part > 1e-12:
                    has_positive = True
                elif real_part < -1e-12:
                    has_negative = True
                else:
                    has_zero = True
            except (TypeError, ValueError):
                all_numeric = False

        if not all_numeric:
            return "unknown"

        if has_positive and has_negative:
            return "saddle"
        if has_positive:
            return "unstable"
        if has_imaginary and not has_negative and not has_positive:
            return "center"
        if has_zero or has_imaginary:
            return "marginally_stable"
        if has_negative and not has_positive and not has_zero:
            return "asymptotically_stable"

        return "stable"

    def _sensitivity_analysis(self, expressions, variables) -> dict:
        """Compute sensitivity ∂f_i/∂x_j at origin."""
        sensitivity = {}
        for i, expr in enumerate(expressions):
            for j, var in enumerate(variables):
                deriv = diff(expr, var)
                key = f"df{i}/d{var}"
                sensitivity[key] = str(deriv)
        return sensitivity

    def _estimate_lyapunov(self, eigenvalues) -> Optional[float]:
        """Estimate largest Lyapunov exponent (real part of dominant eigenvalue)."""
        if not eigenvalues:
            return None
        max_real = None
        for eig in eigenvalues:
            try:
                real_part = float(complex(eig).real)
                if max_real is None or real_part > max_real:
                    max_real = real_part
            except (TypeError, ValueError):
                continue
        return max_real

    def save_to_db(self, report: StabilityReport) -> int:
        """Save stability report to equation_stability table."""
        from src.database import insert_row
        return insert_row("equation_stability", {
            "equation_name": report.equation_name,
            "jacobian_json": report.jacobian_str,
            "eigenvalues_json": json.dumps(
                [str(e) for e in report.eigenvalues], default=str
            ),
            "stability_class": report.stability_class,
            "sensitivity_json": json.dumps(report.sensitivity, default=str),
            "lyapunov_exponent": report.lyapunov_exponent,
            "is_stable": 1 if report.is_stable else 0,
            "notes": json.dumps(report.notes, default=str),
            "sha256_hash": report.sha256_hash,
            "computed_at": datetime.now(timezone.utc).isoformat(),
        })
