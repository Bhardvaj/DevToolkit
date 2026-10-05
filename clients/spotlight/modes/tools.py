"""Tool Environment Diagnostics mode for DevToolkit Spotlight."""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


def _format_tool_title(name: str, ver: Optional[str]) -> str:
    if not ver:
        return name
    v_str = ver if ver.startswith("v") else f"v{ver}"
    return f"{name} {v_str}"


def _get_tool_status_info(tool: Dict[str, Any]) -> tuple[str, str, str, int]:
    """Return (badge, status_display, subtitle, sort_priority)."""
    status_raw = str(tool.get("status") or "").lower()
    installed = tool.get("installed")
    diagnostics = tool.get("diagnostics") or []
    category = tool.get("category", "General")
    p = tool.get("path") or ""

    if status_raw in ("warning", "action_needed") or (installed is True and diagnostics):
        diag_msg = ""
        if diagnostics and isinstance(diagnostics[0], dict):
            diag_msg = diagnostics[0].get("message", "")
        msg = f"Action Needed: {diag_msg}" if diag_msg else "Action Needed"
        return "ACTION NEEDED", "Action Needed", msg, 0

    if status_raw == "healthy" or (installed is True and status_raw not in ("not_found", "not_detected", "warning", "error")):
        sub = f"Healthy • {p}" if p else f"{category} • Healthy"
        return "HEALTHY", "Healthy", sub, 1

    if status_raw in ("not_found", "not_detected") or installed is False:
        return "NOT DETECTED", "Not Detected", f"Not Detected • {category}", 2

    cap = status_raw.capitalize() or "Unknown"
    return status_raw.upper() or "TOOL", cap, f"{category} • {cap}", 3


def query_tools(query: str, client: Optional[Any] = None) -> List[Dict[str, Any]]:
    """Parse tool query and return audited developer tools from daemon."""
    raw = query.strip()
    if raw.startswith("tool:"):
        sub = raw[5:].strip()
    elif raw.startswith("tools:"):
        sub = raw[6:].strip()
    else:
        sub = raw

    if not client or not client.is_alive():
        return [
            {
                "id": "tool_offline",
                "title": "DevToolkit Daemon Offline",
                "subtitle": "Tool diagnostics require the background daemon. Press Enter to start daemon.",
                "type": "tool",
                "badge": "OFFLINE",
                "action": "start_daemon",
            }
        ]

    try:
        tools = client.get_tools()
    except Exception as e:
        logger.debug(f"Failed to fetch tools: {e}")
        return []

    sub_low = sub.lower()

    # Exact tool drilldown e.g. "tool:node"
    if sub_low:
        matching = [t for t in tools if t.get("id", "").lower() == sub_low or t.get("name", "").lower() == sub_low]
        if matching:
            tool = matching[0]
            badge, status_display, sub_text, _ = _get_tool_status_info(tool)
            ver = tool.get("version")
            title_base = _format_tool_title(tool.get("name", "Tool"), ver)
            p = tool.get("path") or "Path not resolved"
            return [
                {
                    "id": f"tool_detail_{tool.get('id')}",
                    "tool_id": tool.get("id"),
                    "title": f"{title_base} [{status_display}]",
                    "subtitle": f"{sub_text} • {p}" if p != "Path not resolved" else sub_text,
                    "type": "tool_detail",
                    "badge": badge,
                    "action": "open_deep_drawer",
                    "path": p,
                    "version": ver or "",
                    "status": status_display,
                    "name": tool.get("name"),
                }
            ]

    # Filtered or full tool list
    filtered_tools = tools
    if sub_low:
        filtered_tools = [
            t for t in tools
            if sub_low in t.get("id", "").lower()
            or sub_low in t.get("name", "").lower()
            or sub_low in t.get("category", "").lower()
        ]

    # Sort tools: ACTION NEEDED (0) -> HEALTHY (1) -> NOT DETECTED (2) -> Other (3), then by name
    annotated = []
    for tool in filtered_tools:
        tid = tool.get("id")
        name = tool.get("name", "Tool")
        ver = tool.get("version")
        category = tool.get("category", "General")
        badge, status_display, sub_text, prio = _get_tool_status_info(tool)
        title = _format_tool_title(name, ver)

        item = {
            "id": f"tool_{tid}",
            "tool_id": tid,
            "name": name,
            "title": title,
            "subtitle": sub_text,
            "version": ver or "",
            "status": status_display,
            "path": tool.get("path") or "",
            "category": category,
            "type": "tool_item",
            "badge": badge,
            "action": "drilldown_tool",
            "_prio": prio,
        }
        annotated.append(item)

    annotated.sort(key=lambda x: (x["_prio"], x["name"].lower()))
    for item in annotated:
        item.pop("_prio", None)

    if not annotated:
        return [
            {
                "id": "tool_none",
                "title": "No Matching Developer Tools Found",
                "subtitle": "Check the tool name or category filter",
                "type": "tool",
                "badge": "TOOLS",
                "action": "none",
            }
        ]

    return annotated


def get_deep_telemetry(tool_id: str, client: Optional[Any] = None) -> Dict[str, Any]:
    """Retrieve 7-zone deep telemetry report for tool."""
    if not client or not client.is_alive():
        return {}
    try:
        return client.get_tool_deep(tool_id)
    except Exception as e:
        logger.debug(f"Failed to fetch deep telemetry for {tool_id}: {e}")
        return {}

