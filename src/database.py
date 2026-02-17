"""
SQLite database layer for the Project Anchor Research System.

Tables:
  - social_posts         : scraped social media references
  - documents            : collected PDF / document metadata
  - academic_records     : publication & author search results
  - government_records   : public FOIA / NASA / DoD cross-references
  - propagation_edges    : repost / amplification graph edges
  - physics_comparisons  : numerical outputs from physics module
  - narrative_patterns   : NLP pattern analysis results
  - ipfs_evidence        : IPFS-pinned evidence chain records
  - taxonomy_entries     : research terminology knowledge base
  Phase II:
  - crypto_keys          : Ed25519 keypair metadata
  - merkle_snapshots     : Merkle tree root snapshots
  - foia_documents       : FOIA / declassified document records
  - investigation_cases  : investigation case files (Tesla, scientist cases)
  - case_claims          : individual claims within investigation cases
  - scientist_cases      : scientist disappearance / death database
  - audit_logs           : audit trail of system operations
"""

import os
import sqlite3
from contextlib import contextmanager
from typing import Generator

from src.config import DB_PATH
from src.logger import get_logger

log = get_logger(__name__)

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS social_posts (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    platform        TEXT NOT NULL,
    post_url        TEXT UNIQUE,
    author          TEXT,
    post_text       TEXT,
    timestamp_utc   TEXT,
    scraped_at      TEXT NOT NULL,
    search_term     TEXT,
    metadata_json   TEXT
);

CREATE TABLE IF NOT EXISTS documents (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    filename        TEXT NOT NULL,
    file_hash_sha256 TEXT,
    source_url      TEXT,
    pdf_metadata    TEXT,
    fonts_used      TEXT,
    header_format   TEXT,
    classification_marking TEXT,
    structural_notes TEXT,
    collected_at    TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS academic_records (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    search_term     TEXT,
    author_name     TEXT,
    title           TEXT,
    journal         TEXT,
    year            INTEGER,
    doi             TEXT,
    institution     TEXT,
    abstract        TEXT,
    source_db       TEXT,
    queried_at      TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS government_records (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    database_name   TEXT,
    query_used      TEXT,
    record_title    TEXT,
    record_url      TEXT,
    fiscal_code     TEXT,
    match_status    TEXT,
    notes           TEXT,
    queried_at      TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS propagation_edges (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    source_url      TEXT,
    target_url      TEXT,
    source_timestamp TEXT,
    target_timestamp TEXT,
    platform        TEXT,
    edge_type       TEXT,
    recorded_at     TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS physics_comparisons (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    description     TEXT,
    equation        TEXT,
    value           REAL,
    units           TEXT,
    source_ref      TEXT,
    computed_at     TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS narrative_patterns (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    source_id       INTEGER,
    pattern_type    TEXT,
    pattern_label   TEXT,
    confidence      REAL,
    detail_json     TEXT,
    analyzed_at     TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS ipfs_evidence (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    evidence_cid    TEXT NOT NULL,
    proof_chain_cid TEXT,
    evidence_type   TEXT NOT NULL,
    description     TEXT,
    content_hash    TEXT,
    content_size    INTEGER DEFAULT 0,
    sequence        INTEGER,
    previous_cid    TEXT,
    signature       TEXT,
    pubkey_fingerprint TEXT,
    metadata_json   TEXT,
    pinned_at       TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_social_platform ON social_posts(platform);
CREATE INDEX IF NOT EXISTS idx_social_timestamp ON social_posts(timestamp_utc);
CREATE INDEX IF NOT EXISTS idx_docs_hash ON documents(file_hash_sha256);
CREATE INDEX IF NOT EXISTS idx_academic_author ON academic_records(author_name);
CREATE INDEX IF NOT EXISTS idx_gov_match ON government_records(match_status);
CREATE INDEX IF NOT EXISTS idx_prop_source ON propagation_edges(source_url);
CREATE TABLE IF NOT EXISTS taxonomy_entries (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    term                TEXT NOT NULL,
    definition          TEXT,
    category            TEXT,
    subcategory         TEXT,
    verification_status TEXT DEFAULT 'unverified',
    related_terms_json  TEXT,
    search_keywords_json TEXT,
    source_ref          TEXT,
    created_at          TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_ipfs_cid ON ipfs_evidence(evidence_cid);
CREATE INDEX IF NOT EXISTS idx_ipfs_type ON ipfs_evidence(evidence_type);
CREATE INDEX IF NOT EXISTS idx_ipfs_sequence ON ipfs_evidence(sequence);
CREATE INDEX IF NOT EXISTS idx_taxonomy_term ON taxonomy_entries(term);
CREATE INDEX IF NOT EXISTS idx_taxonomy_category ON taxonomy_entries(category);
CREATE INDEX IF NOT EXISTS idx_taxonomy_subcategory ON taxonomy_entries(subcategory);
CREATE INDEX IF NOT EXISTS idx_taxonomy_status ON taxonomy_entries(verification_status);

-- ── Phase II Tables ─────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS crypto_keys (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    key_name        TEXT NOT NULL UNIQUE,
    algorithm       TEXT NOT NULL DEFAULT 'Ed25519',
    public_key_hex  TEXT NOT NULL,
    private_key_enc TEXT,
    fingerprint     TEXT NOT NULL,
    created_at      TEXT NOT NULL,
    last_used_at    TEXT,
    is_active       INTEGER DEFAULT 1
);

CREATE TABLE IF NOT EXISTS merkle_snapshots (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    root_hash       TEXT NOT NULL,
    tree_json       TEXT NOT NULL,
    table_hashes    TEXT,
    total_rows      INTEGER DEFAULT 0,
    ipfs_cid        TEXT,
    previous_root   TEXT,
    created_at      TEXT NOT NULL,
    verified_at     TEXT,
    status          TEXT DEFAULT 'created'
);

CREATE TABLE IF NOT EXISTS foia_documents (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    source_agency   TEXT NOT NULL,
    document_id     TEXT,
    title           TEXT,
    url             TEXT,
    date_released   TEXT,
    date_created    TEXT,
    classification  TEXT,
    pages           INTEGER,
    file_hash       TEXT,
    local_path      TEXT,
    content_text    TEXT,
    entities_json   TEXT,
    markings_json   TEXT,
    authenticity    TEXT DEFAULT 'unverified',
    notes           TEXT,
    ingested_at     TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS investigation_cases (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    case_name       TEXT NOT NULL,
    case_type       TEXT NOT NULL,
    subject         TEXT,
    summary         TEXT,
    status          TEXT DEFAULT 'open',
    evidence_json   TEXT,
    timeline_json   TEXT,
    metadata_json   TEXT,
    created_at      TEXT NOT NULL,
    updated_at      TEXT
);

CREATE TABLE IF NOT EXISTS case_claims (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    case_id         INTEGER NOT NULL,
    claim_text      TEXT NOT NULL,
    claim_type      TEXT,
    source_ref      TEXT,
    evidence_cid    TEXT,
    verification    TEXT DEFAULT 'unverified',
    confidence      REAL,
    notes           TEXT,
    created_at      TEXT NOT NULL,
    FOREIGN KEY (case_id) REFERENCES investigation_cases(id)
);

CREATE TABLE IF NOT EXISTS scientist_cases (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    name            TEXT NOT NULL,
    birth_year      INTEGER,
    death_year      INTEGER,
    nationality     TEXT,
    field           TEXT,
    institution     TEXT,
    cause_of_death  TEXT,
    circumstances   TEXT,
    official_ruling TEXT,
    disputed        INTEGER DEFAULT 0,
    related_work    TEXT,
    conspiracy_claims TEXT,
    sources_json    TEXT,
    created_at      TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS audit_logs (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    operation       TEXT NOT NULL,
    module          TEXT,
    detail          TEXT,
    cid_reference   TEXT,
    signature       TEXT,
    user_key        TEXT,
    status          TEXT DEFAULT 'success',
    created_at      TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_crypto_name ON crypto_keys(key_name);
CREATE INDEX IF NOT EXISTS idx_crypto_fp ON crypto_keys(fingerprint);
CREATE INDEX IF NOT EXISTS idx_merkle_root ON merkle_snapshots(root_hash);
CREATE INDEX IF NOT EXISTS idx_foia_agency ON foia_documents(source_agency);
CREATE INDEX IF NOT EXISTS idx_foia_class ON foia_documents(classification);
CREATE INDEX IF NOT EXISTS idx_invest_type ON investigation_cases(case_type);
CREATE INDEX IF NOT EXISTS idx_claims_case ON case_claims(case_id);
CREATE INDEX IF NOT EXISTS idx_claims_verify ON case_claims(verification);
CREATE INDEX IF NOT EXISTS idx_scientist_name ON scientist_cases(name);
CREATE INDEX IF NOT EXISTS idx_scientist_field ON scientist_cases(field);
CREATE INDEX IF NOT EXISTS idx_audit_op ON audit_logs(operation);
CREATE INDEX IF NOT EXISTS idx_audit_time ON audit_logs(created_at);

-- ── Phase III: Mathematical Forensics ───────────────────────────
CREATE TABLE IF NOT EXISTS equation_proofs (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    equation_name   TEXT NOT NULL,
    original_latex  TEXT,
    original_plaintext TEXT,
    sympy_repr      TEXT,
    simplified_form TEXT,
    dimensional_status TEXT DEFAULT 'unknown',
    dimension_map   TEXT,
    complexity_score REAL,
    term_count      INTEGER,
    symbol_count    INTEGER,
    tree_depth      INTEGER,
    discrepancy_flags TEXT,
    alternate_forms TEXT,
    derivation_log  TEXT,
    notes           TEXT,
    sha256_hash     TEXT,
    ipfs_cid        TEXT,
    signature       TEXT,
    verification_status TEXT DEFAULT 'unverified',
    created_at      TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS derivation_steps (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    proof_id        INTEGER NOT NULL,
    step_number     INTEGER NOT NULL,
    operation       TEXT NOT NULL,
    input_expr      TEXT NOT NULL,
    output_expr     TEXT NOT NULL,
    justification   TEXT,
    is_valid        INTEGER DEFAULT 1,
    created_at      TEXT NOT NULL,
    FOREIGN KEY (proof_id) REFERENCES equation_proofs(id)
);

-- ── Phase III: Claim Graph ──────────────────────────────────────
CREATE TABLE IF NOT EXISTS claim_nodes (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    claim_text      TEXT NOT NULL,
    claim_type      TEXT DEFAULT 'assertion',
    first_seen      TEXT,
    first_source    TEXT,
    confidence      REAL DEFAULT 0.0,
    verification    TEXT DEFAULT 'unverified',
    mutation_parent INTEGER,
    mutation_diff   TEXT,
    tags            TEXT,
    created_at      TEXT NOT NULL,
    FOREIGN KEY (mutation_parent) REFERENCES claim_nodes(id)
);

CREATE TABLE IF NOT EXISTS source_nodes (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    source_type     TEXT NOT NULL,
    source_url      TEXT,
    source_title    TEXT,
    platform        TEXT,
    author          TEXT,
    published_at    TEXT,
    credibility     REAL DEFAULT 0.5,
    document_cid    TEXT,
    metadata_json   TEXT,
    created_at      TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS evidence_links (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    from_type       TEXT NOT NULL,
    from_id         INTEGER NOT NULL,
    to_type         TEXT NOT NULL,
    to_id           INTEGER NOT NULL,
    relationship    TEXT NOT NULL,
    weight          REAL DEFAULT 1.0,
    metadata_json   TEXT,
    created_at      TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS entity_nodes (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    entity_name     TEXT NOT NULL,
    entity_type     TEXT DEFAULT 'person',
    aliases         TEXT,
    description     TEXT,
    metadata_json   TEXT,
    created_at      TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_eqproof_name ON equation_proofs(equation_name);
CREATE INDEX IF NOT EXISTS idx_eqproof_cid ON equation_proofs(ipfs_cid);
CREATE INDEX IF NOT EXISTS idx_derivstep_eq ON derivation_steps(proof_id);
CREATE INDEX IF NOT EXISTS idx_claim_type ON claim_nodes(claim_type);
CREATE INDEX IF NOT EXISTS idx_claim_verif ON claim_nodes(verification);
CREATE INDEX IF NOT EXISTS idx_claim_parent ON claim_nodes(mutation_parent);
CREATE INDEX IF NOT EXISTS idx_source_type ON source_nodes(source_type);
CREATE INDEX IF NOT EXISTS idx_source_platform ON source_nodes(platform);
CREATE INDEX IF NOT EXISTS idx_evidence_from ON evidence_links(from_type, from_id);
CREATE INDEX IF NOT EXISTS idx_evidence_to ON evidence_links(to_type, to_id);
CREATE INDEX IF NOT EXISTS idx_evidence_rel ON evidence_links(relationship);
CREATE INDEX IF NOT EXISTS idx_entity_name ON entity_nodes(entity_name);
CREATE INDEX IF NOT EXISTS idx_entity_type ON entity_nodes(entity_type);

-- ── Phase IV: Claim Confidence & Scoring ────────────────────────
CREATE TABLE IF NOT EXISTS claim_scores (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    claim_id        INTEGER NOT NULL,
    score_type      TEXT NOT NULL,
    score_value     REAL NOT NULL,
    components_json TEXT,
    scored_at       TEXT NOT NULL,
    FOREIGN KEY (claim_id) REFERENCES claim_nodes(id)
);

CREATE TABLE IF NOT EXISTS mutation_metrics (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    claim_id        INTEGER NOT NULL,
    chain_length    INTEGER DEFAULT 0,
    shannon_entropy REAL DEFAULT 0.0,
    drift_velocity  REAL DEFAULT 0.0,
    max_diff_ratio  REAL DEFAULT 0.0,
    semantic_stability REAL DEFAULT 1.0,
    computed_at     TEXT NOT NULL,
    FOREIGN KEY (claim_id) REFERENCES claim_nodes(id)
);

CREATE TABLE IF NOT EXISTS propagation_events (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    claim_id        INTEGER NOT NULL,
    event_type      TEXT NOT NULL,
    source_id       INTEGER,
    timestamp       TEXT NOT NULL,
    metadata_json   TEXT,
    created_at      TEXT NOT NULL,
    FOREIGN KEY (claim_id) REFERENCES claim_nodes(id)
);

CREATE INDEX IF NOT EXISTS idx_cscore_claim ON claim_scores(claim_id);
CREATE INDEX IF NOT EXISTS idx_cscore_type ON claim_scores(score_type);
CREATE INDEX IF NOT EXISTS idx_mutation_claim ON mutation_metrics(claim_id);
CREATE INDEX IF NOT EXISTS idx_propev_claim ON propagation_events(claim_id);
CREATE INDEX IF NOT EXISTS idx_propev_time ON propagation_events(timestamp);

-- ── Phase V: Temporal Epistemic Dynamics ────────────────────────
CREATE TABLE IF NOT EXISTS confidence_timeline (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    claim_id        INTEGER NOT NULL,
    score_value     REAL NOT NULL,
    components_json TEXT,
    snapshot_at     TEXT NOT NULL,
    FOREIGN KEY (claim_id) REFERENCES claim_nodes(id)
);

CREATE TABLE IF NOT EXISTS entropy_timeline (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    claim_id        INTEGER NOT NULL,
    shannon_entropy REAL NOT NULL,
    drift_velocity  REAL NOT NULL DEFAULT 0.0,
    chain_length    INTEGER DEFAULT 0,
    snapshot_at     TEXT NOT NULL,
    FOREIGN KEY (claim_id) REFERENCES claim_nodes(id)
);

CREATE TABLE IF NOT EXISTS stability_classifications (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    claim_id        INTEGER NOT NULL,
    classification  TEXT NOT NULL,
    confidence_trend REAL DEFAULT 0.0,
    entropy_trend   REAL DEFAULT 0.0,
    drift_accel     REAL DEFAULT 0.0,
    signal_summary  TEXT,
    classified_at   TEXT NOT NULL,
    FOREIGN KEY (claim_id) REFERENCES claim_nodes(id)
);

CREATE TABLE IF NOT EXISTS epistemic_alerts (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    claim_id        INTEGER NOT NULL,
    alert_type      TEXT NOT NULL,
    severity        TEXT NOT NULL DEFAULT 'info',
    title           TEXT NOT NULL,
    detail          TEXT,
    metric_value    REAL,
    threshold       REAL,
    acknowledged    INTEGER DEFAULT 0,
    created_at      TEXT NOT NULL,
    FOREIGN KEY (claim_id) REFERENCES claim_nodes(id)
);

CREATE INDEX IF NOT EXISTS idx_conf_timeline_claim ON confidence_timeline(claim_id);
CREATE INDEX IF NOT EXISTS idx_conf_timeline_time ON confidence_timeline(snapshot_at);
CREATE INDEX IF NOT EXISTS idx_ent_timeline_claim ON entropy_timeline(claim_id);
CREATE INDEX IF NOT EXISTS idx_ent_timeline_time ON entropy_timeline(snapshot_at);
CREATE INDEX IF NOT EXISTS idx_stability_claim ON stability_classifications(claim_id);
CREATE INDEX IF NOT EXISTS idx_stability_class ON stability_classifications(classification);
CREATE INDEX IF NOT EXISTS idx_alert_claim ON epistemic_alerts(claim_id);
CREATE INDEX IF NOT EXISTS idx_alert_type ON epistemic_alerts(alert_type);
CREATE INDEX IF NOT EXISTS idx_alert_severity ON epistemic_alerts(severity);
CREATE INDEX IF NOT EXISTS idx_alert_ack ON epistemic_alerts(acknowledged);

-- ── Phase VI: Source Intelligence & Network Forensics ───────────
CREATE TABLE IF NOT EXISTS source_reputation (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    source_id       INTEGER NOT NULL,
    reliability     REAL NOT NULL DEFAULT 0.5,
    accuracy_rate   REAL DEFAULT 0.0,
    support_count   INTEGER DEFAULT 0,
    contradict_count INTEGER DEFAULT 0,
    total_claims    INTEGER DEFAULT 0,
    ema_credibility REAL DEFAULT 0.5,
    trend_direction TEXT DEFAULT 'flat',
    computed_at     TEXT NOT NULL,
    FOREIGN KEY (source_id) REFERENCES source_nodes(id)
);

CREATE TABLE IF NOT EXISTS influence_edges (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    from_source_id  INTEGER NOT NULL,
    to_source_id    INTEGER NOT NULL,
    shared_claims   INTEGER DEFAULT 0,
    amplification   REAL DEFAULT 0.0,
    relationship    TEXT DEFAULT 'amplifies',
    first_seen      TEXT,
    last_seen       TEXT,
    created_at      TEXT NOT NULL,
    FOREIGN KEY (from_source_id) REFERENCES source_nodes(id),
    FOREIGN KEY (to_source_id) REFERENCES source_nodes(id)
);

CREATE TABLE IF NOT EXISTS coordination_events (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    cluster_id      TEXT NOT NULL,
    source_ids_json TEXT NOT NULL,
    claim_ids_json  TEXT NOT NULL,
    window_hours    REAL NOT NULL,
    source_count    INTEGER NOT NULL,
    temporal_density REAL DEFAULT 0.0,
    coordination_score REAL DEFAULT 0.0,
    pattern_type    TEXT DEFAULT 'burst',
    detected_at     TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS provenance_traces (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    claim_id        INTEGER NOT NULL,
    origin_type     TEXT NOT NULL,
    origin_id       INTEGER,
    chain_depth     INTEGER DEFAULT 0,
    chain_path_json TEXT NOT NULL,
    origin_source   TEXT,
    confidence      REAL DEFAULT 0.0,
    traced_at       TEXT NOT NULL,
    FOREIGN KEY (claim_id) REFERENCES claim_nodes(id)
);

CREATE INDEX IF NOT EXISTS idx_srep_source ON source_reputation(source_id);
CREATE INDEX IF NOT EXISTS idx_srep_time ON source_reputation(computed_at);
CREATE INDEX IF NOT EXISTS idx_infedge_from ON influence_edges(from_source_id);
CREATE INDEX IF NOT EXISTS idx_infedge_to ON influence_edges(to_source_id);
CREATE INDEX IF NOT EXISTS idx_coord_cluster ON coordination_events(cluster_id);
CREATE INDEX IF NOT EXISTS idx_coord_score ON coordination_events(coordination_score);
CREATE INDEX IF NOT EXISTS idx_provtrace_claim ON provenance_traces(claim_id);
CREATE INDEX IF NOT EXISTS idx_provtrace_origin ON provenance_traces(origin_type);
"""


# ── Connection cache for :memory: databases ──────────────────────────────
_memory_conn: sqlite3.Connection | None = None


def init_db() -> None:
    """Create tables if they do not exist."""
    global _memory_conn
    db_path = os.environ.get("PROJECT_ANCHOR_DB", str(DB_PATH))
    if db_path == ":memory:":
        # Create a persistent in-memory connection
        _memory_conn = sqlite3.connect(":memory:")
        _memory_conn.row_factory = sqlite3.Row
        _memory_conn.execute("PRAGMA foreign_keys=ON")
        _memory_conn.executescript(SCHEMA_SQL)
        _memory_conn.commit()
    else:
        _memory_conn = None
        with _connect() as conn:
            conn.executescript(SCHEMA_SQL)
    log.info("Database initialized at %s", db_path)


@contextmanager
def _connect() -> Generator[sqlite3.Connection, None, None]:
    global _memory_conn
    db_path = os.environ.get("PROJECT_ANCHOR_DB", str(DB_PATH))
    if db_path == ":memory:" and _memory_conn is not None:
        # Reuse the persistent in-memory connection
        yield _memory_conn
        return
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


@contextmanager
def get_connection() -> Generator[sqlite3.Connection, None, None]:
    """Public context manager for database access."""
    with _connect() as conn:
        yield conn


def insert_row(table: str, data: dict) -> int:
    """Insert a single row and return the row id."""
    cols = ", ".join(data.keys())
    placeholders = ", ".join(["?"] * len(data))
    sql = f"INSERT OR IGNORE INTO {table} ({cols}) VALUES ({placeholders})"
    with _connect() as conn:
        cursor = conn.execute(sql, list(data.values()))
        row_id = cursor.lastrowid
    log.debug("Inserted row %d into %s", row_id, table)
    return row_id


def query_rows(table: str, where: str = "", params: tuple = ()) -> list[dict]:
    """Return rows as list of dicts."""
    sql = f"SELECT * FROM {table}"
    if where:
        sql += f" WHERE {where}"
    with _connect() as conn:
        rows = conn.execute(sql, params).fetchall()
    return [dict(row) for row in rows]


def execute_sql(sql: str, params: tuple = ()) -> list[dict]:
    """Execute arbitrary SQL and return rows as dicts (for SELECT) or empty list."""
    with _connect() as conn:
        cursor = conn.execute(sql, params)
        if cursor.description:
            rows = cursor.fetchall()
            return [dict(row) for row in rows]
    return []


def count_rows(table: str, where: str = "", params: tuple = ()) -> int:
    """Return count of rows in a table."""
    sql = f"SELECT COUNT(*) as cnt FROM {table}"
    if where:
        sql += f" WHERE {where}"
    with _connect() as conn:
        row = conn.execute(sql, params).fetchone()
    return row["cnt"] if row else 0
