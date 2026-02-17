"""
Solvability Index – Quantitative measure of equation tractability.

Phase VII: Metrics Refinement

Formula: SI = C / (V + 1) * (1 - S) * D

Where:
  V = number of free variables
  C = number of constraints (equations, boundary conditions)
  S = stability factor (0 = stable, 1 = unstable)
  D = dimensional completeness (0 to 1)

Output range: [0.0, 1.0] where higher = more tractable
"""

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

from src.logger import get_logger
from src.math.equation_parser import EquationParser

log = get_logger(__name__)


@dataclass
class SolvabilityResult:
    """Result of solvability index computation."""
    equation_name: str
    solvability_index: float = 0.0
    free_variables: int = 0
    constraints: int = 0
    stability_factor: float = 0.0
    dimensional_completeness: float = 1.0
    interpretation: str = ""
    sha256_hash: str = ""

    def to_dict(self) -> dict:
        return {
            "equation_name": self.equation_name,
            "solvability_index": round(self.solvability_index, 8),
            "free_variables": self.free_variables,
            "constraints": self.constraints,
            "stability_factor": round(self.stability_factor, 8),
            "dimensional_completeness": round(self.dimensional_completeness, 8),
            "interpretation": self.interpretation,
            "sha256_hash": self.sha256_hash,
        }

    def compute_hash(self):
        """Compute deterministic SHA-256."""
        canonical = json.dumps(self.to_dict(), sort_keys=True, default=str)
        self.sha256_hash = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
        return self.sha256_hash


class SolvabilityIndex:
    """
    Compute equation solvability index using the formula:
    SI = C / (V + 1) * (1 - S) * D
    """

    def __init__(self):
        self.parser = EquationParser()

    def compute(self, equation_str: str, name: str = "unnamed",
                constraints: int = 1,
                stability_factor: float = 0.0,
                dimensional_completeness: float = 1.0) -> SolvabilityResult:
        """
        Compute solvability index for an equation.

        Args:
            equation_str: Plain text equation
            name: Equation name
            constraints: Number of constraints (equations, BCs). Default 1.
            stability_factor: S in [0, 1]. 0=stable, 1=unstable.
            dimensional_completeness: D in [0, 1]. 1=all dims verified.

        Returns:
            SolvabilityResult with index and interpretation
        """
        result = SolvabilityResult(equation_name=name)

        # Parse to count free variables
        parsed = self.parser.parse_plaintext(equation_str, name=name)
        if parsed.parse_error:
            result.interpretation = f"Parse error: {parsed.parse_error}"
            result.compute_hash()
            return result

        V = len(parsed.symbols_found)
        C = max(constraints, 0)
        S = max(0.0, min(1.0, stability_factor))
        D = max(0.0, min(1.0, dimensional_completeness))

        result.free_variables = V
        result.constraints = C
        result.stability_factor = S
        result.dimensional_completeness = D

        # SI = C / (V + 1) * (1 - S) * D
        SI = (C / (V + 1)) * (1.0 - S) * D
        SI = max(0.0, min(1.0, SI))
        result.solvability_index = SI

        # Interpretation
        if SI >= 0.8:
            result.interpretation = "Highly tractable – well-constrained, stable"
        elif SI >= 0.5:
            result.interpretation = "Moderately tractable – solvable with effort"
        elif SI >= 0.2:
            result.interpretation = "Low tractability – under-constrained or unstable"
        else:
            result.interpretation = "Intractable – severely under-constrained or unstable"

        result.compute_hash()
        log.info("Solvability '%s': SI=%.4f (V=%d, C=%d, S=%.2f, D=%.2f) – %s",
                 name, SI, V, C, S, D, result.interpretation)

        return result

    def compute_from_stability(self, equation_str: str, name: str = "unnamed",
                               constraints: int = 1,
                               stability_class: str = "unknown",
                               dimensional_completeness: float = 1.0
                               ) -> SolvabilityResult:
        """
        Compute SI using a stability class string instead of raw factor.

        Stability mapping:
          asymptotically_stable → 0.0
          stable  → 0.1
          marginally_stable → 0.3
          center  → 0.4
          saddle  → 0.7
          unstable → 0.9
          unknown → 0.5
        """
        stability_map = {
            "asymptotically_stable": 0.0,
            "stable": 0.1,
            "marginally_stable": 0.3,
            "center": 0.4,
            "saddle": 0.7,
            "unstable": 0.9,
            "unknown": 0.5,
        }
        S = stability_map.get(stability_class, 0.5)
        return self.compute(equation_str, name=name, constraints=constraints,
                            stability_factor=S,
                            dimensional_completeness=dimensional_completeness)

    def save_to_db(self, result: SolvabilityResult) -> int:
        """Save solvability result to database."""
        from src.database import insert_row
        return insert_row("equation_optimization", {
            "equation_name": result.equation_name,
            "original_expr": f"V={result.free_variables},C={result.constraints}",
            "compression_ratio": result.solvability_index,
            "notes": f"SI={result.solvability_index:.4f} | {result.interpretation}",
            "sha256_hash": result.sha256_hash,
            "optimized_at": datetime.now(timezone.utc).isoformat(),
        })
