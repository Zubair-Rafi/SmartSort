"""
macOS-specific platform adapter.

NOTE: macOS support has not been fully verified in testing.
Functionality is expected to work but should be confirmed on real hardware.
"""
from __future__ import annotations
from pathlib import Path

import platformdirs

from app.platform.base import PlatformAdapter


class MacOSAdapter(PlatformAdapter):
    """
    Platform adapter for macOS.

    Config  : ~/Library/Application Support/SmartSort
    Data    : ~/Library/Application Support/SmartSort
    Logs    : ~/Library/Logs/SmartSort
    Downloads: ~/Downloads

    OS Concept: macOS uses advisory locking (fcntl) similar to Linux.
    Unlike Linux, /proc is not available; instead we use LOCK_NB probe.
    """

    _APP_NAME = "SmartSort"

    def get_downloads_dir(self) -> Path:
        return Path.home() / "Downloads"

    def get_config_dir(self) -> Path:
        return Path(platformdirs.user_config_dir(self._APP_NAME))

    def get_data_dir(self) -> Path:
        return Path(platformdirs.user_data_dir(self._APP_NAME))

    def get_log_dir(self) -> Path:
        return Path(platformdirs.user_log_dir(self._APP_NAME))

    def is_file_locked(self, path: Path) -> bool:
        """Probe with a non-blocking exclusive lock attempt."""
        try:
            import fcntl
            with path.open("rb") as fh:
                fcntl.flock(fh.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                fcntl.flock(fh.fileno(), fcntl.LOCK_UN)
            return False
        except (IOError, OSError):
            return True
        except Exception:
            return False

    def get_platform_name(self) -> str:
        return "macos"
