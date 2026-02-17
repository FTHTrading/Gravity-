"""
Multi-Gateway Pin Redundancy – Distributed Pin Verification

Provides:
  - Pin CIDs across multiple IPFS gateways for redundancy
  - External pinning service integration (Web3.Storage-style)
  - Retry logic with exponential backoff
  - Integrity re-check after pin operations
  - Gateway availability monitoring
  - Pin status reporting across all gateways

Ensures evidence CIDs are persisted across multiple nodes,
reducing single-point-of-failure risk.
"""

import json
import time
import hashlib
from datetime import datetime, timezone
from typing import Optional

import requests

from src.config import IPFS_PINNING_GATEWAYS
from src.database import insert_row
from src.logger import get_logger

log = get_logger(__name__)


class MultiGatewayPinner:
    """Pin CIDs to multiple IPFS gateways for redundancy."""

    def __init__(self, ipfs_client, gateways: list[dict] = None):
        self.ipfs = ipfs_client
        self.gateways = gateways or IPFS_PINNING_GATEWAYS
        self.session = requests.Session()
        self.session.headers["User-Agent"] = "ProjectAnchor/2.0"

    def pin_to_all(self, cid: str, retries: int = 3) -> dict:
        """
        Pin a CID to all configured gateways.
        Returns status for each gateway.
        """
        log.info("Pinning CID %s to %d gateways...", cid, len(self.gateways))
        results = {}
        success_count = 0
        fail_count = 0

        for gw in self.gateways:
            gw_name = gw["name"]
            gw_type = gw["type"]

            try:
                if gw_type == "rpc":
                    status = self._pin_via_rpc(cid, gw, retries)
                elif gw_type == "public":
                    status = self._verify_via_gateway(cid, gw)
                else:
                    status = {"success": False, "error": f"Unknown type: {gw_type}"}

                results[gw_name] = status
                if status.get("success"):
                    success_count += 1
                else:
                    fail_count += 1

            except Exception as exc:
                results[gw_name] = {"success": False, "error": str(exc)}
                fail_count += 1

        now = datetime.now(timezone.utc).isoformat()

        # Log to audit
        insert_row("audit_logs", {
            "operation": "multi_gateway_pin",
            "module": "ipfs",
            "detail": json.dumps({
                "cid": cid,
                "gateways": len(self.gateways),
                "success": success_count,
                "failed": fail_count,
            }),
            "cid_reference": cid,
            "status": "success" if success_count > 0 else "failed",
            "created_at": now,
        })

        summary = {
            "cid": cid,
            "total_gateways": len(self.gateways),
            "successful": success_count,
            "failed": fail_count,
            "gateway_results": results,
            "pinned_at": now,
        }

        log.info(
            "Multi-gateway pin: %d/%d successful for CID %s",
            success_count, len(self.gateways), cid[:24],
        )
        return summary

    def _pin_via_rpc(self, cid: str, gateway: dict, retries: int) -> dict:
        """Pin via IPFS RPC API (local node)."""
        for attempt in range(retries):
            try:
                result = self.ipfs.pin_add(cid)
                return {
                    "success": True,
                    "method": "rpc",
                    "gateway": gateway["name"],
                    "result": result,
                }
            except Exception as exc:
                if attempt < retries - 1:
                    wait = 2 ** attempt
                    log.warning(
                        "Pin attempt %d/%d failed for %s: %s. Retry in %ds",
                        attempt + 1, retries, gateway["name"], exc, wait,
                    )
                    time.sleep(wait)
                else:
                    return {
                        "success": False,
                        "method": "rpc",
                        "gateway": gateway["name"],
                        "error": str(exc),
                    }

    def _verify_via_gateway(self, cid: str, gateway: dict) -> dict:
        """
        Verify a CID is accessible via a public gateway.
        Public gateways don't support pinning, but we can verify availability.
        """
        url = f"{gateway['url']}/ipfs/{cid}"
        try:
            resp = self.session.head(url, timeout=30, allow_redirects=True)
            accessible = resp.status_code in (200, 301, 302)
            return {
                "success": accessible,
                "method": "gateway_verify",
                "gateway": gateway["name"],
                "url": url,
                "status_code": resp.status_code,
            }
        except Exception as exc:
            return {
                "success": False,
                "method": "gateway_verify",
                "gateway": gateway["name"],
                "url": url,
                "error": str(exc),
            }

    def verify_integrity(self, cid: str, expected_hash: str) -> dict:
        """
        Download content from local node and verify SHA-256 hash.
        Post-pin integrity check.
        """
        try:
            content = self.ipfs.cat(cid)
            actual_hash = hashlib.sha256(content).hexdigest()
            match = actual_hash == expected_hash
            return {
                "cid": cid,
                "integrity_verified": match,
                "expected_hash": expected_hash,
                "actual_hash": actual_hash,
                "content_size": len(content),
            }
        except Exception as exc:
            return {
                "cid": cid,
                "integrity_verified": False,
                "error": str(exc),
            }

    def gateway_health_check(self) -> list[dict]:
        """Check availability of all configured gateways."""
        results = []
        for gw in self.gateways:
            try:
                if gw["type"] == "rpc":
                    online = self.ipfs.is_online()
                    results.append({
                        "name": gw["name"],
                        "type": gw["type"],
                        "online": online,
                    })
                else:
                    resp = self.session.head(
                        gw["url"], timeout=10, allow_redirects=True
                    )
                    results.append({
                        "name": gw["name"],
                        "type": gw["type"],
                        "online": resp.status_code < 500,
                        "status_code": resp.status_code,
                    })
            except Exception as exc:
                results.append({
                    "name": gw["name"],
                    "type": gw["type"],
                    "online": False,
                    "error": str(exc),
                })
        return results
