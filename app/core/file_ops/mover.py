"""
Safe file move operations.

OS Concepts demonstrated:
  - Atomic rename on the same filesystem (os.rename / Path.rename)
  - Copy-verify-delete fallback for cross-filesystem moves
  - File permission checks before attempting any operation
  - Directory creation with exist_ok to avoid TOCTOU races
"""
from __future__ import annotations
import os
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from app.core.file_ops.conflict import ConflictStrategy, resolve_conflict
from app.utils.logging_setup import get_logger

logger = get_logger(__name__)


@dataclass
class MoveResult:
    success: bool
    source: Path
    destination: Optional[Path]
    conflict_resolved: bool
    skipped: bool
    error: Optional[str]


def safe_move(
    src: Path,
    dst_dir: Path,
    conflict_strategy: ConflictStrategy = ConflictStrategy.RENAME,
    base_dir: Optional[Path] = None,
) -> MoveResult:
    """
    Move *src* into *dst_dir* with safety checks and conflict resolution.

    Args:
        src              - Source file to move.
        dst_dir          - Target directory (will be created if absent).
        conflict_strategy- What to do if a same-named file already exists.
        base_dir         - If provided, validate dst_dir is within this root
                           (prevents directory-traversal from category names).

    Returns:
        MoveResult with a full description of what happened.
    """
    # ── Pre-flight ────────────────────────────────────────────────────────────
    if not src.exists():
        return _fail(src, f"Source does not exist: {src}")

    if not src.is_file():
        return _fail(src, f"Source is not a regular file: {src}")

    if not os.access(src, os.R_OK):
        return _fail(src, f"No read permission: {src}")

    # Validate destination stays within base_dir (directory traversal guard)
    if base_dir is not None:
        try:
            dst_dir.resolve().relative_to(base_dir.resolve())
        except ValueError:
            return _fail(
                src,
                f"Destination {dst_dir} escapes allowed base directory {base_dir}",
            )

    # ── Create destination directory ──────────────────────────────────────────
    try:
        dst_dir.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        return _fail(src, f"Cannot create directory {dst_dir}: {exc}")

    if not os.access(dst_dir, os.W_OK):
        return _fail(src, f"No write permission for directory: {dst_dir}")

    # ── Conflict resolution ───────────────────────────────────────────────────
    dst_path, conflict = resolve_conflict(src, dst_dir, conflict_strategy)

    if dst_path is None:
        logger.info("Skipping '%s' — file already exists at destination.", src.name)
        return MoveResult(
            success=True, source=src, destination=None,
            conflict_resolved=True, skipped=True, error=None,
        )

    # ── Execute move ──────────────────────────────────────────────────────────
    try:
        _execute_move(src, dst_path)
        logger.info("Moved  '%s'  →  '%s'", src.name, dst_path)
        return MoveResult(
            success=True, source=src, destination=dst_path,
            conflict_resolved=conflict, skipped=False, error=None,
        )
    except OSError as exc:
        logger.error("Move failed '%s' → '%s': %s", src.name, dst_path, exc)
        return MoveResult(
            success=False, source=src, destination=dst_path,
            conflict_resolved=conflict, skipped=False, error=str(exc),
        )


def _execute_move(src: Path, dst: Path) -> None:
    """
    Perform the actual file move.

    Attempt an atomic rename first (works only on the same filesystem/device).
    On POSIX this is guaranteed atomic by the OS.  If rename raises OSError
    (EXDEV = cross-device link not permitted), fall back to:
      1. shutil.copy2(src, dst)   — preserves metadata
      2. size verification
      3. src.unlink()

    OS Concept: os.rename() is atomic on POSIX; there is no window where
    neither the old nor the new path exists.  The copy+delete fallback has
    a window and is not atomic, hence the size verification before delete.
    """
    try:
        src.rename(dst)
    except OSError:
        # Cross-filesystem move — copy then delete
        shutil.copy2(src, dst)
        src_size = src.stat().st_size
        dst_size = dst.stat().st_size
        if src_size != dst_size:
            dst.unlink(missing_ok=True)
            raise OSError(
                f"Copy verification failed: size mismatch "
                f"(src={src_size} dst={dst_size}) for '{src.name}'"
            )
        src.unlink()


def undo_move(op_destination: Path, op_source_dir: Path) -> MoveResult:
    """Reverse a previous move by moving the file back to its original directory."""
    return safe_move(
        src=op_destination,
        dst_dir=op_source_dir,
        conflict_strategy=ConflictStrategy.RENAME,
    )


def _fail(src: Path, error: str) -> MoveResult:
    logger.error("safe_move failed: %s", error)
    return MoveResult(
        success=False, source=src, destination=None,
        conflict_resolved=False, skipped=False, error=error,
    )
