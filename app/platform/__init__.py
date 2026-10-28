"""Platform adapter factory and module-level singleton."""
from __future__ import annotations
import sys

from app.platform.base import PlatformAdapter

_adapter: PlatformAdapter | None = None


def get_platform_adapter() -> PlatformAdapter:
    """Instantiate the correct platform adapter for the current OS."""
    if sys.platform == "win32":
        from app.platform.windows import WindowsAdapter
        return WindowsAdapter()
    elif sys.platform == "darwin":
        from app.platform.macos import MacOSAdapter
        return MacOSAdapter()
    else:
        # Linux and other POSIX systems
        from app.platform.linux import LinuxAdapter
        return LinuxAdapter()


def platform() -> PlatformAdapter:
    """Return the cached, module-level platform adapter singleton."""
    global _adapter
    if _adapter is None:
        _adapter = get_platform_adapter()
    return _adapter
