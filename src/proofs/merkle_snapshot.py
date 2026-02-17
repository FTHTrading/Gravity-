"""
Merkle Snapshot Engine – Deterministic Database Integrity Proofs

Provides:
  - Deterministic hashing of all database rows
  - Merkle tree construction from row hashes
  - Root hash generation + proof path extraction
  - Anchoring root hash to IPFS
  - Snapshot verification against stored roots
  - Chain of snapshots (each references previous root)

Each snapshot captures the entire database state as a Merkle tree,
producing a single root hash that can be independently verified.
"""

import hashlib
import json
import math
from datetime import datetime, timezone
from typing import Optional

from src.database import get_connection, insert_row, query_rows
from src.logger import get_logger

log = get_logger(__name__)

# Tables to include in snapshots (ordered for determinism)
SNAPSHOT_TABLES = [
    "social_posts",
    "documents",
    "academic_records",
    "government_records",
    "propagation_edges",
    "physics_comparisons",
    "narrative_patterns",
    "ipfs_evidence",
    "taxonomy_entries",
    "foia_documents",
    "investigation_cases",
    "case_claims",
    "scientist_cases",
]


class MerkleTree:
    """Binary Merkle tree for data integrity verification."""

    def __init__(self, leaves: list[str]):
        """
        Build a Merkle tree from a list of hex-encoded leaf hashes.
        """
        self.leaves = leaves[:]
        self.tree: list[list[str]] = []
        self.root: str = ""
        self._build()

    def _hash_pair(self, left: str, right: str) -> str:
        """Hash two hex strings together."""
        combined = (left + right).encode("utf-8")
        return hashlib.sha256(combined).hexdigest()

    def _build(self):
        """Construct the Merkle tree bottom-up."""
        if not self.leaves:
            self.root = hashlib.sha256(b"empty").hexdigest()
            self.tree = [[self.root]]
            return

        # Pad to even number if necessary
        current_level = self.leaves[:]
        if len(current_level) % 2 == 1:
            current_level.append(current_level[-1])  # duplicate last

        self.tree = [current_level]

        while len(current_level) > 1:
            next_level = []
            for i in range(0, len(current_level), 2):
                left = current_level[i]
                right = current_level[i + 1] if i + 1 < len(current_level) else left
                next_level.append(self._hash_pair(left, right))

            if len(next_level) > 1 and len(next_level) % 2 == 1:
                next_level.append(next_level[-1])

            self.tree.append(next_level)
            current_level = next_level

        self.root = current_level[0]

    def get_proof(self, leaf_index: int) -> list[dict]:
        """
        Get the Merkle proof path for a specific leaf.
        Returns list of {hash, position} pairs.
        """
        if leaf_index >= len(self.leaves):
            return []

        proof = []
        idx = leaf_index
        for level in self.tree[:-1]:  # All levels except root
            if idx % 2 == 0:
                sibling_idx = idx + 1
                pos = "right"
            else:
                sibling_idx = idx - 1
                pos = "left"

            if sibling_idx < len(level):
                proof.append({"hash": level[sibling_idx], "position": pos})

            idx = idx // 2

        return proof

    @staticmethod
    def verify_proof(leaf_hash: str, proof: list[dict], root: str) -> bool:
        """Verify a Merkle proof against a root hash."""
        current = leaf_hash
        for step in proof:
            if step["position"] == "right":
                combined = (current + step["hash"]).encode("utf-8")
            else:
                combined = (step["hash"] + current).encode("utf-8")
            current = hashlib.sha256(combined).hexdigest()
        return current == root

    def to_dict(self) -> dict:
        """Serialize tree structure."""
        return {
            "root": self.root,
            "leaf_count": len(self.leaves),
            "depth": len(self.tree),
            "tree_levels": [len(level) for level in self.tree],
        }


class MerkleSnapshotEngine:
    """Creates and verifies Merkle snapshots of the entire database."""

    def __init__(self, ipfs_client=None):
        self.ipfs = ipfs_client

    def _hash_row(self, row: dict) -> str:
        """Deterministically hash a database row."""
        # Sort keys for determinism, serialize values
        canonical = json.dumps(row, sort_keys=True, default=str)
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    def _hash_table(self, table_name: str) -> dict:
        """Hash all rows in a table, return table hash + row hashes."""
        try:
            with get_connection() as conn:
                rows = conn.execute(
                    f"SELECT * FROM {table_name} ORDER BY id"
                ).fetchall()
            row_dicts = [dict(r) for r in rows]
        except Exception:
            row_dicts = []

        row_hashes = [self._hash_row(r) for r in row_dicts]

        # Table-level hash = hash of all row hashes concatenated
        if row_hashes:
            combined = "".join(row_hashes)
            table_hash = hashlib.sha256(combined.encode("utf-8")).hexdigest()
        else:
            table_hash = hashlib.sha256(f"empty:{table_name}".encode()).hexdigest()

        return {
            "table": table_name,
            "row_count": len(row_dicts),
            "table_hash": table_hash,
            "row_hashes": row_hashes,
        }

    def create_snapshot(self) -> dict:
        """
        Create a full Merkle snapshot of the database.
        Returns snapshot metadata with root hash.
        """
        log.info("Creating Merkle snapshot of database...")

        # Hash each table
        table_results = {}
        all_leaves = []
        total_rows = 0

        for table in SNAPSHOT_TABLES:
            result = self._hash_table(table)
            table_results[table] = {
                "row_count": result["row_count"],
                "table_hash": result["table_hash"],
            }
            all_leaves.extend(result["row_hashes"])
            total_rows += result["row_count"]

        # If no data, use table hashes as leaves
        if not all_leaves:
            all_leaves = [r["table_hash"] for r in
                          [self._hash_table(t) for t in SNAPSHOT_TABLES]]

        # Build Merkle tree
        tree = MerkleTree(all_leaves)

        now = datetime.now(timezone.utc).isoformat()

        # Get previous snapshot root
        prev_snapshots = query_rows(
            "merkle_snapshots",
            "1=1 ORDER BY id DESC LIMIT 1"
        )
        previous_root = prev_snapshots[0]["root_hash"] if prev_snapshots else None

        # Anchor to IPFS if client available
        ipfs_cid = None
        if self.ipfs:
            try:
                snapshot_data = {
                    "type": "merkle_snapshot",
                    "root_hash": tree.root,
                    "table_hashes": table_results,
                    "total_rows": total_rows,
                    "leaf_count": len(all_leaves),
                    "previous_root": previous_root,
                    "created_at": now,
                }
                result = self.ipfs.add_json(snapshot_data, "merkle_snapshot.json")
                ipfs_cid = result.get("Hash")
                log.info("Snapshot anchored to IPFS: %s", ipfs_cid)
            except Exception as exc:
                log.warning("Failed to anchor snapshot to IPFS: %s", exc)

        # Store in database
        tree_json = json.dumps(tree.to_dict())
        table_hashes_json = json.dumps(table_results)

        insert_row("merkle_snapshots", {
            "root_hash": tree.root,
            "tree_json": tree_json,
            "table_hashes": table_hashes_json,
            "total_rows": total_rows,
            "ipfs_cid": ipfs_cid,
            "previous_root": previous_root,
            "created_at": now,
            "status": "created",
        })

        snapshot = {
            "root_hash": tree.root,
            "total_rows": total_rows,
            "leaf_count": len(all_leaves),
            "table_count": len(SNAPSHOT_TABLES),
            "table_hashes": table_results,
            "ipfs_cid": ipfs_cid,
            "previous_root": previous_root,
            "created_at": now,
        }

        log.info(
            "Merkle snapshot created: root=%s rows=%d leaves=%d",
            tree.root[:16], total_rows, len(all_leaves),
        )
        return snapshot

    def verify_snapshot(self, root_hash: str) -> dict:
        """
        Verify a stored snapshot against current database state.
        Recomputes all hashes and compares against stored root.
        """
        log.info("Verifying snapshot: %s", root_hash)

        # Get stored snapshot
        snapshots = query_rows("merkle_snapshots", "root_hash = ?", (root_hash,))
        if not snapshots:
            return {
                "verified": False,
                "error": f"Snapshot not found: {root_hash}",
            }

        stored = snapshots[0]
        stored_table_hashes = json.loads(stored["table_hashes"]) if stored["table_hashes"] else {}

        # Recompute current state
        all_leaves = []
        table_matches = {}
        total_rows = 0
        mismatches = []

        for table in SNAPSHOT_TABLES:
            result = self._hash_table(table)
            total_rows += result["row_count"]
            all_leaves.extend(result["row_hashes"])

            stored_th = stored_table_hashes.get(table, {})
            current_hash = result["table_hash"]
            stored_hash = stored_th.get("table_hash", "")

            match = current_hash == stored_hash
            table_matches[table] = {
                "match": match,
                "current_rows": result["row_count"],
                "stored_rows": stored_th.get("row_count", 0),
            }
            if not match:
                mismatches.append(table)

        # Rebuild Merkle tree
        if not all_leaves:
            all_leaves = [r["table_hash"] for r in
                          [self._hash_table(t) for t in SNAPSHOT_TABLES]]

        tree = MerkleTree(all_leaves)
        root_match = tree.root == root_hash

        now = datetime.now(timezone.utc).isoformat()

        # Update verification timestamp
        with get_connection() as conn:
            conn.execute(
                "UPDATE merkle_snapshots SET verified_at = ?, status = ? WHERE root_hash = ?",
                (now, "verified" if root_match else "mismatch", root_hash),
            )

        result = {
            "verified": root_match,
            "stored_root": root_hash,
            "computed_root": tree.root,
            "total_rows": total_rows,
            "tables_checked": len(SNAPSHOT_TABLES),
            "tables_matched": len(SNAPSHOT_TABLES) - len(mismatches),
            "mismatched_tables": mismatches,
            "table_details": table_matches,
            "verified_at": now,
        }

        log.info(
            "Snapshot verification: %s (stored=%s computed=%s)",
            "MATCH" if root_match else "MISMATCH",
            root_hash[:16], tree.root[:16],
        )
        return result

    def list_snapshots(self) -> list[dict]:
        """List all stored Merkle snapshots."""
        return query_rows("merkle_snapshots", "1=1 ORDER BY id DESC")

    def get_latest_root(self) -> Optional[str]:
        """Get the most recent snapshot root hash."""
        snapshots = query_rows("merkle_snapshots", "1=1 ORDER BY id DESC LIMIT 1")
        return snapshots[0]["root_hash"] if snapshots else None
