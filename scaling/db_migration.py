"""
Database Migration — SQLite → PostgreSQL
==========================================
Manages schema migration from SQLite (development) to PostgreSQL (production).
Supports Alembic-style versioning and connection pooling via SQLAlchemy.

Usage:
  python -m scaling.db_migration --check      # Check current backend
  python -m scaling.db_migration --migrate    # Migrate SQLite → PostgreSQL
  python -m scaling.db_migration --schema     # Export schema DDL
"""

from __future__ import annotations

import argparse
import os
import sqlite3
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from scaling.config import DATABASE_URL, DB_POOL_SIZE, DB_MAX_OVERFLOW, DB_POOL_TIMEOUT, DB_POOL_RECYCLE

# ── SQLAlchemy (optional, for PostgreSQL) ────────────────────────────
try:
    from sqlalchemy import create_engine, text, pool
    from sqlalchemy.orm import sessionmaker
    HAS_SQLALCHEMY = True
except ImportError:
    HAS_SQLALCHEMY = False


# ═══════════════════════════════════════════════════════════ SCHEMA
# All 33 tables with their CREATE statements for PostgreSQL
POSTGRES_SCHEMA = {
    # Phase I tables (3)
    "search_results": """
        CREATE TABLE IF NOT EXISTS search_results (
            id SERIAL PRIMARY KEY,
            source VARCHAR(100) NOT NULL,
            query TEXT,
            url TEXT,
            title TEXT,
            snippet TEXT,
            content TEXT,
            collected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            metadata JSONB
        )
    """,
    "reddit_posts": """
        CREATE TABLE IF NOT EXISTS reddit_posts (
            id SERIAL PRIMARY KEY,
            post_id VARCHAR(20) UNIQUE,
            subreddit VARCHAR(100),
            title TEXT,
            body TEXT,
            author VARCHAR(100),
            score INTEGER,
            url TEXT,
            created_utc TIMESTAMP,
            collected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """,
    "wayback_snapshots": """
        CREATE TABLE IF NOT EXISTS wayback_snapshots (
            id SERIAL PRIMARY KEY,
            url TEXT,
            timestamp VARCHAR(14),
            status_code INTEGER,
            content TEXT,
            collected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """,

    # Phase II tables (5)
    "keypairs": """
        CREATE TABLE IF NOT EXISTS keypairs (
            id SERIAL PRIMARY KEY,
            name VARCHAR(200) UNIQUE,
            public_key TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """,
    "signatures": """
        CREATE TABLE IF NOT EXISTS signatures (
            id SERIAL PRIMARY KEY,
            record_table VARCHAR(100),
            record_id INTEGER,
            signature TEXT NOT NULL,
            key_name VARCHAR(200),
            signed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            valid BOOLEAN DEFAULT TRUE
        )
    """,
    "merkle_snapshots": """
        CREATE TABLE IF NOT EXISTS merkle_snapshots (
            id SERIAL PRIMARY KEY,
            root_hash VARCHAR(128) NOT NULL,
            leaf_count INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            metadata JSONB
        )
    """,
    "foia_documents": """
        CREATE TABLE IF NOT EXISTS foia_documents (
            id SERIAL PRIMARY KEY,
            filename TEXT,
            file_hash VARCHAR(128),
            agency VARCHAR(200),
            date_received TIMESTAMP,
            content TEXT,
            page_count INTEGER,
            ingested_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """,
    "audit_reports": """
        CREATE TABLE IF NOT EXISTS audit_reports (
            id SERIAL PRIMARY KEY,
            report_type VARCHAR(50),
            content JSONB,
            generated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """,

    # Phase III tables (5)
    "equations": """
        CREATE TABLE IF NOT EXISTS equations (
            id SERIAL PRIMARY KEY,
            raw_text TEXT NOT NULL,
            parsed_sympy TEXT,
            variables JSONB,
            dimensions JSONB,
            source VARCHAR(200),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """,
    "claims": """
        CREATE TABLE IF NOT EXISTS claims (
            id SERIAL PRIMARY KEY,
            text TEXT NOT NULL,
            source VARCHAR(500),
            category VARCHAR(100),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """,
    "evidence": """
        CREATE TABLE IF NOT EXISTS evidence (
            id SERIAL PRIMARY KEY,
            claim_id INTEGER REFERENCES claims(id),
            evidence_type VARCHAR(50),
            content TEXT,
            weight REAL DEFAULT 1.0,
            source VARCHAR(500),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """,
    "claim_edges": """
        CREATE TABLE IF NOT EXISTS claim_edges (
            id SERIAL PRIMARY KEY,
            source_claim_id INTEGER REFERENCES claims(id),
            target_claim_id INTEGER REFERENCES claims(id),
            relationship VARCHAR(50),
            weight REAL DEFAULT 1.0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """,
    "derivation_log": """
        CREATE TABLE IF NOT EXISTS derivation_log (
            id SERIAL PRIMARY KEY,
            equation_id INTEGER REFERENCES equations(id),
            step_number INTEGER,
            operation TEXT,
            result TEXT,
            logged_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """,

    # Phase IV tables (6)
    "confidence_scores": """
        CREATE TABLE IF NOT EXISTS confidence_scores (
            id SERIAL PRIMARY KEY,
            claim_id INTEGER REFERENCES claims(id),
            score REAL NOT NULL,
            components JSONB,
            scored_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """,
    "mutation_entropy": """
        CREATE TABLE IF NOT EXISTS mutation_entropy (
            id SERIAL PRIMARY KEY,
            claim_id INTEGER REFERENCES claims(id),
            entropy REAL,
            mutation_count INTEGER,
            calculated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """,
    "citation_density": """
        CREATE TABLE IF NOT EXISTS citation_density (
            id SERIAL PRIMARY KEY,
            claim_id INTEGER REFERENCES claims(id),
            density REAL,
            citation_count INTEGER,
            calculated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """,
    "contradictions": """
        CREATE TABLE IF NOT EXISTS contradictions (
            id SERIAL PRIMARY KEY,
            claim_a_id INTEGER REFERENCES claims(id),
            claim_b_id INTEGER REFERENCES claims(id),
            contradiction_score REAL,
            explanation TEXT,
            detected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """,
    "propagation_nodes": """
        CREATE TABLE IF NOT EXISTS propagation_nodes (
            id SERIAL PRIMARY KEY,
            claim_id INTEGER REFERENCES claims(id),
            source VARCHAR(500),
            first_seen TIMESTAMP,
            reach INTEGER DEFAULT 0
        )
    """,
    "propagation_edges": """
        CREATE TABLE IF NOT EXISTS propagation_edges (
            id SERIAL PRIMARY KEY,
            source_node_id INTEGER REFERENCES propagation_nodes(id),
            target_node_id INTEGER REFERENCES propagation_nodes(id),
            weight REAL DEFAULT 1.0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """,

    # Phase V tables (7)
    "confidence_timeline": """
        CREATE TABLE IF NOT EXISTS confidence_timeline (
            id SERIAL PRIMARY KEY,
            claim_id INTEGER REFERENCES claims(id),
            score REAL,
            recorded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """,
    "entropy_trend": """
        CREATE TABLE IF NOT EXISTS entropy_trend (
            id SERIAL PRIMARY KEY,
            claim_id INTEGER REFERENCES claims(id),
            entropy REAL,
            recorded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """,
    "drift_vectors": """
        CREATE TABLE IF NOT EXISTS drift_vectors (
            id SERIAL PRIMARY KEY,
            claim_id INTEGER REFERENCES claims(id),
            velocity REAL,
            acceleration REAL,
            direction VARCHAR(20),
            calculated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """,
    "stability_states": """
        CREATE TABLE IF NOT EXISTS stability_states (
            id SERIAL PRIMARY KEY,
            claim_id INTEGER REFERENCES claims(id),
            state VARCHAR(50),
            duration_hours REAL,
            classified_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """,
    "alerts": """
        CREATE TABLE IF NOT EXISTS alerts (
            id SERIAL PRIMARY KEY,
            claim_id INTEGER REFERENCES claims(id),
            alert_type VARCHAR(50),
            severity VARCHAR(20),
            message TEXT,
            triggered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            resolved BOOLEAN DEFAULT FALSE,
            resolved_at TIMESTAMP
        )
    """,
    "alert_config": """
        CREATE TABLE IF NOT EXISTS alert_config (
            id SERIAL PRIMARY KEY,
            alert_type VARCHAR(50) UNIQUE,
            threshold REAL,
            enabled BOOLEAN DEFAULT TRUE,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """,
    "lifecycle_events": """
        CREATE TABLE IF NOT EXISTS lifecycle_events (
            id SERIAL PRIMARY KEY,
            claim_id INTEGER REFERENCES claims(id),
            event_type VARCHAR(50),
            description TEXT,
            occurred_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """,

    # Phase VI tables (7)
    "source_reputation": """
        CREATE TABLE IF NOT EXISTS source_reputation (
            id SERIAL PRIMARY KEY,
            source_id VARCHAR(500) UNIQUE,
            reputation_score REAL,
            credibility_tier VARCHAR(20),
            evidence_count INTEGER DEFAULT 0,
            scored_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """,
    "influence_nodes": """
        CREATE TABLE IF NOT EXISTS influence_nodes (
            id SERIAL PRIMARY KEY,
            source_id VARCHAR(500),
            influence_score REAL,
            centrality REAL,
            community_id INTEGER
        )
    """,
    "influence_edges": """
        CREATE TABLE IF NOT EXISTS influence_edges (
            id SERIAL PRIMARY KEY,
            source_node_id INTEGER REFERENCES influence_nodes(id),
            target_node_id INTEGER REFERENCES influence_nodes(id),
            weight REAL,
            relationship VARCHAR(50)
        )
    """,
    "coordination_events": """
        CREATE TABLE IF NOT EXISTS coordination_events (
            id SERIAL PRIMARY KEY,
            group_id INTEGER,
            source_ids JSONB,
            pattern_type VARCHAR(50),
            confidence REAL,
            detected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """,
    "provenance_chains": """
        CREATE TABLE IF NOT EXISTS provenance_chains (
            id SERIAL PRIMARY KEY,
            claim_id INTEGER REFERENCES claims(id),
            chain JSONB,
            depth INTEGER,
            traced_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """,
    "network_snapshots": """
        CREATE TABLE IF NOT EXISTS network_snapshots (
            id SERIAL PRIMARY KEY,
            snapshot_type VARCHAR(50),
            node_count INTEGER,
            edge_count INTEGER,
            graph_data JSONB,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """,
    "intel_briefs": """
        CREATE TABLE IF NOT EXISTS intel_briefs (
            id SERIAL PRIMARY KEY,
            brief_type VARCHAR(50),
            content JSONB,
            generated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """,
}


class DatabaseMigration:
    """Manages database backend migration and connection pooling."""

    def __init__(self, db_url: Optional[str] = None):
        self.db_url = db_url or DATABASE_URL
        self.is_postgres = self.db_url.startswith("postgresql")
        self.engine = None

    def get_engine(self):
        """Create SQLAlchemy engine with connection pooling."""
        if not HAS_SQLALCHEMY:
            raise RuntimeError("SQLAlchemy not installed. Run: pip install sqlalchemy psycopg2-binary")

        if self.engine is None:
            if self.is_postgres:
                self.engine = create_engine(
                    self.db_url,
                    pool_size=DB_POOL_SIZE,
                    max_overflow=DB_MAX_OVERFLOW,
                    pool_timeout=DB_POOL_TIMEOUT,
                    pool_recycle=DB_POOL_RECYCLE,
                    pool_pre_ping=True,
                    echo=False,
                )
            else:
                self.engine = create_engine(self.db_url, echo=False)
        return self.engine

    def check_backend(self) -> dict[str, Any]:
        """Check current database backend and table count."""
        info = {
            "url": self.db_url.split("@")[-1] if "@" in self.db_url else self.db_url,
            "backend": "postgresql" if self.is_postgres else "sqlite",
            "has_sqlalchemy": HAS_SQLALCHEMY,
            "expected_tables": len(POSTGRES_SCHEMA),
        }

        if self.is_postgres and HAS_SQLALCHEMY:
            engine = self.get_engine()
            with engine.connect() as conn:
                result = conn.execute(text(
                    "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = 'public'"
                ))
                info["existing_tables"] = result.scalar()
        elif not self.is_postgres:
            db_path = self.db_url.replace("sqlite:///", "")
            if Path(db_path).exists():
                conn = sqlite3.connect(db_path)
                cursor = conn.execute("SELECT COUNT(*) FROM sqlite_master WHERE type='table'")
                info["existing_tables"] = cursor.fetchone()[0]
                conn.close()
            else:
                info["existing_tables"] = 0

        return info

    def create_postgres_schema(self):
        """Create all 33 tables in PostgreSQL."""
        if not self.is_postgres:
            raise RuntimeError("Target database must be PostgreSQL")

        engine = self.get_engine()
        created = []
        with engine.begin() as conn:
            for table_name, ddl in POSTGRES_SCHEMA.items():
                conn.execute(text(ddl))
                created.append(table_name)

        return {"tables_created": len(created), "tables": created}

    def migrate_sqlite_to_postgres(self, sqlite_path: Optional[str] = None):
        """Migrate all data from SQLite to PostgreSQL."""
        if not self.is_postgres:
            raise RuntimeError("Target must be PostgreSQL")

        # Source SQLite
        src_path = sqlite_path or str(Path(__file__).resolve().parent.parent / "data" / "project_anchor.db")
        if not Path(src_path).exists():
            return {"status": "skipped", "reason": "SQLite database not found"}

        src_conn = sqlite3.connect(src_path)
        src_conn.row_factory = sqlite3.Row

        # Create target schema
        self.create_postgres_schema()
        engine = self.get_engine()

        migrated = {}
        errors = []

        for table_name in POSTGRES_SCHEMA:
            try:
                cursor = src_conn.execute(f"SELECT * FROM {table_name}")
                rows = cursor.fetchall()
                if not rows:
                    migrated[table_name] = 0
                    continue

                columns = [desc[0] for desc in cursor.description]
                # Skip 'id' column (auto-generated in PostgreSQL)
                insert_cols = [c for c in columns if c != "id"]

                with engine.begin() as conn:
                    for row in rows:
                        row_dict = dict(row)
                        values = {c: row_dict[c] for c in insert_cols if c in row_dict}
                        if values:
                            placeholders = ", ".join(f":{c}" for c in values)
                            col_names = ", ".join(values.keys())
                            conn.execute(
                                text(f"INSERT INTO {table_name} ({col_names}) VALUES ({placeholders})"),
                                values
                            )

                migrated[table_name] = len(rows)
            except Exception as e:
                errors.append({"table": table_name, "error": str(e)})
                migrated[table_name] = 0

        src_conn.close()

        return {
            "status": "completed",
            "tables_migrated": len([v for v in migrated.values() if v > 0]),
            "rows_migrated": sum(migrated.values()),
            "details": migrated,
            "errors": errors,
        }

    def export_schema_ddl(self) -> str:
        """Export all CREATE TABLE statements."""
        lines = [
            "-- ═══════════════════════════════════════════════════════════",
            "-- GRAVITY- | Project Anchor — PostgreSQL Schema (33 tables)",
            f"-- Generated: {datetime.now(timezone.utc).isoformat()}",
            "-- ═══════════════════════════════════════════════════════════",
            "",
        ]
        for table_name, ddl in POSTGRES_SCHEMA.items():
            lines.append(f"-- Table: {table_name}")
            lines.append(ddl.strip() + ";")
            lines.append("")

        return "\n".join(lines)


# ── CLI Entry Point ──────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description="GRAVITY- Database Migration Tool")
    parser.add_argument("--check", action="store_true", help="Check current backend")
    parser.add_argument("--migrate", action="store_true", help="Migrate SQLite → PostgreSQL")
    parser.add_argument("--schema", action="store_true", help="Export schema DDL")
    parser.add_argument("--create", action="store_true", help="Create PostgreSQL schema")
    parser.add_argument("--db-url", type=str, help="Override database URL")
    args = parser.parse_args()

    db = DatabaseMigration(args.db_url)

    if args.check:
        import json
        info = db.check_backend()
        print(json.dumps(info, indent=2))

    elif args.migrate:
        print("Starting SQLite → PostgreSQL migration...")
        result = db.migrate_sqlite_to_postgres()
        import json
        print(json.dumps(result, indent=2))

    elif args.schema:
        print(db.export_schema_ddl())

    elif args.create:
        result = db.create_postgres_schema()
        print(f"Created {result['tables_created']} tables")

    else:
        parser.print_help()


if __name__ == "__main__":
    main()
