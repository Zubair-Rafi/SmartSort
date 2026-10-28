"""
Main application window.

Layout:
  ┌──────────┬──────────────────────────────────┐
  │          │                                   │
  │ Sidebar  │      QStackedWidget               │
  │  nav     │      (6 views)                    │
  │          │                                   │
  │ [● Mon]  │                                   │
  └──────────┴──────────────────────────────────┘

Navigation is driven by QPushButton items in the sidebar; clicking
a button switches the QStackedWidget to the corresponding panel and
updates the active visual state on all nav buttons.
"""
from __future__ import annotations
from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QPushButton,
    QSizePolicy, QStackedWidget, QVBoxLayout, QWidget, QMainWindow,
)

from app.database.db import Database
from app.services.organizer_service import OrganizerService
from app.ui.categories_view import CategoriesView
from app.ui.dashboard import DashboardView
from app.ui.history_view import HistoryView
from app.ui.review_queue import ReviewQueueView
from app.ui.rules_view import RulesView
from app.ui.settings_view import SettingsView
from app.utils.logging_setup import get_logger

logger = get_logger(__name__)


# ── Nav item definition ───────────────────────────────────────────────────────

_NAV_ITEMS: list[tuple[str, str]] = [
    ("dashboard",  "⬛  Dashboard"),
    ("history",    "📋  History"),
    ("categories", "🗂  Categories"),
    ("rules",      "⚙️  Rules"),
    ("review",     "🔍  Review Queue"),
    ("settings",   "⚙  Settings"),
]


class MainWindow(QMainWindow):
    """Primary application window."""

    def __init__(
        self,
        db: Database,
        service: OrganizerService,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self._db = db
        self._service = service
        self._nav_buttons: list[QPushButton] = []

        self.setWindowTitle("SmartSort — Intelligent Download Organizer")
        self.setMinimumSize(980, 660)
        self.resize(1160, 740)

        self._build_ui()
        self._navigate_to(0)   # Start on Dashboard

    # ── Layout construction ───────────────────────────────────────────────────

    def _build_ui(self) -> None:
        central = QWidget()
        self.setCentralWidget(central)
        main_row = QHBoxLayout(central)
        main_row.setContentsMargins(0, 0, 0, 0)
        main_row.setSpacing(0)

        # Left sidebar
        sidebar = self._build_sidebar()
        main_row.addWidget(sidebar)

        # Vertical divider
        divider = QFrame()
        divider.setObjectName("h_divider")
        divider.setFrameShape(QFrame.VLine)
        divider.setFixedWidth(1)
        # Divider styling comes from the stylesheet
        main_row.addWidget(divider)

        # Right: stacked views
        self._stack = QStackedWidget()
        self._stack.setObjectName("content_area")
        self._stack.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        # Instantiate all views
        self._dashboard_view  = DashboardView(self._service)
        self._history_view    = HistoryView(self._service)
        self._categories_view = CategoriesView(self._db)
        self._rules_view      = RulesView()
        self._review_view     = ReviewQueueView(self._service)
        self._settings_view   = SettingsView(self._db)

        for view in (
            self._dashboard_view,
            self._history_view,
            self._categories_view,
            self._rules_view,
            self._review_view,
            self._settings_view,
        ):
            self._stack.addWidget(view)

        main_row.addWidget(self._stack)

        # Cross-view signals
        self._history_view.undo_performed.connect(self._dashboard_view.refresh_stats)
        self._settings_view.watched_dirs_changed.connect(self._on_dirs_changed)

    def _build_sidebar(self) -> QFrame:
        sidebar = QFrame()
        sidebar.setObjectName("sidebar")
        sidebar.setFixedWidth(220)
        layout = QVBoxLayout(sidebar)
        layout.setContentsMargins(12, 20, 12, 12)
        layout.setSpacing(2)

        # Logo / app title
        logo_area = QVBoxLayout()
        logo_area.setSpacing(2)
        app_name = QLabel("SmartSort")
        app_name.setObjectName("app_title")
        tagline = QLabel("Intelligent Organizer")
        tagline.setObjectName("app_subtitle")
        logo_area.addWidget(app_name)
        logo_area.addWidget(tagline)
        layout.addLayout(logo_area)
        layout.addSpacing(20)

        # Divider
        div = QFrame()
        div.setObjectName("h_divider")
        div.setFrameShape(QFrame.HLine)
        div.setFixedHeight(1)
        layout.addWidget(div)
        layout.addSpacing(8)

        # Nav buttons
        for idx, (_, label) in enumerate(_NAV_ITEMS):
            btn = QPushButton(label)
            btn.setObjectName("nav_btn")
            btn.setCheckable(False)
            btn.setCursor(Qt.PointingHandCursor)
            btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            btn.setFixedHeight(38)
            btn.setProperty("active", "false")
            btn.clicked.connect(lambda checked=False, i=idx: self._navigate_to(i))
            layout.addWidget(btn)
            self._nav_buttons.append(btn)

        layout.addStretch()

        # Status indicator
        self._status_label = QLabel("⬛  Monitoring: Off")
        self._status_label.setObjectName("status_badge")
        self._status_label.setWordWrap(True)
        layout.addWidget(self._status_label)

        return sidebar

    # ── Navigation ────────────────────────────────────────────────────────────

    def _navigate_to(self, index: int) -> None:
        self._stack.setCurrentIndex(index)
        for i, btn in enumerate(self._nav_buttons):
            is_active = (i == index)
            btn.setProperty("active", "true" if is_active else "false")
            # Force Qt to re-evaluate the property-based stylesheet rule
            btn.style().unpolish(btn)
            btn.style().polish(btn)

        # Refresh the active view when switching to it
        view = self._stack.currentWidget()
        if hasattr(view, "refresh"):
            view.refresh()  # type: ignore[union-attr]

    # ── Signal handlers ───────────────────────────────────────────────────────

    def _on_dirs_changed(self) -> None:
        """Called when watched directories are added/removed in Settings."""
        logger.info("Watched directories changed — refreshing service.")
        # In M2 this will also restart the Watchdog observer
        self._dashboard_view.refresh_stats()

    # ── Lifecycle ─────────────────────────────────────────────────────────────

    def closeEvent(self, event: QCloseEvent) -> None:
        logger.info("MainWindow closing — shutting down organizer service.")
        self._service.shutdown()
        event.accept()
