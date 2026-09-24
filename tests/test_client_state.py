"""Tests for ClientState observable reactive store and event bus."""

from unittest.mock import MagicMock

from devtoolkit.client.state import ClientState


def test_client_state_initial_values():
    """Verify initial default state values."""
    state = ClientState()
    assert state.active_view == "environment"
    assert state.daemon_connected is False
    assert state.daemon_version == ""
    assert state.daemon_uptime is None
    assert state.tools == []
    assert state.ports == []
    assert state.search_results == []


def test_client_state_subscription_and_emit():
    """Test subscribing to events and receiving emitted payloads."""
    state = ClientState()
    received = []

    unsub = state.subscribe("custom_event", lambda payload: received.append(payload))
    state.emit("custom_event", {"val": 42})
    assert received == [{"val": 42}]

    # Test unsubscribe
    unsub()
    state.emit("custom_event", {"val": 100})
    assert received == [{"val": 42}]  # Not called again


def test_client_state_wildcard_subscription():
    """Test subscribing with wildcard '*' to receive all events."""
    state = ClientState()
    received = []

    state.subscribe("*", lambda payload: received.append(payload))
    state.emit("event_a", "payload_a")
    state.emit("event_b", "payload_b")
    assert received == ["payload_a", "payload_b"]


def test_client_state_view_mutator():
    """Test set_active_view mutates state and notifies subscribers."""
    state = ClientState()
    mock_cb = MagicMock()
    state.subscribe("view_changed", mock_cb)

    state.set_active_view("ports")
    assert state.active_view == "ports"
    mock_cb.assert_called_once_with("ports")

    # Setting same view does not emit redundantly
    state.set_active_view("ports")
    assert mock_cb.call_count == 1


def test_client_state_daemon_status_mutator():
    """Test set_daemon_status mutates connection telemetry and emits."""
    state = ClientState()
    mock_cb = MagicMock()
    state.subscribe("daemon_status", mock_cb)

    state.set_daemon_status(connected=True, version="1.0.0", uptime=12.5)
    assert state.daemon_connected is True
    assert state.daemon_version == "1.0.0"
    assert state.daemon_uptime == 12.5
    mock_cb.assert_called_once_with({"connected": True, "version": "1.0.0", "uptime": 12.5})


def test_client_state_domain_mutators():
    """Test tools, ports, audit, project, search, and config mutators."""
    state = ClientState()

    # Tools
    tools_cb = MagicMock()
    state.subscribe("tools_updated", tools_cb)
    state.set_tools([{"id": "python", "status": "healthy"}])
    assert len(state.tools) == 1
    tools_cb.assert_called_once()

    # Tool selection
    sel_cb = MagicMock()
    state.subscribe("tool_selected", sel_cb)
    state.set_selected_tool("python", {"path": "C:/python.exe"})
    assert state.selected_tool_id == "python"
    assert state.deep_inspection == {"path": "C:/python.exe"}
    sel_cb.assert_called_once()

    # Ports
    ports_cb = MagicMock()
    state.subscribe("ports_updated", ports_cb)
    state.set_ports([{"port": 8000, "process": "python"}])
    assert len(state.ports) == 1
    ports_cb.assert_called_once()

    # Search
    search_cb = MagicMock()
    state.subscribe("search_updated", search_cb)
    state.set_search_results([{"filename": "app.py"}], query="app")
    assert len(state.search_results) == 1
    assert state.search_query_text == "app"
    search_cb.assert_called_once()

    # Config
    cfg_cb = MagicMock()
    state.subscribe("config_updated", cfg_cb)
    state.set_config({"close_action": "minimize"})
    assert state.config == {"close_action": "minimize"}
    cfg_cb.assert_called_once()
