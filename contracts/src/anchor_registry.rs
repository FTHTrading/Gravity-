/// Anchor Registry – Core contract for deterministic hash registration.
///
/// Stores SHA-256 hashes of Merkle roots, claim scores, and equation proofs
/// on-chain for immutable integrity verification.
///
/// Properties:
///   - Deterministic storage
///   - No randomness
///   - No token logic
///   - Content-hash based
///   - Event emission via attributes
///   - Extendable for Substrate or EVM wrappers

#[cfg(feature = "cosmwasm")]
use cosmwasm_std::{
    entry_point, to_json_binary, Binary, Deps, DepsMut, Env,
    MessageInfo, Response, StdError, StdResult,
};

#[cfg(feature = "cosmwasm")]
use cw_storage_plus::Map;

use schemars::JsonSchema;
use serde::{Deserialize, Serialize};

// ── Storage Maps ────────────────────────────────────────────────────────────

/// Registered Merkle root hashes
#[cfg(feature = "cosmwasm")]
pub const ROOTS: Map<&[u8], AnchorEntry> = Map::new("roots");

/// Registered claim score hashes
#[cfg(feature = "cosmwasm")]
pub const CLAIM_SCORES: Map<&[u8], AnchorEntry> = Map::new("claim_scores");

/// Registered equation proof hashes
#[cfg(feature = "cosmwasm")]
pub const EQUATION_PROOFS: Map<&[u8], AnchorEntry> = Map::new("equation_proofs");

/// Contract configuration
#[cfg(feature = "cosmwasm")]
pub const CONFIG: cw_storage_plus::Item<Config> = cw_storage_plus::Item::new("config");

// ── Data Structures ─────────────────────────────────────────────────────────

/// Configuration for the anchor registry contract.
#[derive(Serialize, Deserialize, Clone, Debug, PartialEq, JsonSchema)]
pub struct Config {
    /// Contract administrator address
    pub admin: String,
    /// Total anchors registered
    pub total_anchors: u64,
}

/// An anchored hash entry with metadata.
#[derive(Serialize, Deserialize, Clone, Debug, PartialEq, JsonSchema)]
pub struct AnchorEntry {
    /// The 32-byte SHA-256 hash (hex-encoded)
    pub hash_hex: String,
    /// Anchor type: "root", "claim_score", or "equation_proof"
    pub anchor_type: String,
    /// Block height at registration
    pub registered_at: u64,
    /// Registrant address
    pub registrant: String,
}

// ── Messages ────────────────────────────────────────────────────────────────

/// Instantiation message – sets the admin address.
#[derive(Serialize, Deserialize, Clone, Debug, PartialEq, JsonSchema)]
pub struct InstantiateMsg {
    pub admin: Option<String>,
}

/// Execute messages for hash registration.
#[derive(Serialize, Deserialize, Clone, Debug, PartialEq, JsonSchema)]
#[serde(rename_all = "snake_case")]
pub enum ExecuteMsg {
    /// Register a Merkle root hash (32 bytes)
    RegisterRoot { hash: Binary },
    /// Register a claim score hash (32 bytes)
    RegisterClaimScore { hash: Binary },
    /// Register an equation proof hash (32 bytes)
    RegisterEquationProof { hash: Binary },
}

/// Query messages for hash verification.
#[derive(Serialize, Deserialize, Clone, Debug, PartialEq, JsonSchema)]
#[serde(rename_all = "snake_case")]
pub enum QueryMsg {
    /// Verify whether a root hash is registered
    VerifyRoot { hash: Binary },
    /// Verify whether a claim score hash is registered
    VerifyClaimScore { hash: Binary },
    /// Verify whether an equation proof hash is registered
    VerifyEquationProof { hash: Binary },
    /// Get contract configuration
    GetConfig {},
    /// Get anchor entry details
    GetAnchor { hash: Binary, anchor_type: String },
}

/// Response for verification queries.
#[derive(Serialize, Deserialize, Clone, Debug, PartialEq, JsonSchema)]
pub struct VerifyResponse {
    pub exists: bool,
    pub hash_hex: String,
    pub entry: Option<AnchorEntry>,
}

/// Response for config query.
#[derive(Serialize, Deserialize, Clone, Debug, PartialEq, JsonSchema)]
pub struct ConfigResponse {
    pub admin: String,
    pub total_anchors: u64,
}

// ── Contract Entry Points ───────────────────────────────────────────────────

#[cfg(feature = "cosmwasm")]
#[entry_point]
pub fn instantiate(
    deps: DepsMut,
    _env: Env,
    info: MessageInfo,
    msg: InstantiateMsg,
) -> StdResult<Response> {
    let admin = msg.admin.unwrap_or_else(|| info.sender.to_string());
    let config = Config {
        admin,
        total_anchors: 0,
    };
    CONFIG.save(deps.storage, &config)?;

    Ok(Response::new()
        .add_attribute("action", "instantiate")
        .add_attribute("admin", &config.admin))
}

#[cfg(feature = "cosmwasm")]
#[entry_point]
pub fn execute(
    deps: DepsMut,
    env: Env,
    info: MessageInfo,
    msg: ExecuteMsg,
) -> StdResult<Response> {
    match msg {
        ExecuteMsg::RegisterRoot { hash } => {
            register_hash(deps, env, info, hash, "root", &ROOTS)
        }
        ExecuteMsg::RegisterClaimScore { hash } => {
            register_hash(deps, env, info, hash, "claim_score", &CLAIM_SCORES)
        }
        ExecuteMsg::RegisterEquationProof { hash } => {
            register_hash(deps, env, info, hash, "equation_proof", &EQUATION_PROOFS)
        }
    }
}

#[cfg(feature = "cosmwasm")]
fn register_hash(
    deps: DepsMut,
    env: Env,
    info: MessageInfo,
    hash: Binary,
    anchor_type: &str,
    store: &Map<&[u8], AnchorEntry>,
) -> StdResult<Response> {
    // Validate: must be exactly 32 bytes (SHA-256)
    if hash.len() != 32 {
        return Err(StdError::generic_err(
            "Hash must be exactly 32 bytes (SHA-256)",
        ));
    }

    let hash_hex = hex::encode(hash.as_slice());

    let entry = AnchorEntry {
        hash_hex: hash_hex.clone(),
        anchor_type: anchor_type.to_string(),
        registered_at: env.block.height,
        registrant: info.sender.to_string(),
    };

    store.save(deps.storage, hash.as_slice(), &entry)?;

    // Increment total anchors
    let mut config = CONFIG.load(deps.storage)?;
    config.total_anchors += 1;
    CONFIG.save(deps.storage, &config)?;

    Ok(Response::new()
        .add_attribute("action", format!("register_{}", anchor_type))
        .add_attribute("hash", &hash_hex)
        .add_attribute("registrant", info.sender.to_string())
        .add_attribute("block_height", env.block.height.to_string()))
}

#[cfg(feature = "cosmwasm")]
#[entry_point]
pub fn query(deps: Deps, _env: Env, msg: QueryMsg) -> StdResult<Binary> {
    match msg {
        QueryMsg::VerifyRoot { hash } => {
            to_json_binary(&verify_hash(deps, hash, &ROOTS)?)
        }
        QueryMsg::VerifyClaimScore { hash } => {
            to_json_binary(&verify_hash(deps, hash, &CLAIM_SCORES)?)
        }
        QueryMsg::VerifyEquationProof { hash } => {
            to_json_binary(&verify_hash(deps, hash, &EQUATION_PROOFS)?)
        }
        QueryMsg::GetConfig {} => {
            let config = CONFIG.load(deps.storage)?;
            to_json_binary(&ConfigResponse {
                admin: config.admin,
                total_anchors: config.total_anchors,
            })
        }
        QueryMsg::GetAnchor { hash, anchor_type } => {
            let store = match anchor_type.as_str() {
                "root" => &ROOTS,
                "claim_score" => &CLAIM_SCORES,
                "equation_proof" => &EQUATION_PROOFS,
                _ => return Err(StdError::generic_err("Unknown anchor type")),
            };
            let entry = store.may_load(deps.storage, hash.as_slice())?;
            to_json_binary(&VerifyResponse {
                exists: entry.is_some(),
                hash_hex: hex::encode(hash.as_slice()),
                entry,
            })
        }
    }
}

#[cfg(feature = "cosmwasm")]
fn verify_hash(
    deps: Deps,
    hash: Binary,
    store: &Map<&[u8], AnchorEntry>,
) -> StdResult<VerifyResponse> {
    let entry = store.may_load(deps.storage, hash.as_slice())?;
    Ok(VerifyResponse {
        exists: entry.is_some(),
        hash_hex: hex::encode(hash.as_slice()),
        entry,
    })
}

// ── Pure Functions (no chain dependency) ────────────────────────────────────

/// Validate that a hash is exactly 32 bytes.
pub fn validate_hash(hash: &[u8]) -> bool {
    hash.len() == 32
}

/// Compute SHA-256 of arbitrary data (deterministic).
pub fn compute_sha256(data: &[u8]) -> [u8; 32] {
    use sha2::{Sha256, Digest};
    let mut hasher = Sha256::new();
    hasher.update(data);
    let result = hasher.finalize();
    let mut output = [0u8; 32];
    output.copy_from_slice(&result);
    output
}

/// Format a deterministic anchor payload for off-chain verification.
pub fn format_anchor_payload(
    hash: &[u8; 32],
    anchor_type: &str,
    timestamp: u64,
) -> Vec<u8> {
    let mut payload = Vec::new();
    payload.extend_from_slice(anchor_type.as_bytes());
    payload.push(b':');
    payload.extend_from_slice(&hex::encode(hash).as_bytes());
    payload.push(b':');
    payload.extend_from_slice(&timestamp.to_be_bytes());
    payload
}

// ── Tests ───────────────────────────────────────────────────────────────────

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_validate_hash_valid() {
        let hash = [0u8; 32];
        assert!(validate_hash(&hash));
    }

    #[test]
    fn test_validate_hash_invalid_length() {
        let hash = [0u8; 16];
        assert!(!validate_hash(&hash));
    }

    #[test]
    fn test_compute_sha256_deterministic() {
        let data = b"Project Anchor - Gravity Event";
        let h1 = compute_sha256(data);
        let h2 = compute_sha256(data);
        assert_eq!(h1, h2);
    }

    #[test]
    fn test_compute_sha256_different_inputs() {
        let h1 = compute_sha256(b"input_a");
        let h2 = compute_sha256(b"input_b");
        assert_ne!(h1, h2);
    }

    #[test]
    fn test_format_anchor_payload_deterministic() {
        let hash = compute_sha256(b"test_root");
        let p1 = format_anchor_payload(&hash, "root", 12345);
        let p2 = format_anchor_payload(&hash, "root", 12345);
        assert_eq!(p1, p2);
    }

    #[test]
    fn test_format_anchor_payload_structure() {
        let hash = [0xABu8; 32];
        let payload = format_anchor_payload(&hash, "root", 1);
        let payload_str = String::from_utf8_lossy(&payload);
        assert!(payload_str.starts_with("root:"));
        assert!(payload_str.contains(&hex::encode([0xABu8; 32])));
    }
}
