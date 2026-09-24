"""Decoupled API Client for DevToolkit background data serving daemon."""

from __future__ import annotations

import json
import logging
import threading
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


class DevToolkitAPIError(Exception):
    """Exception raised when an API request to DevToolkit daemon fails."""

    def __init__(self, message: str, status_code: Optional[int] = None, response_body: Optional[str] = None):
        super().__init__(message)
        self.status_code = status_code
        self.response_body = response_body


class DevToolkitClient:
    """Client for consuming DevToolkit HTTP REST and streaming SSE endpoints."""

    def __init__(self, host: str = "127.0.0.1", port: int = 4321, timeout: float = 10.0):
        self.host = host
        self.port = port
        self.timeout = timeout

    @property
    def base_url(self) -> str:
        return f"http://{self.host}:{self.port}"

    # -------------------------------------------------------------------------
    # Core HTTP Utilities
    # -------------------------------------------------------------------------

    def _request(
        self,
        method: str,
        endpoint: str,
        payload: Optional[Dict[str, Any]] = None,
        timeout: Optional[float] = None,
        headers: Optional[Dict[str, str]] = None,
    ) -> Any:
        url = f"{self.base_url}{endpoint}"
        req_headers = {
            "User-Agent": "DevToolkit-NativeClient",
            "Accept": "application/json",
        }
        if headers:
            req_headers.update(headers)

        data = None
        if payload is not None:
            data = json.dumps(payload).encode("utf-8")
            req_headers["Content-Type"] = "application/json"

        req = urllib.request.Request(url, data=data, headers=req_headers, method=method)
        req_timeout = timeout if timeout is not None else self.timeout

        try:
            with urllib.request.urlopen(req, timeout=req_timeout) as resp:
                resp_bytes = resp.read()
                if not resp_bytes:
                    return None
                return json.loads(resp_bytes.decode("utf-8"))
        except urllib.error.HTTPError as e:
            err_body = None
            try:
                err_body = e.read().decode("utf-8")
            except Exception:
                pass
            raise DevToolkitAPIError(
                f"HTTP {e.code} error requesting {method} {endpoint}: {e.reason}",
                status_code=e.code,
                response_body=err_body,
            ) from e
        except urllib.error.URLError as e:
            raise DevToolkitAPIError(
                f"Failed to connect to DevToolkit daemon at {self.base_url}: {e.reason}"
            ) from e
        except Exception as e:
            raise DevToolkitAPIError(f"Unexpected error communicating with daemon: {e}") from e

    def _get(self, endpoint: str, timeout: Optional[float] = None) -> Any:
        return self._request("GET", endpoint, timeout=timeout)

    def _post(self, endpoint: str, payload: Optional[Dict[str, Any]] = None, timeout: Optional[float] = None) -> Any:
        return self._request("POST", endpoint, payload=payload or {}, timeout=timeout)

    def _delete(self, endpoint: str, payload: Optional[Dict[str, Any]] = None, timeout: Optional[float] = None) -> Any:
        return self._request("DELETE", endpoint, payload=payload or {}, timeout=timeout)

    # -------------------------------------------------------------------------
    # Asynchronous Dispatcher
    # -------------------------------------------------------------------------

    def run_async(
        self,
        task_fn: Callable[..., Any],
        *args: Any,
        callback: Optional[Callable[[Any], None]] = None,
        errback: Optional[Callable[[Exception], None]] = None,
        **kwargs: Any,
    ) -> threading.Thread:
        """Run an API method in a background worker thread, dispatching callbacks safely."""

        def _worker():
            try:
                result = task_fn(*args, **kwargs)
                if callback:
                    callback(result)
            except Exception as e:
                logger.debug(f"API async worker error: {e}")
                if errback:
                    errback(e)

        thread = threading.Thread(target=_worker, daemon=True)
        thread.start()
        return thread

    # -------------------------------------------------------------------------
    # System, Health & Configuration
    # -------------------------------------------------------------------------

    def is_alive(self, timeout: float = 1.0) -> bool:
        """Probe daemon /api/health endpoint to verify connectivity."""
        try:
            health = self.get_health(timeout=timeout)
            return bool(health and health.get("status") == "ok")
        except Exception:
            return False

    def get_health(self, timeout: Optional[float] = None) -> Dict[str, Any]:
        """Fetch daemon health status."""
        return self._get("/api/health", timeout=timeout)

    def get_system(self) -> Dict[str, Any]:
        """Fetch workstation system hardware and OS diagnostics."""
        return self._get("/api/system")

    def get_config(self) -> Dict[str, Any]:
        """Fetch user configuration and search paths."""
        return self._get("/api/config")

    def set_close_action(self, action: str) -> Dict[str, Any]:
        """Update window close interception preference ('ask', 'minimize', 'exit')."""
        return self._post("/api/config/close-action", {"action": action})

    def add_search_path(self, path: str) -> Dict[str, Any]:
        """Register a search root directory in configuration."""
        return self._post("/api/config/search-paths", {"path": path})

    def remove_search_path(self, path: Optional[str] = None, index: Optional[int] = None) -> Dict[str, Any]:
        """Remove a search root directory from configuration."""
        payload: Dict[str, Any] = {}
        if path is not None:
            payload["path"] = path
        if index is not None:
            payload["index"] = index
        return self._delete("/api/config/search-paths", payload)

    def send_notification(self, title: str, message: str, icon_type: int = 1) -> Dict[str, Any]:
        """Request the daemon system tray to display a desktop notification."""
        return self._post("/api/daemon/notify", {"title": title, "message": message, "icon_type": icon_type})

    # -------------------------------------------------------------------------
    # Tools & Diagnostics
    # -------------------------------------------------------------------------

    def get_tools(self) -> List[Dict[str, Any]]:
        """Fetch list of all inspected development tools."""
        return self._get("/api/tools")

    def get_tool_deep(self, tool_id: str) -> Dict[str, Any]:
        """Fetch comprehensive deep inspection telemetry for a specific tool."""
        return self._get(f"/api/tool/{urllib.parse.quote(tool_id)}/deep")

    def run_audit(
        self,
        categories: Optional[List[str]] = None,
        tool_ids: Optional[List[str]] = None,
        timeout: float = 30.0,
    ) -> Dict[str, Any]:
        """Trigger synchronous workstation environment audit."""
        payload: Dict[str, Any] = {}
        if categories:
            payload["categories"] = categories
        if tool_ids:
            payload["tool_ids"] = tool_ids
        return self._post("/api/audit", payload, timeout=timeout)

    def stream_audit(
        self,
        on_chunk: Callable[[Dict[str, Any]], None],
        on_complete: Optional[Callable[[], None]] = None,
        on_error: Optional[Callable[[Exception], None]] = None,
    ) -> threading.Thread:
        """Stream workstation audit progress chunk-by-chunk using Server-Sent Events (SSE)."""

        def _worker():
            url = f"{self.base_url}/api/audit/stream"
            req = urllib.request.Request(
                url,
                headers={"Accept": "text/event-stream", "User-Agent": "DevToolkit-NativeClient"},
            )
            try:
                with urllib.request.urlopen(req, timeout=60.0) as resp:
                    for line in resp:
                        decoded = line.decode("utf-8").strip()
                        if decoded.startswith("data:"):
                            raw_json = decoded[5:].strip()
                            if raw_json:
                                chunk = json.loads(raw_json)
                                on_chunk(chunk)
                if on_complete:
                    on_complete()
            except Exception as e:
                logger.debug(f"Audit stream error: {e}")
                if on_error:
                    on_error(e)

        thread = threading.Thread(target=_worker, daemon=True)
        thread.start()
        return thread

    # -------------------------------------------------------------------------
    # Ports & Sockets
    # -------------------------------------------------------------------------

    def get_ports(self) -> List[Dict[str, Any]]:
        """Fetch list of active listening network ports."""
        return self._get("/api/ports")

    def kill_port(self, port: int, force: bool = False) -> Dict[str, Any]:
        """Terminate process listening on a given network port."""
        return self._post("/api/ports/kill", {"port": port, "force": force})

    # -------------------------------------------------------------------------
    # Project Auditor
    # -------------------------------------------------------------------------

    def run_project_audit(self, path: str, timeout: float = 30.0) -> Dict[str, Any]:
        """Audit project directory structure, dependencies, and environment hygiene."""
        return self._post("/api/project/audit", {"path": path}, timeout=timeout)

    # -------------------------------------------------------------------------
    # Fast Search Engine
    # -------------------------------------------------------------------------

    def search_query(
        self,
        query: str,
        category: str = "all",
        scope: str = "all",
        match_path: bool = False,
        is_regex: bool = False,
        case_sensitive: bool = False,
        whole_word: bool = False,
        limit: int = 500,
        offset: int = 0,
    ) -> Dict[str, Any]:
        """Execute fast multi-root filesystem search query."""
        payload = {
            "query": query,
            "category": category,
            "scope": scope,
            "match_path": match_path,
            "is_regex": is_regex,
            "case_sensitive": case_sensitive,
            "whole_word": whole_word,
            "limit": limit,
            "offset": offset,
        }
        return self._post("/api/search/query", payload)

    def get_search_status(self) -> Dict[str, Any]:
        """Fetch search index status, document count, and background watcher health."""
        return self._get("/api/search/status")

    def trigger_reindex(self) -> Dict[str, Any]:
        """Trigger background re-indexing of all monitored search roots."""
        return self._post("/api/search/reindex", {})

    def toggle_realtime(self, enabled: bool) -> Dict[str, Any]:
        """Toggle realtime filesystem watcher."""
        return self._post("/api/search/realtime", {"enabled": enabled})

    # -------------------------------------------------------------------------
    # Desktop Actions
    # -------------------------------------------------------------------------

    def open_folder(self, path: str) -> Dict[str, Any]:
        """Open folder in OS default file manager."""
        return self._post("/api/action/open-folder", {"path": path})

    def open_file(self, path: str) -> Dict[str, Any]:
        """Open file in OS default editor."""
        return self._post("/api/action/open-file", {"path": path})

    def reveal_file(self, path: str) -> Dict[str, Any]:
        """Reveal file selected in OS file manager."""
        return self._post("/api/action/reveal-file", {"path": path})

    def select_folder(self, initial_path: Optional[str] = None) -> Dict[str, Any]:
        """Open native folder picker dialog."""
        payload: Dict[str, Any] = {}
        if initial_path:
            payload["initial_path"] = initial_path
        return self._post("/api/action/select-folder", payload)

    def apply_fix(self, command: str) -> Dict[str, Any]:
        """Execute recommended environment remediation command safely."""
        return self._post("/api/action/apply-fix", {"command": command})
