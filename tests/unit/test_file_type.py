"""
Unit tests for Stage 1 file type classifier.

These tests verify that extensions are correctly mapped to categories
and that edge cases (unknown extensions, compound extensions, temp files)
are handled properly.

All tests operate purely in memory — no real files are accessed.
"""
from __future__ import annotations
import pytest
from pathlib import Path

from app.core.classification.file_type import FileTypeClassifier
from app.database.models import ClassificationMethod


@pytest.fixture
def classifier() -> FileTypeClassifier:
    return FileTypeClassifier()


class TestHighConfidenceExtensions:
    """Extensions that should map with confidence=1.0 (no further analysis needed)."""

    @pytest.mark.parametrize("filename,expected_cat_path", [
        ("movie.mp4",       "Videos"),
        ("clip.mkv",        "Videos"),
        ("photo.jpg",       "Images"),
        ("picture.PNG",     "Images"),   # uppercase extension
        ("track.mp3",       "Audio"),
        ("song.flac",       "Audio"),
        ("setup.exe",       "Installers"),
        ("package.deb",     "Installers"),
        ("archive.zip",     "Archives"),
        ("backup.tar.gz",   "Archives"),  # compound extension
        ("script.py",       "Code"),
        ("main.cpp",        "Code"),
        ("sheet.xlsx",      "Documents/Spreadsheets"),
        ("slides.pptx",     "Documents/Presentations"),
    ])
    def test_extension_maps_correctly(
        self,
        classifier: FileTypeClassifier,
        filename: str,
        expected_cat_path: str,
        tmp_path: Path,
    ) -> None:
        # Create a real (empty) path object — no file system access needed
        fake_path = tmp_path / filename
        result = classifier.classify(fake_path)

        assert result is not None
        assert result.category_path == expected_cat_path, (
            f"{filename}: expected '{expected_cat_path}', got '{result.category_path}'"
        )
        assert result.method == ClassificationMethod.EXTENSION
        assert result.confidence == 1.0

    def test_unknown_extension_goes_to_others(
        self, classifier: FileTypeClassifier, tmp_path: Path
    ) -> None:
        result = classifier.classify(tmp_path / "mystery.xyz123")
        assert result.category_path == "Others"
        assert result.confidence == 1.0

    def test_no_extension_goes_to_others(
        self, classifier: FileTypeClassifier, tmp_path: Path
    ) -> None:
        result = classifier.classify(tmp_path / "Makefile")
        assert result.category_path == "Others"


class TestLowConfidenceExtensions:
    """Extensions that invite further content analysis (confidence < 1.0)."""

    @pytest.mark.parametrize("filename", [
        "document.pdf",
        "thesis.docx",
        "notes.txt",
        "book.epub",
    ])
    def test_document_extensions_have_low_confidence(
        self, classifier: FileTypeClassifier, filename: str, tmp_path: Path
    ) -> None:
        result = classifier.classify(tmp_path / filename)
        assert result.confidence < 1.0, (
            f"{filename} should have confidence < 1.0, got {result.confidence}"
        )

    def test_pdf_confidence_is_half(
        self, classifier: FileTypeClassifier, tmp_path: Path
    ) -> None:
        result = classifier.classify(tmp_path / "report.pdf")
        assert result.confidence == pytest.approx(0.5)

    def test_epub_needs_review(
        self, classifier: FileTypeClassifier, tmp_path: Path
    ) -> None:
        result = classifier.classify(tmp_path / "book.epub")
        assert result.should_review is True   # confidence < auto_confirm_threshold


class TestCompoundExtensions:
    """Compound extensions like .tar.gz should be recognised."""

    def test_tar_gz(self, classifier: FileTypeClassifier, tmp_path: Path) -> None:
        result = classifier.classify(tmp_path / "data.tar.gz")
        assert result.category_path == "Archives"

    def test_tar_bz2(self, classifier: FileTypeClassifier, tmp_path: Path) -> None:
        result = classifier.classify(tmp_path / "data.tar.bz2")
        assert result.category_path == "Archives"


class TestResultStructure:
    """Every result must have the required fields populated."""

    def test_result_fields_populated(
        self, classifier: FileTypeClassifier, tmp_path: Path
    ) -> None:
        result = classifier.classify(tmp_path / "image.png")
        assert result.category_id is not None
        assert result.category_path is not None
        assert 0.0 <= result.confidence <= 1.0
        assert result.method == ClassificationMethod.EXTENSION
        assert isinstance(result.explanation, str)
        assert len(result.explanation) > 0
