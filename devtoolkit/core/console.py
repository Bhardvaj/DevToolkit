"""Windows Console management and suppression utilities for DevToolkit.

Ensures that launching the standalone binary via Windows File Explorer or desktop shortcuts
runs with a clean desktop experience (suppressing the black conhost terminal), while
preserving the terminal window when invoked via PowerShell, Command Prompt, or shell scripts.
"""

from __future__ import annotations

import logging
import os
import sys
from typing import List, Optional

logger = logging.getLogger(__name__)

SW_HIDE = 0
SW_SHOW = 5
SW_RESTORE = 9

KNOWN_SHELL_NAMES = {
    "cmd.exe",
    "powershell.exe",
    "pwsh.exe",
    "windowsterminal.exe",
    "wt.exe",
    "bash.exe",
    "zsh.exe",
    "sh.exe",
    "mintty.exe",
    "conhost.exe",
}


def get_console_pids() -> List[int]:
    """Retrieve process IDs attached to the current Windows console."""
    if sys.platform != "win32":
        return []

    try:
        import ctypes
        from ctypes import wintypes

        kernel32 = ctypes.windll.kernel32
        buffer_size = 16
        process_list = (wintypes.DWORD * buffer_size)()
        count = kernel32.GetConsoleProcessList(process_list, buffer_size)
        if count <= 0:
            return []
        if count > buffer_size:
            buffer_size = count
            process_list = (wintypes.DWORD * buffer_size)()
            count = kernel32.GetConsoleProcessList(process_list, buffer_size)
        return [int(process_list[i]) for i in range(count)]
    except Exception as e:
        logger.debug(f"Failed to query console process list: {e}")
        return []


def is_standalone_console() -> bool:
    """Determine if running in an isolated console created exclusively for this process.

    Returns True when launched via Windows Explorer double-click, desktop shortcut,
    or Run dialog, where Windows automatically allocates a conhost/console with no
    parent interactive shell (PowerShell, CMD, Windows Terminal, bash, etc.).

    Returns False if launched inside an active terminal or when developing under python.exe.
    """
    if sys.platform != "win32":
        return False

    # In local development mode (running uncompiled python.exe), never hide the terminal
    if not getattr(sys, "frozen", False):
        exe_name = os.path.basename(sys.executable).lower()
        if "python" in exe_name:
            return False

    try:
        import ctypes
        from ctypes import wintypes

        kernel32 = ctypes.windll.kernel32
        hwnd = kernel32.GetConsoleWindow()
        if not hwnd:
            return False

        pids = get_console_pids()
        if not pids or len(pids) > 2:
            return False

        PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
        current_name = os.path.basename(sys.executable).lower()

        for pid in pids:
            h = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
            if not h:
                return False
            try:
                buf = ctypes.create_unicode_buffer(1024)
                size = wintypes.DWORD(1024)
                if kernel32.QueryFullProcessImageNameW(h, 0, buf, ctypes.byref(size)):
                    pname = os.path.basename(buf.value).lower()
                    if pname in KNOWN_SHELL_NAMES or pname != current_name:
                        return False
                else:
                    return False
            finally:
                kernel32.CloseHandle(h)

        return True
    except Exception as e:
        logger.debug(f"Failed to evaluate standalone console status: {e}")
        return False


def hide_console_window() -> bool:
    """Hide the console window if running in a standalone Explorer/shortcut launch.

    Returns True if the console window was successfully hidden, False otherwise.
    """
    if sys.platform != "win32":
        return False

    try:
        if not is_standalone_console():
            return False

        import ctypes

        kernel32 = ctypes.windll.kernel32
        user32 = ctypes.windll.user32

        hwnd = kernel32.GetConsoleWindow()
        if hwnd:
            user32.ShowWindow(hwnd, SW_HIDE)
            logger.debug("Console window suppressed for standalone GUI session.")
            return True
        return False
    except Exception as e:
        logger.debug(f"Failed to hide console window: {e}")
        return False


def show_console_window() -> bool:
    """Restore and show the console window if it was previously hidden."""
    if sys.platform != "win32":
        return False

    try:
        import ctypes

        kernel32 = ctypes.windll.kernel32
        user32 = ctypes.windll.user32

        hwnd = kernel32.GetConsoleWindow()
        if hwnd:
            user32.ShowWindow(hwnd, SW_SHOW)
            return True
        return False
    except Exception as e:
        logger.debug(f"Failed to show console window: {e}")
        return False
