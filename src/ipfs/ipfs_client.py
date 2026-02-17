"""
IPFS Client Module – Interface to local Kubo RPC API.

Provides:
  - Connection management and health checks
  - File/directory adding (pinning to IPFS)
  - Content retrieval by CID
  - Pin management (pin, unpin, list)
  - Peer and node status reporting
  - DAG operations for structured data
  - Name publishing (IPNS)

Connects to local Kubo node via HTTP RPC API (default: 127.0.0.1:5001).
All operations produce content-addressed CIDs for immutable evidence trails.
"""

import json
import hashlib
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional, BinaryIO

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from src.config import IPFS_API_URL, IPFS_GATEWAY_URL
from src.logger import get_logger

log = get_logger(__name__)


class IPFSClient:
    """Interface to local IPFS Kubo RPC API."""

    def __init__(self, api_url: str = IPFS_API_URL, gateway_url: str = IPFS_GATEWAY_URL):
        self.api_url = api_url.rstrip("/")
        self.gateway_url = gateway_url.rstrip("/")
        self.session = self._build_session()
        self._peer_id: Optional[str] = None

    @staticmethod
    def _build_session() -> requests.Session:
        session = requests.Session()
        retry = Retry(total=3, backoff_factor=0.5, status_forcelist=[502, 503, 504])
        adapter = HTTPAdapter(max_retries=retry)
        session.mount("http://", adapter)
        session.mount("https://", adapter)
        return session

    # ── API Call Helper ──────────────────────────────────────────────────
    def _api(self, endpoint: str, method: str = "POST", **kwargs) -> requests.Response:
        """Call an IPFS RPC endpoint."""
        url = f"{self.api_url}/api/v0/{endpoint}"
        resp = self.session.request(method, url, timeout=60, **kwargs)
        resp.raise_for_status()
        return resp

    # ── Node Identity & Health ───────────────────────────────────────────
    def node_id(self) -> dict:
        """Get IPFS node identity info."""
        data = self._api("id").json()
        self._peer_id = data.get("ID")
        log.info("IPFS Node ID: %s", self._peer_id)
        return data

    def is_online(self) -> bool:
        """Check if IPFS node is reachable."""
        try:
            self.node_id()
            return True
        except Exception as exc:
            log.warning("IPFS node not reachable: %s", exc)
            return False

    def peer_id(self) -> str:
        """Return cached or fetched peer ID."""
        if not self._peer_id:
            self.node_id()
        return self._peer_id or ""

    def swarm_peers(self) -> list[dict]:
        """List connected swarm peers."""
        data = self._api("swarm/peers").json()
        peers = data.get("Peers") or []
        log.info("Connected to %d IPFS peers", len(peers))
        return peers

    def repo_stat(self) -> dict:
        """Get IPFS repo statistics."""
        return self._api("repo/stat").json()

    def bandwidth_stats(self) -> dict:
        """Get bandwidth statistics."""
        return self._api("stats/bw").json()

    # ── Add Content ──────────────────────────────────────────────────────
    def add_bytes(self, data: bytes, filename: str = "data") -> dict:
        """
        Add raw bytes to IPFS. Returns dict with CID ('Hash'), 'Name', 'Size'.
        Content is automatically pinned.
        """
        files = {"file": (filename, data)}
        resp = self._api("add", files=files, params={"pin": "true", "cid-version": "1"})
        result = resp.json()
        log.info("Added to IPFS: %s → CID: %s (%s bytes)",
                 filename, result.get("Hash"), result.get("Size"))
        return result

    def add_str(self, text: str, filename: str = "data.txt") -> dict:
        """Add a string to IPFS."""
        return self.add_bytes(text.encode("utf-8"), filename)

    def add_json(self, obj: Any, filename: str = "data.json") -> dict:
        """Add a JSON-serializable object to IPFS."""
        data = json.dumps(obj, indent=2, default=str, ensure_ascii=False)
        return self.add_bytes(data.encode("utf-8"), filename)

    def add_file(self, filepath: str | Path) -> dict:
        """Add a file from disk to IPFS."""
        path = Path(filepath)
        if not path.exists():
            raise FileNotFoundError(f"File not found: {path}")

        with open(path, "rb") as f:
            files = {"file": (path.name, f)}
            resp = self._api("add", files=files, params={"pin": "true", "cid-version": "1"})

        result = resp.json()
        log.info("File pinned to IPFS: %s → CID: %s", path.name, result.get("Hash"))
        return result

    def add_directory(self, dirpath: str | Path) -> list[dict]:
        """
        Add an entire directory to IPFS recursively.
        Returns list of {Hash, Name, Size} for each file + the wrapping directory.
        """
        dirpath = Path(dirpath)
        if not dirpath.is_dir():
            raise NotADirectoryError(f"Not a directory: {dirpath}")

        files = []
        for fpath in sorted(dirpath.rglob("*")):
            if fpath.is_file():
                rel = fpath.relative_to(dirpath)
                files.append(
                    ("file", (str(rel), open(fpath, "rb")))
                )

        try:
            resp = self._api(
                "add",
                files=files,
                params={"pin": "true", "wrap-with-directory": "true",
                        "cid-version": "1", "recursive": "true"},
            )
            # Multi-file add returns newline-delimited JSON
            results = [json.loads(line) for line in resp.text.strip().split("\n") if line.strip()]
        finally:
            for _, (_, fobj) in files:
                fobj.close()

        log.info("Directory pinned to IPFS: %s → %d objects", dirpath, len(results))
        return results

    # ── Retrieve Content ─────────────────────────────────────────────────
    def cat(self, cid: str) -> bytes:
        """Retrieve raw content by CID."""
        resp = self._api("cat", params={"arg": cid})
        return resp.content

    def cat_json(self, cid: str) -> Any:
        """Retrieve and parse JSON content by CID."""
        data = self.cat(cid)
        return json.loads(data)

    def get_to_file(self, cid: str, output_path: str | Path) -> Path:
        """Download a CID to a local file."""
        content = self.cat(cid)
        path = Path(output_path)
        path.write_bytes(content)
        log.info("Retrieved CID %s → %s (%d bytes)", cid, path, len(content))
        return path

    # ── Pin Management ───────────────────────────────────────────────────
    def pin_add(self, cid: str) -> dict:
        """Pin a CID to prevent garbage collection."""
        result = self._api("pin/add", params={"arg": cid}).json()
        log.info("Pinned: %s", cid)
        return result

    def pin_rm(self, cid: str) -> dict:
        """Unpin a CID."""
        result = self._api("pin/rm", params={"arg": cid}).json()
        log.info("Unpinned: %s", cid)
        return result

    def pin_ls(self, pin_type: str = "all") -> dict:
        """List pinned CIDs. Types: all, direct, recursive, indirect."""
        return self._api("pin/ls", params={"type": pin_type}).json()

    # ── DAG Operations (structured data) ──────────────────────────────────
    def dag_put(self, obj: Any) -> str:
        """
        Store a structured DAG object in IPFS.
        Returns the CID of the DAG node.
        """
        data = json.dumps(obj, default=str).encode("utf-8")
        files = {"file": ("dag.json", data)}
        resp = self._api("dag/put", files=files,
                         params={"store-codec": "dag-json", "input-codec": "dag-json"})
        result = resp.json()
        cid = result.get("Cid", {}).get("/", str(result))
        log.info("DAG node stored: %s", cid)
        return cid

    def dag_get(self, cid: str) -> Any:
        """Retrieve a DAG node by CID."""
        resp = self._api("dag/get", params={"arg": cid})
        return resp.json()

    # ── IPNS Publishing ──────────────────────────────────────────────────
    def name_publish(self, cid: str, lifetime: str = "24h") -> dict:
        """
        Publish a CID to IPNS (makes it updatable by peer key).
        This lets you have a stable address that points to the latest evidence.
        """
        result = self._api("name/publish",
                           params={"arg": cid, "lifetime": lifetime}).json()
        log.info("Published to IPNS: %s → %s", result.get("Name"), result.get("Value"))
        return result

    def name_resolve(self, name: str = "") -> str:
        """Resolve an IPNS name to its current CID."""
        params = {}
        if name:
            params["arg"] = name
        result = self._api("name/resolve", params=params).json()
        return result.get("Path", "")

    # ── Utility ──────────────────────────────────────────────────────────
    def gateway_url_for(self, cid: str) -> str:
        """Return the local gateway URL for a CID."""
        return f"{self.gateway_url}/ipfs/{cid}"

    def public_gateway_url_for(self, cid: str) -> str:
        """Return a public gateway URL for a CID."""
        return f"https://ipfs.io/ipfs/{cid}"

    def verify_content(self, cid: str, expected_hash: str) -> bool:
        """Download content and verify its SHA-256 matches expected."""
        content = self.cat(cid)
        actual = hashlib.sha256(content).hexdigest()
        match = actual == expected_hash
        log.info("Verify CID %s: SHA-256 %s (expected %s) → %s",
                 cid, actual[:16], expected_hash[:16], "MATCH" if match else "MISMATCH")
        return match

    def status_summary(self) -> dict:
        """Return a full status summary of the IPFS node."""
        try:
            identity = self.node_id()
            repo = self.repo_stat()
            peers = self.swarm_peers()
            return {
                "online": True,
                "peer_id": identity.get("ID"),
                "agent": identity.get("AgentVersion"),
                "repo_size_bytes": repo.get("RepoSize"),
                "repo_objects": repo.get("NumObjects"),
                "connected_peers": len(peers),
                "addresses": identity.get("Addresses", [])[:5],
                "checked_at": datetime.now(timezone.utc).isoformat(),
            }
        except Exception as exc:
            return {"online": False, "error": str(exc)}
