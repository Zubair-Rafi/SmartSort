"""
SQLite schema definition and idempotent initialisation.

OS Concept: WAL (Write-Ahead Logging) mode allows concurrent readers while
a write is in progress — important when background worker threads query
history while the main thread is displaying the UI.
"""
from __future__ import annotations
import sqlite3

SCHEMA_VERSION = 1

_DDL: list[str] = [
    """
    CREATE TABLE IF NOT EXISTS schema_version (
        version    INTEGER NOT NULL,
        applied_at TEXT    NOT NULL DEFAULT (datetime('now'))
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS categories (
        id          TEXT PRIMARY KEY,
        name        TEXT NOT NULL,
        parent_id   TEXT REFERENCES categories(id) ON DELETE SET NULL,
        description TEXT NOT NULL DEFAULT '',
        keywords    TEXT NOT NULL DEFAULT '[]',
        extensions  TEXT NOT NULL DEFAULT '[]',
        destination TEXT NOT NULL,
        enabled     INTEGER NOT NULL DEFAULT 1,
        sort_order  INTEGER NOT NULL DEFAULT 0,
        created_at  TEXT NOT NULL DEFAULT (datetime('now')),
        updated_at  TEXT NOT NULL DEFAULT (datetime('now'))
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS watched_directories (
        id       INTEGER PRIMARY KEY AUTOINCREMENT,
        path     TEXT    NOT NULL UNIQUE,
        enabled  INTEGER NOT NULL DEFAULT 1,
        added_at TEXT    NOT NULL DEFAULT (datetime('now'))
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS rules (
        id                 TEXT PRIMARY KEY,
        name               TEXT NOT NULL,
        description        TEXT NOT NULL DEFAULT '',
        priority           INTEGER NOT NULL DEFAULT 0,
        enabled            INTEGER NOT NULL DEFAULT 1,
        conditions         TEXT NOT NULL DEFAULT '[]',
        action_category_id TEXT REFERENCES categories(id) ON DELETE SET NULL,
        created_at         TEXT NOT NULL DEFAULT (datetime('now')),
        updated_at         TEXT NOT NULL DEFAULT (datetime('now'))
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS file_history (
        id                    INTEGER PRIMARY KEY AUTOINCREMENT,
        filename              TEXT NOT NULL,
        original_path         TEXT NOT NULL,
        destination_path      TEXT,
        category_id           TEXT,
        category_path         TEXT,
        watch_path            TEXT NOT NULL,
        timestamp             TEXT NOT NULL DEFAULT (datetime('now')),
        status                TEXT NOT NULL DEFAULT 'pending',
        classification_method TEXT NOT NULL DEFAULT 'unknown',
        confidence            REAL NOT NULL DEFAULT 0.0,
        explanation           TEXT NOT NULL DEFAULT '',
        error_details         TEXT,
        undone_at             TEXT
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_history_timestamp ON file_history (timestamp DESC)",
    "CREATE INDEX IF NOT EXISTS idx_history_status    ON file_history (status)",
    "CREATE INDEX IF NOT EXISTS idx_categories_parent ON categories  (parent_id)",
]


def initialize_schema(conn: sqlite3.Connection) -> None:
    """
    Create all tables and indices idempotently.
    Safe to call on every application startup.
    """
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")

    for stmt in _DDL:
        conn.execute(stmt)

    row = conn.execute("SELECT version FROM schema_version").fetchone()
    if row is None:
        conn.execute(
            "INSERT INTO schema_version (version) VALUES (?)",
            (SCHEMA_VERSION,),
        )

    conn.commit()
