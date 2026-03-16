"""
DocForge — Database Schema
============================

SQLite schema definitions and database initialisation.
All DDL statements are centralised here for easy migration management.

The schema tracks:
  - documents: Every PDF with extraction results and processing state
  - jobs: Processing job runs with progress counters
  - operations: File rename/move operations for rollback support
  - metrics: Per-stage timing and resource usage for performance analysis
"""

from __future__ import annotations

import sqlite3

from docforge.infra.logging import get_logger

logger = get_logger(__name__)

SCHEMA_VERSION = 1

# =============================================================================
# DDL Statements
# =============================================================================

DOCUMENTS_TABLE = """
CREATE TABLE IF NOT EXISTS documents (
    -- Identity
    file_id         TEXT PRIMARY KEY,
    original_path   TEXT NOT NULL,
    file_size       INTEGER NOT NULL,
    page_count      INTEGER DEFAULT 0,

    -- Processing state
    current_stage   INTEGER DEFAULT 0,
    status          TEXT DEFAULT 'pending',
    error_message   TEXT DEFAULT '',
    created_at      TEXT DEFAULT (datetime('now')),
    updated_at      TEXT DEFAULT (datetime('now')),

    -- Stage 1: PDF metadata
    pdf_metadata    TEXT DEFAULT '{}',
    metadata_fields TEXT DEFAULT '{}',

    -- Stage 2: Text probe
    text_quality    REAL DEFAULT 0.0,
    raw_text        BLOB,

    -- Stage 3: Extraction results
    extraction_strategy TEXT DEFAULT '',
    vlm_fields      TEXT DEFAULT '',
    vlm_model       TEXT DEFAULT '',
    vlm_raw_response TEXT DEFAULT '',
    heuristic_fields TEXT DEFAULT '',
    ocr_text        BLOB,
    ocr_confidence  REAL DEFAULT 0.0,

    -- Stage 4: Merged result
    merged_fields   TEXT DEFAULT '{}',

    -- Stage 5: Output
    canonical_name  TEXT DEFAULT '',
    target_dir      TEXT DEFAULT '',
    processing_ms   INTEGER DEFAULT 0
);
"""

JOBS_TABLE = """
CREATE TABLE IF NOT EXISTS jobs (
    job_id          TEXT PRIMARY KEY,
    source_path     TEXT NOT NULL,
    config_json     TEXT NOT NULL DEFAULT '{}',
    started_at      TEXT DEFAULT (datetime('now')),
    completed_at    TEXT,
    total_files     INTEGER DEFAULT 0,
    processed_files INTEGER DEFAULT 0,
    error_count     INTEGER DEFAULT 0,
    status          TEXT DEFAULT 'running'
);
"""

OPERATIONS_TABLE = """
CREATE TABLE IF NOT EXISTS operations (
    op_id           INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id          TEXT REFERENCES jobs(job_id),
    file_id         TEXT REFERENCES documents(file_id),
    operation       TEXT NOT NULL,
    source_path     TEXT NOT NULL,
    target_path     TEXT NOT NULL,
    executed        INTEGER DEFAULT 0,
    executed_at     TEXT,
    checksum_before TEXT DEFAULT '',
    checksum_after  TEXT DEFAULT ''
);
"""

METRICS_TABLE = """
CREATE TABLE IF NOT EXISTS metrics (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    file_id         TEXT REFERENCES documents(file_id),
    stage           INTEGER,
    duration_ms     INTEGER,
    memory_mb       REAL,
    method          TEXT
);
"""

INDEXES = [
    "CREATE INDEX IF NOT EXISTS idx_doc_status ON documents(status);",
    "CREATE INDEX IF NOT EXISTS idx_doc_stage ON documents(current_stage);",
    "CREATE INDEX IF NOT EXISTS idx_doc_path ON documents(original_path);",
    "CREATE INDEX IF NOT EXISTS idx_doc_strategy ON documents(extraction_strategy);",
    "CREATE INDEX IF NOT EXISTS idx_doc_quality ON documents(text_quality);",
    "CREATE INDEX IF NOT EXISTS idx_ops_job ON operations(job_id);",
    "CREATE INDEX IF NOT EXISTS idx_ops_executed ON operations(executed);",
    "CREATE INDEX IF NOT EXISTS idx_metrics_file ON metrics(file_id);",
]

SCHEMA_VERSION_TABLE = """
CREATE TABLE IF NOT EXISTS schema_version (
    version INTEGER PRIMARY KEY
);
"""


# =============================================================================
# Database Initialisation
# =============================================================================

def configure_db(db_path: str) -> sqlite3.Connection:
    """Open a SQLite connection with optimal settings for DocForge.

    Configures WAL mode, memory-mapped I/O, and appropriate cache sizes
    for high-throughput batch processing.

    Args:
        db_path: Path to the SQLite database file.

    Returns:
        A configured sqlite3.Connection.
    """
    conn = sqlite3.connect(db_path, check_same_thread=False)
    conn.row_factory = sqlite3.Row

    # ── Performance pragmas ─────────────────────────────────────────────
    conn.execute("PRAGMA journal_mode=WAL")        # Write-ahead logging
    conn.execute("PRAGMA synchronous=NORMAL")      # Safe + fast
    conn.execute("PRAGMA cache_size=-64000")        # 64 MB page cache
    conn.execute("PRAGMA mmap_size=268435456")      # 256 MB memory-mapped I/O
    conn.execute("PRAGMA temp_store=MEMORY")        # Temp tables in RAM
    conn.execute("PRAGMA busy_timeout=5000")        # Wait 5s on lock contention
    conn.execute("PRAGMA foreign_keys=ON")          # Enforce FK constraints

    logger.debug("Database connection configured: %s (WAL mode)", db_path)
    return conn


def init_schema(conn: sqlite3.Connection) -> None:
    """Create all tables and indexes if they don't exist.

    Safe to call multiple times — uses CREATE IF NOT EXISTS.

    Args:
        conn: An open sqlite3.Connection.
    """
    logger.info("Initialising database schema (version %d)...", SCHEMA_VERSION)

    conn.execute(DOCUMENTS_TABLE)
    conn.execute(JOBS_TABLE)
    conn.execute(OPERATIONS_TABLE)
    conn.execute(METRICS_TABLE)
    conn.execute(SCHEMA_VERSION_TABLE)

    for idx_sql in INDEXES:
        conn.execute(idx_sql)

    # Record schema version
    conn.execute(
        "INSERT OR IGNORE INTO schema_version (version) VALUES (?)",
        (SCHEMA_VERSION,),
    )
    conn.commit()

    logger.info("Database schema ready (version %d)", SCHEMA_VERSION)
