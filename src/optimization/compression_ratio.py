"""
Compression Ratio – Measure simplification effectiveness.

Phase VII: Metrics Refinement

Computes:
  - Original vs simplified AST complexity
  - Compression ratio = 1 - (simplified_ops / original_ops)
  - Multi-strategy simplification comparison
"""

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone

import sympy
from sympy import (
    simplify, expand, factor, cancel, trigsimp,
    count_ops,
)

from src.logger import get_logger
from src.math.equation_parser import EquationParser

log = get_logger(__name__)


@dataclass
class CompressionResult:
    """Result of compression ratio analysis."""
    equation_name: str
    original_ops: int = 0
    best_simplified_ops: int = 0
    compression_ratio: float = 0.0
    best_strategy: str = "none"
    strategy_results: list = field(default_factory=list)
    sha256_hash: str = ""

    def to_dict(self) -> dict:
        return {
            "equation_name": self.equation_name,
            "original_ops": self.original_ops,
            "best_simplified_ops": self.best_simplified_ops,
            "compression_ratio": round(self.compression_ratio, 8),
            "best_strategy": self.best_strategy,
            "strategy_results": self.strategy_results,
            "sha256_hash": self.sha256_hash,
        }

    def compute_hash(self):
        canonical = json.dumps(self.to_dict(), sort_keys=True, default=str)
        self.sha256_hash = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
        return self.sha256_hash


class CompressionRatio:
    """
    Measure simplification effectiveness across multiple strategies.
    """

    def __init__(self):
        self.parser = EquationParser()

    def compute(self, equation_str: str, name: str = "unnamed") -> CompressionResult:
        """
        Compute compression ratio for an equation.

        Args:
            equation_str: Plain text equation
            name: Equation name

        Returns:
            CompressionResult with strategy comparison
        """
        result = CompressionResult(equation_name=name)

        parsed = self.parser.parse_plaintext(equation_str, name=name)
        if parsed.parse_error:
            result.compute_hash()
            return result

        expr = self.parser.get_expression(parsed)
        if expr is None:
            result.compute_hash()
            return result

        result.original_ops = int(count_ops(expr, visual=False))
        best_ops = result.original_ops
        best_strategy = "none"

        strategies = [
            ("simplify", simplify),
            ("expand", expand),
            ("factor", factor),
            ("cancel", cancel),
            ("trigsimp", trigsimp),
        ]

        for sname, sfn in strategies:
            try:
                candidate = sfn(expr)
                ops = int(count_ops(candidate, visual=False))
                # Verify equivalence
                is_equiv = simplify(expr - candidate) == 0
                ratio = 1.0 - (ops / max(result.original_ops, 1))

                result.strategy_results.append({
                    "strategy": sname,
                    "ops": ops,
                    "ratio": round(ratio, 6),
                    "is_equivalent": is_equiv,
                })

                if ops < best_ops and is_equiv:
                    best_ops = ops
                    best_strategy = sname
            except Exception:
                result.strategy_results.append({
                    "strategy": sname,
                    "ops": None,
                    "ratio": 0.0,
                    "is_equivalent": False,
                })

        result.best_simplified_ops = best_ops
        result.best_strategy = best_strategy
        if result.original_ops > 0:
            result.compression_ratio = 1.0 - (best_ops / result.original_ops)
        else:
            result.compression_ratio = 0.0

        result.compute_hash()
        log.info("Compression '%s': %d → %d ops (ratio=%.2f%%, strategy=%s)",
                 name, result.original_ops, best_ops,
                 result.compression_ratio * 100, best_strategy)

        return result

    def save_to_db(self, result: CompressionResult) -> int:
        """Save compression result to database."""
        from src.database import insert_row
        return insert_row("equation_optimization", {
            "equation_name": result.equation_name,
            "original_complexity": result.original_ops,
            "simplified_complexity": result.best_simplified_ops,
            "compression_ratio": result.compression_ratio,
            "notes": json.dumps(result.strategy_results, default=str),
            "sha256_hash": result.sha256_hash,
            "optimized_at": datetime.now(timezone.utc).isoformat(),
        })
