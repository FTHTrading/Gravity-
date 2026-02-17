"""
IPFS Proof Chain Module – Immutable Evidence Trail.

Creates a verifiable, content-addressed chain of evidence on IPFS:

  - Each piece of evidence (post, document, computation) is pinned to IPFS
  - A DAG-linked proof chain connects all evidence chronologically
  - Each link contains: CID of evidence, SHA-256 hash, timestamp, type
  - The chain itself is stored as a DAG on IPFS
  - Previous link CID is embedded in each new link (blockchain-like)
  - IPNS name points to latest chain head for stable reference

Structure of a proof link:
    {
        "version": 1,
        "sequence": N,
        "timestamp": "ISO-8601",
        "evidence_type": "social_post | document | physics | narrative | ...",
        "evidence_cid": "bafy...",
        "content_hash_sha256": "abc123...",
        "description": "...",
        "previous": { "/": "CID_of_previous_link" },  # IPLD link
        "metadata": { ... }
    }
"""

import json
import hashlib
from datetime import datetime, timezone
from typing import Any, Optional

from src.database import insert_row, query_rows
from src.logger import get_logger

log = get_logger(__name__)


class ProofChain:
    """Build and manage an IPFS-backed immutable proof chain."""

    def __init__(self, ipfs_client):
        """
        Args:
            ipfs_client: An instance of src.ipfs.ipfs_client.IPFSClient
        """
        self.ipfs = ipfs_client
        self._chain_head_cid: Optional[str] = None
        self._sequence: int = 0

        # Load existing chain state from DB
        self._load_state()

    def _load_state(self):
        """Resume chain from database if prior links exist."""
        rows = query_rows("ipfs_evidence", where="1=1 ORDER BY sequence DESC LIMIT 1")
        if rows:
            last = rows[0]
            self._chain_head_cid = last.get("proof_chain_cid")
            self._sequence = last.get("sequence", 0)
            log.info("Proof chain resumed at sequence %d, head CID: %s",
                     self._sequence, self._chain_head_cid)

    # ── Add Evidence to Chain ────────────────────────────────────────────
    def add_evidence(
        self,
        content: Any,
        evidence_type: str,
        description: str,
        content_filename: str = "evidence.json",
        metadata: Optional[dict] = None,
    ) -> dict:
        """
        Pin evidence content to IPFS and append a proof link to the chain.

        Args:
            content: Raw content (str, bytes, or JSON-serializable object)
            evidence_type: Category (social_post, document, physics, etc.)
            description: Human-readable description
            content_filename: Filename for the IPFS object
            metadata: Additional metadata dict

        Returns:
            Dict with evidence_cid, proof_link_cid, sequence, gateway_urls
        """
        # 1. Pin the evidence content to IPFS
        if isinstance(content, bytes):
            evidence_result = self.ipfs.add_bytes(content, content_filename)
            content_hash = hashlib.sha256(content).hexdigest()
        elif isinstance(content, str):
            evidence_result = self.ipfs.add_str(content, content_filename)
            content_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()
        else:
            serialized = json.dumps(content, indent=2, default=str)
            evidence_result = self.ipfs.add_json(content, content_filename)
            content_hash = hashlib.sha256(serialized.encode("utf-8")).hexdigest()

        evidence_cid = evidence_result.get("Hash")
        evidence_size = evidence_result.get("Size")

        # 2. Build the proof link
        self._sequence += 1
        timestamp = datetime.now(timezone.utc).isoformat()

        proof_link = {
            "version": 1,
            "sequence": self._sequence,
            "timestamp": timestamp,
            "evidence_type": evidence_type,
            "evidence_cid": evidence_cid,
            "content_hash_sha256": content_hash,
            "content_size": evidence_size,
            "description": description,
            "metadata": metadata or {},
        }

        # 3. Link to previous (IPLD DAG link)
        if self._chain_head_cid:
            proof_link["previous"] = {"/": self._chain_head_cid}
        else:
            proof_link["previous"] = None  # Genesis link

        # 4. Store the proof link as a DAG node on IPFS
        proof_cid = self.ipfs.dag_put(proof_link)
        self._chain_head_cid = proof_cid

        # 5. Record in local database
        insert_row("ipfs_evidence", {
            "evidence_cid": evidence_cid,
            "proof_chain_cid": proof_cid,
            "evidence_type": evidence_type,
            "description": description,
            "content_hash": content_hash,
            "content_size": int(evidence_size) if evidence_size else 0,
            "sequence": self._sequence,
            "previous_cid": proof_link.get("previous", {}).get("/") if proof_link.get("previous") else None,
            "metadata_json": json.dumps(metadata or {}, default=str),
            "pinned_at": timestamp,
        })

        result = {
            "sequence": self._sequence,
            "evidence_cid": evidence_cid,
            "proof_link_cid": proof_cid,
            "content_hash_sha256": content_hash,
            "gateway_url": self.ipfs.gateway_url_for(evidence_cid),
            "public_url": self.ipfs.public_gateway_url_for(evidence_cid),
            "proof_gateway_url": self.ipfs.gateway_url_for(proof_cid),
        }

        log.info(
            "Evidence #%d pinned: type=%s  CID=%s  proof=%s",
            self._sequence, evidence_type, evidence_cid, proof_cid,
        )
        return result

    # ── Convenience Methods ──────────────────────────────────────────────
    def add_file_evidence(
        self,
        filepath: str,
        evidence_type: str = "document",
        description: str = "",
        metadata: Optional[dict] = None,
    ) -> dict:
        """Pin a file from disk as evidence."""
        from pathlib import Path
        path = Path(filepath)
        content = path.read_bytes()
        if not description:
            description = f"File: {path.name}"
        return self.add_evidence(
            content, evidence_type, description,
            content_filename=path.name, metadata=metadata,
        )

    def add_report_evidence(self, report_data: dict, report_name: str) -> dict:
        """Pin a generated report as evidence."""
        return self.add_evidence(
            report_data,
            evidence_type="report",
            description=f"Research report: {report_name}",
            content_filename=f"{report_name}.json",
        )

    def add_physics_evidence(self, physics_results: list[dict]) -> dict:
        """Pin physics computation results as evidence."""
        return self.add_evidence(
            physics_results,
            evidence_type="physics_computation",
            description=f"Physics comparison suite: {len(physics_results)} computations",
            content_filename="physics_results.json",
        )

    def add_social_post_evidence(self, post: dict) -> dict:
        """Pin a collected social post as evidence."""
        return self.add_evidence(
            post,
            evidence_type="social_post",
            description=f"Social post from {post.get('platform', 'unknown')}",
            content_filename="social_post.json",
            metadata={"platform": post.get("platform"), "url": post.get("post_url")},
        )

    # ── Chain Verification ───────────────────────────────────────────────
    def verify_chain(self, head_cid: Optional[str] = None) -> dict:
        """
        Walk the proof chain backwards from head, verifying each link.
        Returns verification report.
        """
        cid = head_cid or self._chain_head_cid
        if not cid:
            return {"status": "no_chain", "links_verified": 0}

        verified = 0
        broken = []
        current = cid

        while current:
            try:
                link = self.ipfs.dag_get(current)
                verified += 1

                # Verify evidence content hash
                evidence_cid = link.get("evidence_cid")
                expected_hash = link.get("content_hash_sha256")
                if evidence_cid and expected_hash:
                    try:
                        actual_content = self.ipfs.cat(evidence_cid)
                        actual_hash = hashlib.sha256(actual_content).hexdigest()
                        if actual_hash != expected_hash:
                            broken.append({
                                "sequence": link.get("sequence"),
                                "cid": current,
                                "error": "content_hash_mismatch",
                            })
                    except Exception:
                        broken.append({
                            "sequence": link.get("sequence"),
                            "cid": current,
                            "error": "evidence_not_retrievable",
                        })

                # Navigate to previous link
                prev = link.get("previous")
                current = prev.get("/") if isinstance(prev, dict) else None

            except Exception as exc:
                broken.append({"cid": current, "error": str(exc)})
                break

        report = {
            "status": "valid" if not broken else "broken",
            "head_cid": head_cid or self._chain_head_cid,
            "links_verified": verified,
            "broken_links": broken,
            "verified_at": datetime.now(timezone.utc).isoformat(),
        }
        log.info("Chain verification: %d links, %d broken", verified, len(broken))
        return report

    # ── Publish Chain to IPNS ────────────────────────────────────────────
    def publish_to_ipns(self) -> dict:
        """
        Publish the current chain head to IPNS.
        Creates a stable, updatable reference to the latest proof chain.
        """
        if not self._chain_head_cid:
            log.warning("No chain head to publish.")
            return {"error": "no_chain_head"}

        result = self.ipfs.name_publish(self._chain_head_cid)
        log.info("Proof chain published to IPNS: %s", result)
        return result

    # ── Chain Export ─────────────────────────────────────────────────────
    def export_chain_manifest(self) -> dict:
        """
        Build a complete manifest of the proof chain from the database.
        """
        rows = query_rows("ipfs_evidence", where="1=1 ORDER BY sequence ASC")
        return {
            "chain_head": self._chain_head_cid,
            "total_links": len(rows),
            "peer_id": self.ipfs.peer_id(),
            "exported_at": datetime.now(timezone.utc).isoformat(),
            "links": rows,
        }

    @property
    def head_cid(self) -> Optional[str]:
        return self._chain_head_cid

    @property
    def chain_length(self) -> int:
        return self._sequence
