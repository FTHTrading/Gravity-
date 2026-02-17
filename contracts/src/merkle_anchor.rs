/// Merkle Anchor – Specialized sub-module for Merkle root anchoring.
///
/// Provides deterministic payload construction and verification
/// for Merkle tree root hashes from the Phase II snapshot engine.

use schemars::JsonSchema;
use serde::{Deserialize, Serialize};

use crate::anchor_registry::{compute_sha256, validate_hash, format_anchor_payload};

/// A Merkle root registration request with metadata.
#[derive(Serialize, Deserialize, Clone, Debug, PartialEq, JsonSchema)]
pub struct MerkleRootPayload {
    /// The Merkle root hash (32 bytes, hex-encoded)
    pub root_hash: String,
    /// Number of leaves in the tree
    pub leaf_count: u64,
    /// Table hashes included (JSON array)
    pub table_hashes: Option<String>,
    /// Previous root hash for chain linking
    pub previous_root: Option<String>,
    /// SHA-256 of the full payload
    pub payload_hash: String,
}

impl MerkleRootPayload {
    /// Construct a deterministic Merkle root payload.
    ///
    /// The payload hash is computed from the canonical concatenation:
    ///   SHA-256("merkle_root:" + root_hash + ":" + leaf_count + ":" + previous_root)
    pub fn new(
        root_hash: String,
        leaf_count: u64,
        table_hashes: Option<String>,
        previous_root: Option<String>,
    ) -> Self {
        let prev = previous_root.clone().unwrap_or_default();
        let canonical = format!("merkle_root:{}:{}:{}", root_hash, leaf_count, prev);
        let hash = compute_sha256(canonical.as_bytes());
        let payload_hash = hex::encode(hash);

        MerkleRootPayload {
            root_hash,
            leaf_count,
            table_hashes,
            previous_root,
            payload_hash,
        }
    }

    /// Verify payload integrity by recomputing the hash.
    pub fn verify(&self) -> bool {
        let prev = self.previous_root.clone().unwrap_or_default();
        let canonical = format!("merkle_root:{}:{}:{}", self.root_hash, self.leaf_count, prev);
        let hash = compute_sha256(canonical.as_bytes());
        hex::encode(hash) == self.payload_hash
    }

    /// Convert the root hash hex string to raw 32-byte array.
    pub fn root_bytes(&self) -> Option<[u8; 32]> {
        let decoded = hex::decode(&self.root_hash).ok()?;
        if decoded.len() != 32 {
            return None;
        }
        let mut arr = [0u8; 32];
        arr.copy_from_slice(&decoded);
        Some(arr)
    }
}

/// Format a Merkle root for on-chain anchoring.
pub fn format_merkle_anchor(root_hash: &str, leaf_count: u64) -> Vec<u8> {
    let decoded = hex::decode(root_hash).unwrap_or_default();
    if decoded.len() == 32 {
        let mut hash = [0u8; 32];
        hash.copy_from_slice(&decoded);
        format_anchor_payload(&hash, "merkle_root", leaf_count)
    } else {
        Vec::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_merkle_payload_deterministic() {
        let p1 = MerkleRootPayload::new(
            "a".repeat(64), 100, None, None,
        );
        let p2 = MerkleRootPayload::new(
            "a".repeat(64), 100, None, None,
        );
        assert_eq!(p1.payload_hash, p2.payload_hash);
    }

    #[test]
    fn test_merkle_payload_verify() {
        let payload = MerkleRootPayload::new(
            "b".repeat(64), 50, None, Some("c".repeat(64)),
        );
        assert!(payload.verify());
    }

    #[test]
    fn test_merkle_payload_tamper_detection() {
        let mut payload = MerkleRootPayload::new(
            "d".repeat(64), 200, None, None,
        );
        payload.leaf_count = 999;
        assert!(!payload.verify());
    }

    #[test]
    fn test_root_bytes_valid() {
        let hash_hex = hex::encode([0x42u8; 32]);
        let payload = MerkleRootPayload::new(hash_hex, 10, None, None);
        let bytes = payload.root_bytes().unwrap();
        assert_eq!(bytes, [0x42u8; 32]);
    }

    #[test]
    fn test_root_bytes_invalid() {
        let payload = MerkleRootPayload::new("not_hex".to_string(), 10, None, None);
        assert!(payload.root_bytes().is_none());
    }

    #[test]
    fn test_format_merkle_anchor() {
        let hash_hex = hex::encode([0xABu8; 32]);
        let result = format_merkle_anchor(&hash_hex, 100);
        assert!(!result.is_empty());
    }
}
