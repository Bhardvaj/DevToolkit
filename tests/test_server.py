"""Tests for DevToolkit local API server routing and handlers."""

from pathlib import Path
from devtoolkit.server.app import (
    app,
    get_system,
    get_tools,
    get_audit,
    stream_audit,
    get_config,
    post_search_path,
    delete_search_path,
    serve_dashboard,
    SearchPathRequest,
    get_ports,
    post_kill_port,
    post_audit_project,
    KillPortRequest,
    ProjectAuditRequest,
    SelectFolderRequest,
    post_select_folder,
)


def test_server_routes_registered():
    route_paths = [route.path for route in app.routes]
    assert "/api/system" in route_paths
    assert "/api/tools" in route_paths
    assert "/api/audit" in route_paths
    assert "/api/audit/stream" in route_paths
    assert "/api/config" in route_paths
    assert "/api/config/search-paths" in route_paths
    assert "/api/action/open-folder" in route_paths
    assert "/api/action/apply-fix" in route_paths
    assert "/api/action/select-folder" in route_paths
    assert "/api/ports" in route_paths
    assert "/api/ports/kill" in route_paths
    assert "/api/project/audit" in route_paths
    assert "/api/tool/{tool_id}/deep" in route_paths
    assert "/" in route_paths


def test_get_system_handler():
    info = get_system()
    assert info.os_name is not None
    assert info.arch is not None
    assert info.app_version == "0.2.0"


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


def test_ports_handlers():
    ports = get_ports(dev_only=False)
    assert isinstance(ports, list)

    # Test kill port handler on non-existent port
    res = post_kill_port(KillPortRequest(port=99999, force=False))
    assert res.success is False
    assert "No active process" in res.message


def test_project_audit_handler(tmp_path):
    res = post_audit_project(ProjectAuditRequest(path=str(tmp_path)))
    assert res.project_name == tmp_path.name
    assert "Generic Workspace" in [c.name for c in res.checks]


def test_config_handlers(tmp_path, monkeypatch):
    test_cfg = tmp_path / "test_config.yaml"
    monkeypatch.setattr("devtoolkit.core.config.get_config_path", lambda: test_cfg)

    cfg = get_config()
    assert hasattr(cfg, "search_paths")

    custom_dir = tmp_path / "custom_tools"
    custom_dir.mkdir()

    # Add path
    res = post_search_path(SearchPathRequest(path=str(custom_dir)))
    assert res["status"] == "ok"
    assert str(custom_dir) in res["config"].search_paths

    # Remove path by exact path
    del_res = delete_search_path(SearchPathRequest(path=str(custom_dir)))
    assert del_res["status"] == "ok"
    assert del_res["removed"] is True
    assert str(custom_dir) not in del_res["config"].search_paths

    # Remove non-existent path
    del_res2 = delete_search_path(SearchPathRequest(path=str(custom_dir)))
    assert del_res2["status"] == "ok"
    assert del_res2["removed"] is False

    # Re-add and remove by index
    post_search_path(SearchPathRequest(path=str(custom_dir)))
    assert str(custom_dir) in get_config().search_paths
    del_idx_res = delete_search_path(SearchPathRequest(index=0))
    assert del_idx_res["status"] == "ok"
    assert del_idx_res["removed"] is True
    assert len(del_idx_res["config"].search_paths) == 0


def test_serve_dashboard():
    response = serve_dashboard()
    assert "DevToolkit" in response
    assert "WORKSPACE HUB" in response
    assert "Environment" in response
    assert "Port Manager" in response
    assert "Project Auditor" in response
    assert "Environment Watcher" in response
    # Dynamic System & Software Info
    assert "side-os-info" in response
    assert "side-host-name" in response
    assert "side-app-version" in response
    assert "side-python-version" in response
    assert "DEXTER-2" not in response
    assert "Windows 11 (x64)" not in response
    # Phase 5 UI & UX additions
    assert "inspector-drawer" in response
    assert "stat-filter-card" in response
    assert "export-btn" in response
    assert "ports-grouped-container" in response
    assert "rep-score-pct" in response
    assert "project-recent-chips" in response
    assert "openInspectorDrawer" in response
    assert "toggleStatusFilter" in response
    assert "ports-refresh-icon" in response
    assert "skeleton-shimmer" in response
    assert "btn-browse-project" in response
    assert "btn-browse-settings" in response
    assert "browseProjectFolder" in response
    assert "browseSettingsFolder" in response


def test_stream_audit_handler():
    response = stream_audit()
    assert response.media_type == "text/event-stream"


def test_apply_fix_handler():
    from devtoolkit.server.app import post_apply_fix, ApplyFixRequest

    res = post_apply_fix(ApplyFixRequest(command="npm install -g example-cli"))
    assert res["status"] in ("info", "ok")
    assert "npm install" in res["message"]


def test_select_folder_handler(monkeypatch):
    import subprocess
    from collections import namedtuple

    MockResult = namedtuple("MockResult", ["stdout", "returncode"])

    # Test cancelled / empty selection
    monkeypatch.setattr(subprocess, "run", lambda *args, **kwargs: MockResult(stdout="", returncode=0))
    res = post_select_folder(SelectFolderRequest(initial_path="."))
    assert res["status"] == "cancelled"
    assert res["path"] is None

    # Test successful selection
    monkeypatch.setattr(subprocess, "run", lambda *args, **kwargs: MockResult(stdout=r"C:\TestProject", returncode=0))
    res = post_select_folder(SelectFolderRequest(initial_path="C:\\"))
    assert res["status"] == "ok"
    assert "TestProject" in res["path"]


