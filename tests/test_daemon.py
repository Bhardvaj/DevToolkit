"""Tests for DevToolkit background daemon, PID registry, and process management."""

import os
import time
from pathlib import Path
import pytest
from devtoolkit import __version__
from devtoolkit.daemon.models import DaemonState, DaemonStatusResponse
from devtoolkit.daemon.manager import (
    clear_daemon_state,
    get_daemon_state_path,
    get_daemon_status,
    is_daemon_alive,
    is_pid_alive,
    read_daemon_state,
    start_daemon,
    stop_daemon,
    write_daemon_state,
)
from devtoolkit.server.app import app, get_health


@pytest.fixture
def temp_daemon_state(tmp_path, monkeypatch):
    """Isolate daemon state file to a temporary path during tests."""
    temp_file = tmp_path / "daemon.json"
    monkeypatch.setenv("DEVTOOLKIT_DAEMON_STATE", str(temp_file))
    yield temp_file
    if temp_file.exists():
        temp_file.unlink(missing_ok=True)


def test_api_health_endpoint():
    """Test that the /api/health route is registered and handler returns status ok."""
    route_paths = [route.path for route in app.routes]
    assert "/api/health" in route_paths

    data = get_health()
    assert data["status"] == "ok"
    assert data["app"] == "devtoolkit"
    assert data["version"] == __version__
    assert data["pid"] == os.getpid()
    assert "timestamp" in data


def test_daemon_state_serialization():
    """Test DaemonState Pydantic model serialization and round-trip."""
    state = DaemonState(
        pid=1234,
        port=4321,
        host="127.0.0.1",
        version="0.5.1",
        started_at="2026-09-24T00:00:00Z",
        status="running",
    )
    raw = state.model_dump_json()
    assert "1234" in raw
    assert "4321" in raw

    loaded = DaemonState.model_validate_json(raw)
    assert loaded.pid == 1234
    assert loaded.port == 4321
    assert loaded.version == "0.5.1"


def test_daemon_state_file_lifecycle(temp_daemon_state):
    """Test creating, reading, and clearing the daemon.json state file."""
    assert not temp_daemon_state.exists()
    assert read_daemon_state() is None

    state = DaemonState(
        pid=os.getpid(),
        port=4321,
        host="127.0.0.1",
        version=__version__,
        started_at="2026-09-24T00:00:00Z",
    )
    p = write_daemon_state(state)
    assert p == temp_daemon_state
    assert temp_daemon_state.is_file()

    read_state = read_daemon_state()
    assert read_state is not None
    assert read_state.pid == os.getpid()
    assert read_state.port == 4321

    clear_daemon_state()
    assert not temp_daemon_state.exists()
    assert read_daemon_state() is None


def test_is_pid_alive():
    """Test process liveness checks for active and non-existent PIDs."""
    # Current process is always alive
    assert is_pid_alive(os.getpid()) is True

    # Invalid or non-existent PID should be False
    assert is_pid_alive(0) is False
    assert is_pid_alive(-1) is False
    assert is_pid_alive(99999999) is False


def test_daemon_status_when_stopped(temp_daemon_state):
    """Test get_daemon_status when no daemon is active."""
    status = get_daemon_status()
    assert isinstance(status, DaemonStatusResponse)
    assert status.running is False
    assert "not running" in status.message


def test_daemon_status_stale_pid_cleanup(temp_daemon_state):
    """Test that a stale daemon.json with a non-existent PID is cleaned up automatically."""
    stale_state = DaemonState(
        pid=99999999,
        port=4321,
        host="127.0.0.1",
        version="0.1.0",
        started_at="2026-01-01T00:00:00Z",
    )
    write_daemon_state(stale_state)
    assert temp_daemon_state.is_file()

    # get_daemon_status should detect stale PID and clean up state file
    status = get_daemon_status()
    assert status.running is False
    assert not temp_daemon_state.exists()


def test_daemon_spawn_and_terminate(temp_daemon_state):
    """Integration test: start background daemon on custom port and terminate it cleanly."""
    test_port = 4567

    # Ensure stopped before start
    stop_daemon()
    assert not is_daemon_alive(port=test_port)

    # Start detached daemon
    state = start_daemon(port=test_port, host="127.0.0.1", timeout=6.0)
    assert state is not None
    assert state.port == test_port
    assert is_pid_alive(state.pid)

    try:
        # Verify HTTP health probe responds
        assert is_daemon_alive(port=test_port, timeout=2.0) is True

        # Verify get_daemon_status detects active daemon
        status = get_daemon_status()
        assert status.running is True
        assert status.pid == state.pid
        assert status.port == test_port
    finally:
        # Gracefully stop daemon
        stopped = stop_daemon(timeout=5.0)
        assert stopped is True
        assert not is_pid_alive(state.pid)
        assert not is_daemon_alive(port=test_port)
        assert read_daemon_state() is None
