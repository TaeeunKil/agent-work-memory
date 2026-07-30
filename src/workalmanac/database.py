import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS agent_sessions (
  session_id          TEXT PRIMARY KEY,
  provider            TEXT NOT NULL,
  provider_session_id TEXT NOT NULL,
  title               TEXT NOT NULL,
  cwd                 TEXT,
  source_path         TEXT,
  started_at          TEXT,
  ended_at            TEXT,
  modified_at         TEXT NOT NULL,
  state               TEXT NOT NULL,
  content_captured    INTEGER NOT NULL DEFAULT 0,
  distilled_at        TEXT,
  distill_runtime     TEXT,
  created_at          TEXT NOT NULL,
  updated_at          TEXT NOT NULL,
  UNIQUE(provider, provider_session_id, source_path)
);

CREATE TABLE IF NOT EXISTS agent_events (
  event_id      TEXT PRIMARY KEY,
  session_id    TEXT NOT NULL REFERENCES agent_sessions(session_id)
                ON DELETE CASCADE,
  sequence      INTEGER NOT NULL,
  kind          TEXT NOT NULL,
  role          TEXT,
  label         TEXT NOT NULL,
  occurred_at   TEXT,
  content       TEXT NOT NULL,
  source_line   INTEGER NOT NULL,
  created_at    TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_agent_events_session
  ON agent_events(session_id, sequence);

CREATE TABLE IF NOT EXISTS collector_cursors (
  source_id    TEXT PRIMARY KEY,
  provider     TEXT NOT NULL,
  source_path  TEXT NOT NULL,
  last_line    INTEGER NOT NULL,
  size_bytes   INTEGER NOT NULL,
  updated_at   TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS distill_receipts (
  run_id          TEXT PRIMARY KEY,
  runtime         TEXT NOT NULL,
  model           TEXT,
  content_access  TEXT NOT NULL,
  session_ids     TEXT NOT NULL,
  status          TEXT NOT NULL,
  changed_files   TEXT NOT NULL,
  output_summary  TEXT,
  started_at      TEXT NOT NULL,
  finished_at     TEXT
);

CREATE TABLE IF NOT EXISTS sync_receipts (
  run_id               TEXT PRIMARY KEY,
  providers            TEXT NOT NULL,
  include_content      INTEGER NOT NULL,
  status               TEXT NOT NULL,
  sessions_discovered  INTEGER NOT NULL DEFAULT 0,
  sessions_updated     INTEGER NOT NULL DEFAULT 0,
  events_added         INTEGER NOT NULL DEFAULT 0,
  error_type           TEXT,
  started_at           TEXT NOT NULL,
  finished_at          TEXT
);

CREATE VIRTUAL TABLE IF NOT EXISTS search_documents USING fts5(
  kind UNINDEXED,
  identity UNINDEXED,
  title,
  body
);
"""


def connect(path: Path) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path, timeout=30)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA busy_timeout = 30000")
    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute("PRAGMA journal_mode = WAL")
    connection.executescript(SCHEMA)
    ensure_column(connection, "agent_sessions", "distilled_at", "TEXT")
    ensure_column(connection, "agent_sessions", "distill_runtime", "TEXT")
    connection.commit()
    return connection


def ensure_column(
    connection: sqlite3.Connection,
    table: str,
    column: str,
    declaration: str,
) -> None:
    columns = {row["name"] for row in connection.execute(f"PRAGMA table_info({table})")}
    if column not in columns:
        connection.execute(f"ALTER TABLE {table} ADD COLUMN {column} {declaration}")


@contextmanager
def open_database(path: Path) -> Iterator[sqlite3.Connection]:
    connection = connect(path)
    try:
        yield connection
    finally:
        connection.close()
