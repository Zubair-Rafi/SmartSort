"""
Review Queue panel — shows files awaiting manual classification.

In Milestone 1 this panel lists history entries with status=pending or
category_path=None (low-confidence classifications routed to the Review folder).
Full interactive classification arrives in Milestone 3.
"""
from __future__ import annotations
from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QHBoxLayout, QHeaderView, QLabel, QSizePolicy,
    QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget,
)

from app.database.models import OperationStatus
from app.services.organizer_service import OrganizerService


class ReviewQueueView(QWidget):
    """Panel listing files that need human classification."""

    def __init__(self, service: OrganizerService, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._service = service
        self._setup_ui()
        self.refresh()

    def _setup_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(32, 28, 32, 28)
        root.setSpacing(0)

        header = QHBoxLayout()
        col = QVBoxLayout()
        title = QLabel("Review Queue")
        title.setObjectName("page_title")
        sub = QLabel("Files with uncertain classifications that need your attention")
        sub.setObjectName("page_subtitle")
        col.addWidget(title)
        col.addWidget(sub)
        header.addLayout(col)
        header.addStretch()
        root.addLayout(header)
        root.addSpacing(12)

        notice = QLabel(
            "ℹ  Interactive classification (accept / change category) arrives in Milestone 3.\n"
            "Files shown here have been placed in the 'Review' subfolder of your watched directory."
        )
        notice.setObjectName("muted_label")
        notice.setWordWrap(True)
        root.addWidget(notice)
        root.addSpacing(16)

        self._count_label = QLabel("0 files awaiting review")
        self._count_label.setObjectName("section_header")
        root.addWidget(self._count_label)
        root.addSpacing(10)

        self._table = QTableWidget()
        self._table.setColumnCount(4)
        self._table.setHorizontalHeaderLabels(["File", "Explanation", "Confidence", "Time"])
        hdr = self._table.horizontalHeader()
        hdr.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        hdr.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        hdr.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        hdr.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self._table.verticalHeader().setVisible(False)
        self._table.setAlternatingRowColors(True)
        self._table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._table.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        root.addWidget(self._table)

    def refresh(self) -> None:
        all_ops = self._service.get_recent_history(500)
        # Pending ops or ops where no category was assigned
        review_ops = [
            op for op in all_ops
            if op.status == OperationStatus.PENDING
            or (op.status == OperationStatus.SUCCESS and op.category_path is None)
        ]
        self._count_label.setText(f"{len(review_ops)} file(s) awaiting review")
        self._table.setRowCount(len(review_ops))

        for row, op in enumerate(review_ops):
            def _item(t: str) -> QTableWidgetItem:
                i = QTableWidgetItem(t)
                i.setFlags(i.flags() & ~Qt.ItemIsEditable)
                return i

            self._table.setItem(row, 0, _item(op.filename))
            self._table.setItem(row, 1, _item(op.explanation or "—"))
            conf_str = f"{op.confidence:.0%}" if op.confidence > 0 else "—"
            self._table.setItem(row, 2, _item(conf_str))
            self._table.setItem(row, 3, _item(op.timestamp.strftime("%d %b %Y  %H:%M")))
