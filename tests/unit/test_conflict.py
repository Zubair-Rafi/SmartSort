"""
Unit tests for conflict resolution and safe_move.

All tests use pytest's tmp_path fixture — no real user files are touched.
"""
from __future__ import annotations
import pytest
from pathlib import Path

from app.core.file_ops.conflict import ConflictStrategy, resolve_conflict
from app.core.file_ops.mover import MoveResult, safe_move
from app.utils.path_utils import make_unique_path


# ─────────────────────────────────────────────────────────────────────────────
# make_unique_path
# ─────────────────────────────────────────────────────────────────────────────

class TestMakeUniquePath:

    def test_no_conflict_returns_original(self, tmp_path: Path) -> None:
        p = tmp_path / "report.pdf"
        assert make_unique_path(p) == p

    def test_first_conflict_appends_one(self, tmp_path: Path) -> None:
        p = tmp_path / "report.pdf"
        p.touch()
        result = make_unique_path(p)
        assert result == tmp_path / "report (1).pdf"

    def test_second_conflict_appends_two(self, tmp_path: Path) -> None:
        (tmp_path / "report.pdf").touch()
        (tmp_path / "report (1).pdf").touch()
        result = make_unique_path(tmp_path / "report.pdf")
        assert result == tmp_path / "report (2).pdf"

    def test_file_without_extension(self, tmp_path: Path) -> None:
        p = tmp_path / "Makefile"
        p.touch()
        result = make_unique_path(p)
        assert result == tmp_path / "Makefile (1)"

    def test_dotfile(self, tmp_path: Path) -> None:
        p = tmp_path / ".gitignore"
        p.touch()
        result = make_unique_path(p)
        assert result.name.startswith(".gitignore")


# ─────────────────────────────────────────────────────────────────────────────
# resolve_conflict
# ─────────────────────────────────────────────────────────────────────────────

class TestResolveConflict:

    def test_no_conflict_returns_desired(self, tmp_path: Path) -> None:
        src     = tmp_path / "src" / "a.pdf"
        dst_dir = tmp_path / "dst"
        src.parent.mkdir(); dst_dir.mkdir()
        src.touch()

        path, conflict = resolve_conflict(src, dst_dir, ConflictStrategy.RENAME)
        assert path == dst_dir / "a.pdf"
        assert conflict is False

    def test_rename_on_conflict(self, tmp_path: Path) -> None:
        src     = tmp_path / "src" / "a.pdf"
        dst_dir = tmp_path / "dst"
        src.parent.mkdir(); dst_dir.mkdir()
        src.touch()
        (dst_dir / "a.pdf").touch()  # existing file

        path, conflict = resolve_conflict(src, dst_dir, ConflictStrategy.RENAME)
        assert path == dst_dir / "a (1).pdf"
        assert conflict is True

    def test_skip_on_conflict_returns_none(self, tmp_path: Path) -> None:
        src     = tmp_path / "src" / "a.pdf"
        dst_dir = tmp_path / "dst"
        src.parent.mkdir(); dst_dir.mkdir()
        src.touch()
        (dst_dir / "a.pdf").touch()

        path, conflict = resolve_conflict(src, dst_dir, ConflictStrategy.SKIP)
        assert path is None
        assert conflict is True

    def test_overwrite_returns_same_path(self, tmp_path: Path) -> None:
        src     = tmp_path / "src" / "a.pdf"
        dst_dir = tmp_path / "dst"
        src.parent.mkdir(); dst_dir.mkdir()
        src.touch()
        existing = dst_dir / "a.pdf"
        existing.write_text("old content")

        path, conflict = resolve_conflict(src, dst_dir, ConflictStrategy.OVERWRITE)
        assert path == existing
        assert conflict is True


# ─────────────────────────────────────────────────────────────────────────────
# safe_move
# ─────────────────────────────────────────────────────────────────────────────

class TestSafeMove:

    def _make_src(self, base: Path, name: str = "file.pdf", content: str = "data") -> Path:
        src = base / "src"
        src.mkdir(exist_ok=True)
        f = src / name
        f.write_text(content)
        return f

    def test_basic_move_succeeds(self, tmp_path: Path) -> None:
        src = self._make_src(tmp_path)
        dst_dir = tmp_path / "dst"
        result = safe_move(src, dst_dir)

        assert result.success is True
        assert result.skipped is False
        assert result.error is None
        assert result.destination == dst_dir / "file.pdf"
        assert (dst_dir / "file.pdf").exists()
        assert not src.exists()

    def test_creates_destination_directory(self, tmp_path: Path) -> None:
        src = self._make_src(tmp_path)
        dst_dir = tmp_path / "a" / "b" / "c"
        result = safe_move(src, dst_dir)
        assert result.success is True
        assert dst_dir.exists()

    def test_conflict_rename(self, tmp_path: Path) -> None:
        src = self._make_src(tmp_path)
        dst_dir = tmp_path / "dst"
        dst_dir.mkdir()
        (dst_dir / "file.pdf").write_text("existing")

        result = safe_move(src, dst_dir, ConflictStrategy.RENAME)
        assert result.success is True
        assert result.conflict_resolved is True
        assert result.destination == dst_dir / "file (1).pdf"
        assert (dst_dir / "file (1).pdf").exists()
        assert (dst_dir / "file.pdf").read_text() == "existing"  # untouched

    def test_conflict_skip(self, tmp_path: Path) -> None:
        src = self._make_src(tmp_path)
        dst_dir = tmp_path / "dst"
        dst_dir.mkdir()
        (dst_dir / "file.pdf").write_text("existing")

        result = safe_move(src, dst_dir, ConflictStrategy.SKIP)
        assert result.success is True
        assert result.skipped is True
        assert src.exists()  # source was not moved

    def test_missing_source_fails_gracefully(self, tmp_path: Path) -> None:
        nonexistent = tmp_path / "ghost.pdf"
        result = safe_move(nonexistent, tmp_path / "dst")
        assert result.success is False
        assert result.error is not None

    def test_directory_traversal_blocked(self, tmp_path: Path) -> None:
        src = self._make_src(tmp_path)
        base_dir = tmp_path / "safe"
        base_dir.mkdir()
        # Destination is outside base_dir
        outside = tmp_path / "outside"
        result = safe_move(src, outside, base_dir=base_dir)
        assert result.success is False
        assert "escapes" in (result.error or "").lower()

    def test_source_content_preserved(self, tmp_path: Path) -> None:
        src = self._make_src(tmp_path, content="Hello, SmartSort!")
        dst_dir = tmp_path / "dst"
        result = safe_move(src, dst_dir)
        assert result.success is True
        assert result.destination is not None
        assert result.destination.read_text() == "Hello, SmartSort!"
