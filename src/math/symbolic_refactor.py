"""
Symbolic Refactor Engine – Algebraic Manipulation & Error Detection

Provides:
  - expand, factor, simplify, differentiate, integrate, solve
  - Series expansion
  - Canonical form comparison
  - Redundancy detection
  - Algebraic consistency checks
  - Nondimensionalization transform stubs
"""

from dataclasses import dataclass, field
from typing import Optional

import sympy

from src.logger import get_logger

log = get_logger(__name__)


@dataclass
class RefactorResult:
    """Result of a symbolic refactoring operation."""
    operation: str
    input_expr: str
    output_expr: str = ""
    sympy_input: Optional[object] = None
    sympy_output: Optional[object] = None
    is_equivalent: bool = True
    complexity_before: int = 0
    complexity_after: int = 0
    notes: list = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "operation": self.operation,
            "input": self.input_expr,
            "output": self.output_expr,
            "is_equivalent": self.is_equivalent,
            "complexity_before": self.complexity_before,
            "complexity_after": self.complexity_after,
            "notes": self.notes,
        }


@dataclass
class ConsistencyReport:
    """Report from algebraic consistency checking."""
    equation_name: str
    canonical_form: str
    is_consistent: bool = True
    equivalent_forms: list = field(default_factory=list)
    contradictions: list = field(default_factory=list)
    redundancies: list = field(default_factory=list)
    notes: list = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "equation_name": self.equation_name,
            "canonical_form": self.canonical_form,
            "is_consistent": self.is_consistent,
            "equivalent_forms": self.equivalent_forms,
            "contradictions": self.contradictions,
            "redundancies": self.redundancies,
            "notes": self.notes,
        }


class SymbolicRefactor:
    """
    Symbolic manipulation engine for equation forensics.

    Wraps SymPy's algebra engine with forensic-grade logging
    and equivalence tracking.
    """

    @staticmethod
    def _expr_complexity(expr) -> int:
        """Count nodes in sympy expression tree."""
        return expr.count_ops() if expr else 0

    def simplify(self, parsed_eq) -> RefactorResult:
        """Full simplification pipeline."""
        expr = _get_expr(parsed_eq)
        result = RefactorResult(
            operation="simplify",
            input_expr=str(expr),
            complexity_before=self._expr_complexity(expr),
        )
        simplified = sympy.simplify(expr)
        result.output_expr = str(simplified)
        result.sympy_output = simplified
        result.complexity_after = self._expr_complexity(simplified)
        result.is_equivalent = sympy.simplify(expr - simplified) == 0
        if result.complexity_after < result.complexity_before:
            result.notes.append(
                f"Reduced complexity from {result.complexity_before} "
                f"to {result.complexity_after}"
            )
        log.info("simplify: %s → %s", result.input_expr, result.output_expr)
        return result

    def expand(self, parsed_eq) -> RefactorResult:
        """Expand products and powers."""
        expr = _get_expr(parsed_eq)
        result = RefactorResult(
            operation="expand",
            input_expr=str(expr),
            complexity_before=self._expr_complexity(expr),
        )
        expanded = sympy.expand(expr)
        result.output_expr = str(expanded)
        result.sympy_output = expanded
        result.complexity_after = self._expr_complexity(expanded)
        result.is_equivalent = True
        log.info("expand: %s → %s", result.input_expr, result.output_expr)
        return result

    def factor(self, parsed_eq) -> RefactorResult:
        """Factor expression."""
        expr = _get_expr(parsed_eq)
        result = RefactorResult(
            operation="factor",
            input_expr=str(expr),
            complexity_before=self._expr_complexity(expr),
        )
        factored = sympy.factor(expr)
        result.output_expr = str(factored)
        result.sympy_output = factored
        result.complexity_after = self._expr_complexity(factored)
        result.is_equivalent = True
        log.info("factor: %s → %s", result.input_expr, result.output_expr)
        return result

    def differentiate(self, parsed_eq, var_name: str = "x") -> RefactorResult:
        """Differentiate expression with respect to a variable."""
        expr = _get_expr(parsed_eq)
        var = sympy.Symbol(var_name)
        result = RefactorResult(
            operation=f"diff(d/{var_name})",
            input_expr=str(expr),
            complexity_before=self._expr_complexity(expr),
        )
        derived = sympy.diff(expr, var)
        result.output_expr = str(derived)
        result.sympy_output = derived
        result.complexity_after = self._expr_complexity(derived)
        result.is_equivalent = False  # Derivative is a different expression
        result.notes.append(f"Differentiated with respect to {var_name}")
        log.info("diff(%s, %s) → %s", result.input_expr, var_name, result.output_expr)
        return result

    def integrate(self, parsed_eq, var_name: str = "x") -> RefactorResult:
        """Integrate expression with respect to a variable."""
        expr = _get_expr(parsed_eq)
        var = sympy.Symbol(var_name)
        result = RefactorResult(
            operation=f"integrate(d{var_name})",
            input_expr=str(expr),
            complexity_before=self._expr_complexity(expr),
        )
        integral = sympy.integrate(expr, var)
        result.output_expr = str(integral)
        result.sympy_output = integral
        result.complexity_after = self._expr_complexity(integral)
        result.is_equivalent = False
        result.notes.append(f"Integrated with respect to {var_name} (constant omitted)")
        log.info("integrate(%s, %s) → %s", result.input_expr, var_name, result.output_expr)
        return result

    def solve_for(self, parsed_eq, var_name: str = "x") -> RefactorResult:
        """Solve equation for a variable (requires is_equation)."""
        result = RefactorResult(
            operation=f"solve({var_name})",
            input_expr=str(parsed_eq.sympy_expr),
        )

        if not parsed_eq.is_equation or not parsed_eq.lhs or not parsed_eq.rhs:
            result.notes.append("Not an equation — cannot solve")
            result.output_expr = ""
            return result

        var = sympy.Symbol(var_name)
        equation = sympy.Eq(parsed_eq.lhs, parsed_eq.rhs)
        solutions = sympy.solve(equation, var)

        if solutions:
            result.output_expr = str(solutions)
            result.sympy_output = solutions
            result.notes.append(f"Found {len(solutions)} solution(s) for {var_name}")
        else:
            result.output_expr = "No solution found"
            result.notes.append(f"No symbolic solution for {var_name}")

        log.info("solve(%s, %s) → %s", result.input_expr, var_name, result.output_expr)
        return result

    def series_expand(
        self, parsed_eq, var_name: str = "x", point: float = 0, order: int = 6
    ) -> RefactorResult:
        """Taylor/Maclaurin series expansion."""
        expr = _get_expr(parsed_eq)
        var = sympy.Symbol(var_name)
        result = RefactorResult(
            operation=f"series({var_name}, {point}, O={order})",
            input_expr=str(expr),
            complexity_before=self._expr_complexity(expr),
        )
        try:
            series = sympy.series(expr, var, point, order)
            result.output_expr = str(series)
            result.sympy_output = series
            result.complexity_after = self._expr_complexity(series.removeO())
            result.notes.append(f"Expanded about {var_name}={point} to order {order}")
        except Exception as e:
            result.output_expr = f"Series expansion failed: {e}"
            result.notes.append(str(e))

        log.info("series(%s) → %s", result.input_expr, result.output_expr)
        return result

    def check_equivalence(self, parsed_eq_a, parsed_eq_b) -> bool:
        """
        Check if two parsed equations are algebraically equivalent.

        Returns True if (A - B) simplifies to zero.
        """
        expr_a = _get_expr(parsed_eq_a)
        expr_b = _get_expr(parsed_eq_b)
        diff = sympy.simplify(expr_a - expr_b)
        equiv = diff == 0
        log.info("Equivalence check: %s ≡ %s → %s", expr_a, expr_b, equiv)
        return equiv

    def canonical_form(self, parsed_eq) -> str:
        """
        Return a canonical (normalized) string representation.

        Useful for deduplication and comparison.
        """
        expr = _get_expr(parsed_eq)
        canon = sympy.nsimplify(sympy.simplify(expr))
        return str(canon)

    def check_consistency(self, parsed_eq, reference_exprs: list = None) -> ConsistencyReport:
        """
        Check algebraic consistency of an equation.

        Optionally compare against reference expressions to detect
        contradictions or redundancies.
        """
        expr = _get_expr(parsed_eq)
        canon = self.canonical_form(parsed_eq)
        report = ConsistencyReport(
            equation_name=parsed_eq.name,
            canonical_form=canon,
        )

        # Self-consistency: check for trivial identities
        simplified = sympy.simplify(expr)
        if simplified == 0:
            report.notes.append("Expression simplifies to zero (trivial identity)")
        if simplified == sympy.oo or simplified == -sympy.oo:
            report.is_consistent = False
            report.contradictions.append("Expression diverges to infinity")

        # Check for NaN
        if simplified is sympy.nan:
            report.is_consistent = False
            report.contradictions.append("Expression evaluates to NaN")

        # Compare against references
        if reference_exprs:
            for i, ref in enumerate(reference_exprs):
                ref_expr = _get_expr(ref) if hasattr(ref, "sympy_expr") else ref
                diff = sympy.simplify(expr - ref_expr)
                if diff == 0:
                    report.redundancies.append(
                        f"Equivalent to reference expression #{i + 1}: {ref_expr}"
                    )
                else:
                    report.equivalent_forms.append(
                        f"Differs from reference #{i + 1} by: {diff}"
                    )

        log.info("Consistency check '%s': consistent=%s",
                 parsed_eq.name, report.is_consistent)
        return report

    def detect_redundancy(self, equations: list) -> list:
        """
        Given a list of ParsedEquation objects, find duplicate/equivalent pairs.

        Returns list of (i, j) index pairs that are equivalent.
        """
        pairs = []
        for i in range(len(equations)):
            for j in range(i + 1, len(equations)):
                try:
                    if self.check_equivalence(equations[i], equations[j]):
                        pairs.append((i, j))
                        log.info("Redundancy: eq[%d] ≡ eq[%d]", i, j)
                except Exception:
                    pass
        return pairs


def _get_expr(parsed_eq):
    """Extract the working expression from a ParsedEquation."""
    if hasattr(parsed_eq, "rhs") and parsed_eq.rhs and parsed_eq.is_equation:
        return parsed_eq.rhs
    if hasattr(parsed_eq, "sympy_expr"):
        return parsed_eq.sympy_expr
    return parsed_eq  # Assume raw sympy expression
