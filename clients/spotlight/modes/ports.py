"""Port Inspector & Killer mode for DevToolkit Spotlight."""

from __future__ import annotations

import logging
import re
import webbrowser
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


def query_ports(query: str, client: Optional[Any] = None) -> List[Dict[str, Any]]:
    """Parse port query and return matching port entries from daemon."""
    raw = query.strip()
    if raw.startswith("port:"):
        sub = raw[5:].strip()
    elif raw.startswith("ports:"):
        sub = raw[6:].strip()
    else:
        sub = raw

    if not client or not client.is_alive():
        return [
            {
                "id": "port_offline",
                "title": "DevToolkit Daemon Offline",
                "subtitle": "Port inspection requires the background daemon. Press Enter to start daemon.",
                "type": "port",
                "badge": "OFFLINE",
                "action": "start_daemon",
            }
        ]

    try:
        ports_data = client.get_ports(timeout=2.0)
    except Exception as e:
        logger.debug(f"Failed to fetch ports: {e}")
        return []

    # Check for direct kill syntax e.g. "port:3000 kill"
    m_kill = re.match(r"^(\d+)\s+kill$", sub.lower())
    if m_kill:
        target_port = int(m_kill.group(1))
        matching = [p for p in ports_data if p.get("port") == target_port]
        if matching:
            p_info = matching[0]
            is_dev = bool(p_info.get("is_dev") or p_info.get("is_dev_port"))
            return [
                {
                    "id": f"port_{target_port}_kill",
                    "port": target_port,
                    "pid": p_info.get("pid"),
                    "process_name": p_info.get("process_name", "Unknown"),
                    "is_dev": is_dev,
                    "title": f"Kill Port :{target_port} ({p_info.get('process_name')})",
                    "subtitle": f"PID: {p_info.get('pid')} • Press Enter to terminate process immediately",
                    "type": "port",
                    "badge": "KILL",
                    "action": "kill_port",
                }
            ]
        return [
            {
                "id": f"port_{target_port}_none",
                "title": f"Port :{target_port} Not Found",
                "subtitle": "No active process is currently listening on this port",
                "type": "port",
                "badge": "IDLE",
                "action": "none",
            }
        ]

    # Check for specific port number e.g. "port:3000"
    if sub.isdigit():
        target_port = int(sub)
        matching = [p for p in ports_data if p.get("port") == target_port]
        if matching:
            p_info = matching[0]
            is_dev = bool(p_info.get("is_dev") or p_info.get("is_dev_port"))
            proc_name = p_info.get("process_name", "Unknown")
            pid = p_info.get("pid")
            category = p_info.get("category") or ("Dev" if is_dev else "Service")
            primary_action_hint = "Enter to Open in Browser" if is_dev else "Enter to Kill Process"

            return [
                {
                    "id": f"port_{target_port}_detail",
                    "port": target_port,
                    "pid": pid,
                    "process_name": proc_name,
                    "is_dev": is_dev,
                    "category": category,
                    "title": f":{target_port} {proc_name} (PID {pid}) [{category}]",
                    "subtitle": f"{category} • PID {pid}",
                    "type": "port_detail",
                    "badge": category.upper(),
                    "action": "open_browser" if is_dev else "kill_port",
                }
            ]
        return [
            {
                "id": f"port_{target_port}_none",
                "title": f"Port :{target_port} Not Found",
                "subtitle": "No active process is currently listening on this port",
                "type": "port",
                "badge": "IDLE",
                "action": "none",
            }
        ]

    # Filter dev only e.g. "port:dev", "port:devs", "port:development"
    if sub.lower() in ("dev", "devs", "development"):
        ports_data = [
            p for p in ports_data
            if p.get("is_dev") or p.get("is_dev_port") or str(p.get("category", "")).lower() in ("dev", "database", "debug")
        ]
    elif sub:
        q_low = sub.lower()
        ports_data = [
            p for p in ports_data
            if q_low in str(p.get("port", ""))
            or q_low in p.get("process_name", "").lower()
            or q_low in p.get("category", "").lower()
        ]

    # Render ports list
    results: List[Dict[str, Any]] = []
    for p in ports_data:
        port_num = p.get("port")
        proc = p.get("process_name", "Unknown")
        pid = p.get("pid")
        is_dev = bool(p.get("is_dev") or p.get("is_dev_port"))
        category = p.get("category") or ("Dev" if is_dev else "Service")

        results.append(
            {
                "id": f"port_{port_num}",
                "port": port_num,
                "pid": pid,
                "process_name": proc,
                "is_dev": is_dev,
                "category": category,
                "title": f":{port_num} {proc} (PID {pid})",
                "subtitle": f"{category} • PID {pid}",
                "type": "port_item",
                "badge": category.upper(),
                "action": "drilldown_port",
            }
        )

    if not results:
        if sub.lower() in ("dev", "devs", "development"):
            return [
                {
                    "id": "port_no_dev",
                    "title": "No Active Dev Ports Found",
                    "subtitle": "No developer servers (Node, Python, Vite, etc.) are currently listening. Type 'port:' to view all ports.",
                    "type": "port",
                    "badge": "PORTS",
                    "action": "none",
                }
            ]
        return [
            {
                "id": "port_none",
                "title": f"No Matching Ports for '{sub}'" if sub else "No Active Ports Found",
                "subtitle": "No active sockets match the query criteria. Type 'port:' to view all ports.",
                "type": "port",
                "badge": "PORTS",
                "action": "none",
            }
        ]

    return results


def kill_target_port(port: int, client: Optional[Any] = None) -> Dict[str, Any]:
    """Terminate the process listening on target port."""
    if not client or not client.is_alive():
        return {"status": "error", "message": "DevToolkit Daemon is offline."}

    try:
        res = client.post("/api/ports/kill", data={"port": port, "force": True})
        if res.get("success"):
            return {"status": "ok", "message": f"Successfully killed process on port :{port}."}
        return {"status": "error", "message": res.get("message", f"Failed to kill port :{port}")}
    except Exception as e:
        return {"status": "error", "message": f"Error killing port: {e}"}

