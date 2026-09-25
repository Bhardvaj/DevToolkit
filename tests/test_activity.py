"""Tests for daemon background activity tracking and UI synchronization."""

import pytest
from devtoolkit.daemon.activity import get_activity_tracker
from devtoolkit.server.app import app
from devtoolkit.server.routes.system import get_daemon_activity


def test_activity_tracker_lifecycle():
    """Verify ActivityTracker records start and finish states for scan and index."""
    tracker = get_activity_tracker()

    tracker.start_scan("Testing scan start")
    status = tracker.get_status()
    assert status["is_scanning"] is True
    assert status["last_scan_message"] == "Testing scan start"

    tracker.finish_scan("Testing scan finish")
    status = tracker.get_status()
    assert status["is_scanning"] is False
    assert status["last_scan_message"] == "Testing scan finish"
    assert status["scan_count"] >= 1

    tracker.start_index("Testing index start")
    status = tracker.get_status()
    assert status["is_indexing"] is True

    tracker.finish_index("Testing index finish")
    status = tracker.get_status()
    assert status["is_indexing"] is False
    assert status["index_count"] >= 1


def test_daemon_activity_endpoint():
    """Verify /api/daemon/activity endpoint handler returns live status dictionary."""
    route_paths = [route.path for route in app.routes]
    assert "/api/daemon/activity" in route_paths

    data = get_daemon_activity()
    assert isinstance(data, dict)
    assert "is_scanning" in data
    assert "is_indexing" in data
    assert "scan_count" in data
    assert "index_count" in data

