"""DevToolkit Background Daemon process manager and state coordinator."""

import json
import os
import signal
import subprocess
import sys
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from devtoolkit import __version__
from devtoolkit.daemon.models import DaemonState, DaemonStatusResponse


def get_daemon_state_path() -> Path:
    """Return the absolute path to the daemon persistent state lockfile."""
    env_override = os.environ.get("DEVTOOLKIT_DAEMON_STATE")
    if env_override:
        p = Path(env_override).resolve()
        p.parent.mkdir(parents=True, exist_ok=True)
        return p

    daemon_dir = Path.home() / ".devtoolkit"
    daemon_dir.mkdir(parents=True, exist_ok=True)
    return daemon_dir / "daemon.json"


def read_daemon_state() -> Optional[DaemonState]:
    """Read and validate the daemon state file from disk."""
    state_file = get_daemon_state_path()
    if not state_file.is_file():
        return None
    try:
        data = json.loads(state_file.read_text(encoding="utf-8"))
        return DaemonState(**data)
    except Exception:
        return None


def write_daemon_state(state: DaemonState) -> Path:
    """Persist active daemon state to disk."""
    state_file = get_daemon_state_path()
    state_file.parent.mkdir(parents=True, exist_ok=True)
    state_file.write_text(state.model_dump_json(indent=2), encoding="utf-8")
    return state_file


def clear_daemon_state() -> None:
    """Remove the daemon state file if it exists."""
    state_file = get_daemon_state_path()
    if state_file.exists():
        try:
            state_file.unlink(missing_ok=True)
        except OSError:
            pass


def is_pid_alive(pid: int) -> bool:
    """Check whether a process with the given PID is currently alive."""
    if pid <= 0:
        return False

    if sys.platform == "win32":
        import ctypes
        from ctypes import wintypes

        kernel32 = ctypes.windll.kernel32
        PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
        STILL_ACTIVE = 259

        handle = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
        if not handle:
            return False
        try:
            exit_code = wintypes.DWORD()
            success = kernel32.GetExitCodeProcess(handle, ctypes.byref(exit_code))
            return bool(success and exit_code.value == STILL_ACTIVE)
        finally:
            kernel32.CloseHandle(handle)
    else:
        try:
            os.kill(pid, 0)
            return True
        except (OSError, ProcessLookupError):
            return False


def is_daemon_alive(host: str = "127.0.0.1", port: int = 4321, timeout: float = 1.0) -> bool:
    """Probe the daemon health endpoint to verify active HTTP serving."""
    url = f"http://{host}:{port}/api/health"
    try:
        req = urllib.request.Request(
            url,
            headers={"User-Agent": "DevToolkit-Daemon-Probe"},
        )
        with urllib.request.urlopen(req, timeout=timeout) as response:
            if response.status == 200:
                payload = json.loads(response.read().decode("utf-8"))
                return payload.get("status") == "ok"
    except Exception:
        return False
    return False


def start_daemon(
    port: int = 4321,
    host: str = "127.0.0.1",
    timeout: float = 6.0,
) -> DaemonState:
    """Spawn the DevToolkit background daemon process if not already running."""
    # 1. Check if already alive
    existing_state = read_daemon_state()
    if existing_state and is_pid_alive(existing_state.pid) and is_daemon_alive(existing_state.host, existing_state.port):
        return existing_state

    # Clean up any stale state file
    clear_daemon_state()

    # 2. Build spawn command
    if getattr(sys, "frozen", False):
        cmd = [sys.executable, "daemon", "run", "--port", str(port), "--host", host]
    else:
        cmd = [sys.executable, "-m", "devtoolkit.cli.main", "daemon", "run", "--port", str(port), "--host", host]

    # 3. Spawn detached process
    creationflags = 0
    if sys.platform == "win32":
        # DETACHED_PROCESS (0x08) | CREATE_NEW_PROCESS_GROUP (0x200)
        creationflags = subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP
        proc = subprocess.Popen(
            cmd,
            creationflags=creationflags,
            close_fds=True,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    else:
        proc = subprocess.Popen(
            cmd,
            start_new_session=True,
            close_fds=True,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

    # 4. Wait for health check confirmation
    deadline = time.time() + timeout
    while time.time() < deadline:
        if is_daemon_alive(host, port):
            state = read_daemon_state()
            if state:
                return state
            # If daemon state file write is pending, construct state from PID
            state = DaemonState(
                pid=proc.pid,
                port=port,
                host=host,
                version=__version__,
                started_at=datetime.now(timezone.utc).isoformat(),
                status="running",
            )
            write_daemon_state(state)
            return state
        time.sleep(0.1)

    raise RuntimeError(f"DevToolkit daemon failed to start on {host}:{port} within {timeout}s.")


def stop_daemon(timeout: float = 4.0) -> bool:
    """Terminate the active DevToolkit daemon process gracefully."""
    state = read_daemon_state()
    if not state or not is_pid_alive(state.pid):
        clear_daemon_state()
        return False

    pid = state.pid
    try:
        if sys.platform == "win32":
            # On Windows, os.kill(pid, SIGTERM) invokes TerminateProcess
            os.kill(pid, signal.SIGTERM)
        else:
            os.kill(pid, signal.SIGTERM)
    except (OSError, ProcessLookupError):
        pass

    deadline = time.time() + timeout
    while time.time() < deadline:
        if not is_pid_alive(pid):
            clear_daemon_state()
            return True
        time.sleep(0.1)

    # Force kill if still lingering
    try:
        if sys.platform == "win32":
            subprocess.run(["taskkill", "/F", "/T", "/PID", str(pid)], capture_output=True)
        else:
            os.kill(pid, signal.SIGKILL)
    except Exception:
        pass

    clear_daemon_state()
    return True


def get_daemon_status() -> DaemonStatusResponse:
    """Query and return the live status of the DevToolkit daemon."""
    state_file = get_daemon_state_path()
    state = read_daemon_state()

    if not state or not is_pid_alive(state.pid):
        clear_daemon_state()
        return DaemonStatusResponse(
            running=False,
            state_path=str(state_file),
            message="DevToolkit daemon is not running.",
        )

    alive = is_daemon_alive(state.host, state.port)
    if not alive:
        return DaemonStatusResponse(
            running=False,
            pid=state.pid,
            port=state.port,
            host=state.host,
            state_path=str(state_file),
            message="Daemon process is present but not responding to health probes.",
        )

    # Calculate uptime if started_at is valid ISO timestamp
    uptime_sec = None
    if state.started_at:
        try:
            started = datetime.fromisoformat(state.started_at)
            uptime_sec = round((datetime.now(timezone.utc) - started).total_seconds(), 1)
        except Exception:
            pass

    search_status = None
    try:
        url = f"http://{state.host}:{state.port}/api/search/status"
        req = urllib.request.Request(url, headers={"User-Agent": "DevToolkit-Daemon-Probe"})
        with urllib.request.urlopen(req, timeout=1.0) as resp:
            if resp.status == 200:
                search_status = json.loads(resp.read().decode("utf-8"))
    except Exception:
        pass

    return DaemonStatusResponse(
        running=True,
        pid=state.pid,
        port=state.port,
        host=state.host,
        version=state.version or __version__,
        uptime_seconds=uptime_sec,
        state_path=str(state_file),
        search_status=search_status,
        message=f"DevToolkit daemon active on http://{state.host}:{state.port} (PID {state.pid}).",
    )
