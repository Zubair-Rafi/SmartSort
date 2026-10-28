"""
SmartSort application entry point.

Bootstrap sequence:
  1. Determine platform-appropriate directories
  2. Initialise logging
  3. Initialise SQLite database
  4. Seed default categories (idempotent)
  5. Register default Downloads directory if no watched dirs exist
  6. Construct OrganizerService
  7. Launch QApplication + MainWindow
"""
from __future__ import annotations
import sys

from PySide6.QtGui import QFont
from PySide6.QtWidgets import QApplication, QMessageBox

from app.database.db import Database
from app.platform import platform
from app.services.category_loader import seed_categories
from app.services.organizer_service import OrganizerService
from app.ui.main_window import MainWindow
from app.ui.stylesheet import APP_STYLESHEET
from app.utils.config import AppConfig
from app.utils.logging_setup import get_logger, setup_logging


def _bootstrap() -> tuple[Database, OrganizerService]:
    """
    Set up all application services before any UI is shown.
    Returns the Database and OrganizerService instances.
    """
    adapter = platform()

    # Directories
    data_dir   = adapter.get_data_dir()
    log_dir    = adapter.get_log_dir()
    data_dir.mkdir(parents=True, exist_ok=True)

    # Logging
    setup_logging(log_dir)
    logger = get_logger("smartsort.main")
    logger.info("SmartSort starting — platform: %s", adapter.get_platform_name())
    logger.info("Data directory: %s", data_dir)
    logger.info("Config directory: %s", adapter.get_config_dir())

    # Database
    db_path = data_dir / "smartsort.db"
    db = Database(db_path)

    # Seed categories (no-op if already seeded)
    n = seed_categories(db)
    if n:
        logger.info("Seeded %d categories from default JSON.", n)

    # Register default Downloads directory on first run
    cfg = AppConfig.instance()
    if cfg.get("first_run", True):
        downloads = adapter.get_downloads_dir()
        if downloads.exists():
            db.add_watched_directory(str(downloads))
            logger.info("First run — added default watch: %s", downloads)
        cfg.set("first_run", False)

    service = OrganizerService(db)
    return db, service


def main() -> None:
    app = QApplication(sys.argv)
    app.setApplicationName("SmartSort")
    app.setOrganizationName("SmartSort")
    app.setApplicationVersion("0.1.0")

    # Apply stylesheet before any window appears
    app.setStyleSheet(APP_STYLESHEET)

    # Use system default font with a readable size
    font = app.font()
    font.setPointSize(10)
    app.setFont(font)

    try:
        db, service = _bootstrap()
    except Exception as exc:
        QMessageBox.critical(
            None, "Startup Error",
            f"SmartSort failed to start:\n\n{exc}\n\n"
            "Please check the log files for details.",
        )
        sys.exit(1)

    window = MainWindow(db, service)
    window.show()

    exit_code = app.exec()
    db.close()
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
