"""
Model Efficiency Score – Quantify computational cost of equations.

Phase VII: Metrics Refinement

Metrics:
  - Operation count (adds, muls, pows, etc.)
  - Expression tree depth
  - Parameter count
  - Normalized cost = ops / symbols
"""

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timezone

import sympy
from sympy import count_ops, Symbol, simplify, srepr

from src.logger import get_logger
from src.math.equation_parser import EquationParser

log = get_logger(__name__)


@dataclass
class EfficiencyResult:
    """Result of model efficiency analysis."""
    equation_name: str
    operation_count: int = 0
    tree_depth: int = 0
    parameter_count: int = 0
    normalized_cost: float = 0.0
    efficiency_score: float = 0.0
    details: dict = None
    sha256_hash: str = ""

    def __post_init__(self):
        if self.details is None:
            self.details = {}

    def to_dict(self) -> dict:
        return {
            "equation_name": self.equation_name,
            "operation_count": self.operation_count,
            "tree_depth": self.tree_depth,
            "parameter_count": self.parameter_count,
            "normalized_cost": round(self.normalized_cost, 6),
            "efficiency_score": round(self.efficiency_score, 6),
            "details": self.details,
            "sha256_hash": self.sha256_hash,
        }

    def compute_hash(self):
        canonical = json.dumps(self.to_dict(), sort_keys=True, default=str)
        self.sha256_hash = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
        return self.sha256_hash


def _tree_depth(expr) -> int:
    """Compute the depth of a SymPy expression tree."""
    if not expr.args:
        return 0
    return 1 + max(_tree_depth(a) for a in expr.args)


def _count_ops_detailed(expr) -> dict:
    """Detailed operation count by type."""
    counts = {"Add": 0, "Mul": 0, "Pow": 0, "Symbol": 0, "Number": 0, "Other": 0}
    for node in sympy.preorder_traversal(expr):
        cls_name = type(node).__name__
        if cls_name in counts:
            counts[cls_name] += 1
        elif isinstance(node, Symbol):
            counts["Symbol"] += 1
        elif isinstance(node, sympy.Number):
            counts["Number"] += 1
        else:
            counts["Other"] += 1
    return counts


class ModelEfficiencyScore:
    """
    Analyze computational efficiency of mathematical expressions.
    """

    def __init__(self):
        self.parser = EquationParser()

    def compute(self, equation_str: str, name: str = "unnamed") -> EfficiencyResult:
        """
        Compute efficiency score for an equation.

        Args:
            equation_str: Plain text equation
            name: Equation name

        Returns:
            EfficiencyResult with all metrics
        """
        result = EfficiencyResult(equation_name=name)

        parsed = self.parser.parse_plaintext(equation_str, name=name)
        if parsed.parse_error:
            result.compute_hash()
            return result

        expr = self.parser.get_expression(parsed)
        if expr is None:
            result.compute_hash()
            return result

        # Metrics
        result.operation_count = int(count_ops(expr, visual=False))
        result.tree_depth = _tree_depth(expr)
        result.parameter_count = len(parsed.symbols_found)
        result.details = _count_ops_detailed(expr)

        # Normalized cost: ops per symbol (lower is more efficient)
        if result.parameter_count > 0:
            result.normalized_cost = result.operation_count / result.parameter_count
        else:
            result.normalized_cost = float(result.operation_count)

        # Efficiency score: inverse of normalized cost, scaled to [0, 1]
        # Score = 1 / (1 + normalized_cost)
        result.efficiency_score = 1.0 / (1.0 + result.normalized_cost)

        result.compute_hash()
        log.info("Efficiency '%s': ops=%d, depth=%d, params=%d, score=%.4f",
                 name, result.operation_count, result.tree_depth,
                 result.parameter_count, result.efficiency_score)

        return result

    def save_to_db(self, result: EfficiencyResult) -> int:
        """Save efficiency result to database."""
        from src.database import insert_row
        return insert_row("equation_optimization", {
            "equation_name": result.equation_name,
            "original_expr": f"ops={result.operation_count}",
            "original_complexity": result.operation_count,
            "simplified_complexity": result.tree_depth,
            "notes": json.dumps(result.to_dict(), sort_keys=True, default=str),
            "sha256_hash": result.sha256_hash,
            "optimized_at": datetime.now(timezone.utc).isoformat(),
        })
