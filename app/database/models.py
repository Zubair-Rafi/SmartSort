"""
Data model dataclasses for SmartSort.

These are plain Python dataclasses used throughout the application.
They are the canonical in-memory representation of all database entities.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional


class OperationStatus(str, Enum):
    PENDING = "pending"
    SUCCESS = "success"
    FAILED  = "failed"
    SKIPPED = "skipped"
    UNDONE  = "undone"


class ClassificationMethod(str, Enum):
    EXTENSION = "extension"
    FILENAME  = "filename"
    METADATA  = "metadata"
    TFIDF     = "tfidf"
    RULE      = "rule"
    MANUAL    = "manual"
    UNKNOWN   = "unknown"


@dataclass
class Category:
    """A node in the hierarchical category tree."""
    id: str
    name: str
    parent_id: Optional[str]
    description: str
    keywords: list[str]
    extensions: list[str]     # Extensions that auto-map to this category
    destination: str           # Relative path from watch root, e.g. "Books/Fiction"
    enabled: bool = True
    sort_order: int = 0
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)


@dataclass
class WatchedDirectory:
    path: str
    enabled: bool = True
    added_at: datetime = field(default_factory=datetime.now)
    id: int = -1               # Assigned by DB on insert


@dataclass
class Rule:
    id: str
    name: str
    priority: int
    conditions: list[dict]     # Serialised as JSON in SQLite
    action_category_id: str
    description: str = ""
    enabled: bool = True
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)


@dataclass
class FileOperation:
    """A record of one file move attempt, stored in file_history."""
    filename: str
    original_path: str
    watch_path: str
    timestamp: datetime
    status: OperationStatus
    destination_path: Optional[str] = None
    category_id: Optional[str] = None
    category_path: Optional[str] = None
    classification_method: ClassificationMethod = ClassificationMethod.UNKNOWN
    confidence: float = 0.0
    explanation: str = ""
    error_details: Optional[str] = None
    undone_at: Optional[datetime] = None
    id: int = -1               # Assigned by DB on insert


@dataclass
class ClassificationResult:
    """
    The output of the classification pipeline for a single file.

    Fields:
        category_id   - DB category ID, or None if unclassified
        category_path - Human-readable path like "Books/Non-Fiction/Self-Help"
        confidence    - Lexical similarity score 0.0–1.0 (NOT a probability)
        method        - Which pipeline stage produced this result
        explanation   - Human-readable rationale shown in the UI
        alternatives  - Up to 3 runner-up categories with their scores
        should_review - True when the user should confirm before moving
    """
    category_id: Optional[str]
    category_path: Optional[str]
    confidence: float
    method: ClassificationMethod
    explanation: str
    alternatives: list[tuple[str, float]] = field(default_factory=list)
    should_review: bool = False
