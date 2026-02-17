/// Equation Proof Anchor – Deterministic anchoring for formal mathematical proofs.
///
/// Encapsulates equation proof trees, stability analyses, and optimization
/// results into a deterministic, hashable payload for on-chain anchoring.

use schemars::JsonSchema;
use serde::{Deserialize, Serialize};

use crate::anchor_registry::compute_sha256;

/// An equation proof anchor payload.
#[derive(Serialize, Deserialize, Clone, Debug, PartialEq, JsonSchema)]
pub struct EquationProofPayload {
    /// Name of the equation
    pub equation_name: String,
    /// SHA-256 of the SymPy canonical representation
    pub equation_hash: String,
    /// SHA-256 of the proof tree JSON
    pub proof_tree_hash: String,
    /// Stability classification (stable, unstable, marginal, unknown)
    pub stability_class: String,
    /// Solvability index (0.0 – 1.0)
    pub solvability_index: String,
    /// Compression ratio after optimization
    pub compression_ratio: String,
    /// Whether dimensional analysis passed
    pub dimensional_valid: bool,
    /// SHA-256 of the complete payload
    pub payload_hash: String,
}

impl EquationProofPayload {
    /// Construct a deterministic equation proof payload.
    ///
    /// Canonical form:
    ///   "equation_proof:{name}:{eq_hash}:{proof_hash}:{stability}:{si}:{cr}:{dim_valid}"
    pub fn new(
        equation_name: String,
        equation_hash: String,
        proof_tree_hash: String,
        stability_class: String,
        solvability_index: f64,
        compression_ratio: f64,
        dimensional_valid: bool,
    ) -> Self {
        let si_str = format!("{:.8}", solvability_index);
        let cr_str = format!("{:.8}", compression_ratio);
        let dim_str = if dimensional_valid { "1" } else { "0" };

        let canonical = format!(
            "equation_proof:{}:{}:{}:{}:{}:{}:{}",
            equation_name, equation_hash, proof_tree_hash,
            stability_class, si_str, cr_str, dim_str
        );
        let hash = compute_sha256(canonical.as_bytes());
        let payload_hash = hex::encode(hash);

        EquationProofPayload {
            equation_name,
            equation_hash,
            proof_tree_hash,
            stability_class,
            solvability_index: si_str,
            compression_ratio: cr_str,
            dimensional_valid,
            payload_hash,
        }
    }

    /// Verify payload integrity by recomputing the hash.
    pub fn verify(&self) -> bool {
        let dim_str = if self.dimensional_valid { "1" } else { "0" };
        let canonical = format!(
            "equation_proof:{}:{}:{}:{}:{}:{}:{}",
            self.equation_name, self.equation_hash, self.proof_tree_hash,
            self.stability_class, self.solvability_index,
            self.compression_ratio, dim_str
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
    fn test_equation_proof_deterministic() {
        let p1 = EquationProofPayload::new(
            "newton_gravity".into(), "a".repeat(64), "b".repeat(64),
            "stable".into(), 0.95, 0.45, true,
        );
        let p2 = EquationProofPayload::new(
            "newton_gravity".into(), "a".repeat(64), "b".repeat(64),
            "stable".into(), 0.95, 0.45, true,
        );
        assert_eq!(p1.payload_hash, p2.payload_hash);
    }

    #[test]
    fn test_equation_proof_verify() {
        let payload = EquationProofPayload::new(
            "einstein_energy".into(), "c".repeat(64), "d".repeat(64),
            "stable".into(), 1.0, 0.5, true,
        );
        assert!(payload.verify());
    }

    #[test]
    fn test_equation_proof_tamper_detection() {
        let mut payload = EquationProofPayload::new(
            "maxwell_gauss".into(), "e".repeat(64), "f".repeat(64),
            "stable".into(), 0.8, 0.3, true,
        );
        payload.dimensional_valid = false;
        assert!(!payload.verify());
    }

    #[test]
    fn test_equation_proof_hash_bytes() {
        let payload = EquationProofPayload::new(
            "test".into(), "a".repeat(64), "b".repeat(64),
            "unknown".into(), 0.5, 0.5, false,
        );
        let bytes = payload.hash_bytes();
        assert_eq!(bytes.len(), 32);
        // Should not be all zeros (would mean decode failed)
        assert!(bytes.iter().any(|&b| b != 0));
    }

    #[test]
    fn test_equation_proof_different_stability() {
        let stable = EquationProofPayload::new(
            "eq".into(), "a".repeat(64), "b".repeat(64),
            "stable".into(), 0.5, 0.5, true,
        );
        let unstable = EquationProofPayload::new(
            "eq".into(), "a".repeat(64), "b".repeat(64),
            "unstable".into(), 0.5, 0.5, true,
        );
        assert_ne!(stable.payload_hash, unstable.payload_hash);
    }
}
