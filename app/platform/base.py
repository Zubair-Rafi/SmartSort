"""Abstract platform adapter interface."""
from __future__ import annotations
from abc import ABC, abstractmethod
from pathlib import Path


class PlatformAdapter(ABC):
    """
    Abstracts OS-specific path conventions and file-locking behaviour.

    Concrete implementations:
      - WindowsAdapter  (app/platform/windows.py)
      - LinuxAdapter    (app/platform/linux.py)
      - MacOSAdapter    (app/platform/macos.py)

    OS Concept: OS abstraction layer — one interface, multiple platform
    implementations, so core logic never branches on sys.platform.
    """

    @abstractmethod
    def get_downloads_dir(self) -> Path:
        """Return the user's default Downloads directory."""
        ...

    @abstractmethod
    def get_config_dir(self) -> Path:
        """Return the OS-appropriate application config directory."""
        ...

    @abstractmethod
    def get_data_dir(self) -> Path:
        """Return the OS-appropriate application data directory."""
        ...

    @abstractmethod
    def get_log_dir(self) -> Path:
        """Return the OS-appropriate application log directory."""
        ...

    @abstractmethod
    def is_file_locked(self, path: Path) -> bool:
        """
        Return True if the file is held open by another process.
        Used to detect in-progress downloads before moving a file.
        """
        ...

    @abstractmethod
    def get_platform_name(self) -> str:
        """Return 'windows', 'linux', or 'macos'."""
        ...
