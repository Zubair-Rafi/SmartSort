"""
Application configuration manager.

Settings are persisted in <config_dir>/settings.json with an in-memory
cache so repeated reads don't touch disk.  All mutations auto-save.
"""
from __future__ import annotations
import json
import threading
from pathlib import Path
from typing import Any

from app.platform import platform
from app.utils.logging_setup import get_logger

logger = get_logger(__name__)

DEFAULT_SETTINGS: dict[str, Any] = {
    # ── Monitoring ────────────────────────────────────────────────────────────
    "auto_organize": False,
    "stability_poll_interval": 2.0,    # seconds between stability polls
    "min_stable_duration": 5.0,        # seconds file must remain unchanged
    "max_workers": 2,                  # concurrent classification workers
    "temp_extensions": [
        ".part", ".crdownload", ".download", ".tmp", ".opdownload",
        ".aria2", ".!ut", ".downloading", ".incomplete",
    ],

    # ── Classification thresholds (tuned empirically) ─────────────────────
    # These are NOT calibrated probabilities — adjust based on your usage.
    "auto_confirm_threshold": 0.72,
    "suggest_threshold": 0.45,

    # ── Content extraction limits ─────────────────────────────────────────
    "max_file_size_mb": 50,
    "max_pages_to_analyze": 10,
    "max_chars_to_extract": 5000,
    "max_extraction_seconds": 10.0,

    # ── UI / notifications ────────────────────────────────────────────────
    "theme": "dark",
    "notifications_enabled": True,
    "notify_on_success": False,   # silent success — only count on dashboard
    "notify_on_review": True,
    "notify_on_error": True,

    # ── First-run state ───────────────────────────────────────────────────
    "first_run": True,
    "organize_existing_on_startup": False,
}


class AppConfig:
    """
    Thread-safe JSON configuration singleton.

    Usage:
        cfg = AppConfig.instance()
        val = cfg.get("auto_confirm_threshold", 0.72)
        cfg.set("auto_organize", True)
    """

    _instance: "AppConfig | None" = None
    _class_lock = threading.Lock()

    def __init__(self) -> None:
        self._config_dir: Path = platform().get_config_dir()
        self._config_file: Path = self._config_dir / "settings.json"
        self._settings: dict[str, Any] = {}
        self._rw_lock = threading.RLock()
        self._load()

    @classmethod
    def instance(cls) -> "AppConfig":
        """Return (or create) the global AppConfig singleton."""
        with cls._class_lock:
            if cls._instance is None:
                cls._instance = cls()
            return cls._instance

    # ── Private ──────────────────────────────────────────────────────────────

    def _load(self) -> None:
        with self._rw_lock:
            self._settings = dict(DEFAULT_SETTINGS)
            if self._config_file.exists():
                try:
                    on_disk = json.loads(
                        self._config_file.read_text(encoding="utf-8")
                    )
                    self._settings.update(on_disk)
                except (json.JSONDecodeError, OSError) as exc:
                    logger.warning(
                        "Failed to load settings from %s: %s — using defaults.",
                        self._config_file, exc,
                    )

    # ── Public API ────────────────────────────────────────────────────────────

    def save(self) -> None:
        """Persist current settings to disk."""
        with self._rw_lock:
            try:
                self._config_dir.mkdir(parents=True, exist_ok=True)
                self._config_file.write_text(
                    json.dumps(self._settings, indent=2, ensure_ascii=False),
                    encoding="utf-8",
                )
            except OSError as exc:
                logger.error("Failed to save settings: %s", exc)

    def get(self, key: str, default: Any = None) -> Any:
        with self._rw_lock:
            return self._settings.get(key, default)

    def set(self, key: str, value: Any) -> None:
        with self._rw_lock:
            self._settings[key] = value
        self.save()

    def get_all(self) -> dict[str, Any]:
        with self._rw_lock:
            return dict(self._settings)

    def reset_to_defaults(self) -> None:
        with self._rw_lock:
            self._settings = dict(DEFAULT_SETTINGS)
        self.save()
