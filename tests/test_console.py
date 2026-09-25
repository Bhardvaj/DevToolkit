"""Tests for DevToolkit console detection and window suppression utilities."""

import os
import sys
from unittest.mock import MagicMock, patch

import pytest

from devtoolkit.core.console import (
    SW_HIDE,
    SW_SHOW,
    get_console_pids,
    hide_console_window,
    is_standalone_console,
    show_console_window,
)


def test_get_console_pids():
    """Verify get_console_pids returns a list of integers."""
    pids = get_console_pids()
    assert isinstance(pids, list)
    if sys.platform == "win32":
        for pid in pids:
            assert isinstance(pid, int)
            assert pid > 0
    else:
        assert pids == []


def test_is_standalone_console_dev_mode():
    """In uncompiled development mode, the developer's console must never be suppressed."""
    assert is_standalone_console() is False


def test_hide_console_window_in_dev_mode():
    """hide_console_window must return False and not hide console in development mode."""
    assert hide_console_window() is False


def test_is_standalone_console_non_windows():
    """On non-Windows platforms, standalone console detection always returns False."""
    with patch("sys.platform", "linux"):
        assert is_standalone_console() is False
        assert hide_console_window() is False
        assert show_console_window() is False


def test_is_standalone_console_mocked_standalone():
    """Verify standalone detection when only instances of DevToolkit.exe are attached."""
    with patch("sys.platform", "win32"), \
         patch.object(sys, "frozen", True, create=True), \
         patch.object(sys, "executable", r"C:\Tools\DevToolkit.exe"), \
         patch("devtoolkit.core.console.get_console_pids", return_value=[1001, 1002]), \
         patch("ctypes.windll.kernel32") as mock_k32:

        mock_k32.GetConsoleWindow.return_value = 54321
        mock_k32.OpenProcess.return_value = 9999

        def mock_query(h, flags, buf, size_ref):
            buf.value = r"C:\Tools\DevToolkit.exe"
            return 1

        mock_k32.QueryFullProcessImageNameW.side_effect = mock_query

        assert is_standalone_console() is True


def test_is_standalone_console_mocked_shell_present():
    """Verify standalone detection returns False when an interactive shell is in the console."""
    with patch("sys.platform", "win32"), \
         patch.object(sys, "frozen", True, create=True), \
         patch.object(sys, "executable", r"C:\Tools\DevToolkit.exe"), \
         patch("devtoolkit.core.console.get_console_pids", return_value=[1001, 2002]), \
         patch("ctypes.windll.kernel32") as mock_k32:

        mock_k32.GetConsoleWindow.return_value = 54321
        mock_k32.OpenProcess.return_value = 9999

        call_count = 0

        def mock_query(h, flags, buf, size_ref):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                buf.value = r"C:\Tools\DevToolkit.exe"
            else:
                buf.value = r"C:\Windows\System32\powershell.exe"
            return 1

        mock_k32.QueryFullProcessImageNameW.side_effect = mock_query

        assert is_standalone_console() is False


def test_is_standalone_console_mocked_count_exceeded():
    """Verify standalone detection returns False when count > 2 (multiple processes in console)."""
    with patch("sys.platform", "win32"), \
         patch.object(sys, "frozen", True, create=True), \
         patch.object(sys, "executable", r"C:\Tools\DevToolkit.exe"), \
         patch("devtoolkit.core.console.get_console_pids", return_value=[1001, 1002, 1003]), \
         patch("ctypes.windll.kernel32") as mock_k32:

        mock_k32.GetConsoleWindow.return_value = 54321
        assert is_standalone_console() is False


def test_hide_console_window_mocked():
    """Verify hide_console_window invokes ShowWindow with SW_HIDE when standalone."""
    with patch("devtoolkit.core.console.is_standalone_console", return_value=True), \
         patch("sys.platform", "win32"), \
         patch("ctypes.windll.kernel32") as mock_k32, \
         patch("ctypes.windll.user32") as mock_u32:

        mock_k32.GetConsoleWindow.return_value = 54321

        result = hide_console_window()
        assert result is True
        mock_u32.ShowWindow.assert_called_once_with(54321, SW_HIDE)


def test_show_console_window_mocked():
    """Verify show_console_window invokes ShowWindow with SW_SHOW."""
    with patch("sys.platform", "win32"), \
         patch("ctypes.windll.kernel32") as mock_k32, \
         patch("ctypes.windll.user32") as mock_u32:

        mock_k32.GetConsoleWindow.return_value = 54321

        result = show_console_window()
        assert result is True
        mock_u32.ShowWindow.assert_called_once_with(54321, SW_SHOW)
