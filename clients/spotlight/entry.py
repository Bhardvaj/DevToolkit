"""Main application entry point for DevToolkit Spotlight.

Resident workstation command palette executable (DevToolkitSpotlight.exe)
providing instantaneous <10ms Alt+Space summoning, multi-mode developer tools,
Win32 system tray integration, and zero daemon code bundling.
"""

from __future__ import annotations

import argparse
import logging
from logging.handlers import RotatingFileHandler
import os
from pathlib import Path
import sys
import threading
import time

from clients.spotlight import __version__
from clients.spotlight.hotkey import GlobalHotkeyListener
from clients.spotlight.settings import load_spotlight_settings
from clients.spotlight.tray import SpotlightTray
from clients.spotlight.window import SPOTLIGHT_TITLE, SpotlightWindowManager
from devtoolkit.client.api import DevToolkitClient

logger = logging.getLogger("spotlight")

MUTEX_NAME = "Local\\DevToolkitSpotlight_SingleInstance_Mutex"
ERROR_ALREADY_EXISTS = 183


def ensure_safe_stdio() -> None:
    """Redirect null stdio streams in Windows GUI subsystem mode."""
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


def setup_spotlight_logging() -> None:
    """Configure rotating log file handler in the application directory."""
    log_dir = Path(sys.executable).parent if getattr(sys, "frozen", False) else Path.cwd()
    log_file = log_dir / "spotlight.log"

    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)

    # File handler (5MB, 2 backups)
    try:
        fh = RotatingFileHandler(
            log_file,
            maxBytes=5 * 1024 * 1024,
            backupCount=2,
            encoding="utf-8",
        )
        fh.setFormatter(
            logging.Formatter(
                fmt="%(asctime)s [%(levelname)s] [%(name)s]: %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S",
            )
        )
        root_logger.addHandler(fh)
    except Exception as e:
        print(f"Failed to initialize file logger: {e}", file=sys.stderr)

    # Console handler (if stdout attached and is interactive)
    if sys.stdout and hasattr(sys.stdout, "isatty"):
        try:
            if sys.stdout.isatty():
                ch = logging.StreamHandler(sys.stdout)
                ch.setFormatter(
                    logging.Formatter(
                        fmt="[%(levelname)s] %(message)s",
                    )
                )
                root_logger.addHandler(ch)
        except Exception:
            pass


def acquire_single_instance_mutex():
    """Ensure only one instance of DevToolkit Spotlight runs concurrently."""
    if sys.platform != "win32":
        return None

    import ctypes
    from ctypes import wintypes

    kernel32 = ctypes.windll.kernel32
    user32 = ctypes.windll.user32

    kernel32.CreateMutexW.argtypes = [wintypes.LPVOID, wintypes.BOOL, wintypes.LPCWSTR]
    kernel32.CreateMutexW.restype = wintypes.HANDLE

    mutex = kernel32.CreateMutexW(None, False, MUTEX_NAME)
    last_err = kernel32.GetLastError()

    if last_err == ERROR_ALREADY_EXISTS:
        # Existing instance already running - bring its window to foreground
        logger.info("DevToolkit Spotlight is already running. Activating existing instance.")
        user32.FindWindowW.argtypes = [wintypes.LPCWSTR, wintypes.LPCWSTR]
        user32.FindWindowW.restype = wintypes.HWND
        hwnd = user32.FindWindowW(None, SPOTLIGHT_TITLE)
        if hwnd:
            SW_RESTORE = 9
            SW_SHOW = 5
            user32.ShowWindow(hwnd, SW_RESTORE)
            user32.ShowWindow(hwnd, SW_SHOW)
            user32.SetForegroundWindow(hwnd)
        sys.exit(0)

    return mutex


_current_wm: SpotlightWindowManager | None = None


def resolve_daemon_target(cli_host: str, cli_port: int) -> tuple[str, int]:
    """Auto-discover daemon host and port from active daemon.json if present."""
    import json
    base_dirs = [
        Path(sys.executable).parent if getattr(sys, "frozen", False) else Path.cwd(),
        Path.cwd(),
        Path.cwd() / "dist",
        Path.home() / ".devtoolkit",
    ]
    for d in base_dirs:
        state_file = d / "daemon.json"
        if state_file.is_file():
            try:
                data = json.loads(state_file.read_text(encoding="utf-8"))
                s_port = data.get("port")
                s_host = data.get("host", "127.0.0.1")
                if s_port:
                    return s_host, int(s_port)
            except Exception:
                pass
    return cli_host, cli_port


def main() -> None:
    """Parse CLI options, initialize components, and start Spotlight."""
    global _current_wm
    ensure_safe_stdio()
    setup_spotlight_logging()

    try:
        parser = argparse.ArgumentParser(
            prog="DevToolkitSpotlight",
            description="DevToolkit Spotlight: Workstation Developer Command Palette",
        )
        parser.add_argument("--port", type=int, default=4321, help="DevToolkit daemon port.")
        parser.add_argument("--host", type=str, default="127.0.0.1", help="DevToolkit daemon host.")
        parser.add_argument("--no-tray", action="store_true", help="Disable system tray icon.")
        parser.add_argument("--no-hotkey", action="store_true", help="Disable global keyboard hotkey.")
        parser.add_argument("--version", "-v", action="store_true", help="Display Spotlight version.")

        args = parser.parse_args()

        if args.version:
            print(f"DevToolkit Spotlight v{__version__}")
            sys.exit(0)

        target_host, target_port = resolve_daemon_target(args.host, args.port)
        logger.info(f"Starting DevToolkit Spotlight v{__version__} (Daemon target: http://{target_host}:{target_port})")

        mutex = acquire_single_instance_mutex()

        client = DevToolkitClient(host=target_host, port=target_port)
        settings = load_spotlight_settings()

        wm = SpotlightWindowManager(client=client)
        _current_wm = wm

        # 1. Background global hotkey listener
        hotkey_listener: GlobalHotkeyListener | None = None
        if not args.no_hotkey and sys.platform == "win32":
            hotkey_listener = GlobalHotkeyListener(
                hotkey_str=settings.hotkey,
                fallback_hotkey_str=settings.fallback_hotkey,
                on_hotkey=wm.toggle,
            )
            hotkey_listener.start()
            logger.info(f"Global hotkey listener registered for: {settings.hotkey}")

        # 2. Native Win32 system tray
        tray: SpotlightTray | None = None
        if not args.no_tray and sys.platform == "win32":
            tray = SpotlightTray(
                on_open_spotlight=wm.show,
                on_open_settings=wm.open_settings_dialog,
                on_exit=wm.quit,
            )
            tray.start()
            logger.info("Spotlight system tray icon started.")

        try:
            # 3. Create and run PyWebView window
            wm.start()
        finally:
            logger.info("Shutting down DevToolkit Spotlight...")
            if tray:
                tray.stop()
            if hotkey_listener:
                hotkey_listener.stop()

            if mutex and sys.platform == "win32":
                import ctypes
                ctypes.windll.kernel32.CloseHandle(mutex)
    except Exception as e:
        logger.critical(f"Fatal error starting Spotlight: {e}", exc_info=True)
        if sys.platform == "win32":
            try:
                import ctypes
                MB_ICONERROR = 0x00000010
                MB_TOPMOST = 0x00040000
                ctypes.windll.user32.MessageBoxW(
                    None,
                    f"DevToolkit Spotlight failed to launch:\n\n{e}\n\nPlease check spotlight.log for complete traceback.",
                    "DevToolkit Spotlight Error",
                    MB_ICONERROR | MB_TOPMOST,
                )
            except Exception:
                pass
        sys.exit(1)


if __name__ == "__main__":
    main()

