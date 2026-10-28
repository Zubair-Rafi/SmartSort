"""
Dashboard panel — Milestone 1 implementation.

Shows:
  - Four stat cards (total, today, pending review, errors)
  - "Organize Now" button that runs organize_existing_files() in a QThread
  - Live progress bar during the organize run
  - Recent activity list (last 20 operations)

OS Concept: QThread wraps the organizer worker, preventing the
classification/move pipeline from blocking the GUI event loop.
Qt signals carry progress updates across the thread boundary safely.
"""
from __future__ import annotations
import threading
from datetime import date
from typing import Optional

from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QMessageBox,
    QProgressBar, QPushButton, QSizePolicy,
    QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget,
)

from app.database.models import OperationStatus
from app.services.organizer_service import OrganizeProgress, OrganizerService
from app.utils.logging_setup import get_logger

logger = get_logger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# Worker thread
# ─────────────────────────────────────────────────────────────────────────────

class _OrganizeWorker(QThread):
    """
    Runs organize_existing_files() in a background thread.
    Emits progress and completed signals that are automatically
    marshalled to the main thread by Qt's signal-slot mechanism.
    """
    progress_update = Signal(OrganizeProgress)
    completed       = Signal(int, int)  # success_count, total_count
    error_occurred  = Signal(str)

    def __init__(self, service: OrganizerService, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._service = service
        self._cancel = threading.Event()

    def run(self) -> None:
        watch_dirs = self._service.get_watched_directories()
        if not watch_dirs:
            self.error_occurred.emit(
                "No watched directories configured.\n"
                "Add a directory in the Settings panel first."
            )
            self.completed.emit(0, 0)
            return

        total_success = total_count = 0
        for watch_dir in watch_dirs:
            ok, cnt = self._service.organize_existing_files(
                watch_root=watch_dir,
                progress_callback=self.progress_update.emit,
                cancel_event=self._cancel,
            )
            total_success += ok
            total_count += cnt

        self.completed.emit(total_success, total_count)

    def cancel(self) -> None:
        self._cancel.set()


# ─────────────────────────────────────────────────────────────────────────────
# Dashboard widget
# ─────────────────────────────────────────────────────────────────────────────

class DashboardView(QWidget):
    """Main dashboard panel."""

    def __init__(self, service: OrganizerService, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._service = service
        self._worker: Optional[_OrganizeWorker] = None
        self._setup_ui()
        self.refresh_stats()

    # ── UI construction ───────────────────────────────────────────────────────

    def _setup_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(32, 28, 32, 28)
        root.setSpacing(0)

        # Header
        header = QHBoxLayout()
        title_col = QVBoxLayout()
        title = QLabel("Dashboard")
        title.setObjectName("page_title")
        subtitle = QLabel("Overview of your file organization activity")
        subtitle.setObjectName("page_subtitle")
        title_col.addWidget(title)
        title_col.addWidget(subtitle)
        header.addLayout(title_col)
        header.addStretch()

        self._organize_btn = QPushButton("⚡  Organize Now")
        self._organize_btn.setObjectName("primary_btn")
        self._organize_btn.setFixedHeight(36)
        self._organize_btn.setCursor(Qt.PointingHandCursor)
        self._organize_btn.clicked.connect(self._on_organize_clicked)
        header.addWidget(self._organize_btn)

        root.addLayout(header)
        root.addSpacing(24)

        # Stat cards
        cards_row = QHBoxLayout()
        cards_row.setSpacing(16)
        self._card_total   = self._make_stat_card("0", "Files Organized")
        self._card_today   = self._make_stat_card("0", "Today")
        self._card_review  = self._make_stat_card("0", "Awaiting Review")
        self._card_errors  = self._make_stat_card("0", "Errors")
        for card in (self._card_total, self._card_today, self._card_review, self._card_errors):
            cards_row.addWidget(card)
        root.addLayout(cards_row)
        root.addSpacing(28)

        # Progress area (hidden while idle)
        self._progress_frame = QFrame()
        self._progress_frame.setObjectName("stat_card")
        prog_layout = QVBoxLayout(self._progress_frame)
        prog_layout.setContentsMargins(16, 12, 16, 12)
        prog_layout.setSpacing(8)

        prog_header = QHBoxLayout()
        self._prog_label = QLabel("Organizing files…")
        self._prog_label.setObjectName("muted_label")
        self._cancel_btn = QPushButton("Cancel")
        self._cancel_btn.setObjectName("secondary_btn")
        self._cancel_btn.setFixedHeight(28)
        self._cancel_btn.clicked.connect(self._on_cancel_clicked)
        prog_header.addWidget(self._prog_label)
        prog_header.addStretch()
        prog_header.addWidget(self._cancel_btn)
        prog_layout.addLayout(prog_header)

        self._progress_bar = QProgressBar()
        self._progress_bar.setTextVisible(False)
        self._progress_bar.setFixedHeight(6)
        prog_layout.addWidget(self._progress_bar)

        self._progress_frame.setVisible(False)
        root.addWidget(self._progress_frame)

        # Recent activity header
        act_header = QHBoxLayout()
        section_lbl = QLabel("RECENT ACTIVITY")
        section_lbl.setObjectName("section_header")
        act_header.addWidget(section_lbl)
        act_header.addStretch()
        self._refresh_btn = QPushButton("Refresh")
        self._refresh_btn.setObjectName("secondary_btn")
        self._refresh_btn.setFixedHeight(28)
        self._refresh_btn.clicked.connect(self.refresh_stats)
        act_header.addWidget(self._refresh_btn)
        root.addLayout(act_header)
        root.addSpacing(10)

        # Activity table
        self._activity_table = QTableWidget()
        self._activity_table.setColumnCount(4)
        self._activity_table.setHorizontalHeaderLabels(
            ["File", "Category", "Status", "Time"]
        )
        self._activity_table.horizontalHeader().setStretchLastSection(False)
        self._activity_table.horizontalHeader().setSectionResizeMode(
            0, self._activity_table.horizontalHeader().ResizeMode.Stretch
        )
        self._activity_table.horizontalHeader().setSectionResizeMode(
            1, self._activity_table.horizontalHeader().ResizeMode.ResizeToContents
        )
        self._activity_table.horizontalHeader().setSectionResizeMode(
            2, self._activity_table.horizontalHeader().ResizeMode.ResizeToContents
        )
        self._activity_table.horizontalHeader().setSectionResizeMode(
            3, self._activity_table.horizontalHeader().ResizeMode.ResizeToContents
        )
        self._activity_table.setAlternatingRowColors(True)
        self._activity_table.setSelectionBehavior(
            QTableWidget.SelectionBehavior.SelectRows
        )
        self._activity_table.setEditTriggers(
            QTableWidget.EditTrigger.NoEditTriggers
        )
        self._activity_table.verticalHeader().setVisible(False)
        self._activity_table.setSizePolicy(
            QSizePolicy.Expanding, QSizePolicy.Expanding
        )
        root.addWidget(self._activity_table)

    @staticmethod
    def _make_stat_card(value: str, label: str) -> QFrame:
        card = QFrame()
        card.setObjectName("stat_card")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(4)

        val_lbl = QLabel(value)
        val_lbl.setObjectName("stat_value")
        val_lbl.setProperty("_value_label", True)

        lbl_lbl = QLabel(label)
        lbl_lbl.setObjectName("stat_label")

        layout.addWidget(val_lbl)
        layout.addWidget(lbl_lbl)
        return card

    def _get_value_label(self, card: QFrame) -> Optional[QLabel]:
        for child in card.findChildren(QLabel):
            if child.property("_value_label"):
                return child
        return None

    # ── Data refresh ──────────────────────────────────────────────────────────

    def refresh_stats(self) -> None:
        stats = self._service.get_history_stats()
        total   = stats.get("success", 0)
        errors  = stats.get("failed",  0)
        pending = stats.get("pending", 0)

        # Count today's successes
        today_count = 0
        for op in self._service.get_recent_history(500):
            if (
                op.status == OperationStatus.SUCCESS
                and op.timestamp.date() == date.today()
            ):
                today_count += 1

        def _set(card: QFrame, v: str) -> None:
            lbl = self._get_value_label(card)
            if lbl:
                lbl.setText(v)

        _set(self._card_total,  str(total))
        _set(self._card_today,  str(today_count))
        _set(self._card_review, str(pending))
        _set(self._card_errors, str(errors))

        self._populate_activity_table()

    def _populate_activity_table(self) -> None:
        recent = self._service.get_recent_history(20)
        self._activity_table.setRowCount(len(recent))

        STATUS_COLOURS = {
            "success": "#3fb950",
            "failed":  "#f85149",
            "skipped": "#d29922",
            "undone":  "#8b949e",
            "pending": "#8b949e",
        }

        for row, op in enumerate(recent):
            items = [
                op.filename,
                op.category_path or "—",
                op.status.value.capitalize(),
                op.timestamp.strftime("%H:%M  %d %b"),
            ]
            for col, text in enumerate(items):
                item = QTableWidgetItem(text)
                item.setFlags(item.flags() & ~Qt.ItemIsEditable)
                if col == 2:  # Status column — coloured
                    colour = STATUS_COLOURS.get(op.status.value, "#8b949e")
                    item.setForeground(
                        __import__("PySide6.QtGui", fromlist=["QColor"]).QColor(colour)
                    )
                self._activity_table.setItem(row, col, item)

    # ── Organize workflow ─────────────────────────────────────────────────────

    def _on_organize_clicked(self) -> None:
        watch_dirs = self._service.get_watched_directories()
        if not watch_dirs:
            QMessageBox.warning(
                self, "No Watched Directories",
                "No directories are being monitored.\n\n"
                "Go to Settings → Watched Directories and add a folder.",
            )
            return

        dir_list = "\n".join(f"  • {d}" for d in watch_dirs)
        reply = QMessageBox.question(
            self, "Organize Existing Files",
            f"SmartSort will organize files in:\n\n{dir_list}\n\n"
            "Files already in subfolders will not be touched.\n"
            "Continue?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if reply != QMessageBox.Yes:
            return

        self._start_worker()

    def _start_worker(self) -> None:
        self._organize_btn.setEnabled(False)
        self._progress_frame.setVisible(True)
        self._progress_bar.setValue(0)
        self._prog_label.setText("Starting…")

        self._worker = _OrganizeWorker(self._service, self)
        self._worker.progress_update.connect(self._on_progress)
        self._worker.completed.connect(self._on_completed)
        self._worker.error_occurred.connect(self._on_worker_error)
        self._worker.start()

    def _on_progress(self, prog: OrganizeProgress) -> None:
        pct = int(prog.files_processed / max(prog.files_total, 1) * 100)
        self._progress_bar.setValue(pct)
        status = "✓" if prog.success else "✗"
        self._prog_label.setText(
            f"{status}  {prog.filename}  "
            f"({prog.files_processed}/{prog.files_total})"
        )

    def _on_completed(self, success: int, total: int) -> None:
        self._organize_btn.setEnabled(True)
        self._progress_frame.setVisible(False)
        self._progress_bar.setValue(100)
        self.refresh_stats()

        if total == 0:
            QMessageBox.information(
                self, "Nothing to Organize",
                "No files were found in the watched directories\n"
                "(or all files are in subfolders already).",
            )
        else:
            QMessageBox.information(
                self, "Done",
                f"Organized {success} of {total} file(s) successfully.",
            )

    def _on_worker_error(self, msg: str) -> None:
        self._organize_btn.setEnabled(True)
        self._progress_frame.setVisible(False)
        QMessageBox.warning(self, "Organization Error", msg)

    def _on_cancel_clicked(self) -> None:
        if self._worker and self._worker.isRunning():
            self._worker.cancel()
            self._prog_label.setText("Cancelling…")
            self._cancel_btn.setEnabled(False)
