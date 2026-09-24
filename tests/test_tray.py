"""Tests for System Tray subsystem, window close interception, and notification endpoints."""

import sys
from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException

from devtoolkit.core.config import DevToolkitConfig, load_config, set_close_action
from devtoolkit.daemon.tray import (
    ID_EXIT,
    ID_OPEN_BROWSER,
    ID_OPEN_NATIVE,
    ID_OPEN_WINDOW,
    ID_REINDEX,
    ID_RESCAN,
    ID_STATUS,
    NIF_ICON,
    NIF_INFO,
    NIF_MESSAGE,
    NIF_TIP,
    NIIF_INFO,
    NIM_ADD,
    NIM_DELETE,
    NIM_MODIFY,
    WM_TRAYICON,
    DevToolkitTray,
    activate_or_launch_native_ui,
    activate_or_launch_ui,
    find_existing_window,
    restore_window_by_hwnd,
)
from devtoolkit.server.app import app, post_close_action, post_daemon_notify
from devtoolkit.server.models import CloseActionRequest, DaemonNotifyRequest


def test_close_action_configuration(tmp_path, monkeypatch):
    """Verify close_action default and persistent modification."""
    fake_config = tmp_path / "devtoolkit.config.yaml"
    monkeypatch.setenv("DEVTOOLKIT_CONFIG", str(fake_config))

    # 1. Default should be 'ask'
    cfg = load_config()
    assert cfg.close_action == "ask"

    # 2. Modify to 'minimize'
    assert set_close_action("minimize") is True
    cfg2 = load_config()
    assert cfg2.close_action == "minimize"

    # 3. Case-insensitive modification to 'EXIT'
    assert set_close_action("EXIT") is True
    cfg3 = load_config()
    assert cfg3.close_action == "exit"

    # 4. Reject invalid options
    assert set_close_action("invalid_choice") is False
    assert set_close_action("") is False
    cfg4 = load_config()
    assert cfg4.close_action == "exit"


def test_api_routes_registered():
    """Verify /api/config/close-action and /api/daemon/notify routes are registered."""
    route_paths = [route.path for route in app.routes]
    assert "/api/config/close-action" in route_paths
    assert "/api/daemon/notify" in route_paths


def test_post_close_action_handler(tmp_path, monkeypatch):
    """Test post_close_action route handler."""
    fake_config = tmp_path / "devtoolkit.config.yaml"
    monkeypatch.setenv("DEVTOOLKIT_CONFIG", str(fake_config))

    # Valid update
    res = post_close_action(CloseActionRequest(action="minimize"))
    assert res["status"] == "ok"
    assert res["action"] == "minimize"
    assert res["config"].close_action == "minimize"

    # Invalid update raises HTTPException(400)
    with pytest.raises(HTTPException) as exc_info:
        post_close_action(CloseActionRequest(action="destroy"))
    assert exc_info.value.status_code == 400
    assert "Invalid close_action" in exc_info.value.detail


def test_post_daemon_notify_handler():
    """Test post_daemon_notify route handler with inactive and active tray."""
    # 1. Inactive tray
    mock_request = MagicMock()
    mock_request.app.state.tray = None

    res1 = post_daemon_notify(
        DaemonNotifyRequest(title="Test", message="Hello World"),
        request=mock_request,
    )
    assert res1["status"] == "ok"
    assert res1["delivered"] is False

    # 2. Active mock tray
    mock_tray = MagicMock()
    mock_tray.show_notification.return_value = True
    mock_request.app.state.tray = mock_tray

    res2 = post_daemon_notify(
        DaemonNotifyRequest(title="Audit Complete", message="Everything verified", icon_type=1),
        request=mock_request,
    )
    assert res2["status"] == "ok"
    assert res2["delivered"] is True
    mock_tray.show_notification.assert_called_once_with(
        title="Audit Complete", message="Everything verified", icon_type=1
    )


def test_tray_constants_and_ids():
    """Verify menu IDs and Win32 constants are defined accurately."""
    assert ID_OPEN_WINDOW == 1001
    assert ID_OPEN_BROWSER == 1002
    assert ID_RESCAN == 1003
    assert ID_REINDEX == 1004
    assert ID_STATUS == 1005
    assert ID_EXIT == 1006
    assert ID_OPEN_NATIVE == 1007

    assert NIM_ADD == 0
    assert NIM_MODIFY == 1
    assert NIM_DELETE == 2

    assert NIF_MESSAGE == 0x01
    assert NIF_ICON == 0x02
    assert NIF_TIP == 0x04
    assert NIF_INFO == 0x10
    assert NIIF_INFO == 1
    assert WM_TRAYICON == 0x0400 + 20


@pytest.mark.skipif(sys.platform != "win32", reason="Win32 ctypes structures only on Windows")
def test_tray_ctypes_structure_sizes():
    """Verify Win32 ctypes structure alignment and sizes."""
    import ctypes
    from devtoolkit.daemon.tray import NOTIFYICONDATAW, WNDCLASSEX

    nid_size = ctypes.sizeof(NOTIFYICONDATAW)
    assert nid_size in (952, 976)

    wc_size = ctypes.sizeof(WNDCLASSEX)
    assert wc_size > 0


def test_devtoolkit_tray_callbacks():
    """Verify DevToolkitTray callback dispatch mechanism."""
    mock_open_win = MagicMock()
    mock_open_native = MagicMock()
    mock_open_browser = MagicMock()
    mock_rescan = MagicMock()
    mock_reindex = MagicMock()
    mock_exit = MagicMock()

    tray = DevToolkitTray(
        port=4321,
        host="127.0.0.1",
        on_open_window=mock_open_win,
        on_open_native=mock_open_native,
        on_open_browser=mock_open_browser,
        on_rescan=mock_rescan,
        on_reindex=mock_reindex,
        on_exit=mock_exit,
    )

    # Primary click callback
    tray._handle_primary_click()
    mock_open_win.assert_called_once()

    # Native UI click callback
    tray._handle_open_native()
    mock_open_native.assert_called_once()

    # Browser callback
    tray._handle_open_browser()
    mock_open_browser.assert_called_once()

    # Rescan callback
    tray._handle_rescan()
    mock_rescan.assert_called_once()

    # Reindex callback
    tray._handle_reindex()
    mock_reindex.assert_called_once()

    # Exit callback
    with patch("devtoolkit.daemon.tray.find_existing_window", return_value=None):
        with patch("devtoolkit.daemon.manager.stop_daemon") as mock_stop:
            tray._handle_exit()
            mock_exit.assert_called_once()
            mock_stop.assert_not_called()


def test_window_helpers_mocked():
    """Test window restore and activation helper functions."""
    # Test activate_or_launch_ui when window already exists
    with patch("devtoolkit.daemon.tray.find_existing_window", return_value=12345):
        with patch("devtoolkit.daemon.tray.restore_window_by_hwnd", return_value=True) as mock_restore:
            with patch("subprocess.Popen") as mock_popen:
                result = activate_or_launch_ui(port=4321)
                assert result is True
                mock_restore.assert_called_once_with(12345)
                mock_popen.assert_not_called()

    # Test activate_or_launch_ui when window does NOT exist -> launches subprocess
    with patch("devtoolkit.daemon.tray.find_existing_window", return_value=None):
        with patch("subprocess.Popen") as mock_popen:
            result = activate_or_launch_ui(port=4321)
            assert result is True
            mock_popen.assert_called_once()

    # Test activate_or_launch_native_ui when window already exists
    with patch("devtoolkit.daemon.tray.find_existing_window", return_value=54321):
        with patch("devtoolkit.daemon.tray.restore_window_by_hwnd", return_value=True) as mock_restore:
            with patch("subprocess.Popen") as mock_popen:
                result = activate_or_launch_native_ui(port=4321)
                assert result is True
                mock_restore.assert_called_once_with(54321)
                mock_popen.assert_not_called()

    # Test activate_or_launch_native_ui when window does NOT exist -> launches subprocess
    with patch("devtoolkit.daemon.tray.find_existing_window", return_value=None):
        with patch("subprocess.Popen") as mock_popen:
            result = activate_or_launch_native_ui(port=4321)
            assert result is True
            mock_popen.assert_called_once()


def test_tray_lifecycle_graceful():
    """Test DevToolkitTray start and stop lifecycle handles graceful shutdown."""
    tray = DevToolkitTray(port=4321)
    assert not tray.is_running
    started = tray.start()
    assert isinstance(started, bool)
    tray.stop()
    assert not tray.is_running
