"""
Settings panel — configures watched directories and all preferences.

Milestone 1 features:
  - Add / remove watched directories (persisted to SQLite)
  - "Organize Existing Files" button shortcut
  - Classification threshold sliders
  - Worker thread count
  - Temp extension list (read-only for M1)

Full settings parity (auto-organize toggle, notification options, etc.)
will be completed in Milestone 5.
"""
from __future__ import annotations
from pathlib import Path
from typing import Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QDialog, QDialogButtonBox, QDoubleSpinBox, QFileDialog,
    QFrame, QHBoxLayout, QLabel, QListWidget, QListWidgetItem,
    QMessageBox, QPushButton, QScrollArea, QSizePolicy,
    QSpinBox, QVBoxLayout, QWidget,
)

from app.database.db import Database
from app.services.category_loader import seed_categories
from app.utils.config import AppConfig
from app.utils.logging_setup import get_logger

logger = get_logger(__name__)


class SettingsView(QWidget):
    """Settings panel."""

    watched_dirs_changed = Signal()  # Dashboard/watcher should reload

    def __init__(self, db: Database, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._db = db
        self._cfg = AppConfig.instance()
        self._setup_ui()
        self._load_values()

    # ── UI ────────────────────────────────────────────────────────────────────

    def _setup_ui(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(32, 28, 32, 28)
        outer.setSpacing(0)

        # Header
        title = QLabel("Settings")
        title.setObjectName("page_title")
        sub = QLabel("Configure SmartSort's behaviour and watched directories")
        sub.setObjectName("page_subtitle")
        outer.addWidget(title)
        outer.addWidget(sub)
        outer.addSpacing(24)

        # Scroll area for all settings
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setSpacing(24)
        layout.setContentsMargins(0, 0, 0, 0)

        # ── Section: Watched Directories ──────────────────────────────────────
        layout.addWidget(self._section("WATCHED DIRECTORIES"))

        dir_card = self._card()
        dir_inner = QVBoxLayout(dir_card)
        dir_inner.setSpacing(10)

        dir_hint = QLabel(
            "SmartSort monitors these directories for new files.\n"
            "Organized files are placed in subfolders inside each directory."
        )
        dir_hint.setObjectName("muted_label")
        dir_hint.setWordWrap(True)
        dir_inner.addWidget(dir_hint)

        self._dir_list = QListWidget()
        self._dir_list.setFixedHeight(140)
        self._dir_list.setAlternatingRowColors(True)
        dir_inner.addWidget(self._dir_list)

        dir_btns = QHBoxLayout()
        add_btn = QPushButton("＋  Add Directory")
        add_btn.setObjectName("primary_btn")
        add_btn.setFixedHeight(32)
        add_btn.clicked.connect(self._add_directory)

        remove_btn = QPushButton("Remove Selected")
        remove_btn.setObjectName("danger_btn")
        remove_btn.setFixedHeight(32)
        remove_btn.clicked.connect(self._remove_directory)

        dir_btns.addWidget(add_btn)
        dir_btns.addWidget(remove_btn)
        dir_btns.addStretch()
        dir_inner.addLayout(dir_btns)
        layout.addWidget(dir_card)

        # ── Section: Classification ───────────────────────────────────────────
        layout.addWidget(self._section("CLASSIFICATION"))

        cls_card = self._card()
        cls_inner = QVBoxLayout(cls_card)
        cls_inner.setSpacing(12)

        cls_note = QLabel(
            "⚠  These thresholds are empirically tuned starting points.\n"
            "They are lexical similarity scores — not calibrated probabilities."
        )
        cls_note.setObjectName("warning_label")
        cls_note.setWordWrap(True)
        cls_inner.addWidget(cls_note)

        cls_inner.addLayout(self._double_spin_row(
            "Auto-confirm threshold",
            "auto_confirm_threshold", 0.0, 1.0, 0.01,
            "Files scoring above this are moved automatically.",
        ))
        cls_inner.addLayout(self._double_spin_row(
            "Suggest threshold",
            "suggest_threshold", 0.0, 1.0, 0.01,
            "Files scoring above this show a suggestion in the Review Queue.",
        ))
        layout.addWidget(cls_card)

        # ── Section: Performance ──────────────────────────────────────────────
        layout.addWidget(self._section("PERFORMANCE"))

        perf_card = self._card()
        perf_inner = QVBoxLayout(perf_card)
        perf_inner.setSpacing(12)
        perf_inner.addLayout(self._int_spin_row(
            "Concurrent workers",
            "max_workers", 1, 8,
            "Number of files classified simultaneously. Increase with caution.",
        ))
        perf_inner.addLayout(self._double_spin_row(
            "Min stable duration (s)",
            "min_stable_duration", 1.0, 60.0, 0.5,
            "How long a file must remain unchanged before it is processed.",
        ))
        layout.addWidget(perf_card)

        # ── Section: Data ─────────────────────────────────────────────────────
        layout.addWidget(self._section("DATA"))

        data_card = self._card()
        data_inner = QVBoxLayout(data_card)
        data_inner.setSpacing(10)

        reseed_btn = QPushButton("Re-seed Default Categories")
        reseed_btn.setObjectName("secondary_btn")
        reseed_btn.setFixedHeight(32)
        reseed_btn.setToolTip(
            "Re-load the built-in category tree from categories_default.json.\n"
            "Existing custom categories are NOT removed."
        )
        reseed_btn.clicked.connect(self._reseed_categories)
        data_inner.addWidget(reseed_btn)
        layout.addWidget(data_card)

        layout.addStretch()
        scroll.setWidget(content)
        outer.addWidget(scroll)

    # ── Helpers ───────────────────────────────────────────────────────────────

    @staticmethod
    def _section(text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setObjectName("section_header")
        return lbl

    @staticmethod
    def _card() -> QFrame:
        card = QFrame()
        card.setObjectName("stat_card")
        return card

    def _double_spin_row(
        self, label: str, cfg_key: str,
        min_val: float, max_val: float, step: float,
        tooltip: str = "",
    ) -> QHBoxLayout:
        row = QHBoxLayout()
        lbl = QLabel(label)
        lbl.setToolTip(tooltip)
        spin = QDoubleSpinBox()
        spin.setRange(min_val, max_val)
        spin.setSingleStep(step)
        spin.setDecimals(2)
        spin.setFixedWidth(90)
        spin.setValue(self._cfg.get(cfg_key, 0.0))
        spin.setToolTip(tooltip)
        spin.valueChanged.connect(lambda v, k=cfg_key: self._cfg.set(k, v))
        row.addWidget(lbl)
        row.addStretch()
        row.addWidget(spin)
        return row

    def _int_spin_row(
        self, label: str, cfg_key: str,
        min_val: int, max_val: int,
        tooltip: str = "",
    ) -> QHBoxLayout:
        row = QHBoxLayout()
        lbl = QLabel(label)
        lbl.setToolTip(tooltip)
        spin = QSpinBox()
        spin.setRange(min_val, max_val)
        spin.setFixedWidth(90)
        spin.setValue(int(self._cfg.get(cfg_key, min_val)))
        spin.setToolTip(tooltip)
        spin.valueChanged.connect(lambda v, k=cfg_key: self._cfg.set(k, v))
        row.addWidget(lbl)
        row.addStretch()
        row.addWidget(spin)
        return row

    # ── Populate from DB ──────────────────────────────────────────────────────

    def _load_values(self) -> None:
        self._dir_list.clear()
        for wd in self._db.get_all_watched_directories():
            item = QListWidgetItem(wd.path)
            item.setData(Qt.UserRole, wd.path)
            self._dir_list.addItem(item)

    # ── Directory management ──────────────────────────────────────────────────

    def _add_directory(self) -> None:
        path_str = QFileDialog.getExistingDirectory(
            self, "Select Directory to Watch",
            str(Path.home()),
        )
        if not path_str:
            return
        path = Path(path_str).resolve()

        if not path.exists():
            QMessageBox.warning(self, "Invalid Directory", f"Directory does not exist:\n{path}")
            return

        self._db.add_watched_directory(str(path))
        self._load_values()
        self.watched_dirs_changed.emit()
        logger.info("Added watched directory: %s", path)

    def _remove_directory(self) -> None:
        selected = self._dir_list.selectedItems()
        if not selected:
            return
        path_str = selected[0].data(Qt.UserRole)
        reply = QMessageBox.question(
            self, "Remove Directory",
            f"Stop watching:\n{path_str}\n\nFiles already organized will not be moved back.",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No,
        )
        if reply != QMessageBox.Yes:
            return
        self._db.remove_watched_directory(path_str)
        self._load_values()
        self.watched_dirs_changed.emit()

    def _reseed_categories(self) -> None:
        n = seed_categories(self._db)
        QMessageBox.information(
            self, "Categories Re-seeded",
            f"Loaded {n} categories from categories_default.json.",
        )
