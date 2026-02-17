"""
IPNS Publisher Module – Stable Evidence Pointers

Provides:
  - Publish proof-chain root / Merkle snapshot to IPNS
  - Auto-update IPNS pointer on new archive operations
  - Manual publish / resolve commands
  - History tracking of all IPNS publications
  - Integration with audit logging

IPNS gives a stable name (based on peer key) that can be updated
to point at the latest evidence CID, so external verifiers can use
one permanent address to always find the current state.
"""

import json
from datetime import datetime, timezone
from typing import Optional

from src.database import insert_row, query_rows, get_connection
from src.logger import get_logger

log = get_logger(__name__)


class IPNSPublisher:
    """Manages IPNS publishing for stable evidence pointers."""

    def __init__(self, ipfs_client):
        self.ipfs = ipfs_client

    def publish(
        self,
        cid: str,
        lifetime: str = "24h",
        description: str = "",
    ) -> dict:
        """
        Publish a CID to IPNS.
        The IPNS name is derived from the node's peer key.
        """
        log.info("Publishing CID %s to IPNS (lifetime=%s)...", cid, lifetime)

        try:
            result = self.ipfs.name_publish(cid, lifetime=lifetime)
        except Exception as exc:
            log.error("IPNS publish failed: %s", exc)
            return {"success": False, "error": str(exc)}

        now = datetime.now(timezone.utc).isoformat()

        ipns_name = result.get("Name", "")
        ipns_value = result.get("Value", "")

        # Log to audit
        insert_row("audit_logs", {
            "operation": "ipns_publish",
            "module": "ipns",
            "detail": json.dumps({
                "cid": cid,
                "ipns_name": ipns_name,
                "ipns_value": ipns_value,
                "lifetime": lifetime,
                "description": description,
            }),
            "cid_reference": cid,
            "signature": "",
            "user_key": ipns_name,
            "status": "success",
            "created_at": now,
        })

        publish_result = {
            "success": True,
            "ipns_name": ipns_name,
            "ipns_value": ipns_value,
            "cid": cid,
            "lifetime": lifetime,
            "published_at": now,
        }

        log.info(
            "IPNS published: /ipns/%s → /ipfs/%s",
            ipns_name[:24] + "...",
            cid[:24] + "...",
        )
        return publish_result

    def resolve(self, name: str = "") -> dict:
        """
        Resolve an IPNS name to its current CID.
        If no name given, resolves this node's own IPNS name.
        """
        log.info("Resolving IPNS name: %s", name or "(self)")

        try:
            path = self.ipfs.name_resolve(name)
        except Exception as exc:
            log.error("IPNS resolve failed: %s", exc)
            return {"success": False, "error": str(exc)}

        now = datetime.now(timezone.utc).isoformat()

        # Extract CID from path (format: /ipfs/Qm...)
        cid = path.replace("/ipfs/", "").strip("/") if path else ""

        result = {
            "success": True,
            "ipns_name": name or "(self)",
            "resolved_path": path,
            "resolved_cid": cid,
            "resolved_at": now,
        }

        log.info("IPNS resolved: %s → %s", name or "(self)", path)
        return result

    def publish_evidence_root(
        self,
        evidence_cid: Optional[str] = None,
        merkle_root_cid: Optional[str] = None,
    ) -> dict:
        """
        Publish a composite evidence manifest to IPNS.
        Wraps evidence chain head + merkle snapshot root into a single DAG node.
        """
        if not evidence_cid and not merkle_root_cid:
            log.warning("No CID provided to publish")
            return {"success": False, "error": "No CID provided"}

        manifest = {
            "type": "project_anchor_evidence_root",
            "version": "2.0",
            "evidence_chain_head": evidence_cid,
            "merkle_snapshot_root": merkle_root_cid,
            "published_at": datetime.now(timezone.utc).isoformat(),
        }

        try:
            # Store manifest as DAG node
            manifest_cid = self.ipfs.dag_put(manifest)
            log.info("Evidence manifest stored: %s", manifest_cid)

            # Publish the manifest to IPNS
            return self.publish(
                manifest_cid,
                lifetime="48h",
                description="Project Anchor evidence root manifest",
            )
        except Exception as exc:
            log.error("Failed to publish evidence root: %s", exc)
            return {"success": False, "error": str(exc)}

    def get_publish_history(self) -> list[dict]:
        """Get history of all IPNS publications from audit log."""
        return query_rows(
            "audit_logs",
            "operation = 'ipns_publish' ORDER BY id DESC",
        )
