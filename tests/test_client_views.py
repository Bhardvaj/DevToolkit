"""Unit tests for DevToolkit Python Native UI Views, Dialogs, and Interactions."""

import os
import tkinter as tk
from unittest.mock import MagicMock, patch
import pytest

from devtoolkit.client.api import DevToolkitClient
from devtoolkit.client.app import DevToolkitApp
from devtoolkit.client.dialogs.tool_inspector import ToolInspectorModal
from devtoolkit.client.state import ClientState
from devtoolkit.client.views import (
    EnvironmentView,
    PortManagerView,
    ProjectAuditorView,
    SearchView,
    SettingsView,
)


@pytest.fixture
def mock_client():
    """Mock DevToolkitClient with synchronous background dispatch for tests."""
    client = MagicMock(spec=DevToolkitClient)
    client.base_url = "http://127.0.0.1:4321"
    client.port = 4321
    client.host = "127.0.0.1"

    # Synchronous run_async for deterministic testing
    def sync_run_async(task_fn, *args, callback=None, errback=None, **kwargs):
        try:
            res = task_fn(*args, **kwargs)
            if callback:
                callback(res)
        except Exception as e:
            if errback:
                errback(e)
        mock_thread = MagicMock()
        return mock_thread

    client.run_async.side_effect = sync_run_async
    return client


# -----------------------------------------------------------------------------
# Environment View & Tool Inspector Tests
# -----------------------------------------------------------------------------

def test_environment_view_metrics_and_filter(tk_root, mock_client):
    """Test EnvironmentView metrics calculation and real-time filtering."""
    state = ClientState()
    state.set_tools([
        {
            "id": "python",
            "name": "Python",
            "category": "runtimes",
            "version": "3.12.0",
            "status": "healthy",
            "installed": True,
            "binary_path": "C:\\Python\\python.exe",
        },
        {
            "id": "rust",
            "name": "Rust (rustc)",
            "category": "compilers",
            "version": None,
            "status": "not_found",
            "installed": False,
            "binary_path": None,
        },
    ])

    view = EnvironmentView(parent=tk_root, client=mock_client, state=state)

    # Check metrics
    assert view.metric_labels["total"].cget("text") == "2"
    assert view.metric_labels["installed"].cget("text") == "1"
    assert view.metric_labels["missing"].cget("text") == "1"
    assert view.metric_labels["health"].cget("text") == "50.0%"

    # Verify rows in treeview
    children = view.tree.get_children()
    assert len(children) == 2

    # Filter by category
    view.category_var.set("runtimes")
    view._on_filter_changed()
    assert len(view.tree.get_children()) == 1
    assert view.tree.get_children()[0] == "python"

    # Filter by text
    view.category_var.set("All Categories")
    view.search_var.set("rust")
    view._on_filter_changed()
    assert len(view.tree.get_children()) == 1
    assert view.tree.get_children()[0] == "rust"

    view.destroy()


def test_tool_inspector_modal(tk_root, mock_client):
    """Test ToolInspectorModal layout and asynchronous data population."""
    mock_client.get_tool_deep.return_value = {
        "tool_id": "python",
        "probe_latency_ms": 15,
        "instances": [
            {"path": "C:\\Python312\\python.exe", "version": "3.12.0", "is_active": True, "details": "PATH"},
            {"path": "C:\\Python311\\python.exe", "version": "3.11.4", "is_active": False, "details": "Store"},
        ],
        "env_vars": [
            {"name": "PYTHONHOME", "status": "missing", "value": None, "message": "Not required"},
            {"name": "PATH", "status": "aligned", "value": "C:\\Python312", "message": "Valid"},
        ],
        "telemetry": {
            "sys_platform": "win32",
            "site_packages": ["C:\\Python312\\Lib\\site-packages"],
        },
        "raw_dumps": {
            "python --version": "Python 3.12.0",
        },
        "discovery_trace": ["Probing Registry...", "Probing PATH..."],
    }

    base_tool = {
        "id": "python",
        "name": "Python",
        "category": "runtimes",
        "version": "3.12.0",
        "binary_path": "C:\\Python312\\python.exe",
        "installed": True,
    }

    modal = ToolInspectorModal(parent=tk_root, client=mock_client, tool_id="python", base_tool=base_tool)
    tk_root.update()

    # Verify tabs and data populated
    assert modal.latency_badge.cget("text") == "⚡ 15ms"
    assert len(modal.inst_tree.get_children()) == 2
    assert len(modal.env_tree.get_children()) == 2
    assert len(modal.telem_tree.get_children()) >= 2

    raw_content = modal.raw_text.get("1.0", tk.END)
    assert "=== DISCOVERY TRACE ===" in raw_content
    assert "=== CLI DUMP: python --version ===" in raw_content

    # Clipboard copy
    modal._copy_to_clipboard("test_path")

    # Reveal path
    modal._reveal_path("C:\\Python312\\python.exe")
    mock_client.reveal_file.assert_called_with("C:\\Python312\\python.exe")

    modal.destroy()


# -----------------------------------------------------------------------------
# Port Manager Tests
# -----------------------------------------------------------------------------

def test_port_manager_view(tk_root, mock_client):
    """Test PortManagerView active listening ports, filtering, and kill actions."""
    mock_client.get_ports.return_value = [
        {"port": 4321, "protocol": "TCP", "pid": 1100, "process_name": "python.exe", "address": "127.0.0.1"},
        {"port": 8080, "protocol": "TCP", "pid": 2200, "process_name": "node.exe", "address": "0.0.0.0"},
    ]
    mock_client.kill_port.return_value = {
        "port": 8080,
        "pid": 2200,
        "process_name": "node.exe",
        "killed": True,
        "message": "Terminated successfully.",
    }

    state = ClientState()
    view = PortManagerView(parent=tk_root, client=mock_client, state=state)
    tk_root.update()

    # Verify loaded ports
    assert len(view.tree.get_children()) == 2

    # Filter by port number
    view.filter_var.set("8080")
    view._on_filter_changed()
    assert len(view.tree.get_children()) == 1

    # Filter clear
    view.filter_var.set("")
    view._on_filter_changed()
    assert len(view.tree.get_children()) == 2

    # Select row 8080
    view.tree.selection_set("port_8080_2200")
    view._on_select_row()
    assert str(view.kill_btn.cget("state")) == "normal"
    assert "8080" in str(view.selected_info_lbl.cget("text"))

    # Test kill with user confirmation
    with patch("tkinter.messagebox.askyesno", return_value=True), patch("tkinter.messagebox.showinfo"):
        view._confirm_and_kill_port()
        mock_client.kill_port.assert_called_once_with(port=8080, force=True)

    # Test kill cancelled by user
    mock_client.kill_port.reset_mock()
    with patch("tkinter.messagebox.askyesno", return_value=False):
        view._confirm_and_kill_port()
        mock_client.kill_port.assert_not_called()

    view.destroy()


# -----------------------------------------------------------------------------
# Project Auditor Tests
# -----------------------------------------------------------------------------

def test_project_auditor_view(tk_root, mock_client):
    """Test ProjectAuditorView directory browsing, audit trigger, and results presentation."""
    state = ClientState()
    view = ProjectAuditorView(parent=tk_root, client=mock_client, state=state)

    # Initial empty state
    assert len(view.results_container.winfo_children()) == 1

    # Mock audit report
    mock_report = {
        "project_name": "SampleApp",
        "project_path": "C:\\Dev\\SampleApp",
        "ready_to_build": False,
        "detected_types": ["Node.js", "TypeScript"],
        "checks": [
            {
                "name": "Node.js",
                "required": ">= 18.0.0",
                "detected": "20.10.0",
                "satisfied": True,
                "message": "Compatible node runtime found.",
            },
            {
                "name": "pnpm",
                "required": ">= 8.0.0",
                "detected": None,
                "satisfied": False,
                "message": "pnpm package manager is not installed.",
            },
        ],
        "suggested_actions": ["Run 'npm install -g pnpm' to install package manager."],
    }
    mock_client.run_project_audit.return_value = mock_report

    view.path_var.set("C:\\Dev\\SampleApp")
    view._trigger_audit()
    tk_root.update()

    # Verify results rendered
    assert state.project_report == mock_report
    # Results container should have report cards instead of empty placeholder
    assert len(view.results_container.winfo_children()) >= 2

    view.destroy()


# -----------------------------------------------------------------------------
# Fast Search View Tests
# -----------------------------------------------------------------------------

def test_search_view(tk_root, mock_client):
    """Test SearchView query execution and file opening actions."""
    mock_client.search_query.return_value = {
        "results": [
            {"filename": "main.py", "path": "C:\\Dev\\main.py", "size_bytes": 2048},
            {"filename": "config.yaml", "path": "C:\\Dev\\config.yaml", "size_bytes": 1024},
        ],
        "total": 2,
        "took_ms": 4,
    }

    state = ClientState()
    view = SearchView(parent=tk_root, client=mock_client, state=state)

    view.query_var.set("main.py")
    view._trigger_search()
    tk_root.update()

    # Verify results populated in treeview
    children = view.tree.get_children()
    assert len(children) == 2

    # Select first result and test file operations
    view.tree.selection_set(children[0])

    view._open_selected_file()
    mock_client.open_file.assert_called_with("C:\\Dev\\main.py")

    view._reveal_selected_file()
    mock_client.reveal_file.assert_called_with("C:\\Dev\\main.py")

    view._open_containing_folder()
    mock_client.open_folder.assert_called_with("C:\\Dev\\main.py")

    view.destroy()


# -----------------------------------------------------------------------------
# Settings View Tests
# -----------------------------------------------------------------------------

def test_settings_view(tk_root, mock_client):
    """Test SettingsView close behavior updates and search roots management."""
    mock_client.get_config.return_value = {
        "close_action": "minimize",
        "search_paths": ["C:\\Projects", "D:\\Dev"],
    }
    mock_client.set_close_action.return_value = {"status": "ok", "action": "exit"}
    mock_client.add_search_path.return_value = {
        "close_action": "minimize",
        "search_paths": ["C:\\Projects", "D:\\Dev", "C:\\Work"],
    }
    mock_client.remove_search_path.return_value = {
        "close_action": "minimize",
        "search_paths": ["D:\\Dev"],
    }

    state = ClientState()
    view = SettingsView(parent=tk_root, client=mock_client, state=state)
    tk_root.update()

    # Verify loaded close action and roots
    assert view.close_action_var.get() == "minimize"
    assert view.roots_listbox.size() == 2

    # Update close action
    view.close_action_var.set("exit")
    view._update_close_action()
    mock_client.set_close_action.assert_called_with("exit")

    # Add directory
    with patch("tkinter.filedialog.askdirectory", return_value="C:\\Work"):
        view._add_search_directory()
        mock_client.add_search_path.assert_called_once()

    # Remove directory
    view.roots_listbox.selection_set(0)
    view._remove_search_directory()
    mock_client.remove_search_path.assert_called_once()

    # Re-index roots
    with patch("tkinter.messagebox.showinfo"):
        view._reindex_roots()
        mock_client.trigger_reindex.assert_called_once()

    view.destroy()


# -----------------------------------------------------------------------------
# App Shell Shortcuts & Routing Tests
# -----------------------------------------------------------------------------

def test_app_shortcuts_and_routing(tk_root, mock_client):
    """Test DevToolkitApp keyboard navigation and active view transitions."""
    state = ClientState()
    app = DevToolkitApp(root=tk_root, client=mock_client, state=state)

    # Initial view is environment
    assert state.active_view == "environment"
    assert isinstance(app._active_view_frame, EnvironmentView)

    # Route to ports
    state.set_active_view("ports")
    tk_root.update()
    assert isinstance(app._active_view_frame, PortManagerView)

    # Route to projects
    state.set_active_view("projects")
    tk_root.update()
    assert isinstance(app._active_view_frame, ProjectAuditorView)

    # Route to search
    state.set_active_view("search")
    tk_root.update()
    assert isinstance(app._active_view_frame, SearchView)

    # Route to settings
    state.set_active_view("settings")
    tk_root.update()
    assert isinstance(app._active_view_frame, SettingsView)

    # Test re-scan invocation
    mock_client.run_audit.return_value = {"reports": []}
    app._trigger_rescan()
    mock_client.run_audit.assert_called_once()

    # Test daemon status badge update
    app._on_daemon_status({"connected": True})
    tk_root.update()
    assert "Daemon Active" in app.status_badge.cget("text")

    app._on_daemon_status({"connected": False})
    tk_root.update()
    assert "Daemon Disconnected" in app.status_badge.cget("text")
