"""
Formal Proof Export – Export SymPy proof trees, optional SMT-LIB export,
and deterministic serialization for archiving.

Phase VII-A: Mathematical Expansion

Capabilities:
  - Export SymPy proof tree (step-by-step transformations)
  - Optional SMT-LIB 2.0 export for automated theorem provers
  - Deterministic JSON serialization
  - SHA-256 hashing of all proof artifacts
  - IPFS-compatible archiving format
"""

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

import sympy
from sympy import (
    Symbol, symbols, Eq, simplify, expand, factor,
    latex, srepr, count_ops,
)

from src.logger import get_logger
from src.math.equation_parser import EquationParser

log = get_logger(__name__)


@dataclass
class ProofStep:
    """A single step in a formal proof tree."""
    step_number: int
    operation: str
    input_expr: str
    output_expr: str
    justification: str = ""
    axioms_used: list = field(default_factory=list)
    is_valid: bool = True

    def to_dict(self) -> dict:
        return {
            "step_number": self.step_number,
            "operation": self.operation,
            "input_expr": self.input_expr,
            "output_expr": self.output_expr,
            "justification": self.justification,
            "axioms_used": self.axioms_used,
            "is_valid": self.is_valid,
        }


@dataclass
class FormalProof:
    """A complete formal proof with exportable representations."""
    equation_name: str
    proof_format: str = "sympy"
    starting_expr: str = ""
    conclusion: str = ""
    steps: list = field(default_factory=list)
    axioms_used: list = field(default_factory=list)
    assumptions: list = field(default_factory=list)
    proof_tree_json: str = ""
    smt_lib_export: str = ""
    is_valid: bool = True
    sha256_hash: str = ""
    ipfs_cid: str = ""
    signature: str = ""
    created_at: str = ""

    def to_dict(self) -> dict:
        return {
            "equation_name": self.equation_name,
            "proof_format": self.proof_format,
            "starting_expr": self.starting_expr,
            "conclusion": self.conclusion,
            "steps": [s.to_dict() for s in self.steps],
            "axioms_used": self.axioms_used,
            "assumptions": self.assumptions,
            "is_valid": self.is_valid,
            "sha256_hash": self.sha256_hash,
            "created_at": self.created_at,
        }

    def compute_hash(self):
        """Compute deterministic SHA-256 of the proof."""
        canonical = json.dumps(self.to_dict(), sort_keys=True, default=str)
        self.sha256_hash = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
        return self.sha256_hash


class FormalProofExporter:
    """
    Generate formal proof trees from SymPy transformations
    and export to JSON, SMT-LIB, or IPFS-compatible formats.
    """

    # Common axioms/rules used in proofs
    AXIOMS = {
        "commutativity": "a + b = b + a; a * b = b * a",
        "associativity": "(a + b) + c = a + (b + c)",
        "distributivity": "a * (b + c) = a*b + a*c",
        "identity_add": "a + 0 = a",
        "identity_mul": "a * 1 = a",
        "inverse_add": "a + (-a) = 0",
        "inverse_mul": "a * (1/a) = 1, a != 0",
        "power_rule": "d/dx(x^n) = n*x^(n-1)",
        "chain_rule": "d/dx(f(g(x))) = f'(g(x)) * g'(x)",
        "substitution": "If a = b, then f(a) = f(b)",
    }

    def __init__(self):
        self.parser = EquationParser()

    def generate_proof(self, equation_str: str, name: str = "unnamed",
                       assumptions: list = None) -> FormalProof:
        """
        Generate a formal proof tree for an equation.

        Applies a sequence of algebraic transformations and records
        each step with justification for formal verification.

        Args:
            equation_str: Plain text equation (e.g., 'E = m*c**2')
            name: Equation name
            assumptions: List of assumption strings

        Returns:
            FormalProof with complete proof tree
        """
        proof = FormalProof(
            equation_name=name,
            assumptions=assumptions or [],
            created_at=datetime.now(timezone.utc).isoformat(),
        )

        parsed = self.parser.parse_plaintext(equation_str, name=name)
        if parsed.parse_error:
            proof.is_valid = False
            proof.compute_hash()
            return proof

        expr = self.parser.get_expression(parsed)
        if expr is None:
            proof.is_valid = False
            proof.compute_hash()
            return proof

        proof.starting_expr = str(expr)
        current_expr = expr
        step_num = 0

        # Step 1: Expand
        expanded = expand(current_expr)
        if expanded != current_expr:
            step_num += 1
            proof.steps.append(ProofStep(
                step_number=step_num,
                operation="expand",
                input_expr=str(current_expr),
                output_expr=str(expanded),
                justification="Apply distributive law",
                axioms_used=["distributivity"],
                is_valid=simplify(current_expr - expanded) == 0,
            ))
            current_expr = expanded

        # Step 2: Simplify
        simplified = simplify(current_expr)
        if simplified != current_expr:
            step_num += 1
            proof.steps.append(ProofStep(
                step_number=step_num,
                operation="simplify",
                input_expr=str(current_expr),
                output_expr=str(simplified),
                justification="Algebraic simplification",
                axioms_used=["commutativity", "associativity", "identity_add",
                             "identity_mul"],
                is_valid=simplify(current_expr - simplified) == 0,
            ))
            current_expr = simplified

        # Step 3: Factor
        factored = factor(current_expr)
        if factored != current_expr:
            step_num += 1
            proof.steps.append(ProofStep(
                step_number=step_num,
                operation="factor",
                input_expr=str(current_expr),
                output_expr=str(factored),
                justification="Factor common terms",
                axioms_used=["distributivity", "inverse_mul"],
                is_valid=simplify(current_expr - factored) == 0,
            ))
            current_expr = factored

        # If equation form, verify LHS = RHS
        if parsed.is_equation and parsed.lhs is not None and parsed.rhs is not None:
            step_num += 1
            diff_expr = simplify(parsed.lhs - parsed.rhs)
            is_eq_valid = (diff_expr == 0)
            proof.steps.append(ProofStep(
                step_number=step_num,
                operation="verify_equation",
                input_expr=f"LHS - RHS = {parsed.lhs} - ({parsed.rhs})",
                output_expr=str(diff_expr),
                justification="Verify LHS - RHS = 0" if is_eq_valid
                              else f"LHS - RHS = {diff_expr} ≠ 0",
                axioms_used=["substitution"],
                is_valid=is_eq_valid,
            ))

        proof.conclusion = str(current_expr)

        # Collect all axioms used
        all_axioms = set()
        for step in proof.steps:
            all_axioms.update(step.axioms_used)
        proof.axioms_used = sorted(all_axioms)

        # Check overall validity
        proof.is_valid = all(s.is_valid for s in proof.steps)

        # Serialize proof tree
        proof.proof_tree_json = json.dumps(
            proof.to_dict(), sort_keys=True, default=str, indent=2
        )

        # Generate SMT-LIB export
        proof.smt_lib_export = self._export_smt_lib(parsed, proof)

        proof.compute_hash()
        log.info("Generated proof for '%s': %d steps, valid=%s, hash=%s",
                 name, len(proof.steps), proof.is_valid, proof.sha256_hash[:16])

        return proof

    def _export_smt_lib(self, parsed, proof: FormalProof) -> str:
        """
        Export proof obligations in SMT-LIB 2.0 format.

        This generates a satisfiability check that can be verified
        by Z3, CVC5, or other SMT solvers.
        """
        lines = [
            "; SMT-LIB 2.0 Export",
            f"; Equation: {proof.equation_name}",
            f"; Generated: {proof.created_at}",
            f"; SHA-256: {proof.sha256_hash}",
            "(set-logic QF_NRA)  ; Quantifier-free nonlinear real arithmetic",
            "",
        ]

        # Declare variables
        if parsed and parsed.symbols_found:
            for sym in sorted(parsed.symbols_found):
                lines.append(f"(declare-const {sym} Real)")
            lines.append("")

        # Add assumptions
        for i, assumption in enumerate(proof.assumptions):
            lines.append(f"; Assumption {i + 1}: {assumption}")

        # Add proof obligation
        if parsed and parsed.is_equation and parsed.lhs is not None:
            lines.append("")
            lines.append("; Proof obligation: LHS = RHS")
            lines.append(f"; LHS: {parsed.lhs}")
            lines.append(f"; RHS: {parsed.rhs}")
            lines.append("")
            lines.append("; Assert negation (check unsatisfiability)")
            lines.append(f"(assert (not (= {_to_smt(parsed.lhs)} {_to_smt(parsed.rhs)})))")
            lines.append("")
            lines.append("(check-sat)")
            lines.append("; Expected: unsat (proving the equation holds)")
        else:
            lines.append("")
            lines.append("; Expression (not an equation)")
            lines.append("(check-sat)")

        lines.append("(exit)")
        return "\n".join(lines)

    def save_to_db(self, proof: FormalProof) -> int:
        """Save formal proof to database."""
        from src.database import insert_row
        return insert_row("formal_proofs", {
            "equation_name": proof.equation_name,
            "proof_tree_json": proof.proof_tree_json,
            "smt_lib_export": proof.smt_lib_export,
            "proof_format": proof.proof_format,
            "axioms_used": json.dumps(proof.axioms_used),
            "assumptions": json.dumps(proof.assumptions),
            "conclusion": proof.conclusion,
            "is_valid": 1 if proof.is_valid else 0,
            "sha256_hash": proof.sha256_hash,
            "ipfs_cid": proof.ipfs_cid or None,
            "signature": proof.signature or None,
            "created_at": proof.created_at,
        })


def _to_smt(expr) -> str:
    """Convert a SymPy expression to SMT-LIB s-expression (best effort)."""
    if expr is None:
        return "0"
    s = str(expr)
    # Simple transformations for common patterns
    s = s.replace("**", "^")
    # Wrap in prefix notation for basic ops
    # This is a simplified converter; full conversion would need a tree walk
    return s
