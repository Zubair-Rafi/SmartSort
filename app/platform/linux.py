"""Linux-specific platform adapter."""
from __future__ import annotations
import os
import subprocess
from pathlib import Path

import platformdirs

from app.platform.base import PlatformAdapter


class LinuxAdapter(PlatformAdapter):
    """
    Platform adapter for Linux (XDG Base Directory Specification).

    Config  : $XDG_CONFIG_HOME/smartsort  (default ~/.config/smartsort)
    Data    : $XDG_DATA_HOME/smartsort    (default ~/.local/share/smartsort)
    Logs    : $XDG_CACHE_HOME/smartsort   (default ~/.cache/smartsort)
    Downloads: $XDG_DOWNLOAD_DIR          (default ~/Downloads)

    OS Concept: On Linux, file locking is advisory — not enforced by the kernel.
    We detect open file handles by scanning /proc/<pid>/fd symlinks, which is
    a direct read of the kernel's per-process file descriptor tables.
    """

    _APP_NAME = "smartsort"

    def get_downloads_dir(self) -> Path:
        # Respect XDG_DOWNLOAD_DIR set by the desktop environment
        try:
            result = subprocess.run(
                ["xdg-user-dir", "DOWNLOAD"],
                capture_output=True, text=True, timeout=2,
            )
            if result.returncode == 0:
                dl = Path(result.stdout.strip())
                if dl.exists():
                    return dl
        except (FileNotFoundError, subprocess.TimeoutExpired):
            pass
        return Path.home() / "Downloads"

    def get_config_dir(self) -> Path:
        return Path(platformdirs.user_config_dir(self._APP_NAME))

    def get_data_dir(self) -> Path:
        return Path(platformdirs.user_data_dir(self._APP_NAME))

    def get_log_dir(self) -> Path:
        return Path(platformdirs.user_log_dir(self._APP_NAME))

    def is_file_locked(self, path: Path) -> bool:
        """
        Scan /proc/<pid>/fd to find any process with an open file descriptor
        pointing at this file. Falls back to advisory locking via fcntl.

        OS Concept: /proc virtual filesystem exposes kernel data structures
        (open file descriptors) as regular files — a direct window into the
        kernel's process table.
        """
        proc = Path("/proc")
        if not proc.exists():
            return self._fcntl_locked(path)

        try:
            target = str(path.resolve())
            for pid_dir in proc.iterdir():
                if not pid_dir.name.isdigit():
                    continue
                fd_dir = pid_dir / "fd"
                try:
                    for fd_link in fd_dir.iterdir():
                        try:
                            if os.readlink(fd_link) == target:
                                return True
                        except OSError:
                            continue
                except (PermissionError, OSError):
                    continue
        except Exception:
            return self._fcntl_locked(path)

        return False

    def _fcntl_locked(self, path: Path) -> bool:
        """Advisory lock fallback using fcntl.LOCK_NB."""
        try:
            import fcntl
            with path.open("rb") as fh:
                fcntl.flock(fh.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                fcntl.flock(fh.fileno(), fcntl.LOCK_UN)
            return False
        except (IOError, OSError):
            return True

    def get_platform_name(self) -> str:
        return "linux"
