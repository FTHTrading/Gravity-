/// Gravity- Anchor Contracts
///
/// Deterministic, integrity-only smart contract layer for anchoring:
///   - Merkle root hashes
///   - Claim score hashes
///   - Equation proof hashes
///
/// No token logic. No external randomness. Content-hash addressed.
/// Compatible with CosmWasm, with Substrate/EVM wrapper stubs.

pub mod anchor_registry;
pub mod merkle_anchor;
pub mod claim_score_anchor;
pub mod equation_proof_anchor;

#[cfg(feature = "cosmwasm")]
pub use anchor_registry::{
    execute as registry_execute,
    instantiate as registry_instantiate,
    query as registry_query,
};
