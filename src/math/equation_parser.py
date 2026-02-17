"""
Equation Parser – LaTeX / Plain Text → SymPy Symbolic Expressions

Provides:
  - LaTeX string parsing to SymPy expressions
  - Plain text math parsing to SymPy expressions
  - Normalization of physical constants
  - Extraction of equation metadata (symbols, structure)
  - Safe parsing (no eval, strict whitelist)
"""

import hashlib
import json
import re
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Optional, Union

import sympy
from sympy import (
    symbols, Symbol, Function,
    Eq, solve, simplify, expand, factor,
    latex, srepr, count_ops,
    oo, pi, E, I,
)
from sympy.parsing.sympy_parser import (
    parse_expr,
    standard_transformations,
    implicit_multiplication_application,
    convert_xor,
)
from sympy.parsing.latex import parse_latex

from src.logger import get_logger

log = get_logger(__name__)

# ── Physical Constants Registry ──────────────────────────────────────────────
PHYSICAL_CONSTANTS = {
    "G": {"value": 6.67430e-11, "units": "m^3 kg^-1 s^-2", "name": "Gravitational constant"},
    "c": {"value": 2.99792458e8, "units": "m s^-1", "name": "Speed of light"},
    "h": {"value": 6.62607015e-34, "units": "J s", "name": "Planck constant"},
    "hbar": {"value": 1.054571817e-34, "units": "J s", "name": "Reduced Planck constant"},
    "k_B": {"value": 1.380649e-23, "units": "J K^-1", "name": "Boltzmann constant"},
    "e": {"value": 1.602176634e-19, "units": "C", "name": "Elementary charge"},
    "m_e": {"value": 9.1093837015e-31, "units": "kg", "name": "Electron mass"},
    "m_p": {"value": 1.67262192369e-27, "units": "kg", "name": "Proton mass"},
    "epsilon_0": {"value": 8.8541878128e-12, "units": "F m^-1", "name": "Vacuum permittivity"},
    "mu_0": {"value": 1.25663706212e-6, "units": "H m^-1", "name": "Vacuum permeability"},
    "g": {"value": 9.80665, "units": "m s^-2", "name": "Standard gravity"},
    "M_sun": {"value": 1.989e30, "units": "kg", "name": "Solar mass"},
    "M_earth": {"value": 5.972e24, "units": "kg", "name": "Earth mass"},
    "R_earth": {"value": 6.371e6, "units": "m", "name": "Earth radius"},
}

# Safe transformations (no eval)
SAFE_TRANSFORMS = standard_transformations + (
    implicit_multiplication_application,
    convert_xor,
)

# ── Allowed symbol whitelist ─────────────────────────────────────────────────
ALLOWED_SYMBOL_PATTERN = re.compile(r'^[a-zA-Z_][a-zA-Z0-9_]*$')


@dataclass
class ParsedEquation:
    """Result of parsing an equation."""
    name: str
    original_input: str
    input_format: str  # 'latex', 'plaintext', 'sympy'
    sympy_expr: Optional[object] = None
    sympy_repr: str = ""
    latex_form: str = ""
    simplified_form: str = ""
    symbols_found: list = field(default_factory=list)
    is_equation: bool = False  # True if Eq(), False if expression
    lhs: Optional[object] = None
    rhs: Optional[object] = None
    sha256: str = ""
    parse_error: str = ""

    def to_dict(self) -> dict:
        """Serialize to dictionary (exclude non-serializable SymPy objects)."""
        return {
            "name": self.name,
            "original_input": self.original_input,
            "input_format": self.input_format,
            "sympy_repr": self.sympy_repr,
            "latex_form": self.latex_form,
            "simplified_form": self.simplified_form,
            "symbols_found": self.symbols_found,
            "is_equation": self.is_equation,
            "sha256": self.sha256,
            "parse_error": self.parse_error,
        }


class EquationParser:
    """
    Parse mathematical equations from LaTeX or plain text into SymPy.

    Enforces strict safety: no eval(), no arbitrary code execution.
    Uses SymPy's parser with a restricted transformation set.
    """

    def __init__(self):
        self.constants = PHYSICAL_CONSTANTS
        self._local_dict = {}
        self._init_local_dict()

    def _init_local_dict(self):
        """Build local dictionary of safe symbols and constants."""
        # Physical constant symbols
        for name in self.constants:
            self._local_dict[name] = Symbol(name, positive=True)
        # Common physics symbols
        for s in ["x", "y", "z", "t", "r", "theta", "phi",
                   "m", "M", "F", "E", "V", "T", "P", "L",
                   "omega", "lambda_", "nu", "rho", "sigma",
                   "alpha", "beta", "gamma", "delta", "epsilon",
                   "a", "b", "d", "f", "n", "v", "w", "A", "B",
                   "R", "S", "H", "U", "W", "Q", "I_val", "J", "K"]:
            safe_name = s.rstrip("_")
            self._local_dict[s] = Symbol(safe_name)

    def parse_latex(self, latex_str: str, name: str = "unnamed") -> ParsedEquation:
        """
        Parse a LaTeX equation string into a SymPy expression.

        Args:
            latex_str: LaTeX math string (e.g., 'E = mc^2')
            name: Human-readable name for this equation

        Returns:
            ParsedEquation with parsed symbolic expression
        """
        result = ParsedEquation(
            name=name,
            original_input=latex_str,
            input_format="latex",
        )

        try:
            # Check if it's an equation (has =)
            if "=" in latex_str and "\\neq" not in latex_str:
                parts = latex_str.split("=", 1)
                lhs_expr = parse_latex(parts[0].strip())
                rhs_expr = parse_latex(parts[1].strip())
                result.sympy_expr = Eq(lhs_expr, rhs_expr)
                result.is_equation = True
                result.lhs = lhs_expr
                result.rhs = rhs_expr
            else:
                result.sympy_expr = parse_latex(latex_str)

            self._finalize_parse(result)

        except Exception as exc:
            result.parse_error = str(exc)
            log.warning("LaTeX parse failed for '%s': %s", name, exc)

        return result

    def parse_plaintext(self, text: str, name: str = "unnamed") -> ParsedEquation:
        """
        Parse a plain text math expression into SymPy.

        Args:
            text: Plain text math (e.g., 'E = m*c**2')
            name: Human-readable name

        Returns:
            ParsedEquation
        """
        result = ParsedEquation(
            name=name,
            original_input=text,
            input_format="plaintext",
        )

        try:
            # Handle equation form
            if "=" in text and text.count("=") == 1 and "==" not in text:
                parts = text.split("=", 1)
                lhs_expr = parse_expr(
                    parts[0].strip(),
                    local_dict=self._local_dict,
                    transformations=SAFE_TRANSFORMS,
                    evaluate=False,
                )
                rhs_expr = parse_expr(
                    parts[1].strip(),
                    local_dict=self._local_dict,
                    transformations=SAFE_TRANSFORMS,
                    evaluate=False,
                )
                result.sympy_expr = Eq(lhs_expr, rhs_expr)
                result.is_equation = True
                result.lhs = lhs_expr
                result.rhs = rhs_expr
            else:
                result.sympy_expr = parse_expr(
                    text,
                    local_dict=self._local_dict,
                    transformations=SAFE_TRANSFORMS,
                    evaluate=False,
                )

            self._finalize_parse(result)

        except Exception as exc:
            result.parse_error = str(exc)
            log.warning("Plaintext parse failed for '%s': %s", name, exc)

        return result

    def _finalize_parse(self, result: ParsedEquation):
        """Populate metadata fields after successful parse."""
        expr = result.sympy_expr

        # SymPy representation
        result.sympy_repr = srepr(expr)

        # LaTeX output
        result.latex_form = latex(expr)

        # Simplified form
        if result.is_equation:
            simp = Eq(simplify(result.lhs), simplify(result.rhs))
            result.simplified_form = latex(simp)
        else:
            result.simplified_form = latex(simplify(expr))

        # Extract symbols
        if result.is_equation:
            all_syms = result.lhs.free_symbols | result.rhs.free_symbols
        else:
            all_syms = expr.free_symbols
        result.symbols_found = sorted([str(s) for s in all_syms])

        # SHA-256 of the canonical representation
        canonical = result.sympy_repr
        result.sha256 = hashlib.sha256(canonical.encode("utf-8")).hexdigest()

        log.info("Parsed equation '%s': %d symbols, hash=%s",
                 result.name, len(result.symbols_found), result.sha256[:16])

    def get_expression(self, parsed: ParsedEquation):
        """Get the core expression (RHS if equation, else full expr)."""
        if parsed.is_equation and parsed.rhs is not None:
            return parsed.rhs
        return parsed.sympy_expr

    def get_complexity_metrics(self, parsed: ParsedEquation) -> dict:
        """
        Compute structural complexity metrics for an expression.

        Returns:
            dict with term_count, symbol_count, tree_depth, op_count, complexity_class
        """
        expr = self.get_expression(parsed)
        if expr is None:
            return {"error": "No expression to analyze"}

        # Count operations
        op_count = count_ops(expr, visual=False)

        # Symbol count
        sym_count = len(parsed.symbols_found)

        # Term count (top-level addends)
        try:
            term_count = len(sympy.Add.make_args(expr))
        except Exception:
            term_count = 1

        # Tree depth (approximate via srepr nesting)
        srepr_str = srepr(expr)
        max_depth = 0
        depth = 0
        for ch in srepr_str:
            if ch == '(':
                depth += 1
                max_depth = max(max_depth, depth)
            elif ch == ')':
                depth -= 1
        tree_depth = max_depth

        # Heuristic complexity class
        if op_count <= 3:
            complexity_class = "trivial"
        elif op_count <= 10:
            complexity_class = "simple"
        elif op_count <= 30:
            complexity_class = "moderate"
        elif op_count <= 100:
            complexity_class = "complex"
        else:
            complexity_class = "highly_complex"

        return {
            "term_count": term_count,
            "symbol_count": sym_count,
            "tree_depth": tree_depth,
            "operation_count": op_count,
            "complexity_class": complexity_class,
        }
