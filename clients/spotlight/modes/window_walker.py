"""Window Walker module: search, switch to, and manage running top-level windows."""

from __future__ import annotations

import logging
import sys
from typing import Any, Dict, List, Optional

from clients.spotlight.icons import get_process_icon_data_url

logger = logging.getLogger(__name__)


def list_open_windows(query: str = "") -> List[Dict[str, Any]]:
    """Enumerate visible desktop application windows, optionally filtering by title/process."""
    if sys.platform != "win32":
        return []

    import ctypes
    from ctypes import wintypes

    user32 = ctypes.windll.user32
    kernel32 = ctypes.windll.kernel32

    WNDENUMPROC = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

    windows: List[Dict[str, Any]] = []
    q_low = query.strip().lower()

    def _enum_cb(hwnd, lparam):
        if not user32.IsWindowVisible(hwnd):
            return True

        length = user32.GetWindowTextLengthW(hwnd)
        if length == 0:
            return True

        buff = ctypes.create_unicode_buffer(length + 1)
        user32.GetWindowTextW(hwnd, buff, length + 1)
        title = buff.value.strip()

        if not title:
            return True

        # Filter out common hidden tool windows / shell overlays
        if title in ("Program Manager", "Settings", "Windows Input Experience"):
            return True

        # Check process ID
        pid = wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))

        # Filter by search query if specified
        if q_low and q_low not in title.lower():
            return True

        win_item = {
            "id": f"win_{hwnd}",
            "hwnd": hwnd,
            "pid": pid.value,
            "title": title,
            "subtitle": f"PID: {pid.value}",
            "type": "window",
            "badge": "WINDOW",
            "action": "switch_window",
        }
        icon_url = get_process_icon_data_url(pid.value)
        if icon_url:
            win_item["icon"] = icon_url

        windows.append(win_item)
        return True

    cb = WNDENUMPROC(_enum_cb)
    user32.EnumWindows(cb, 0)

    return windows


def switch_to_window(hwnd: int) -> bool:
    """Restore and bring window to the foreground."""
    if sys.platform != "win32" or not hwnd:
        return False
    try:
        import ctypes
        from ctypes import wintypes

        user32 = ctypes.windll.user32
        SW_RESTORE = 9
        SW_SHOW = 5

        user32.ShowWindow(hwnd, SW_RESTORE)
        user32.ShowWindow(hwnd, SW_SHOW)
        user32.SetForegroundWindow(hwnd)
        return True
    except Exception as e:
        logger.debug(f"Failed to switch to window {hwnd}: {e}")
        return False


def close_window_by_hwnd(hwnd: int) -> bool:
    """Send WM_CLOSE to window."""
    if sys.platform != "win32" or not hwnd:
        return False
    try:
        import ctypes
        user32 = ctypes.windll.user32
        WM_CLOSE = 0x0010
        user32.PostMessageW(hwnd, WM_CLOSE, 0, 0)
        return True
    except Exception as e:
        logger.debug(f"Failed to close window {hwnd}: {e}")
        return False

