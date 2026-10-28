"""File operation history recording and undo."""
from __future__ import annotations
from datetime import datetime
from pathlib import Path
from typing import Optional

from app.core.file_ops.mover import undo_move
from app.database.db import Database
from app.database.models import (
    ClassificationResult, FileOperation,
    ClassificationMethod, OperationStatus,
)
from app.utils.logging_setup import get_logger

logger = get_logger(__name__)


class HistoryService:
    """
    Records every file operation in the SQLite history table and provides
    a safe, conflict-aware undo mechanism.
    """

    def __init__(self, db: Database) -> None:
        self._db = db

    # ── Recording ─────────────────────────────────────────────────────────────

    def record_pending(
        self,
        src: Path,
        watch_path: Path,
        result: ClassificationResult,
    ) -> int:
        """
        Write a PENDING record before the move is attempted.
        Returns the row ID for subsequent status updates.
        """
        op = FileOperation(
            filename=src.name,
            original_path=str(src),
            watch_path=str(watch_path),
            timestamp=datetime.now(),
            status=OperationStatus.PENDING,
            category_id=result.category_id,
            category_path=result.category_path,
            classification_method=result.method,
            confidence=result.confidence,
            explanation=result.explanation,
        )
        return self._db.record_operation(op)

    def mark_success(self, op_id: int, destination: Path) -> None:
        self._db.update_operation_status(
            op_id, OperationStatus.SUCCESS,
            destination_path=str(destination),
        )

    def mark_failed(self, op_id: int, error: str) -> None:
        self._db.update_operation_status(
            op_id, OperationStatus.FAILED,
            error_details=error,
        )

    def mark_skipped(self, op_id: int) -> None:
        self._db.update_operation_status(op_id, OperationStatus.SKIPPED)

    # ── Queries ───────────────────────────────────────────────────────────────

    def get_recent(self, limit: int = 100) -> list[FileOperation]:
        return self._db.get_recent_history(limit)

    def get_stats(self) -> dict[str, int]:
        return self._db.get_stats()

    # ── Undo ──────────────────────────────────────────────────────────────────

    def undo(self, op_id: int) -> tuple[bool, str]:
        """
        Reverse a file move.  Returns (success, human-readable message).

        Safety checks performed:
          1. Operation must have status=SUCCESS.
          2. File must still exist at the recorded destination.
          3. Move back with RENAME conflict resolution (never overwrites).
        """
        op = self._db.get_operation(op_id)
        if op is None:
            return False, f"Operation ID {op_id} not found."

        if op.status != OperationStatus.SUCCESS:
            return False, (
                f"Cannot undo — operation status is '{op.status.value}', "
                "only 'success' operations can be undone."
            )

        if op.destination_path is None:
            return False, "Operation has no recorded destination path."

        dst = Path(op.destination_path)
        src_dir = Path(op.original_path).parent

        if not dst.exists():
            return False, (
                f"File no longer exists at '{dst}'.\n"
                "It may have been moved or deleted externally."
            )

        result = undo_move(op_destination=dst, op_source_dir=src_dir)

        if result.success:
            self._db.mark_undone(op_id)
            msg = f"Restored '{op.filename}' to '{src_dir}'."
            if result.conflict_resolved and result.destination:
                msg += f" (Renamed to '{result.destination.name}' to avoid conflict.)"
            logger.info("Undo [op=%d]: %s", op_id, msg)
            return True, msg
        else:
            logger.error("Undo [op=%d] failed: %s", op_id, result.error)
            return False, f"Undo failed: {result.error}"
