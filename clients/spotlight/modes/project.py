"""Project Workstation Auditor mode for DevToolkit Spotlight."""

from __future__ import annotations

import logging
import os
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


def query_project_audit(query: str, client: Optional[Any] = None) -> List[Dict[str, Any]]:
    """Parse project path, run audit via daemon, and return structured card."""
    raw = query.strip()
    if raw.startswith("proj:"):
        target_path = raw[5:].strip()
    elif raw.startswith("project:"):
        target_path = raw[8:].strip()
    else:
        target_path = raw

    if not target_path:
        target_path = "."

    resolved_path = str(Path(target_path).resolve())

    if not client or not client.is_alive():
        return [
            {
                "id": "proj_offline",
                "title": "DevToolkit Daemon Offline",
                "subtitle": f"Project audit for '{resolved_path}' requires daemon. Press Enter to start daemon.",
                "type": "project",
                "badge": "OFFLINE",
                "action": "start_daemon",
                "path": resolved_path,
            }
        ]

    try:
        report = client.post("/api/project/audit", data={"path": resolved_path})
    except Exception as e:
        logger.debug(f"Project audit failed: {e}")
        return [
            {
                "id": "proj_err",
                "title": f"Audit Failed: {resolved_path}",
                "subtitle": str(e),
                "type": "project",
                "badge": "ERROR",
                "action": "none",
                "path": resolved_path,
            }
        ]

    p_name = report.get("project_name", Path(resolved_path).name)
    frameworks = ", ".join(report.get("frameworks", [])) or "Standard Project"
    git_info = report.get("git_info") or {}
    branch = git_info.get("branch", "No Git")
    uncommitted = git_info.get("uncommitted_changes_count", 0)
    git_summary = f"{branch} ({uncommitted} uncommitted files)" if git_info.get("is_repo") else "Not a Git repo"
    cleanable_bytes = report.get("total_cleanable_bytes", 0)
    cleanable_mb = round(cleanable_bytes / (1024 * 1024), 1)

    return [
        {
            "id": f"proj_{p_name}",
            "project_name": p_name,
            "title": f"{p_name} — {frameworks}",
            "subtitle": f"{frameworks} • Git: {branch}",
            "frameworks": frameworks,
            "git_summary": git_summary,
            "branch": branch,
            "uncommitted": uncommitted,
            "cleanable_mb": cleanable_mb,
            "type": "project",
            "badge": "AUDIT",
            "action": "open_terminal",
            "path": resolved_path,
        }
    ]


def open_in_terminal(target_path: str) -> bool:
    """Launch Windows Terminal or PowerShell in the target directory."""
    if not target_path or not Path(target_path).exists():
        return False

    p = str(Path(target_path).resolve())
    try:
        # Check if Windows Terminal (wt.exe) is available
        subprocess.Popen(["wt.exe", "-d", p], close_fds=True)
        return True
    except FileNotFoundError:
        try:
            # Fallback to PowerShell
            subprocess.Popen(["powershell.exe", "-NoExit", "-Command", f'Set-Location "{p}"'], close_fds=True)
            return True
        except Exception as e:
            logger.error(f"Failed to launch terminal: {e}")
            return False

