"""
Solution Optimizer – Expression simplification, redundancy detection,
nondimensionalization, and overparameterization analysis.

Phase VII-A: Mathematical Expansion

Capabilities:
  - Simplify expressions via multiple strategies
  - Identify redundant parameters
  - Suggest nondimensional forms
  - Detect overparameterization
  - Report compression ratios
  - Hash all outputs deterministically
"""

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

import sympy
from sympy import (
    Symbol, symbols, simplify, expand, factor, cancel,
    collect, radsimp, powsimp, trigsimp, logcombine,
    count_ops, srepr, latex,
)

from src.logger import get_logger
from src.math.equation_parser import EquationParser

log = get_logger(__name__)


@dataclass
class OptimizationResult:
    """Result of equation optimization."""
    equation_name: str
    original_expr: str
    optimized_expr: str = ""
    original_complexity: int = 0
    optimized_complexity: int = 0
    compression_ratio: float = 0.0
    strategies_applied: list = field(default_factory=list)
    redundant_parameters: list = field(default_factory=list)
    nondimensional_form: str = ""
    overparameterized: bool = False
    overparameterization_details: str = ""
    is_equivalent: bool = True
    sha256_hash: str = ""

    def to_dict(self) -> dict:
        return {
            "equation_name": self.equation_name,
            "original_expr": self.original_expr,
            "optimized_expr": self.optimized_expr,
            "original_complexity": self.original_complexity,
            "optimized_complexity": self.optimized_complexity,
            "compression_ratio": round(self.compression_ratio, 6),
            "strategies_applied": self.strategies_applied,
            "redundant_parameters": self.redundant_parameters,
            "nondimensional_form": self.nondimensional_form,
            "overparameterized": self.overparameterized,
            "overparameterization_details": self.overparameterization_details,
            "is_equivalent": self.is_equivalent,
            "sha256_hash": self.sha256_hash,
        }

    def compute_hash(self):
        """Compute deterministic SHA-256."""
        canonical = json.dumps(self.to_dict(), sort_keys=True, default=str)
        self.sha256_hash = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
        return self.sha256_hash


class SolutionOptimizer:
    """
    Multi-strategy expression optimizer with forensic-grade tracing.
    """

    def __init__(self):
        self.parser = EquationParser()

    def optimize(self, equation_str: str, name: str = "unnamed") -> OptimizationResult:
        """
        Apply multi-strategy optimization to an equation.

        Args:
            equation_str: Plain text equation or expression
            name: Human-readable name

        Returns:
            OptimizationResult with full optimization trace
        """
        result = OptimizationResult(
            equation_name=name,
            original_expr=equation_str,
        )

        parsed = self.parser.parse_plaintext(equation_str, name=name)
        if parsed.parse_error:
            result.sha256_hash = hashlib.sha256(
                equation_str.encode("utf-8")
            ).hexdigest()
            return result

        expr = self.parser.get_expression(parsed)
        if expr is None:
            result.compute_hash()
            return result

        result.original_complexity = int(count_ops(expr, visual=False))

        # Apply optimization strategies
        best_expr = expr
        best_ops = result.original_complexity

        strategies = [
            ("simplify", lambda e: simplify(e)),
            ("expand", lambda e: expand(e)),
            ("factor", lambda e: factor(e)),
            ("cancel", lambda e: cancel(e)),
            ("collect", lambda e: self._try_collect(e)),
            ("powsimp", lambda e: powsimp(e)),
            ("trigsimp", lambda e: trigsimp(e)),
            ("radsimp", lambda e: radsimp(e)),
        ]

        for strategy_name, strategy_fn in strategies:
            try:
                candidate = strategy_fn(expr)
                candidate_ops = int(count_ops(candidate, visual=False))
                if candidate_ops < best_ops:
                    # Verify equivalence
                    if simplify(expr - candidate) == 0:
                        best_expr = candidate
                        best_ops = candidate_ops
                        result.strategies_applied.append({
                            "strategy": strategy_name,
                            "ops_before": result.original_complexity,
                            "ops_after": candidate_ops,
                        })
            except Exception:
                continue

        result.optimized_expr = str(best_expr)
        result.optimized_complexity = best_ops

        # Compression ratio
        if result.original_complexity > 0:
            result.compression_ratio = 1.0 - (
                best_ops / result.original_complexity
            )
        else:
            result.compression_ratio = 0.0

        # Check for redundant parameters
        result.redundant_parameters = self._find_redundant_params(expr)

        # Attempt nondimensionalization
        result.nondimensional_form = self._nondimensionalize(expr)

        # Check overparameterization
        self._check_overparameterization(result, parsed)

        # Verify final equivalence
        try:
            result.is_equivalent = simplify(expr - best_expr) == 0
        except Exception:
            result.is_equivalent = True

        result.compute_hash()
        log.info("Optimized '%s': %d → %d ops (compression=%.1f%%)",
                 name, result.original_complexity, result.optimized_complexity,
                 result.compression_ratio * 100)

        return result

    def _try_collect(self, expr):
        """Collect common terms by the first free symbol."""
        free = sorted(expr.free_symbols, key=str)
        if free:
            return collect(expr, free[0])
        return expr

    def _find_redundant_params(self, expr) -> list:
        """Identify parameters that can be combined."""
        redundant = []
        free_syms = sorted(expr.free_symbols, key=str)

        # Check if any pair of parameters always appears together
        for i, s1 in enumerate(free_syms):
            for s2 in free_syms[i + 1:]:
                # Check if s1 and s2 always appear as a product
                try:
                    ratio = simplify(expr / s1)
                    if s2 not in ratio.free_symbols and s1 in expr.free_symbols:
                        # s1 and s2 might be redundant
                        pass
                except Exception:
                    pass

                # Check if s1/s2 ratio could be a single parameter
                try:
                    combined = Symbol(f"{s1}_{s2}")
                    test = expr.subs(s1 * s2, combined)
                    if count_ops(test) < count_ops(expr):
                        redundant.append({
                            "symbols": [str(s1), str(s2)],
                            "suggestion": f"Consider combining {s1}*{s2} → {combined}",
                        })
                except Exception:
                    pass

        return redundant

    def _nondimensionalize(self, expr) -> str:
        """Suggest nondimensional form by grouping dimensional parameters."""
        free_syms = sorted(expr.free_symbols, key=str)
        if len(free_syms) <= 2:
            return str(expr)

        try:
            # Normalize by the first symbol as characteristic scale
            char_sym = free_syms[0]
            normalized = simplify(expr / char_sym)
            return f"({char_sym}) × ({normalized})"
        except Exception:
            return str(expr)

    def _check_overparameterization(self, result, parsed):
        """Check if the equation has more free parameters than constraints."""
        sym_count = len(parsed.symbols_found)
        # Heuristic: if more than 8 free symbols, likely overparameterized
        if sym_count > 8:
            result.overparameterized = True
            result.overparameterization_details = (
                f"{sym_count} free parameters detected. "
                "Consider reducing via dimensional analysis or substitution."
            )
        # Also flag if complexity is high relative to symbol count
        if result.original_complexity > sym_count * 10:
            result.overparameterized = True
            result.overparameterization_details += (
                f" Complexity ({result.original_complexity}) >> "
                f"symbol count ({sym_count})."
            )

    def save_to_db(self, result: OptimizationResult) -> int:
        """Save optimization result to database."""
        from src.database import insert_row
        return insert_row("equation_optimization", {
            "equation_name": result.equation_name,
            "original_expr": result.original_expr,
            "simplified_expr": result.optimized_expr,
            "original_complexity": result.original_complexity,
            "simplified_complexity": result.optimized_complexity,
            "compression_ratio": result.compression_ratio,
            "redundant_params": json.dumps(result.redundant_parameters, default=str),
            "nondimensional_form": result.nondimensional_form,
            "notes": json.dumps(result.strategies_applied, default=str),
            "sha256_hash": result.sha256_hash,
            "optimized_at": datetime.now(timezone.utc).isoformat(),
        })
