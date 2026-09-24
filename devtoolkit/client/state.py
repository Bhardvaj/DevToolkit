"""Observable state store and reactive event bus for DevToolkit Native UI."""

from __future__ import annotations

import logging
import threading
from typing import Any, Callable, Dict, List, Optional, Set

logger = logging.getLogger(__name__)


class ClientState:
    """Thread-safe observable state store with pub/sub event dispatching."""

    def __init__(self):
        self._lock = threading.RLock()
        self._subscribers: Dict[str, Set[Callable[[Any], None]]] = {}

        # View Routing
        self.active_view: str = "environment"

        # Daemon Connection
        self.daemon_connected: bool = False
        self.daemon_version: str = ""
        self.daemon_uptime: Optional[float] = None

        # Workstation Environment & Audit
        self.system_info: Optional[Dict[str, Any]] = None
        self.config: Optional[Dict[str, Any]] = None
        self.tools: List[Dict[str, Any]] = []
        self.selected_tool_id: Optional[str] = None
        self.deep_inspection: Optional[Dict[str, Any]] = None
        self.audit_report: Optional[Dict[str, Any]] = None
        self.is_auditing: bool = False

        # Ports & Sockets
        self.ports: List[Dict[str, Any]] = []
        self.is_loading_ports: bool = False

        # Project Auditor
        self.project_path: str = ""
        self.project_report: Optional[Dict[str, Any]] = None
        self.is_auditing_project: bool = False

        # Search Engine
        self.search_query_text: str = ""
        self.search_results: List[Dict[str, Any]] = []
        self.is_searching: bool = False
        self.search_status: Optional[Dict[str, Any]] = None

    # -------------------------------------------------------------------------
    # Pub/Sub Event Bus
    # -------------------------------------------------------------------------

    def subscribe(self, event: str, callback: Callable[[Any], None]) -> Callable[[], None]:
        """Register a subscriber callback for a named event or '*' for all events."""
        with self._lock:
            if event not in self._subscribers:
                self._subscribers[event] = set()
            self._subscribers[event].add(callback)

        def unsubscribe():
            with self._lock:
                if event in self._subscribers:
                    self._subscribers[event].discard(callback)

        return unsubscribe

    def emit(self, event: str, payload: Any = None) -> None:
        """Dispatch an event to all registered listeners safely."""
        with self._lock:
            targets = list(self._subscribers.get(event, []))
            wildcard_targets = list(self._subscribers.get("*", []))

        for cb in targets + wildcard_targets:
            try:
                cb(payload)
            except Exception as e:
                logger.error(f"Error in state subscriber for '{event}': {e}")

    # -------------------------------------------------------------------------
    # State Mutators (Auto-Emitting)
    # -------------------------------------------------------------------------

    def set_active_view(self, view: str) -> None:
        """Switch current navigation route ('environment', 'ports', 'projects', 'search', 'settings')."""
        with self._lock:
            if self.active_view == view:
                return
            self.active_view = view
        self.emit("view_changed", view)

    def set_daemon_status(self, connected: bool, version: str = "", uptime: Optional[float] = None) -> None:
        """Update background daemon connection telemetry."""
        with self._lock:
            changed = (
                self.daemon_connected != connected
                or self.daemon_version != version
                or self.daemon_uptime != uptime
            )
            self.daemon_connected = connected
            self.daemon_version = version
            self.daemon_uptime = uptime
        if changed:
            self.emit("daemon_status", {"connected": connected, "version": version, "uptime": uptime})

    def set_system_info(self, info: Dict[str, Any]) -> None:
        """Update system hardware & platform diagnostics."""
        with self._lock:
            self.system_info = info
        self.emit("system_info", info)

    def set_config(self, config: Dict[str, Any]) -> None:
        """Update user preferences and configuration."""
        with self._lock:
            self.config = config
        self.emit("config_updated", config)

    def set_tools(self, tools: List[Dict[str, Any]]) -> None:
        """Update discovered tool cards."""
        with self._lock:
            self.tools = tools
        self.emit("tools_updated", tools)

    def set_selected_tool(self, tool_id: Optional[str], deep_data: Optional[Dict[str, Any]] = None) -> None:
        """Select a tool for inspection drawer."""
        with self._lock:
            self.selected_tool_id = tool_id
            self.deep_inspection = deep_data
        self.emit("tool_selected", {"tool_id": tool_id, "data": deep_data})

    def set_audit_report(self, report: Optional[Dict[str, Any]], is_auditing: bool = False) -> None:
        """Update environment audit summary."""
        with self._lock:
            self.audit_report = report
            self.is_auditing = is_auditing
        self.emit("audit_updated", {"report": report, "is_auditing": is_auditing})

    def set_ports(self, ports: List[Dict[str, Any]], is_loading: bool = False) -> None:
        """Update active listening ports."""
        with self._lock:
            self.ports = ports
            self.is_loading_ports = is_loading
        self.emit("ports_updated", ports)

    def set_project_report(self, report: Optional[Dict[str, Any]], is_auditing: bool = False) -> None:
        """Update project hygiene audit report."""
        with self._lock:
            self.project_report = report
            self.is_auditing_project = is_auditing
        self.emit("project_updated", {"report": report, "is_auditing": is_auditing})

    def set_search_results(self, results: List[Dict[str, Any]], query: str = "", is_searching: bool = False) -> None:
        """Update filesystem search matches."""
        with self._lock:
            self.search_results = results
            self.search_query_text = query
            self.is_searching = is_searching
        self.emit("search_updated", {"results": results, "query": query, "is_searching": is_searching})

    def set_search_status(self, status: Dict[str, Any]) -> None:
        """Update search engine health and document count."""
        with self._lock:
            self.search_status = status
        self.emit("search_status", status)
