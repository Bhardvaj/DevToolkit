"""Unit tests for Spotlight native application and process icon extraction."""

from __future__ import annotations

import os
import sys
import pytest
from clients.spotlight.icons import get_app_icon_data_url, warm_icons_background


def test_get_app_icon_data_url_invalid():
    assert get_app_icon_data_url("") is None
    assert get_app_icon_data_url("C:\\NonExistent\\Path\\fake_app_12345.exe") is None


@pytest.mark.skipif(sys.platform != "win32", reason="Windows only test")
def test_get_app_icon_data_url_notepad():
    url = get_app_icon_data_url("C:\\Windows\\notepad.exe")
    assert url is not None
    assert url.startswith("data:image/png;base64,")
    # Verify cached call returns identical URL instantaneously
    assert get_app_icon_data_url("C:\\Windows\\notepad.exe") == url


@pytest.mark.skipif(sys.platform != "win32", reason="Windows only test")
def test_warm_icons_background():
    warm_icons_background(["C:\\Windows\\notepad.exe", "C:\\Windows\\explorer.exe"])
