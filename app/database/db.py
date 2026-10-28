"""
Thread-safe SQLite database wrapper.

OS Concepts:
- threading.local() for per-thread connection isolation — SQLite connections
  must not be shared across threads.
- WAL journal mode enables concurrent reads while a write is in progress.
- Foreign key enforcement via PRAGMA for data integrity.
"""
from __future__ import annotations
import json
import sqlite3
import threading
from datetime import datetime
from pathlib import Path
from typing import Optional

from app.database.migrations import initialize_schema
from app.database.models import (
    Category, ClassificationMethod, FileOperation,
    OperationStatus, Rule, WatchedDirectory,
)
from app.utils.logging_setup import get_logger

logger = get_logger(__name__)


class Database:
    """
    Per-thread SQLite connections managed via threading.local().

    Each thread that calls self.conn receives its own SQLite connection
    to the same database file.  WAL mode allows concurrent readers while
    a single writer holds the write lock.
    """

    def __init__(self, db_path: Path) -> None:
        self._db_path = db_path
        self._local = threading.local()
        db_path.parent.mkdir(parents=True, exist_ok=True)
        # Initialise schema on the calling thread's connection
        with self._new_connection() as conn:
            initialize_schema(conn)
        logger.info("Database initialised at %s", db_path)

    # ── Connection management ─────────────────────────────────────────────────

    def _new_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self._db_path), check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute("PRAGMA journal_mode = WAL")
        return conn

    @property
    def conn(self) -> sqlite3.Connection:
        if not hasattr(self._local, "conn") or self._local.conn is None:
            self._local.conn = self._new_connection()
        return self._local.conn

    def close(self) -> None:
        """Close this thread's connection."""
        if hasattr(self._local, "conn") and self._local.conn is not None:
            self._local.conn.close()
            self._local.conn = None

    # ── Category operations ───────────────────────────────────────────────────

    def upsert_category(self, cat: Category) -> None:
        self.conn.execute(
            """
            INSERT INTO categories
                (id, name, parent_id, description, keywords, extensions,
                 destination, enabled, sort_order, created_at, updated_at)
            VALUES (?,?,?,?,?,?,?,?,?,?,?)
            ON CONFLICT(id) DO UPDATE SET
                name        = excluded.name,
                parent_id   = excluded.parent_id,
                description = excluded.description,
                keywords    = excluded.keywords,
                extensions  = excluded.extensions,
                destination = excluded.destination,
                enabled     = excluded.enabled,
                sort_order  = excluded.sort_order,
                updated_at  = excluded.updated_at
            """,
            (
                cat.id, cat.name, cat.parent_id, cat.description,
                json.dumps(cat.keywords), json.dumps(cat.extensions),
                cat.destination, int(cat.enabled), cat.sort_order,
                cat.created_at.isoformat(), cat.updated_at.isoformat(),
            ),
        )
        self.conn.commit()

    def get_all_categories(self) -> list[Category]:
        rows = self.conn.execute(
            "SELECT * FROM categories ORDER BY sort_order, name"
        ).fetchall()
        return [self._row_to_category(r) for r in rows]

    def get_category(self, cat_id: str) -> Optional[Category]:
        row = self.conn.execute(
            "SELECT * FROM categories WHERE id = ?", (cat_id,)
        ).fetchone()
        return self._row_to_category(row) if row else None

    def get_category_by_destination(self, destination: str) -> Optional[Category]:
        row = self.conn.execute(
            "SELECT * FROM categories WHERE destination = ?", (destination,)
        ).fetchone()
        return self._row_to_category(row) if row else None

    def delete_category(self, cat_id: str) -> None:
        self.conn.execute("DELETE FROM categories WHERE id = ?", (cat_id,))
        self.conn.commit()

    def count_categories(self) -> int:
        return self.conn.execute("SELECT COUNT(*) FROM categories").fetchone()[0]

    def _row_to_category(self, row: sqlite3.Row) -> Category:
        return Category(
            id=row["id"],
            name=row["name"],
            parent_id=row["parent_id"],
            description=row["description"],
            keywords=json.loads(row["keywords"]),
            extensions=json.loads(row["extensions"]),
            destination=row["destination"],
            enabled=bool(row["enabled"]),
            sort_order=row["sort_order"],
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
        )

    # ── Watched directory operations ──────────────────────────────────────────

    def add_watched_directory(self, path: str) -> WatchedDirectory:
        now = datetime.now().isoformat()
        self.conn.execute(
            "INSERT OR IGNORE INTO watched_directories (path, added_at) VALUES (?,?)",
            (path, now),
        )
        self.conn.commit()
        wd = self.get_watched_directory(path)
        assert wd is not None
        return wd

    def get_watched_directory(self, path: str) -> Optional[WatchedDirectory]:
        row = self.conn.execute(
            "SELECT * FROM watched_directories WHERE path = ?", (path,)
        ).fetchone()
        return self._row_to_watched_dir(row) if row else None

    def get_all_watched_directories(self) -> list[WatchedDirectory]:
        rows = self.conn.execute(
            "SELECT * FROM watched_directories WHERE enabled = 1"
        ).fetchall()
        return [self._row_to_watched_dir(r) for r in rows]

    def remove_watched_directory(self, path: str) -> None:
        self.conn.execute(
            "DELETE FROM watched_directories WHERE path = ?", (path,)
        )
        self.conn.commit()

    def _row_to_watched_dir(self, row: sqlite3.Row) -> WatchedDirectory:
        return WatchedDirectory(
            id=row["id"],
            path=row["path"],
            enabled=bool(row["enabled"]),
            added_at=datetime.fromisoformat(row["added_at"]),
        )

    # ── History / file operation records ──────────────────────────────────────

    def record_operation(self, op: FileOperation) -> int:
        """Insert a FileOperation and return its new row ID."""
        cursor = self.conn.execute(
            """
            INSERT INTO file_history (
                filename, original_path, destination_path,
                category_id, category_path, watch_path,
                timestamp, status, classification_method,
                confidence, explanation, error_details
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                op.filename, op.original_path, op.destination_path,
                op.category_id, op.category_path, op.watch_path,
                op.timestamp.isoformat(), op.status.value,
                op.classification_method.value, op.confidence,
                op.explanation, op.error_details,
            ),
        )
        self.conn.commit()
        return cursor.lastrowid  # type: ignore[return-value]

    def update_operation_status(
        self,
        op_id: int,
        status: OperationStatus,
        destination_path: Optional[str] = None,
        error_details: Optional[str] = None,
    ) -> None:
        self.conn.execute(
            """
            UPDATE file_history
            SET status           = ?,
                destination_path = COALESCE(?, destination_path),
                error_details    = COALESCE(?, error_details)
            WHERE id = ?
            """,
            (status.value, destination_path, error_details, op_id),
        )
        self.conn.commit()

    def mark_undone(self, op_id: int) -> None:
        self.conn.execute(
            "UPDATE file_history SET status='undone', undone_at=? WHERE id=?",
            (datetime.now().isoformat(), op_id),
        )
        self.conn.commit()

    def get_recent_history(self, limit: int = 100) -> list[FileOperation]:
        rows = self.conn.execute(
            "SELECT * FROM file_history ORDER BY timestamp DESC LIMIT ?",
            (limit,),
        ).fetchall()
        return [self._row_to_operation(r) for r in rows]

    def get_operation(self, op_id: int) -> Optional[FileOperation]:
        row = self.conn.execute(
            "SELECT * FROM file_history WHERE id = ?", (op_id,)
        ).fetchone()
        return self._row_to_operation(row) if row else None

    def count_by_status(self, status: OperationStatus) -> int:
        return self.conn.execute(
            "SELECT COUNT(*) FROM file_history WHERE status = ?",
            (status.value,),
        ).fetchone()[0]

    def get_stats(self) -> dict[str, int]:
        """Return counts keyed by status."""
        rows = self.conn.execute(
            "SELECT status, COUNT(*) as cnt FROM file_history GROUP BY status"
        ).fetchall()
        return {r["status"]: r["cnt"] for r in rows}

    def _row_to_operation(self, row: sqlite3.Row) -> FileOperation:
        return FileOperation(
            id=row["id"],
            filename=row["filename"],
            original_path=row["original_path"],
            destination_path=row["destination_path"],
            category_id=row["category_id"],
            category_path=row["category_path"],
            watch_path=row["watch_path"],
            timestamp=datetime.fromisoformat(row["timestamp"]),
            status=OperationStatus(row["status"]),
            classification_method=ClassificationMethod(row["classification_method"]),
            confidence=row["confidence"],
            explanation=row["explanation"],
            error_details=row["error_details"],
            undone_at=(
                datetime.fromisoformat(row["undone_at"])
                if row["undone_at"] else None
            ),
        )
