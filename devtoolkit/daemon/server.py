"""Server daemon execution runner with state registration and graceful shutdown."""

import atexit
import os
import signal
import sys
from datetime import datetime, timezone

import uvicorn

from devtoolkit import __version__
from devtoolkit.daemon.models import DaemonState
from devtoolkit.daemon.manager import clear_daemon_state, write_daemon_state
from devtoolkit.server.app import app


def run_daemon_server(host: str = "127.0.0.1", port: int = 4321) -> None:
    """Run uvicorn server in daemon mode, managing state lockfile and signals."""
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

    def _cleanup(*args):
        clear_daemon_state()
        sys.exit(0)

    # 2. Register cleanup handlers
    atexit.register(clear_daemon_state)
    try:
        signal.signal(signal.SIGTERM, _cleanup)
        signal.signal(signal.SIGINT, _cleanup)
    except Exception:
        pass

    # 3. Start uvicorn server
    try:
        uvicorn.run(app, host=host, port=port, log_level="warning")
    finally:
        clear_daemon_state()
