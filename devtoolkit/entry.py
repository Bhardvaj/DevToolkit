"""Main application dispatcher for DevToolkit native desktop GUI executable.

Compiled with PyInstaller's `--windowed` flag to guarantee a 100% clean desktop launch
with zero terminal popups, zero lingering conhost windows, and co-located rotating logging.
"""

from __future__ import annotations

import argparse
import logging
import os
from pathlib import Path
import sys

from devtoolkit import __version__
from devtoolkit.core.logging import setup_client_logging, setup_daemon_logging

logger = logging.getLogger("devtoolkit.entry")


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


def main() -> None:
    """Parse launch intent and dispatch to background daemon or desktop client."""
    ensure_safe_stdio()

    # Pre-parse arguments or flags
    parser = argparse.ArgumentParser(
        prog="DevToolkit",
        description="DevToolkit: Workstation Environment Inspector & Developer Daemon",
        add_help=False,
    )
    parser.add_argument("--daemon", action="store_true", help="Run background daemon service.")
    parser.add_argument("--web", action="store_true", help="Launch in default web browser instead of desktop window.")
    parser.add_argument("--dev", action="store_true", help="Launch in frontend development mode.")
    parser.add_argument("--port", type=int, default=4321, help="Local daemon server port.")
    parser.add_argument("--host", type=str, default="127.0.0.1", help="Network host interface to bind.")
    parser.add_argument("--version", "-v", action="store_true", help="Show version.")

    # Also handle subcommands like `daemon run` if passed
    raw_args = sys.argv[1:]
    if raw_args and raw_args[0] == "daemon":
        # e.g. ["daemon", "run", "--port", "4321", "--host", "127.0.0.1"]
        raw_args = ["--daemon"] + [a for a in raw_args[1:] if a != "run"]

    args, unknown = parser.parse_known_args(raw_args)

    if args.version:
        if sys.stdout and sys.stdout != open(os.devnull, "w"):
            print(f"DevToolkit v{__version__}")
        return

    # Intent 1: Run Headless Background Daemon
    if args.daemon:
        setup_daemon_logging()
        logger.info(f"Starting DevToolkit Daemon on {args.host}:{args.port}")
        from devtoolkit.daemon.server import run_daemon_server

        run_daemon_server(host=args.host, port=args.port, with_tray=True)
        return

    # Intent 2 & 3: Launch Embedded Desktop Client or Web Browser
    setup_client_logging()
    logger.info(f"Starting DevToolkit Desktop Client (port={args.port}, web={args.web}, dev={args.dev})")
    from devtoolkit.client.desktop import launch_desktop_window

    launch_desktop_window(port=args.port, web_only=args.web, dev=args.dev)


if __name__ == "__main__":
    main()

