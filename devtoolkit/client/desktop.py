"""Embedded PyWebView desktop window client for DevToolkit."""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
import sys
import threading
import time
import urllib.request
import webbrowser
from typing import Optional

logger = logging.getLogger(__name__)

WINDOW_TITLE = "DevToolkit ⚡ Workstation Environment Inspector"


def ensure_safe_stdio() -> None:
    """Ensure sys.stdout and sys.stderr are valid writers in GUI/windowed mode."""
    if sys.stdout is None:
        try:
            sys.stdout = open(os.devnull, "w", encoding="utf-8")
        except Exception:
            pass
    if sys.stderr is None:
        try:
            sys.stderr = open(os.devnull, "w", encoding="utf-8")
        except Exception:
            pass


def find_existing_window(title: str = WINDOW_TITLE) -> Optional[int]:
    """Search for an existing top-level window matching title on Windows."""
    if sys.platform != "win32":
        return None
    try:
        import ctypes
        from ctypes import wintypes

        user32 = ctypes.windll.user32
        user32.FindWindowW.argtypes = [wintypes.LPCWSTR, wintypes.LPCWSTR]
        user32.FindWindowW.restype = wintypes.HWND
        hwnd = user32.FindWindowW(None, title)
        return int(hwnd) if hwnd else None
    except Exception as e:
        logger.debug(f"Failed to find existing window: {e}")
        return None


def restore_window_by_hwnd(hwnd: int) -> bool:
    """Restore and bring to foreground a Win32 window by HWND."""
    if sys.platform != "win32" or not hwnd:
        return False
    try:
        import ctypes
        from ctypes import wintypes

        SW_RESTORE = 9
        SW_SHOW = 5

        user32 = ctypes.windll.user32
        user32.ShowWindow.argtypes = [wintypes.HWND, ctypes.c_int]
        user32.ShowWindow.restype = wintypes.BOOL
        user32.SetForegroundWindow.argtypes = [wintypes.HWND]
        user32.SetForegroundWindow.restype = wintypes.BOOL

        user32.ShowWindow(hwnd, SW_RESTORE)
        user32.ShowWindow(hwnd, SW_SHOW)
        user32.SetForegroundWindow(hwnd)
        logger.info(f"Restored window HWND {hwnd} to foreground.")
        return True
    except Exception as e:
        logger.debug(f"Failed to restore window {hwnd}: {e}")
        return False


def notify_daemon_tray(port: int, title: str, message: str) -> None:
    """Send desktop notification request to daemon tray service."""
    try:
        data = json.dumps({"title": title, "message": message}).encode("utf-8")
        req = urllib.request.Request(
            f"http://127.0.0.1:{port}/api/daemon/notify",
            data=data,
            headers={"Content-Type": "application/json", "User-Agent": "DevToolkit-DesktopClient"},
            method="POST",
        )
        urllib.request.urlopen(req, timeout=1.0)
    except Exception as e:
        logger.debug(f"Failed to notify tray: {e}")


def launch_desktop_window(port: int = 4321, web_only: bool = False, dev: bool = False) -> None:
    """Launch or attach to background daemon and open native desktop window or browser."""
    ensure_safe_stdio()
    logger.info(f"launch_desktop_window requested (port={port}, web_only={web_only}, dev={dev})")

    # 1. If native window is already active on Windows, bring it to front
    if not web_only and not dev and sys.platform == "win32":
        hwnd = find_existing_window(WINDOW_TITLE)
        if hwnd:
            logger.info(f"Existing window found (HWND {hwnd}). Restoring to foreground.")
            restore_window_by_hwnd(hwnd)
            return

    # 2. Ensure background daemon is running
    from devtoolkit.daemon.manager import is_daemon_alive, start_daemon

    if not is_daemon_alive(port=port):
        logger.info(f"Daemon not responding on port {port}. Starting daemon...")
        try:
            start_daemon(port=port)
            logger.info("Daemon started successfully.")
        except Exception as e:
            logger.warning(f"Failed to spawn detached daemon ({e}). Falling back to in-process server thread.")
            from devtoolkit.server.app import run_server

            server_thread = threading.Thread(target=run_server, args=(port,), daemon=True)
            server_thread.start()
            time.sleep(0.8)

    url = f"http://127.0.0.1:{port}"

    # 3. Web or dev mode: open default browser
    if web_only or dev:
        logger.info(f"Opening browser at {url}")
        webbrowser.open(url)
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            logger.info("Browser client loop terminated.")
        return

    # 4. Native PyWebView embedded window
    try:
        import webview

        logger.info(f"Creating PyWebView window loading {url}")
        window = webview.create_window(
            title=WINDOW_TITLE,
            url=url,
            width=1140,
            height=780,
            min_size=(880, 600),
            text_select=True,
        )

        def on_closing() -> bool:
            from devtoolkit.core.config import load_config
            from devtoolkit.daemon.manager import is_daemon_alive, stop_daemon

            logger.info("Window close event received.")
            if not is_daemon_alive(port=port):
                logger.info("Daemon is not alive. Closing window directly.")
                return True

            cfg = load_config()
            action = getattr(cfg, "close_action", "ask")

            if action == "minimize":
                logger.info("Config close_action is 'minimize'. Hiding window.")
                try:
                    window.hide()
                    notify_daemon_tray(
                        port,
                        "DevToolkit",
                        "DevToolkit minimized to system tray. Click the tray icon anytime to restore.",
                    )
                except Exception:
                    pass
                return False

            if action == "exit":
                logger.info("Config close_action is 'exit'. Stopping daemon.")
                stop_daemon()
                return True

            if sys.platform == "win32":
                import ctypes

                MB_YESNOCANCEL = 0x00000003
                MB_ICONQUESTION = 0x00000020
                MB_TOPMOST = 0x00040000
                MB_SETFOREGROUND = 0x00010000
                IDYES = 6
                IDNO = 7

                text = (
                    "DevToolkit background daemon is currently active.\n\n"
                    "Would you like to minimize to the System Tray to keep services running in background, "
                    "or exit completely?\n\n"
                    "• [Yes] Minimize to System Tray\n"
                    "• [No] Exit Completely (Stop all background services)\n"
                    "• [Cancel] Stay in DevToolkit"
                )
                title = "DevToolkit"

                res = ctypes.windll.user32.MessageBoxW(
                    None, text, title, MB_YESNOCANCEL | MB_ICONQUESTION | MB_TOPMOST | MB_SETFOREGROUND
                )

                if res == IDYES:
                    logger.info("User chose: Minimize to System Tray.")
                    try:
                        window.hide()
                        notify_daemon_tray(
                            port,
                            "DevToolkit",
                            "DevToolkit minimized to system tray. Click the tray icon anytime to restore.",
                        )
                    except Exception:
                        pass
                    return False
                elif res == IDNO:
                    logger.info("User chose: Exit Completely.")
                    stop_daemon()
                    return True
                else:
                    logger.info("User chose: Cancel.")
                    return False

            logger.info("Defaulting to stop_daemon and exit.")
            stop_daemon()
            return True

        window.events.closing += on_closing
        webview.start()
        logger.info("PyWebView event loop finished.")
    except Exception as e:
        logger.warning(f"Could not open native window ({e}). Falling back to browser at {url}.")
        webbrowser.open(url)
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            pass

