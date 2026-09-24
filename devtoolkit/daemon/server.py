"""Server daemon execution runner with state registration, system tray service, and graceful shutdown."""

import atexit
import logging
import os
import signal
import sys
from datetime import datetime, timezone

import uvicorn

from devtoolkit import __version__
from devtoolkit.daemon.models import DaemonState
from devtoolkit.daemon.manager import clear_daemon_state, write_daemon_state
from devtoolkit.server.app import app

logger = logging.getLogger(__name__)


def run_daemon_server(host: str = "127.0.0.1", port: int = 4321, with_tray: bool = True) -> None:
    """Run uvicorn server in daemon mode, managing state lockfile, system tray, and signals."""
    # 1. Register daemon state
    state = DaemonState(
        pid=os.getpid(),
        port=port,
        host=host,
        version=__version__,
        started_at=datetime.now(timezone.utc).isoformat(),
        status="running",
    )
    write_daemon_state(state)

    config = uvicorn.Config(app, host=host, port=port, log_level="warning")
    server = uvicorn.Server(config)
    tray = None

    def _cleanup(*args):
        nonlocal tray
        if tray:
            try:
                tray.stop()
            except Exception:
                pass
            tray = None
        clear_daemon_state()
        server.should_exit = True

    # 2. Register cleanup handlers
    atexit.register(clear_daemon_state)
    try:
        signal.signal(signal.SIGTERM, _cleanup)
        signal.signal(signal.SIGINT, _cleanup)
    except Exception:
        pass

    # 3. Start System Tray icon if requested
    if with_tray:
        try:
            from devtoolkit.daemon.tray import DevToolkitTray

            def _on_tray_exit():
                server.should_exit = True

            tray = DevToolkitTray(port=port, host=host, on_exit=_on_tray_exit)
            tray.start()
            app.state.tray = tray
        except Exception as e:
            logger.debug(f"Tray initialization skipped: {e}")

    # 4. Run uvicorn server
    try:
        server.run()
    finally:
        if tray:
            try:
                tray.stop()
            except Exception:
                pass
        clear_daemon_state()
