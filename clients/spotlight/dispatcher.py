"""Central query router and mode dispatcher for DevToolkit Spotlight."""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from clients.spotlight.modes.actions import execute_action, list_palette_actions
from clients.spotlight.modes.calc import evaluate_calc_query
from clients.spotlight.modes.default import launch_target_path, query_default, reveal_in_explorer
from clients.spotlight.modes.guide import get_command_guide
from clients.spotlight.modes.ports import kill_target_port, query_ports
from clients.spotlight.modes.project import open_in_terminal, query_project_audit
from clients.spotlight.modes.tools import get_deep_telemetry, query_tools
from clients.spotlight.modes.window_walker import close_window_by_hwnd, list_open_windows, switch_to_window

logger = logging.getLogger(__name__)


ALL_SCOPES = {"app", "file", "port", "calc", "tool", "window", "project", "action"}


def dispatch_query(
    query: str,
    client: Optional[Any] = None,
    enabled_scopes: Optional[List[str]] = None,
) -> List[Dict[str, Any]]:
    """Route user input to corresponding query mode based on leading prefixes and enabled scopes."""
    q = query.strip()
    if not q:
        return []

    active_scopes = set(enabled_scopes) if enabled_scopes is not None else ALL_SCOPES

    # 1. Interactive Cheatsheet & Guide
    if q.startswith("?"):
        return get_command_guide()

    # 2. Inline Math, Base Conversions, Epoch, UUID
    if q.startswith("="):
        if "calc" not in active_scopes:
            return []
        return evaluate_calc_query(q)

    # 3. Command Palette Actions
    if q.startswith(">") or q.startswith("/"):
        if "action" not in active_scopes:
            return []
        return list_palette_actions(q, client=client)

    # 4. Port Inspector & Killer
    if q.startswith("port:") or q.startswith("ports:"):
        if "port" not in active_scopes:
            return []
        return query_ports(q, client=client)

    # 5. Tool Diagnostics
    if q.startswith("tool:") or q.startswith("tools:"):
        if "tool" not in active_scopes:
            return []
        return query_tools(q, client=client)

    # 6. Project Workstation Auditor
    if q.startswith("proj:") or q.startswith("project:"):
        if "project" not in active_scopes:
            return []
        return query_project_audit(q, client=client)

    # 7. Window Walker
    if q.startswith("w:") or q.startswith("window:"):
        if "window" not in active_scopes:
            return []
        sub = q[2:].strip() if q.startswith("w:") else q[7:].strip()
        return list_open_windows(sub)

    # 8. Default: Fast Search + Desktop App Launcher
    return query_default(
        q,
        client=client,
        allow_apps=("app" in active_scopes),
        allow_files=("file" in active_scopes),
    )

