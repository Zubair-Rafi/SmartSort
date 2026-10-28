"""
Categories panel — Milestone 1 (read-only tree view).

Displays the full category hierarchy loaded from the database.
Edit/create/delete will be added in Milestone 4.
"""
from __future__ import annotations
from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QHBoxLayout, QLabel, QSizePolicy, QTreeWidget,
    QTreeWidgetItem, QVBoxLayout, QWidget,
)

from app.database.db import Database
from app.database.models import Category
from app.utils.logging_setup import get_logger

logger = get_logger(__name__)


class CategoriesView(QWidget):
    """Hierarchical category tree browser."""

    def __init__(self, db: Database, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._db = db
        self._setup_ui()
        self.refresh()

    def _setup_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(32, 28, 32, 28)
        root.setSpacing(0)

        # Header
        header = QHBoxLayout()
        col = QVBoxLayout()
        title = QLabel("Categories")
        title.setObjectName("page_title")
        sub = QLabel("Category hierarchy used for file organization")
        sub.setObjectName("page_subtitle")
        col.addWidget(title)
        col.addWidget(sub)
        header.addLayout(col)
        header.addStretch()
        root.addLayout(header)
        root.addSpacing(12)

        notice = QLabel(
            "ℹ  Full category management (create, edit, delete) arrives in Milestone 4."
        )
        notice.setObjectName("muted_label")
        notice.setWordWrap(True)
        root.addWidget(notice)
        root.addSpacing(16)

        # Tree
        self._tree = QTreeWidget()
        self._tree.setHeaderLabels(["Category", "Destination", "Extensions"])
        self._tree.header().setSectionResizeMode(
            0, self._tree.header().ResizeMode.ResizeToContents
        )
        self._tree.header().setSectionResizeMode(
            1, self._tree.header().ResizeMode.ResizeToContents
        )
        self._tree.header().setSectionResizeMode(
            2, self._tree.header().ResizeMode.Stretch
        )
        self._tree.setAlternatingRowColors(True)
        self._tree.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        root.addWidget(self._tree)

    def refresh(self) -> None:
        self._tree.clear()
        cats = self._db.get_all_categories()
        cat_map: dict[str, Category] = {c.id: c for c in cats}
        node_map: dict[str, QTreeWidgetItem] = {}

        # Build root nodes first, then children in a single pass
        def _make_item(cat: Category) -> QTreeWidgetItem:
            exts = ", ".join(cat.extensions) if cat.extensions else "—"
            item = QTreeWidgetItem([cat.name, cat.destination, exts])
            item.setData(0, Qt.UserRole, cat.id)
            if not cat.enabled:
                for col in range(3):
                    item.setForeground(col, __import__(
                        "PySide6.QtGui", fromlist=["QColor"]
                    ).QColor("#484f58"))
            return item

        for cat in cats:
            node_map[cat.id] = _make_item(cat)

        for cat in cats:
            item = node_map[cat.id]
            if cat.parent_id and cat.parent_id in node_map:
                node_map[cat.parent_id].addChild(item)
            else:
                self._tree.addTopLevelItem(item)

        self._tree.expandAll()
