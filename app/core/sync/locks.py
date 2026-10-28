"""
Thread synchronization utilities.

OS Concepts:
  - Mutex (threading.Lock) guards critical sections
  - Per-path locking prevents two threads from concurrently processing
    the same file — analogous to inode-level locking in a filesystem
  - Reference counting ensures locks are removed when no longer needed
  - Context manager guarantees lock release even on exceptions (RAII pattern)
"""
from __future__ import annotations
import threading
from contextlib import contextmanager
from pathlib import Path
from typing import Generator


class PathLockManager:
    """
    User-space per-path exclusive locks.

    Multiple worker threads may receive filesystem events for different files
    simultaneously.  This manager ensures only one thread processes a given
    file path at any point in time, preventing duplicate operations and
    race conditions on shared state.

    Implementation:
        - A registry dict maps resolved path strings to (Lock, refcount) pairs.
        - The registry itself is protected by a separate meta-lock.
        - Reference counting lets us clean up locks that are no longer needed.
    """

    def __init__(self) -> None:
        self._meta: threading.Lock = threading.Lock()
        self._registry: dict[str, tuple[threading.Lock, int]] = {}

    @contextmanager
    def lock(self, path: Path) -> Generator[None, None, None]:
        """
        Acquire an exclusive lock for *path*.  Blocks until available.

        Usage:
            with path_lock_manager.lock(file_path):
                # safe to process file exclusively
        """
        key = str(path.resolve())
        file_lock = self._ref_acquire(key)
        try:
            file_lock.acquire()
            yield
        finally:
            file_lock.release()
            self._ref_release(key)

    def _ref_acquire(self, key: str) -> threading.Lock:
        with self._meta:
            if key not in self._registry:
                self._registry[key] = (threading.Lock(), 0)
            lock, count = self._registry[key]
            self._registry[key] = (lock, count + 1)
            return lock

    def _ref_release(self, key: str) -> None:
        with self._meta:
            if key not in self._registry:
                return
            lock, count = self._registry[key]
            if count <= 1:
                del self._registry[key]
            else:
                self._registry[key] = (lock, count - 1)

    def is_locked(self, path: Path) -> bool:
        """Return True if another thread currently holds this path's lock."""
        key = str(path.resolve())
        with self._meta:
            return key in self._registry and self._registry[key][1] > 0


# Application-wide singleton — import and use directly
global_path_locks = PathLockManager()
