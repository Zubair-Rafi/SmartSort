"""Abstract base for all classification pipeline stages."""
from __future__ import annotations
from abc import ABC, abstractmethod
from pathlib import Path

from app.database.models import ClassificationResult


class BaseClassifier(ABC):
    """
    Interface that every pipeline stage must implement.

    The pipeline calls each stage in sequence.  A stage returns a result
    to signal completion, or None to let the next stage try.
    """

    @abstractmethod
    def classify(self, file_path: Path) -> ClassificationResult | None:
        """
        Attempt to classify file_path.

        Returns ClassificationResult if this stage produced a usable result.
        Returns None if this stage cannot classify the file (pipeline continues).
        """
        ...

    @property
    @abstractmethod
    def stage_name(self) -> str:
        """Human-readable label shown in the UI explanation string."""
        ...
