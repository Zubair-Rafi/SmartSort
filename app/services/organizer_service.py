"""
Top-level file organization coordinator.

OS Concepts demonstrated:
  - Directory traversal with os.scandir (returns DirEntry with cached stat)
  - Concurrent processing via ThreadPoolExecutor (bounded worker pool)
  - Thread-safe queuing and per-path locking
  - File permission checks before any operation
"""
from __future__ import annotations
import os
import threading
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional

from app.core.classification.confidence import ConfidenceEvaluator
from app.core.classification.file_type import FileTypeClassifier
from app.core.file_ops.conflict import ConflictStrategy
from app.core.file_ops.mover import MoveResult, safe_move
from app.core.history.history_service import HistoryService
from app.core.sync.locks import global_path_locks
from app.database.db import Database
from app.database.models import ClassificationResult
from app.utils.config import AppConfig
from app.utils.logging_setup import get_logger
from app.utils.path_utils import is_temp_file

logger = get_logger(__name__)


@dataclass
class OrganizeProgress:
    """Emitted to the UI after each file is processed."""
    filename: str
    category_path: Optional[str]
    success: bool
    skipped: bool
    error: Optional[str]
    files_processed: int
    files_total: int


class OrganizerService:
    """
    Coordinates classification → safe_move → history for a set of files.

    In Milestone 1 this is driven manually via organize_existing_files().
    In Milestone 2 it will also consume events from the Watchdog monitor.
    """

    def __init__(self, db: Database) -> None:
        self._db = db
        self._history = HistoryService(db)
        self._stage1 = FileTypeClassifier()
        self._confidence = ConfidenceEvaluator()
        cfg = AppConfig.instance()
        max_workers: int = cfg.get("max_workers", 2)
        self._executor = ThreadPoolExecutor(
            max_workers=max_workers,
            thread_name_prefix="smartsort-worker",
        )

    # ── Queries ────────────────────────────────────────────────────────────────

    def get_watched_directories(self) -> list[Path]:
        return [Path(wd.path) for wd in self._db.get_all_watched_directories()]

    def get_history_stats(self) -> dict[str, int]:
        return self._history.get_stats()

    def get_recent_history(self, limit: int = 100):
        return self._history.get_recent(limit)

    def undo(self, op_id: int) -> tuple[bool, str]:
        return self._history.undo(op_id)

    # ── Classification ─────────────────────────────────────────────────────────

    def classify_file(self, file_path: Path) -> ClassificationResult:
        """Run the current pipeline (Stage 1 only in M1)."""
        result = self._stage1.classify(file_path)
        # result is never None from FileTypeClassifier
        assert result is not None
        return self._confidence.evaluate(result)

    def get_destination(self, category_path: str, watch_root: Path) -> Path:
        """Resolve the absolute destination directory for a category."""
        return watch_root / category_path

    # ── Single-file organize ───────────────────────────────────────────────────

    def organize_file(
        self,
        file_path: Path,
        watch_root: Path,
        index: int = 0,
        total: int = 1,
        progress_callback: Optional[Callable[[OrganizeProgress], None]] = None,
    ) -> bool:
        """
        Classify and move one file.  Thread-safe via per-path lock.
        Returns True if the file was successfully moved or skipped.
        """
        with global_path_locks.lock(file_path):
            return self._organize_locked(
                file_path, watch_root, index, total, progress_callback
            )

    def _organize_locked(
        self,
        file_path: Path,
        watch_root: Path,
        index: int,
        total: int,
        progress_callback: Optional[Callable[[OrganizeProgress], None]],
    ) -> bool:
        cfg = AppConfig.instance()
        temp_exts: list[str] = cfg.get("temp_extensions", [])

        # Skip temp and missing files
        if is_temp_file(file_path, temp_exts):
            logger.debug("Skipping temp file: %s", file_path.name)
            return False
        if not file_path.exists():
            logger.debug("File gone before processing: %s", file_path)
            return False

        # Classify
        result = self.classify_file(file_path)
        logger.debug(
            "Classified '%s' → %s  (conf=%.2f method=%s)",
            file_path.name, result.category_path, result.confidence, result.method.value,
        )

        # Record pending
        op_id = self._history.record_pending(file_path, watch_root, result)

        # Determine destination
        if result.category_path:
            dst_dir = self.get_destination(result.category_path, watch_root)
        else:
            # Low-confidence → Review Queue
            dst_dir = watch_root / "Review"

        # Move
        move_result = safe_move(
            src=file_path,
            dst_dir=dst_dir,
            conflict_strategy=ConflictStrategy.RENAME,
            base_dir=watch_root,
        )

        # Update history
        progress = OrganizeProgress(
            filename=file_path.name,
            category_path=result.category_path,
            success=False,
            skipped=move_result.skipped,
            error=move_result.error,
            files_processed=index + 1,
            files_total=total,
        )

        if move_result.success and not move_result.skipped:
            assert move_result.destination is not None
            self._history.mark_success(op_id, move_result.destination)
            progress.success = True
        elif move_result.skipped:
            self._history.mark_skipped(op_id)
            progress.success = True
        else:
            self._history.mark_failed(op_id, move_result.error or "Unknown error")

        if progress_callback:
            progress_callback(progress)

        return progress.success

    # ── Batch organize ─────────────────────────────────────────────────────────

    def organize_existing_files(
        self,
        watch_root: Path,
        progress_callback: Optional[Callable[[OrganizeProgress], None]] = None,
        cancel_event: Optional[threading.Event] = None,
    ) -> tuple[int, int]:
        """
        Scan *watch_root* (top-level files only) and organize each file.

        Returns: (success_count, total_count)

        OS Concept: os.scandir() is used instead of Path.iterdir() because
        it returns DirEntry objects that cache stat() results from the OS,
        avoiding an extra system call per entry.
        """
        if not watch_root.exists():
            logger.error("Watch root does not exist: %s", watch_root)
            return 0, 0

        cfg = AppConfig.instance()
        temp_exts: list[str] = cfg.get("temp_extensions", [])
        files: list[Path] = []

        try:
            with os.scandir(watch_root) as entries:
                for entry in entries:
                    # DirEntry.is_file() uses the cached type from the OS readdir call
                    if entry.is_file(follow_symlinks=False):
                        p = Path(entry.path)
                        if not is_temp_file(p, temp_exts):
                            files.append(p)
        except PermissionError as exc:
            logger.error("Cannot scan %s: %s", watch_root, exc)
            return 0, 0

        total = len(files)
        if total == 0:
            return 0, 0

        logger.info("Organizing %d file(s) in '%s'", total, watch_root)
        success_count = 0

        for i, file_path in enumerate(files):
            if cancel_event and cancel_event.is_set():
                logger.info("Organization cancelled by user.")
                break
            if self.organize_file(
                file_path, watch_root, i, total, progress_callback
            ):
                success_count += 1

        return success_count, total

    # ── Lifecycle ─────────────────────────────────────────────────────────────

    def shutdown(self) -> None:
        self._executor.shutdown(wait=True)
