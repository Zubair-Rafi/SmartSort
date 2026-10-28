"""
Activity History panel.

Shows all recorded file operations with:
  - Filename, original path, destination, category, status, confidence, time
  - Undo button for each successful operation
  - Colour-coded status column
"""
from __future__ import annotations
from typing import Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QAbstractItemView, QFrame, QHBoxLayout, QHeaderView,
    QLabel, QMessageBox, QPushButton, QSizePolicy,
    QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget,
)

from app.database.models import FileOperation, OperationStatus
from app.services.organizer_service import OrganizerService
from app.utils.logging_setup import get_logger

logger = get_logger(__name__)

_STATUS_COLOUR: dict[str, str] = {
    "success": "#3fb950",
    "failed":  "#f85149",
    "skipped": "#d29922",
    "undone":  "#8b949e",
    "pending": "#8b949e",
}

_COLUMNS = ["File", "Category", "Status", "Confidence", "Time", "Action"]
_COL_FILE   = 0
_COL_CAT    = 1
_COL_STATUS = 2
_COL_CONF   = 3
_COL_TIME   = 4
_COL_ACTION = 5


class HistoryView(QWidget):
    """Activity history panel with inline undo support."""

    undo_performed = Signal()   # Tells the dashboard to refresh stats

    def __init__(self, service: OrganizerService, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._service = service
        self._ops: list[FileOperation] = []
        self._setup_ui()
        self.refresh()

    # ── UI construction ───────────────────────────────────────────────────────

    def _setup_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(32, 28, 32, 28)
        root.setSpacing(0)

        # Header
        header = QHBoxLayout()
        title_col = QVBoxLayout()
        title = QLabel("Activity History")
        title.setObjectName("page_title")
        sub = QLabel("All file operations recorded by SmartSort")
        sub.setObjectName("page_subtitle")
        title_col.addWidget(title)
        title_col.addWidget(sub)
        header.addLayout(title_col)
        header.addStretch()

        refresh_btn = QPushButton("Refresh")
        refresh_btn.setObjectName("secondary_btn")
        refresh_btn.setFixedHeight(30)
        refresh_btn.clicked.connect(self.refresh)
        header.addWidget(refresh_btn)
        root.addLayout(header)
        root.addSpacing(20)

        # Summary row
        self._summary_label = QLabel("")
        self._summary_label.setObjectName("muted_label")
        root.addWidget(self._summary_label)
        root.addSpacing(12)

        # Table
        self._table = QTableWidget()
        self._table.setColumnCount(len(_COLUMNS))
        self._table.setHorizontalHeaderLabels(_COLUMNS)
        hdr = self._table.horizontalHeader()
        hdr.setSectionResizeMode(_COL_FILE,   QHeaderView.ResizeMode.Stretch)
        hdr.setSectionResizeMode(_COL_CAT,    QHeaderView.ResizeMode.ResizeToContents)
        hdr.setSectionResizeMode(_COL_STATUS, QHeaderView.ResizeMode.ResizeToContents)
        hdr.setSectionResizeMode(_COL_CONF,   QHeaderView.ResizeMode.ResizeToContents)
        hdr.setSectionResizeMode(_COL_TIME,   QHeaderView.ResizeMode.ResizeToContents)
        hdr.setSectionResizeMode(_COL_ACTION, QHeaderView.ResizeMode.ResizeToContents)
        self._table.verticalHeader().setVisible(False)
        self._table.setAlternatingRowColors(True)
        self._table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._table.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        root.addWidget(self._table)

    # ── Data ──────────────────────────────────────────────────────────────────

    def refresh(self) -> None:
        self._ops = self._service.get_recent_history(200)
        self._rebuild_table()

    def _rebuild_table(self) -> None:
        self._table.setRowCount(len(self._ops))

        stats = self._service.get_history_stats()
        total   = sum(stats.values())
        success = stats.get("success", 0)
        failed  = stats.get("failed", 0)
        self._summary_label.setText(
            f"{total} total operations  ·  {success} succeeded  ·  {failed} failed"
        )

        for row, op in enumerate(self._ops):
            self._set_row(row, op)

        self._table.setRowCount(len(self._ops))

    def _set_row(self, row: int, op: FileOperation) -> None:
        def _item(text: str) -> QTableWidgetItem:
            item = QTableWidgetItem(text)
            item.setFlags(item.flags() & ~Qt.ItemIsEditable)
            return item

        colour = QColor(_STATUS_COLOUR.get(op.status.value, "#8b949e"))

        # File
        file_item = _item(op.filename)
        file_item.setToolTip(op.original_path)
        self._table.setItem(row, _COL_FILE, file_item)

        # Category
        self._table.setItem(row, _COL_CAT, _item(op.category_path or "—"))

        # Status
        status_item = _item(op.status.value.capitalize())
        status_item.setForeground(colour)
        if op.error_details:
            status_item.setToolTip(op.error_details)
        self._table.setItem(row, _COL_STATUS, status_item)

        # Confidence
        conf_text = f"{op.confidence:.0%}" if op.confidence > 0 else "—"
        self._table.setItem(row, _COL_CONF, _item(conf_text))

        # Time
        self._table.setItem(
            row, _COL_TIME,
            _item(op.timestamp.strftime("%d %b %Y  %H:%M"))
        )

        # Undo button (only for success operations that haven't been undone)
        if op.status == OperationStatus.SUCCESS and op.destination_path:
            undo_btn = QPushButton("Undo")
            undo_btn.setObjectName("secondary_btn")
            undo_btn.setFixedHeight(26)
            undo_btn.setCursor(Qt.PointingHandCursor)
            op_id = op.id
            undo_btn.clicked.connect(lambda checked=False, oid=op_id: self._undo(oid))
            self._table.setCellWidget(row, _COL_ACTION, undo_btn)
        else:
            self._table.setItem(row, _COL_ACTION, _item(""))

    # ── Undo ──────────────────────────────────────────────────────────────────

    def _undo(self, op_id: int) -> None:
        op = next((o for o in self._ops if o.id == op_id), None)
        if op is None:
            return

        reply = QMessageBox.question(
            self, "Confirm Undo",
            f"Restore '{op.filename}' to its original location?\n\n"
            f"From: {op.destination_path}\n"
            f"To:   {op.original_path}",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No,
        )
        if reply != QMessageBox.Yes:
            return

        success, msg = self._service.undo(op_id)
        if success:
            QMessageBox.information(self, "Undo Successful", msg)
            self.undo_performed.emit()
        else:
            QMessageBox.warning(self, "Undo Failed", msg)

        self.refresh()
