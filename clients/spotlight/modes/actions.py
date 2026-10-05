"""System action catalog and execution dispatcher for DevToolkit Spotlight."""

from __future__ import annotations

import logging
import os
import sys
import webbrowser
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


def list_system_actions(query: str = "", client: Optional[Any] = None) -> List[Dict[str, Any]]:
    """Return all built-in system actions, filterable by query."""
    q = query.strip()
    if q.startswith(">") or q.startswith("/"):
        q = q[1:].strip()
    q_low = q.lower()

    is_online = client.is_alive() if client else False
    daemon_port = getattr(client, "port", 4321) if client else 4321

    daemon_action = {
        "id": "act_daemon_status",
        "title": f"> DevToolkit Daemon ({'Online' if is_online else 'Offline'})",
        "subtitle": f"Status: {'Active on port ' + str(daemon_port) if is_online else 'Offline — daemon service is not running'}",
        "command": "daemon",
        "badge": "ONLINE" if is_online else "OFFLINE",
        "action": "open_dashboard" if is_online else "start_daemon",
    }

    actions = [
        daemon_action,
        {
            "id": "act_settings",
            "title": "> Settings",
            "subtitle": "Customize global hotkey, multi-monitor display, theme colors, and blur intensity",
            "command": "settings",
            "badge": "CONFIG",
            "action": "open_settings",
        },
        {
            "id": "act_config",
            "title": "> View Daemon Config",
            "subtitle": "Inspect DevToolkit configuration (devtoolkit.config.yaml)",
            "command": "config",
            "badge": "CONFIG",
            "action": "open_config",
        },
        {
            "id": "act_dashboard",
            "title": "> Open DevToolkit Dashboard",
            "subtitle": "Open full web and desktop workstation inspector in browser",
            "command": "dashboard",
            "badge": "UI",
            "action": "open_dashboard",
        },
        {
            "id": "act_reindex",
            "title": "> Re-index Fast Search",
            "subtitle": "Trigger immediate NTFS USN / directory re-crawl in daemon",
            "command": "reindex",
            "badge": "SEARCH",
            "action": "trigger_reindex",
        },
        {
            "id": "act_rescan",
            "title": "> Re-scan Developer Tools",
            "subtitle": "Trigger full parallel environment audit across all 22 compilers and runtimes",
            "command": "rescan",
            "badge": "AUDIT",
            "action": "trigger_rescan",
        },
        {
            "id": "act_logs",
            "title": "> View Logs",
            "subtitle": "Open spotlight.log or daemon.log in default text editor",
            "command": "logs",
            "badge": "LOGS",
            "action": "open_logs",
        },
        {
            "id": "act_quit",
            "title": "> Quit Spotlight",
            "subtitle": "Gracefully terminate DevToolkit Spotlight resident background process",
            "command": "quit",
            "badge": "EXIT",
            "action": "quit_spotlight",
        },
    ]

    if not q_low:
        return actions

    return [a for a in actions if q_low in a["command"].lower() or q_low in a["title"].lower() or q_low in a["subtitle"].lower()]


def execute_action(action_name: str, client: Optional[Any] = None) -> Dict[str, Any]:
    """Execute a built-in system action."""
    act = action_name.lower().strip()

    if act in ("open_dashboard", "daemon"):
        port = getattr(client, "port", 4321) if client else 4321
        webbrowser.open(f"http://127.0.0.1:{port}")
        return {"status": "ok", "message": "Dashboard opened in browser."}

    elif act == "start_daemon":
        base_dir = Path(sys.executable).parent if getattr(sys, "frozen", False) else Path.cwd()
        daemon_exe = base_dir / "devtoolkit.exe"
        if daemon_exe.is_file():
            import subprocess
            subprocess.Popen([str(daemon_exe)], creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
            return {"status": "ok", "message": "Launching DevToolkit Daemon..."}
        return {"status": "warning", "message": "devtoolkit.exe not found in app directory."}

    elif act == "trigger_reindex":
        if client and client.is_alive():
            try:
                client.post("/api/search/reindex", data={})
                return {"status": "ok", "message": "Fast Search re-indexing started."}
            except Exception as e:
                return {"status": "error", "message": f"Failed reindex: {e}"}
        return {"status": "error", "message": "DevToolkit Daemon is offline."}

    elif act == "trigger_rescan":
        if client and client.is_alive():
            try:
                client.post("/api/audit", data={})
                return {"status": "ok", "message": "Environment audit re-scan started."}
            except Exception as e:
                return {"status": "error", "message": f"Failed rescan: {e}"}
        return {"status": "error", "message": "DevToolkit Daemon is offline."}

    elif act == "open_logs":
        log_paths = [
            Path("spotlight.log").resolve(),
            Path("daemon.log").resolve(),
        ]
        opened = False
        for p in log_paths:
            if p.is_file():
                if sys.platform == "win32":
                    os.startfile(str(p))
                    opened = True
                    break
        if not opened:
            return {"status": "warning", "message": "No active log files found yet."}
        return {"status": "ok", "message": "Log file opened."}

    elif act == "open_config":
        env_override = os.environ.get("DEVTOOLKIT_CONFIG")
        candidates = []
        if env_override:
            candidates.append(Path(env_override).resolve())
        base_dir = Path(sys.executable).parent if getattr(sys, "frozen", False) else Path.cwd()
        candidates.extend([
            base_dir / "devtoolkit.config.yaml",
            base_dir / ".devtoolkit.yaml",
            Path("devtoolkit.config.yaml").resolve(),
        ])
        for cfg_p in candidates:
            if cfg_p.is_file() and sys.platform == "win32":
                os.startfile(str(cfg_p))
                return {"status": "ok", "message": "Config opened."}
        return {"status": "warning", "message": "Config file not found."}

    return {"status": "ok"}


# Backward compatibility alias
list_palette_actions = list_system_actions

