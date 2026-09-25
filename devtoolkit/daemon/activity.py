"""Real-time activity and background task status tracking for DevToolkit daemon."""

from __future__ import annotations

import threading
import time
from typing import Any, Dict, Optional


class ActivityTracker:
    """Thread-safe state tracker for background scan and index operations."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self.is_scanning = False
        self.is_indexing = False
        self.scan_count = 0
        self.index_count = 0
        self.last_scan_message = ""
        self.last_index_message = ""
        self.last_scan_time: Optional[float] = None
        self.last_index_time: Optional[float] = None

    def start_scan(self, message: str = "Scanning environment...") -> None:
        with self._lock:
            self.is_scanning = True
            self.last_scan_message = message

    def finish_scan(self, message: str = "Scan complete", success: bool = True) -> None:
        with self._lock:
            self.is_scanning = False
            self.scan_count += 1
            self.last_scan_message = message
            self.last_scan_time = time.time()

    def start_index(self, message: str = "Indexing files...") -> None:
        with self._lock:
            self.is_indexing = True
            self.last_index_message = message

    def finish_index(self, message: str = "Index complete", success: bool = True) -> None:
        with self._lock:
            self.is_indexing = False
            self.index_count += 1
            self.last_index_message = message
            self.last_index_time = time.time()

    def get_status(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "is_scanning": self.is_scanning,
                "is_indexing": self.is_indexing,
                "scan_count": self.scan_count,
                "index_count": self.index_count,
                "last_scan_message": self.last_scan_message,
                "last_index_message": self.last_index_message,
                "last_scan_time": self.last_scan_time,
                "last_index_time": self.last_index_time,
            }


_activity_tracker = ActivityTracker()


def get_activity_tracker() -> ActivityTracker:
    """Return singleton ActivityTracker instance."""
    return _activity_tracker

