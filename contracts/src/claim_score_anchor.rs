/// Claim Score Anchor – Deterministic anchoring for epistemic claim scores.
///
/// Encapsulates Bayesian confidence scores, mutation entropy metrics,
/// and citation density data into a deterministic, hashable payload
/// for on-chain integrity anchoring.

use schemars::JsonSchema;
use serde::{Deserialize, Serialize};

use crate::anchor_registry::compute_sha256;

/// A claim score anchor payload.
#[derive(Serialize, Deserialize, Clone, Debug, PartialEq, JsonSchema)]
pub struct ClaimScorePayload {
    /// Claim ID from the evidence graph
    pub claim_id: u64,
    /// Composite confidence score (0.0 – 1.0)
    pub composite_score: String,
    /// Shannon entropy of mutation chain
    pub shannon_entropy: String,
    /// Citation density score
    pub citation_density: String,
    /// Number of supporting sources
    pub support_count: u64,
    /// Number of contradicting sources
    pub contradict_count: u64,
    /// Stability classification
    pub stability_class: String,
    /// SHA-256 of the canonical payload
    pub payload_hash: String,
}

impl ClaimScorePayload {
    /// Construct a deterministic claim score payload.
    ///
    /// Canonical form: "claim_score:{id}:{composite}:{entropy}:{density}:{support}:{contradict}:{stability}"
    pub fn new(
        claim_id: u64,
        composite_score: f64,
        shannon_entropy: f64,
        citation_density: f64,
        support_count: u64,
        contradict_count: u64,
        stability_class: String,
    ) -> Self {
        // Fixed-precision serialization for determinism
        let composite_str = format!("{:.8}", composite_score);
        let entropy_str = format!("{:.8}", shannon_entropy);
        let density_str = format!("{:.8}", citation_density);

        let canonical = format!(
            "claim_score:{}:{}:{}:{}:{}:{}:{}",
            claim_id, composite_str, entropy_str, density_str,
            support_count, contradict_count, stability_class
        );
        let hash = compute_sha256(canonical.as_bytes());
        let payload_hash = hex::encode(hash);

        ClaimScorePayload {
            claim_id,
            composite_score: composite_str,
            shannon_entropy: entropy_str,
            citation_density: density_str,
            support_count,
            contradict_count,
            stability_class,
            payload_hash,
        }
    }

    /// Verify payload integrity by recomputing the hash.
    pub fn verify(&self) -> bool {
        let canonical = format!(
            "claim_score:{}:{}:{}:{}:{}:{}:{}",
            self.claim_id, self.composite_score, self.shannon_entropy,
            self.citation_density, self.support_count, self.contradict_count,
            self.stability_class
        );
        let hash = compute_sha256(canonical.as_bytes());
        hex::encode(hash) == self.payload_hash
    }

    /// Get the raw 32-byte hash for on-chain registration.
    pub fn hash_bytes(&self) -> [u8; 32] {
        let decoded = hex::decode(&self.payload_hash).unwrap_or_default();
        let mut arr = [0u8; 32];
        if decoded.len() == 32 {
            arr.copy_from_slice(&decoded);
        }
        arr
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_claim_score_deterministic() {
        let p1 = ClaimScorePayload::new(1, 0.85, 1.234, 0.75, 5, 2, "stable".into());
        let p2 = ClaimScorePayload::new(1, 0.85, 1.234, 0.75, 5, 2, "stable".into());
        assert_eq!(p1.payload_hash, p2.payload_hash);
    }

    #[test]
    fn test_claim_score_verify() {
        let payload = ClaimScorePayload::new(42, 0.92, 0.5, 0.88, 10, 1, "converging".into());
        assert!(payload.verify());
    }

    #[test]
    fn test_claim_score_tamper_detection() {
        let mut payload = ClaimScorePayload::new(1, 0.5, 0.5, 0.5, 3, 3, "volatile".into());
        payload.support_count = 100;
        assert!(!payload.verify());
    }

    #[test]
    fn test_claim_score_fixed_precision() {
        let payload = ClaimScorePayload::new(1, 0.1 + 0.2, 0.0, 0.0, 0, 0, "unknown".into());
        // Fixed precision should produce consistent string
        assert!(payload.composite_score.len() > 0);
        assert!(payload.verify());
    }

    #[test]
    fn test_hash_bytes_length() {
        let payload = ClaimScorePayload::new(1, 0.5, 0.5, 0.5, 1, 1, "stable".into());
        let bytes = payload.hash_bytes();
        assert_eq!(bytes.len(), 32);
    }
}
