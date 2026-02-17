"""
Derivation Logger – Step-by-Step Transformation Ledger + IPFS Anchoring

Provides:
  - Record each algebraic derivation step
  - Persist full derivation chains to SQLite
  - Serialize derivation to JSON
  - Compute SHA-256 hashes
  - Pin derivation objects to IPFS
  - Sign derivation CIDs with Ed25519
  - Anchor in Merkle snapshot
"""

import hashlib
import json
from datetime import datetime, timezone
from dataclasses import dataclass, field, asdict
from typing import Optional

from src.database import insert_row, query_rows, get_connection
from src.logger import get_logger

log = get_logger(__name__)


@dataclass
class DerivationStep:
    """One step in a derivation chain."""
    step_number: int
    operation: str          # e.g., "simplify", "expand", "substitute", "differentiate"
    input_expr: str
    output_expr: str
    justification: str = ""
    is_valid: bool = True

    def to_dict(self) -> dict:
        return {
            "step_number": self.step_number,
            "operation": self.operation,
            "input_expr": self.input_expr,
            "output_expr": self.output_expr,
            "justification": self.justification,
            "is_valid": self.is_valid,
        }


@dataclass
class DerivationChain:
    """Complete derivation from starting expression to final form."""
    name: str
    description: str = ""
    steps: list = field(default_factory=list)
    starting_expr: str = ""
    final_expr: str = ""
    sha256: str = ""
    ipfs_cid: str = ""
    signature_hex: str = ""
    created_at: str = ""

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "description": self.description,
            "starting_expr": self.starting_expr,
            "final_expr": self.final_expr,
            "steps": [s.to_dict() for s in self.steps],
            "sha256": self.sha256,
            "ipfs_cid": self.ipfs_cid,
            "signature_hex": self.signature_hex,
            "created_at": self.created_at,
        }


class DerivationLogger:
    """
    Records algebraic derivations step-by-step and anchors them
    to IPFS + cryptographic signatures for forensic integrity.
    """

    def __init__(self):
        self._chains: dict[str, DerivationChain] = {}

    # ── Chain Management ─────────────────────────────────────────────────
    def start_chain(self, name: str, starting_expr: str, description: str = "") -> DerivationChain:
        """Begin a new derivation chain."""
        chain = DerivationChain(
            name=name,
            description=description,
            starting_expr=starting_expr,
            created_at=datetime.now(timezone.utc).isoformat(),
        )
        self._chains[name] = chain
        log.info("Started derivation chain '%s' from: %s", name, starting_expr)
        return chain

    def add_step(
        self,
        chain_name: str,
        operation: str,
        input_expr: str,
        output_expr: str,
        justification: str = "",
        is_valid: bool = True,
    ) -> DerivationStep:
        """Add a transformation step to an existing chain."""
        chain = self._chains.get(chain_name)
        if not chain:
            raise KeyError(f"No derivation chain named '{chain_name}'")

        step = DerivationStep(
            step_number=len(chain.steps) + 1,
            operation=operation,
            input_expr=input_expr,
            output_expr=output_expr,
            justification=justification,
            is_valid=is_valid,
        )
        chain.steps.append(step)
        chain.final_expr = output_expr
        log.info("  Step %d [%s]: %s → %s",
                 step.step_number, operation, input_expr, output_expr)
        return step

    def add_refactor_result(self, chain_name: str, refactor_result) -> DerivationStep:
        """
        Add a step from a SymbolicRefactor result object.

        Args:
            chain_name: Name of the active derivation chain
            refactor_result: RefactorResult from symbolic_refactor module
        """
        return self.add_step(
            chain_name=chain_name,
            operation=refactor_result.operation,
            input_expr=refactor_result.input_expr,
            output_expr=refactor_result.output_expr,
            justification="; ".join(refactor_result.notes) if refactor_result.notes else "",
            is_valid=refactor_result.is_equivalent,
        )

    def finalize_chain(self, chain_name: str) -> DerivationChain:
        """
        Finalize a derivation chain:
          1. Hash the full chain to SHA-256
          2. Mark as complete.
        """
        chain = self._chains.get(chain_name)
        if not chain:
            raise KeyError(f"No derivation chain named '{chain_name}'")

        # Compute hash of canonical JSON representation
        canonical = json.dumps(chain.to_dict(), sort_keys=True, default=str)
        chain.sha256 = hashlib.sha256(canonical.encode()).hexdigest()

        log.info("Finalized chain '%s' | %d steps | SHA-256: %s",
                 chain_name, len(chain.steps), chain.sha256)
        return chain

    def get_chain(self, chain_name: str) -> Optional[DerivationChain]:
        """Return a chain by name."""
        return self._chains.get(chain_name)

    def list_chains(self) -> list[str]:
        """List all active chain names."""
        return list(self._chains.keys())

    # ── Database Persistence ─────────────────────────────────────────────
    def save_to_db(self, chain_name: str) -> int:
        """
        Persist an entire derivation chain to equation_proofs + derivation_steps tables.
        Returns the equation_proof row ID.
        """
        chain = self._chains.get(chain_name)
        if not chain:
            raise KeyError(f"No derivation chain named '{chain_name}'")

        if not chain.sha256:
            self.finalize_chain(chain_name)

        now = datetime.now(timezone.utc).isoformat()

        # Insert master record into equation_proofs
        proof_id = insert_row("equation_proofs", {
            "equation_name": chain.name,
            "original_latex": "",
            "original_plaintext": chain.starting_expr,
            "sympy_repr": chain.final_expr,
            "simplified_form": chain.final_expr,
            "dimensional_status": "unverified",
            "complexity_score": len(chain.steps),
            "sha256_hash": chain.sha256,
            "ipfs_cid": chain.ipfs_cid or "",
            "signature": chain.signature_hex or "",
            "verification_status": "logged",
            "created_at": now,
        })

        # Insert each step
        for step in chain.steps:
            insert_row("derivation_steps", {
                "proof_id": proof_id,
                "step_number": step.step_number,
                "operation": step.operation,
                "input_expr": step.input_expr,
                "output_expr": step.output_expr,
                "justification": step.justification,
                "is_valid": 1 if step.is_valid else 0,
                "created_at": now,
            })

        log.info("Saved derivation '%s' to DB (proof_id=%d, %d steps)",
                 chain_name, proof_id, len(chain.steps))
        return proof_id

    def load_from_db(self, proof_id: int) -> Optional[DerivationChain]:
        """Load a derivation chain from the database by proof_id."""
        proofs = query_rows("equation_proofs", "id = ?", (proof_id,))
        if not proofs:
            return None

        proof = proofs[0]
        chain = DerivationChain(
            name=proof["equation_name"],
            starting_expr=proof["original_plaintext"],
            final_expr=proof["simplified_form"],
            sha256=proof["sha256_hash"],
            ipfs_cid=proof["ipfs_cid"],
            signature_hex=proof["signature"],
            created_at=proof["created_at"],
        )

        steps = query_rows("derivation_steps", "proof_id = ?", (proof_id,))
        for row in sorted(steps, key=lambda r: r["step_number"]):
            chain.steps.append(DerivationStep(
                step_number=row["step_number"],
                operation=row["operation"],
                input_expr=row["input_expr"],
                output_expr=row["output_expr"],
                justification=row["justification"],
                is_valid=bool(row["is_valid"]),
            ))

        self._chains[chain.name] = chain
        return chain

    # ── IPFS Anchoring ───────────────────────────────────────────────────
    def anchor_to_ipfs(self, chain_name: str) -> str:
        """
        Serialize derivation chain to JSON → pin to IPFS → record CID.

        Returns the IPFS CID.
        """
        chain = self._chains.get(chain_name)
        if not chain:
            raise KeyError(f"No derivation chain named '{chain_name}'")

        if not chain.sha256:
            self.finalize_chain(chain_name)

        try:
            from src.ipfs.ipfs_client import IPFSClient
            client = IPFSClient()

            payload = chain.to_dict()
            result = client.add_json(payload, filename=f"derivation_{chain_name}.json")
            cid = result.get("Hash", "")
            chain.ipfs_cid = cid

            log.info("Pinned derivation '%s' to IPFS: %s", chain_name, cid)
            return cid
        except Exception as e:
            log.error("IPFS anchoring failed for '%s': %s", chain_name, e)
            return ""

    def sign_chain(self, chain_name: str, key_name: str = "default", passphrase: str = "") -> str:
        """
        Sign a derivation chain's CID with Ed25519.

        Must call anchor_to_ipfs first so a CID is available.
        Returns signature hex string.
        """
        chain = self._chains.get(chain_name)
        if not chain:
            raise KeyError(f"No derivation chain named '{chain_name}'")

        if not chain.ipfs_cid:
            log.warning("No CID for '%s' — call anchor_to_ipfs first", chain_name)
            return ""

        try:
            from src.crypto.signature_manager import SignatureManager
            sm = SignatureManager()
            sig_result = sm.sign_cid(chain.ipfs_cid, key_name=key_name, passphrase=passphrase)
            chain.signature_hex = sig_result["signature_hex"]
            log.info("Signed derivation '%s' CID %s (sig: %s…)",
                     chain_name, chain.ipfs_cid, chain.signature_hex[:16])
            return chain.signature_hex
        except Exception as e:
            log.error("Signing failed for '%s': %s", chain_name, e)
            return ""

    # ── Full Pipeline ────────────────────────────────────────────────────
    def anchor_and_sign(
        self,
        chain_name: str,
        key_name: str = "default",
        passphrase: str = "",
        save_db: bool = True,
    ) -> dict:
        """
        Complete pipeline: finalize → anchor to IPFS → sign → save to DB.

        Returns dict with sha256, ipfs_cid, signature_hex, proof_id.
        """
        self.finalize_chain(chain_name)
        cid = self.anchor_to_ipfs(chain_name)
        sig = ""
        if cid:
            sig = self.sign_chain(chain_name, key_name=key_name, passphrase=passphrase)

        proof_id = 0
        if save_db:
            proof_id = self.save_to_db(chain_name)

        chain = self._chains[chain_name]
        result = {
            "chain_name": chain_name,
            "sha256": chain.sha256,
            "ipfs_cid": cid,
            "signature_hex": sig,
            "proof_id": proof_id,
            "steps": len(chain.steps),
        }
        log.info("Full anchor pipeline complete for '%s': %s", chain_name, result)
        return result
