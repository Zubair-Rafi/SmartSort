"""
Safe path manipulation utilities.

OS Concepts:
- Directory traversal prevention via Path.resolve() + relative_to()
- Cross-platform path normalization through pathlib
"""
from __future__ import annotations
from pathlib import Path


def safe_resolve(base: Path, relative: str) -> Path | None:
    """
    Resolve *relative* against *base*, ensuring the result stays inside *base*.

    Returns None for any path that would escape the base directory.
    Protects against directory traversal attacks from user-supplied category names.
    """
    try:
        rel = Path(relative)
        if rel.is_absolute():
            return None
        # Reject explicit traversal components
        for part in rel.parts:
            if part in (".", ".."):
                return None
        resolved = (base / rel).resolve()
        resolved.relative_to(base.resolve())   # raises ValueError if outside base
        return resolved
    except (ValueError, RuntimeError):
        return None


def make_unique_path(path: Path) -> Path:
    """
    Append a counter suffix until a non-conflicting filename is found.

    ``report.pdf`` → ``report (1).pdf`` → ``report (2).pdf`` …

    OS Concept: Querying filesystem state (Path.exists) to detect name
    conflicts before committing a file operation.
    """
    if not path.exists():
        return path

    stem = path.stem
    suffix = path.suffix
    parent = path.parent
    counter = 1

    while True:
        candidate = parent / f"{stem} ({counter}){suffix}"
        if not candidate.exists():
            return candidate
        counter += 1


def is_temp_file(path: Path, temp_extensions: list[str]) -> bool:
    """Return True if the file has a known temporary download extension."""
    suffix = path.suffix.lower()
    # Also check compound suffixes like .tar.gz.part
    all_suffixes = "".join(s.lower() for s in path.suffixes)
    return suffix in temp_extensions or any(
        all_suffixes.endswith(t) for t in temp_extensions
    )


def normalize_extension(path: Path) -> str:
    """Return the lowercase extension including the leading dot."""
    return path.suffix.lower()
