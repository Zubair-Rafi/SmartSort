"""
Stage 1 — File type classification by extension.

This is the fastest and cheapest stage.  For binary formats (video, audio,
images, archives, installers, source code) the extension is definitive and
the result is returned with high confidence, skipping all further analysis.

Documents (PDF, DOCX, EPUB, …) are returned with lower confidence so that
later stages can attempt more specific subcategory classification.

OS Concept: Reading file metadata (the extension in the directory entry)
without opening the file — zero I/O cost, pure in-memory lookup.
"""
from __future__ import annotations
from pathlib import Path

from app.core.classification.base import BaseClassifier
from app.database.models import ClassificationMethod, ClassificationResult
from app.utils.logging_setup import get_logger

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# extension → (category_id, confidence)
#
# confidence 1.0 — extension is fully deterministic; no further analysis needed
# confidence 0.6–0.9 — extension gives a top-level hint; later stages refine
# ---------------------------------------------------------------------------
_EXT_MAP: dict[str, tuple[str, float]] = {
    # Images ─────────────────────────────────────────────────────────────────
    ".jpg": ("images", 1.0), ".jpeg": ("images", 1.0), ".png":  ("images", 1.0),
    ".gif": ("images", 1.0), ".bmp":  ("images", 1.0), ".webp": ("images", 1.0),
    ".svg": ("images", 1.0), ".heic": ("images", 1.0), ".heif": ("images", 1.0),
    ".tiff":("images", 1.0), ".tif":  ("images", 1.0), ".raw":  ("images", 1.0),
    ".cr2": ("images", 1.0), ".nef":  ("images", 1.0), ".arw":  ("images", 1.0),
    ".ico": ("images", 1.0),

    # Videos ──────────────────────────────────────────────────────────────────
    ".mp4": ("videos", 1.0), ".mkv":  ("videos", 1.0), ".avi":  ("videos", 1.0),
    ".mov": ("videos", 1.0), ".wmv":  ("videos", 1.0), ".flv":  ("videos", 1.0),
    ".webm":("videos", 1.0), ".m4v":  ("videos", 1.0), ".mpg":  ("videos", 1.0),
    ".mpeg":("videos", 1.0), ".3gp":  ("videos", 1.0),
    ".ts":  ("videos", 0.8),  # also TypeScript — lower confidence

    # Audio ───────────────────────────────────────────────────────────────────
    ".mp3": ("audio", 1.0), ".wav":  ("audio", 1.0), ".flac": ("audio", 1.0),
    ".aac": ("audio", 1.0), ".ogg":  ("audio", 1.0), ".m4a":  ("audio", 1.0),
    ".wma": ("audio", 1.0), ".opus": ("audio", 1.0), ".aiff": ("audio", 1.0),

    # Archives ────────────────────────────────────────────────────────────────
    ".zip": ("archives", 1.0), ".rar": ("archives", 1.0), ".7z":  ("archives", 1.0),
    ".tar": ("archives", 1.0), ".gz":  ("archives", 1.0), ".bz2": ("archives", 1.0),
    ".xz":  ("archives", 1.0), ".zst": ("archives", 1.0), ".lz4": ("archives", 1.0),
    ".iso": ("archives", 1.0), ".img": ("archives", 0.8),

    # Installers ──────────────────────────────────────────────────────────────
    ".exe":     ("installers", 1.0), ".msi":     ("installers", 1.0),
    ".deb":     ("installers", 1.0), ".rpm":     ("installers", 1.0),
    ".pkg":     ("installers", 1.0), ".dmg":     ("installers", 1.0),
    ".appimage":("installers", 1.0), ".snap":    ("installers", 1.0),
    ".flatpak": ("installers", 1.0),

    # Source code ─────────────────────────────────────────────────────────────
    ".py": ("code", 1.0), ".js":   ("code", 1.0), ".jsx":  ("code", 1.0),
    ".ts": ("code", 0.9), ".tsx":  ("code", 1.0), ".cpp":  ("code", 1.0),
    ".cc": ("code", 1.0), ".cxx":  ("code", 1.0), ".c":    ("code", 1.0),
    ".h":  ("code", 1.0), ".hpp":  ("code", 1.0), ".java": ("code", 1.0),
    ".cs": ("code", 1.0), ".go":   ("code", 1.0), ".rs":   ("code", 1.0),
    ".php":("code", 1.0), ".rb":   ("code", 1.0), ".swift":("code", 1.0),
    ".kt": ("code", 1.0), ".html": ("code", 1.0), ".css":  ("code", 1.0),
    ".scss":("code",1.0), ".sass": ("code", 1.0), ".sql":  ("code", 1.0),
    ".sh": ("code", 1.0), ".bash": ("code", 1.0), ".zsh":  ("code", 1.0),
    ".ps1":("code", 1.0), ".bat":  ("code", 1.0), ".r":    ("code", 1.0),
    ".m":  ("code", 0.8), ".scala":("code", 1.0), ".dart": ("code", 1.0),
    ".lua":("code", 1.0), ".pl":   ("code", 1.0), ".toml": ("code", 1.0),
    ".yaml":("code",1.0), ".yml":  ("code", 1.0), ".json": ("code", 0.8),
    ".xml":("code", 0.9),

    # Spreadsheets (treated as document subcategory) ─────────────────────────
    ".xls": ("documents-spreadsheets", 1.0), ".xlsx":("documents-spreadsheets", 1.0),
    ".ods": ("documents-spreadsheets", 1.0), ".csv": ("documents-spreadsheets", 0.9),

    # Presentations ───────────────────────────────────────────────────────────
    ".ppt": ("documents-presentations", 1.0), ".pptx":("documents-presentations", 1.0),
    ".odp": ("documents-presentations", 1.0),

    # Office documents — lower confidence to invite content analysis ──────────
    ".doc": ("documents", 0.8), ".docx":("documents", 0.8),
    ".odt": ("documents", 0.8), ".rtf": ("documents", 0.8),
    ".txt": ("documents", 0.6), ".md":  ("documents", 0.7),
    ".rst": ("documents", 0.7),

    # PDFs — can be anything; invite content analysis ─────────────────────────
    ".pdf": ("documents", 0.5),

    # E-books — invite content analysis for subcategory ───────────────────────
    ".epub": ("books", 0.6), ".mobi": ("books", 0.7),
    ".azw":  ("books", 0.8), ".azw3": ("books", 0.8), ".fb2": ("books", 0.8),
}

# Human-readable path for each built-in category ID
_ID_TO_PATH: dict[str, str] = {
    "images":                    "Images",
    "videos":                    "Videos",
    "audio":                     "Audio",
    "archives":                  "Archives",
    "installers":                "Installers",
    "code":                      "Code",
    "documents":                 "Documents",
    "documents-spreadsheets":    "Documents/Spreadsheets",
    "documents-presentations":   "Documents/Presentations",
    "books":                     "Books",
    "academic":                  "Academic",
    "others":                    "Others",
}


class FileTypeClassifier(BaseClassifier):
    """
    Stage 1 classifier: maps file extensions to categories.

    Always returns a result — files with unknown extensions go to Others.
    """

    @property
    def stage_name(self) -> str:
        return "file_type"

    def classify(self, file_path: Path) -> ClassificationResult:
        ext = file_path.suffix.lower()

        if ext in _EXT_MAP:
            return self._result(ext, *_EXT_MAP[ext])

        # Try compound extension (e.g. .tar.gz)
        if len(file_path.suffixes) >= 2:
            compound = "".join(file_path.suffixes[-2:]).lower()
            if compound in _EXT_MAP:
                return self._result(compound, *_EXT_MAP[compound])

        logger.debug("Unknown extension '%s' → Others  (%s)", ext, file_path.name)
        return ClassificationResult(
            category_id="others",
            category_path="Others",
            confidence=1.0,
            method=ClassificationMethod.EXTENSION,
            explanation=f"Extension '{ext}' is not recognised — placed in Others.",
            should_review=False,
        )

    def _result(
        self, ext: str, cat_id: str, confidence: float
    ) -> ClassificationResult:
        cat_path = _ID_TO_PATH.get(cat_id, cat_id.replace("-", "/").title())
        return ClassificationResult(
            category_id=cat_id,
            category_path=cat_path,
            confidence=confidence,
            method=ClassificationMethod.EXTENSION,
            explanation=f"Extension '{ext}' maps to '{cat_path}'.",
            should_review=(confidence < 0.72),
        )
