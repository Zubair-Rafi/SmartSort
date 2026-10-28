"""
Rules panel — Milestone 1 placeholder.

Displays a notice that custom rule management arrives in Milestone 4.
The rules engine architecture is already wired up in the backend;
this panel will expose it to the user in a future milestone.
"""
from __future__ import annotations
from typing import Optional

from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget


class RulesView(QWidget):
    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        root = QVBoxLayout(self)
        root.setContentsMargins(32, 28, 32, 28)
        root.setSpacing(12)

        title = QLabel("Rules")
        title.setObjectName("page_title")
        root.addWidget(title)

        sub = QLabel("Custom file organization rules with priority ordering")
        sub.setObjectName("page_subtitle")
        root.addWidget(sub)

        root.addSpacing(24)

        notice = QLabel(
            "🚧  Rule management UI (create, edit, prioritize, enable/disable rules)\n"
            "is scheduled for Milestone 4.\n\n"
            "The rule engine is already implemented in the backend — this panel\n"
            "will expose it to the user once the core pipeline is stable."
        )
        notice.setObjectName("muted_label")
        notice.setWordWrap(True)
        root.addWidget(notice)

        root.addStretch()
