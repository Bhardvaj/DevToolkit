"""Unit tests for DevToolkit Spotlight query prefix routing and mode execution."""

from __future__ import annotations

from unittest.mock import MagicMock
import pytest
from clients.spotlight.dispatcher import dispatch_query
from clients.spotlight.modes.actions import execute_action, list_system_actions
from clients.spotlight.modes.guide import get_command_guide
from clients.spotlight.modes.ports import kill_target_port, query_ports
from clients.spotlight.modes.tools import query_tools


def test_dispatch_empty_query():
    assert dispatch_query("") == []
    assert dispatch_query("   ") == []


def test_dispatch_guide_mode():
    res = dispatch_query("?")
    assert len(res) >= 5
    for item in res:
        assert item["type"] == "guide"
        assert "title" in item
        assert "subtitle" in item
        assert "badge" in item


def test_dispatch_calc_mode():
    res = dispatch_query("= 128 * 4")
    assert len(res) == 1
    assert res[0]["title"] == "512"
    assert res[0]["badge"] == "CALC"


def test_dispatch_system_actions():
    res = dispatch_query(">")
    assert len(res) >= 6
    commands = [item["command"] for item in res]
    assert "settings" in commands
    assert "config" in commands
    assert "dashboard" in commands
    assert "reindex" in commands
    assert "rescan" in commands
    assert "logs" in commands
    assert "quit" in commands
    assert "daemon" in commands

    # Filtering
    filtered = dispatch_query("> sett")
    assert len(filtered) == 1
    assert filtered[0]["command"] == "settings"

    d_filtered = dispatch_query("> daemon")
    assert len(d_filtered) >= 1
    assert d_filtered[0]["command"] == "daemon"


def test_dispatch_window_walker():
    res = dispatch_query("w:")
    # On Windows this queries EnumWindows; on any OS it returns a list
    assert isinstance(res, list)


def test_dispatch_ports_offline():
    res = dispatch_query("port:")
    assert len(res) == 1
    assert "Offline" in res[0]["title"]
    assert res[0]["action"] == "start_daemon"


def test_dispatch_ports_online():
    mock_client = MagicMock()
    mock_client.is_alive.return_value = True
    mock_client.get_ports.return_value = [
        {
            "port": 3000,
            "protocol": "TCP",
            "pid": 1234,
            "process_name": "node.exe",
            "is_dev": True,
        },
        {
            "port": 5432,
            "protocol": "TCP",
            "pid": 5678,
            "process_name": "postgres.exe",
            "is_dev": False,
        },
    ]

    # Query all ports
    res = dispatch_query("port:", client=mock_client)
    assert len(res) == 2
    assert res[0]["title"] == ":3000 node.exe (PID 1234)"
    assert res[0]["badge"] == "DEV"
    assert res[0]["action"] == "drilldown_port"

    # Query dev ports only
    dev_res = dispatch_query("port:dev", client=mock_client)
    assert len(dev_res) == 1
    assert dev_res[0]["title"] == ":3000 node.exe (PID 1234)"

    # Query specific port detail
    spec_res = dispatch_query("port:3000", client=mock_client)
    assert len(spec_res) == 1
    assert spec_res[0]["action"] == "open_browser"  # Dev port opens browser on Enter

    spec_db = dispatch_query("port:5432", client=mock_client)
    assert len(spec_db) == 1
    assert spec_db[0]["action"] == "kill_port"  # Non-dev port kills on Enter

    # Port kill command
    kill_res = dispatch_query("port:3000 kill", client=mock_client)
    assert len(kill_res) == 1
    assert kill_res[0]["action"] == "kill_port"


def test_dispatch_ports_dev_with_daemon_is_dev_port():
    """Verify port:dev works with authentic daemon PortInfo serialization containing is_dev_port."""
    mock_client = MagicMock()
    mock_client.is_alive.return_value = True
    mock_client.get_ports.return_value = [
        {
            "port": 5173,
            "protocol": "TCP",
            "pid": 1111,
            "process_name": "vite.exe",
            "address": "127.0.0.1",
            "is_dev_port": True,
            "is_dev": True,
            "is_system_critical": False,
            "category": "Dev",
        },
        {
            "port": 5432,
            "protocol": "TCP",
            "pid": 2222,
            "process_name": "postgres.exe",
            "address": "127.0.0.1",
            "is_dev_port": True,
            "is_dev": True,
            "is_system_critical": False,
            "category": "Database",
        },
        {
            "port": 135,
            "protocol": "TCP",
            "pid": 3333,
            "process_name": "svchost.exe",
            "address": "0.0.0.0",
            "is_dev_port": False,
            "is_dev": False,
            "is_system_critical": True,
            "category": "System",
        },
    ]

    # Query port:dev
    dev_res = dispatch_query("port:dev", client=mock_client)
    assert len(dev_res) == 2
    ports = [item["port"] for item in dev_res]
    assert 5173 in ports
    assert 5432 in ports
    assert 135 not in ports

    # When no dev ports match
    mock_client.get_ports.return_value = [
        {
            "port": 135,
            "protocol": "TCP",
            "pid": 3333,
            "process_name": "svchost.exe",
            "address": "0.0.0.0",
            "is_dev_port": False,
            "is_dev": False,
            "is_system_critical": True,
            "category": "System",
        }
    ]
    empty_res = dispatch_query("port:dev", client=mock_client)
    assert len(empty_res) == 1
    assert empty_res[0]["id"] == "port_no_dev"
    assert "No Active Dev Ports Found" in empty_res[0]["title"]


def test_dispatch_tools():
    mock_client = MagicMock()
    mock_client.is_alive.return_value = True
    mock_client.get_tools.return_value = [
        {
            "id": "node",
            "name": "Node.js",
            "status": "healthy",
            "version": "v20.10.0",
            "path": "C:\\Program Files\\nodejs\\node.exe",
        },
        {
            "id": "python",
            "name": "Python",
            "status": "healthy",
            "version": "3.12.0",
            "path": "C:\\Python312\\python.exe",
        },
    ]

    res = dispatch_query("tool:", client=mock_client)
    assert len(res) == 2
    assert res[0]["title"] == "Node.js v20.10.0"
    assert res[0]["badge"] == "HEALTHY"
    assert res[0]["action"] == "drilldown_tool"

    # Query specific tool
    node_res = dispatch_query("tool:node", client=mock_client)
    assert len(node_res) == 1
    assert node_res[0]["title"] == "Node.js v20.10.0 [Healthy]"
    assert node_res[0]["action"] == "open_deep_drawer"


def test_dispatch_tools_health_statuses_and_sorting():
    """Verify authentic health statuses (ACTION NEEDED, HEALTHY, NOT DETECTED) and prioritization."""
    mock_client = MagicMock()
    mock_client.is_alive.return_value = True
    mock_client.get_tools.return_value = [
        {
            "id": "ollama",
            "name": "Ollama",
            "installed": False,
            "status": "not_found",
            "version": None,
            "category": "ai",
        },
        {
            "id": "python",
            "name": "Python",
            "installed": True,
            "status": "healthy",
            "version": "3.14.5",
            "category": "languages",
            "path": "C:\\Python314\\python.exe",
        },
        {
            "id": "docker",
            "name": "Docker Desktop",
            "installed": True,
            "status": "warning",
            "version": "24.0.7",
            "category": "containers",
            "diagnostics": [{"message": "Docker engine daemon is not running."}],
        },
    ]

    # Query all tools
    res = dispatch_query("tool:", client=mock_client)
    assert len(res) == 3

    # Priority 1: Action Needed / Warning
    assert res[0]["title"] == "Docker Desktop v24.0.7"
    assert res[0]["badge"] == "ACTION NEEDED"
    assert "Action Needed: Docker engine daemon is not running." in res[0]["subtitle"]

    # Priority 2: Healthy
    assert res[1]["title"] == "Python v3.14.5"
    assert res[1]["badge"] == "HEALTHY"
    assert "Healthy" in res[1]["subtitle"]

    # Priority 3: Not Detected
    assert res[2]["title"] == "Ollama"
    assert res[2]["badge"] == "NOT DETECTED"
    assert "Not Detected" in res[2]["subtitle"]


def test_dispatch_tools_alias_and_t_removal():
    """Verify tools: alias works and short prefix t: is excluded from tools routing."""
    mock_client = MagicMock()
    mock_client.is_alive.return_value = True
    mock_client.get_tools.return_value = [
        {
            "id": "git",
            "name": "Git",
            "installed": True,
            "status": "healthy",
            "version": "2.43.0",
            "category": "vcs",
            "path": "C:\\Program Files\\Git\\cmd\\git.exe",
        }
    ]
    mock_client.get.return_value = {"results": []}

    # tools: alias must work
    tools_res = dispatch_query("tools:", client=mock_client)
    assert len(tools_res) == 1
    assert tools_res[0]["title"] == "Git v2.43.0"
    assert tools_res[0]["badge"] == "HEALTHY"

    # t: must NOT route to tools; it must fall through to default search
    t_res = dispatch_query("t:", client=mock_client)
    # Default search with empty results from mock_client.get returns []
    assert t_res == []


def test_dispatch_default_search_online():
    mock_client = MagicMock()
    mock_client.is_alive.return_value = True
    mock_client.get.return_value = {
        "results": [
            {
                "name": "Visual Studio Code",
                "path": "C:\\VSCode\\Code.exe",
                "entry_type": "app",
                "is_dir": False,
            }
        ]
    }

    res = dispatch_query("vsc", client=mock_client)
    assert len(res) == 1
    assert res[0]["title"] == "Visual Studio Code"
    assert res[0]["badge"] == "APP"
    assert res[0]["action"] == "launch_app"


def test_window_manager_dimensions_and_reset():
    from clients.spotlight.window import (
        DEFAULT_BAR_HEIGHT,
        DEFAULT_EMPTY_HEIGHT,
        MAX_WINDOW_HEIGHT,
        WINDOW_WIDTH,
        SpotlightWindowManager,
    )

    assert WINDOW_WIDTH == 840
    assert DEFAULT_BAR_HEIGHT == 58
    assert DEFAULT_EMPTY_HEIGHT == 92
    assert MAX_WINDOW_HEIGHT == 640

    mock_client = MagicMock()
    wm = SpotlightWindowManager(client=mock_client)
    mock_window = MagicMock()
    wm.window = mock_window

    assert wm._current_height == 92

    # Height clamping tests
    wm.set_height(30)
    assert wm._current_height == 58

    wm.set_height(800)
    assert wm._current_height == 640

    wm.set_height(400)
    assert wm._current_height == 400

    # Show with reset=True evaluates resetSpotlight
    wm.show(reset=True)
    mock_window.evaluate_js.assert_called_with("if(window.resetSpotlight){ window.resetSpotlight(); }")

    # Hide evaluates resetSpotlight
    mock_window.evaluate_js.reset_mock()
    wm.hide()
    mock_window.evaluate_js.assert_called_with("if(window.resetSpotlight){ window.resetSpotlight(); }")


def test_spotlight_empty_state_and_daemon_status():
    from clients.spotlight.window import SpotlightJSAPI

    mock_wm = MagicMock()
    mock_client = MagicMock()

    # When offline: empty state is [] and get_daemon_status reflects offline
    mock_client.is_alive.return_value = False
    api_offline = SpotlightJSAPI(mock_wm, mock_client)
    assert api_offline.get_empty_state() == []
    status_offline = api_offline.get_daemon_status()
    assert status_offline["online"] is False
    assert status_offline["status"] == "offline"

    # When online: empty state is [] and get_daemon_status reflects online
    mock_client.is_alive.return_value = True
    api_online = SpotlightJSAPI(mock_wm, mock_client)
    assert api_online.get_empty_state() == []
    status_online = api_online.get_daemon_status()
    assert status_online["online"] is True
    assert status_online["status"] == "online"


def test_native_app_icon_extraction():
    import sys
    from clients.spotlight.icons import get_app_icon_data_url, get_process_icon_data_url

    assert get_app_icon_data_url("") is None
    assert get_app_icon_data_url("non_existent_file_xyz.exe") is None
    assert get_process_icon_data_url(0) is None

    if sys.platform == "win32":
        import os
        notepad = os.path.join(os.environ.get("SystemRoot", r"C:\Windows"), "notepad.exe")
        if os.path.exists(notepad):
            icon_url = get_app_icon_data_url(notepad)
            assert icon_url is not None
            assert icon_url.startswith("data:image/png;base64,")
            # Verify caching
            assert get_app_icon_data_url(notepad) == icon_url


def test_dispatch_enabled_scopes_filtering():
    # 1. Calc disabled
    assert dispatch_query("= 128 * 4", enabled_scopes=["app", "file"]) == []
    assert len(dispatch_query("= 128 * 4", enabled_scopes=["calc"])) == 1

    # 2. Action mode disabled
    assert dispatch_query(">", enabled_scopes=["app", "file"]) == []
    assert len(dispatch_query(">", enabled_scopes=["action"])) >= 6

    # 3. Port disabled
    assert dispatch_query("port:", enabled_scopes=["app", "calc"]) == []

    # 4. Tool disabled
    assert dispatch_query("tool:", enabled_scopes=["app", "calc"]) == []

    # 5. Project disabled
    assert dispatch_query("proj:.", enabled_scopes=["app", "calc"]) == []

    # 6. Window walker disabled
    assert dispatch_query("w:", enabled_scopes=["app", "calc"]) == []




