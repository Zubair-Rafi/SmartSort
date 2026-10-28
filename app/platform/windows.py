"""Windows-specific platform adapter."""
from __future__ import annotations
from pathlib import Path

import platformdirs

from app.platform.base import PlatformAdapter


class WindowsAdapter(PlatformAdapter):
    """
    Platform adapter for Microsoft Windows.

    Config  : %APPDATA%\\SmartSort
    Data    : %LOCALAPPDATA%\\SmartSort
    Logs    : %LOCALAPPDATA%\\SmartSort\\Logs
    Downloads: %USERPROFILE%\\Downloads

    OS Concept: Mandatory file locking on Windows — the OS prevents
    exclusive opens while another process holds the file, so attempting
    to open with 'rb' is a reliable lock-detection probe.
    """

    _APP_NAME = "SmartSort"
    _APP_AUTHOR = "SmartSort"

    def get_downloads_dir(self) -> Path:
        return Path.home() / "Downloads"

    def get_config_dir(self) -> Path:
        return Path(platformdirs.user_config_dir(self._APP_NAME, self._APP_AUTHOR))

    def get_data_dir(self) -> Path:
        return Path(platformdirs.user_data_dir(self._APP_NAME, self._APP_AUTHOR))

    def get_log_dir(self) -> Path:
        return Path(platformdirs.user_log_dir(self._APP_NAME, self._APP_AUTHOR))

    def is_file_locked(self, path: Path) -> bool:
        """
        On Windows, attempt to open the file for reading.
        PermissionError indicates the file is locked by another process
        (e.g., a browser still writing a download).
        """
        try:
            with path.open("rb") as fh:
                fh.read(1)
            return False
        except PermissionError:
            return True
        except OSError:
            return False

    def get_platform_name(self) -> str:
        return "windows"
