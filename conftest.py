"""
Shared pytest fixtures for SmartSort tests.

All fixtures operate on temporary directories so no real user data
is ever accessed or modified during testing.
"""
from __future__ import annotations
import pytest
from pathlib import Path

from app.database.db import Database
from app.services.organizer_service import OrganizerService
from app.utils.config import AppConfig


# ── Directory fixtures ────────────────────────────────────────────────────────

@pytest.fixture
def tmp_downloads(tmp_path: Path) -> Path:
    """A temporary directory simulating a Downloads folder."""
    dl = tmp_path / "Downloads"
    dl.mkdir()
    return dl


@pytest.fixture
def tmp_db(tmp_path: Path) -> Database:
    """An in-memory-equivalent SQLite DB in a temp directory."""
    db = Database(tmp_path / "test.db")
    return db


@pytest.fixture
def tmp_service(tmp_db: Database, tmp_path: Path) -> OrganizerService:
    """OrganizerService wired to the temp DB."""
    return OrganizerService(tmp_db)


# ── Sample file factories ─────────────────────────────────────────────────────

@pytest.fixture
def make_file(tmp_downloads: Path):
    """
    Factory that creates a named file with optional content inside tmp_downloads.

    Usage:
        pdf = make_file("report.pdf", b"%PDF-1.4 ...")
        mp4 = make_file("video.mp4")   # empty file, extension sufficient
    """
    def _factory(name: str, content: bytes = b"") -> Path:
        p = tmp_downloads / name
        p.write_bytes(content)
        return p
    return _factory
