"""
Cryptographic Signature Manager – Ed25519 Keypair & CID Signing

Provides:
  - Ed25519 keypair generation (private key encrypted at rest)
  - CID signing before database insertion
  - Signature verification before proof-chain linking
  - Key management (create, list, activate/deactivate)
  - Fingerprint-based key identification

Uses Python's built-in cryptography via the `cryptography` library.
Private keys are stored encrypted with a passphrase using Fernet symmetric encryption.
"""

import hashlib
import json
import os
import base64
from datetime import datetime, timezone
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Optional

from src.config import KEYS_DIR
from src.database import insert_row, query_rows, get_connection
from src.logger import get_logger

log = get_logger(__name__)

# Ed25519 via cryptography library
try:
    from cryptography.hazmat.primitives.asymmetric.ed25519 import (
        Ed25519PrivateKey,
        Ed25519PublicKey,
    )
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
    from cryptography.hazmat.primitives import hashes
    from cryptography.fernet import Fernet
    HAS_CRYPTO = True
except ImportError:
    HAS_CRYPTO = False


@dataclass
class KeyInfo:
    """Metadata for a signing key."""
    key_name: str
    algorithm: str
    public_key_hex: str
    fingerprint: str
    created_at: str
    is_active: bool


class SignatureManager:
    """Ed25519 cryptographic signature management for IPFS evidence."""

    def __init__(self, keys_dir: Path = KEYS_DIR):
        self.keys_dir = Path(keys_dir)
        self.keys_dir.mkdir(parents=True, exist_ok=True)
        if not HAS_CRYPTO:
            log.warning("cryptography library not installed. "
                        "Install with: pip install cryptography")

    def _require_crypto(self):
        if not HAS_CRYPTO:
            raise ImportError(
                "cryptography library required. Install: pip install cryptography"
            )

    # ── Key Generation ───────────────────────────────────────────────────
    def generate_keypair(
        self,
        key_name: str = "default",
        passphrase: str = "",
    ) -> KeyInfo:
        """
        Generate a new Ed25519 keypair.
        Private key is stored encrypted in keys_dir.
        Public key metadata is stored in the database.
        """
        self._require_crypto()

        # Generate key
        private_key = Ed25519PrivateKey.generate()
        public_key = private_key.public_key()

        # Serialize
        pub_bytes = public_key.public_bytes(
            serialization.Encoding.Raw,
            serialization.PublicFormat.Raw,
        )
        pub_hex = pub_bytes.hex()
        fingerprint = hashlib.sha256(pub_bytes).hexdigest()[:32]

        # Encrypt and store private key
        priv_bytes = private_key.private_bytes(
            serialization.Encoding.Raw,
            serialization.PrivateFormat.Raw,
            serialization.NoEncryption(),
        )

        if passphrase:
            encrypted = self._encrypt_key(priv_bytes, passphrase)
        else:
            # Base64 encode without encryption (dev mode)
            encrypted = base64.b64encode(priv_bytes).decode()

        # Save private key file
        key_file = self.keys_dir / f"{key_name}.key"
        key_file.write_text(encrypted)
        log.info("Private key saved: %s", key_file)

        # Save public key file
        pub_file = self.keys_dir / f"{key_name}.pub"
        pub_file.write_text(pub_hex)
        log.info("Public key saved: %s", pub_file)

        now = datetime.now(timezone.utc).isoformat()

        # Store in database
        insert_row("crypto_keys", {
            "key_name": key_name,
            "algorithm": "Ed25519",
            "public_key_hex": pub_hex,
            "private_key_enc": "(encrypted on disk)",
            "fingerprint": fingerprint,
            "created_at": now,
            "is_active": 1,
        })

        info = KeyInfo(
            key_name=key_name,
            algorithm="Ed25519",
            public_key_hex=pub_hex,
            fingerprint=fingerprint,
            created_at=now,
            is_active=True,
        )
        log.info("Generated Ed25519 keypair '%s' fingerprint=%s", key_name, fingerprint)
        return info

    def _encrypt_key(self, key_bytes: bytes, passphrase: str) -> str:
        """Encrypt private key bytes using Fernet derived from passphrase."""
        salt = os.urandom(16)
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=480_000,
        )
        derived = base64.urlsafe_b64encode(kdf.derive(passphrase.encode()))
        fernet = Fernet(derived)
        encrypted = fernet.encrypt(key_bytes)
        # Store salt + encrypted together
        payload = {
            "salt": base64.b64encode(salt).decode(),
            "data": encrypted.decode(),
        }
        return json.dumps(payload)

    def _decrypt_key(self, encrypted_str: str, passphrase: str) -> bytes:
        """Decrypt private key bytes."""
        payload = json.loads(encrypted_str)
        salt = base64.b64decode(payload["salt"])
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=480_000,
        )
        derived = base64.urlsafe_b64encode(kdf.derive(passphrase.encode()))
        fernet = Fernet(derived)
        return fernet.decrypt(payload["data"].encode())

    def _load_private_key(
        self, key_name: str = "default", passphrase: str = ""
    ) -> "Ed25519PrivateKey":
        """Load a private key from disk."""
        self._require_crypto()

        key_file = self.keys_dir / f"{key_name}.key"
        if not key_file.exists():
            raise FileNotFoundError(f"Key not found: {key_file}")

        encrypted_str = key_file.read_text()

        if passphrase:
            priv_bytes = self._decrypt_key(encrypted_str, passphrase)
        else:
            priv_bytes = base64.b64decode(encrypted_str)

        return Ed25519PrivateKey.from_private_bytes(priv_bytes)

    def _load_public_key(self, key_name: str = "default") -> "Ed25519PublicKey":
        """Load a public key from disk or database."""
        self._require_crypto()

        pub_file = self.keys_dir / f"{key_name}.pub"
        if pub_file.exists():
            pub_hex = pub_file.read_text().strip()
            pub_bytes = bytes.fromhex(pub_hex)
            return Ed25519PublicKey.from_public_bytes(pub_bytes)

        # Fallback: load from database
        rows = query_rows("crypto_keys", "key_name = ?", (key_name,))
        if not rows:
            raise FileNotFoundError(f"Public key not found for: {key_name}")
        pub_hex = rows[0]["public_key_hex"]
        pub_bytes = bytes.fromhex(pub_hex)
        return Ed25519PublicKey.from_public_bytes(pub_bytes)

    # ── Signing ──────────────────────────────────────────────────────────
    def sign_cid(
        self,
        cid: str,
        key_name: str = "default",
        passphrase: str = "",
    ) -> dict:
        """
        Sign a CID string with the specified Ed25519 key.
        Returns dict with signature_hex, fingerprint, algorithm, timestamp.
        """
        self._require_crypto()

        private_key = self._load_private_key(key_name, passphrase)
        public_key = private_key.public_key()

        # Create the message: CID as UTF-8
        message = cid.encode("utf-8")
        signature = private_key.sign(message)

        # Get fingerprint
        pub_bytes = public_key.public_bytes(
            serialization.Encoding.Raw,
            serialization.PublicFormat.Raw,
        )
        fingerprint = hashlib.sha256(pub_bytes).hexdigest()[:32]

        now = datetime.now(timezone.utc).isoformat()

        # Update last_used_at
        with get_connection() as conn:
            conn.execute(
                "UPDATE crypto_keys SET last_used_at = ? WHERE key_name = ?",
                (now, key_name),
            )

        # Log to audit
        insert_row("audit_logs", {
            "operation": "sign_cid",
            "module": "crypto",
            "detail": json.dumps({"cid": cid, "key": key_name}),
            "cid_reference": cid,
            "signature": signature.hex(),
            "user_key": fingerprint,
            "status": "success",
            "created_at": now,
        })

        result = {
            "cid": cid,
            "signature_hex": signature.hex(),
            "fingerprint": fingerprint,
            "algorithm": "Ed25519",
            "signed_at": now,
        }
        log.info("Signed CID %s with key '%s' (fp: %s)", cid, key_name, fingerprint)
        return result

    def verify_cid(
        self,
        cid: str,
        signature_hex: str,
        key_name: str = "default",
    ) -> dict:
        """
        Verify a signature on a CID.
        Returns dict with verified (bool), details.
        """
        self._require_crypto()

        try:
            public_key = self._load_public_key(key_name)
            message = cid.encode("utf-8")
            signature = bytes.fromhex(signature_hex)
            public_key.verify(signature, message)
            verified = True
            error = None
        except Exception as exc:
            verified = False
            error = str(exc)

        now = datetime.now(timezone.utc).isoformat()

        insert_row("audit_logs", {
            "operation": "verify_cid",
            "module": "crypto",
            "detail": json.dumps({
                "cid": cid,
                "key": key_name,
                "verified": verified,
                "error": error,
            }),
            "cid_reference": cid,
            "signature": signature_hex[:64],
            "user_key": key_name,
            "status": "verified" if verified else "failed",
            "created_at": now,
        })

        result = {
            "cid": cid,
            "verified": verified,
            "key_name": key_name,
            "checked_at": now,
        }
        if error:
            result["error"] = error

        log.info("Verify CID %s: %s", cid, "VALID" if verified else f"INVALID ({error})")
        return result

    # ── Key Management ───────────────────────────────────────────────────
    def list_keys(self) -> list[KeyInfo]:
        """List all registered signing keys."""
        rows = query_rows("crypto_keys")
        return [
            KeyInfo(
                key_name=r["key_name"],
                algorithm=r["algorithm"],
                public_key_hex=r["public_key_hex"],
                fingerprint=r["fingerprint"],
                created_at=r["created_at"],
                is_active=bool(r["is_active"]),
            )
            for r in rows
        ]

    def get_fingerprint(self, key_name: str = "default") -> str:
        """Get the fingerprint for a key."""
        rows = query_rows("crypto_keys", "key_name = ?", (key_name,))
        if not rows:
            raise FileNotFoundError(f"Key not found: {key_name}")
        return rows[0]["fingerprint"]

    def deactivate_key(self, key_name: str) -> None:
        """Deactivate a key (keeps it but marks inactive)."""
        with get_connection() as conn:
            conn.execute(
                "UPDATE crypto_keys SET is_active = 0 WHERE key_name = ?",
                (key_name,),
            )
        log.info("Deactivated key: %s", key_name)
