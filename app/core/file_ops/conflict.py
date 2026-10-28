"""
Filename conflict resolution strategies and helpers.
"""
from __future__ import annotations
from enum import Enum
from pathlib import Path

from app.utils.path_utils import make_unique_path


class ConflictStrategy(str, Enum):
    RENAME    = "rename"     # Append (1), (2), … until unique
    SKIP      = "skip"       # Leave file at source
    OVERWRITE = "overwrite"  # Replace existing — use with caution
    ASK       = "ask"        # Prompt user (resolved at service level)


def resolve_conflict(
    src: Path,
    dst_dir: Path,
    strategy: ConflictStrategy = ConflictStrategy.RENAME,
) -> tuple[Path | None, bool]:
    """
    Compute the final destination path, respecting the conflict strategy.

    Returns:
        (resolved_path, conflict_occurred)

        resolved_path is None when strategy=SKIP and the file already exists.
    """
    desired = dst_dir / src.name

    if not desired.exists():
        return desired, False

    # Conflict detected
    if strategy == ConflictStrategy.RENAME:
        return make_unique_path(desired), True

    if strategy == ConflictStrategy.OVERWRITE:
        return desired, True

    if strategy == ConflictStrategy.SKIP:
        return None, True

    # ASK is handled upstream; fall back to RENAME
    return make_unique_path(desired), True
