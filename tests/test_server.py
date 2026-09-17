"""Tests for DevToolkit local API server routing and handlers."""

from devtoolkit.server.app import app, get_system, get_tools, get_audit, serve_dashboard


def test_server_routes_registered():
    route_paths = [route.path for route in app.routes]
    assert "/api/system" in route_paths
    assert "/api/tools" in route_paths
    assert "/api/audit" in route_paths
    assert "/api/action/open-folder" in route_paths
    assert "/" in route_paths


def test_get_system_handler():
    info = get_system()
    assert info.os_name is not None
    assert info.arch is not None


def test_get_tools_handler():
    tools = get_tools()
    assert len(tools) >= 8
    tool_ids = {t["id"] for t in tools}
    assert "node" in tool_ids
    assert "python" in tool_ids
    assert "git" in tool_ids


def test_get_audit_handler():
    summary = get_audit()
    assert summary.total_tools >= 8
    assert len(summary.reports) == summary.total_tools


def test_serve_dashboard():
    response = serve_dashboard()
    assert "DevToolkit" in response
    assert "glass-card" in response

