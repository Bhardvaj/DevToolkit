"""FastAPI local server and PyWebView desktop window launcher."""

import ipaddress
import os
import sys
import threading
import time
import webbrowser
from pathlib import Path
from typing import List

from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
import uvicorn

from devtoolkit import __version__
from devtoolkit.core.models import AuditSummary, DeepTelemetryReport
from devtoolkit.modules.utilities.ports import PortInfo, PortKillResult
from devtoolkit.modules.utilities.project_auditor import ProjectAuditReport
from devtoolkit.server.models import (
    ApplyFixRequest,
    AuditRequest,
    KillPortRequest,
    OpenFolderRequest,
    ProjectAuditRequest,
    SearchPathRequest,
    SelectFolderRequest,
)
from devtoolkit.server.routes.actions import (
    open_file,
    open_folder,
    post_apply_fix,
    post_select_folder,
    reveal_file,
)
from devtoolkit.server.routes.audit import (
    get_audit,
    get_tool_deep,
    get_tools,
    post_audit,
    registry,
    stream_audit,
)
from devtoolkit.server.routes.ports import get_ports, post_kill_port
from devtoolkit.server.routes.project import post_audit_project
from devtoolkit.server.routes.search import (
    get_search_query,
    get_search_status,
    post_search_query,
    toggle_realtime,
    trigger_reindex,
)
from devtoolkit.server.routes.system import (
    delete_search_path,
    get_config,
    get_daemon_activity,
    get_health,
    get_system,
    post_close_action,
    post_daemon_notify,
    post_search_path,
)
from devtoolkit.server.routes.spotlight import (
    get_spotlight_settings,
    get_spotlight_status,
    post_spotlight_launch,
    post_spotlight_open_config,
    post_spotlight_open_logs,
    post_spotlight_settings,
    post_spotlight_stop,
)
from devtoolkit.server.ui import EMBEDDED_UI_HTML, get_dashboard_html

def warmup_search_engine_background():
    """Background worker to warm up the search index on server startup."""
    def _worker():
        try:
            from devtoolkit.core.config import load_config
            from devtoolkit.core.search import get_search_engine

            config = load_config()
            raw_roots = getattr(config, "search_paths", []) or []
            target_paths = [Path(r).expanduser().resolve() for r in raw_roots if Path(r).exists() and Path(r).is_dir()]
            if target_paths:
                engine = get_search_engine()
                engine.index_roots(target_paths)
        except Exception:
            pass

    t = threading.Thread(target=_worker, daemon=True)
    t.start()


@asynccontextmanager
async def lifespan(application: FastAPI):
    warmup_search_engine_background()
    yield


app = FastAPI(title="DevToolkit API", version=__version__, lifespan=lifespan)

# The bundled UI is always served from the same loopback origin as the API, so
# cross-origin access is never needed by DevToolkit itself. Allowing any origin
# let every page the user browsed drive this API: launching files via
# /api/action/open-file, terminating processes via /api/ports/kill, and reading
# the whole filesystem index via /api/search/query. Loopback origins only keeps
# local frontend dev servers working while shutting remote pages out.
LOOPBACK_ORIGIN_REGEX = r"^https?://(127(\.\d+){3}|localhost|\[::1\])(:\d+)?$"

app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=LOOPBACK_ORIGIN_REGEX,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def host_without_port(raw_host: str) -> str:
    """Strip the optional port from a Host header value."""
    value = raw_host.strip()
    if value.startswith("["):  # bracketed IPv6 literal, e.g. [::1]:4321
        closing = value.find("]")
        return value[1:closing] if closing != -1 else value[1:]
    if value.count(":") == 1:
        return value.rsplit(":", 1)[0]
    return value


def is_local_host_header(raw_host: str) -> bool:
    """Whether a Host header addressed this server directly rather than via a DNS name.

    Blocks DNS rebinding: a remote page on ``http://attacker.test:4321`` whose
    name resolves to 127.0.0.1 is same-origin to the browser, so CORS never
    applies. Bare IP literals are accepted so that binding to a LAN address
    (``--host 0.0.0.0``) keeps working.
    """
    host = host_without_port(raw_host).lower()
    if not host or host == "localhost" or host.endswith(".localhost"):
        return True
    try:
        ipaddress.ip_address(host)
    except ValueError:
        return False
    return True


@app.middleware("http")
async def reject_rebound_hostnames(request: Request, call_next):
    host_header = request.headers.get("host", "")
    if not is_local_host_header(host_header):
        return JSONResponse(
            status_code=421,
            content={"detail": f"Host '{host_header}' is not a local address for this server."},
        )
    return await call_next(request)


def register_routes(application: FastAPI) -> None:
    """Register modular domain routes directly onto the FastAPI application."""
    # System & Configuration
    application.add_api_route("/api/config", get_config, methods=["GET"], tags=["system"])
    application.add_api_route("/api/config/close-action", post_close_action, methods=["POST"], tags=["system"])
    application.add_api_route("/api/config/search-paths", post_search_path, methods=["POST"], tags=["system"])
    application.add_api_route("/api/config/search-paths", delete_search_path, methods=["DELETE"], tags=["system"])
    application.add_api_route("/api/system", get_system, methods=["GET"], tags=["system"])
    application.add_api_route("/api/health", get_health, methods=["GET"], tags=["system"])
    application.add_api_route("/api/daemon/notify", post_daemon_notify, methods=["POST"], tags=["system"])
    application.add_api_route("/api/daemon/activity", get_daemon_activity, methods=["GET"], tags=["system"])


    # Environment Audit & Tools
    application.add_api_route("/api/audit", get_audit, methods=["GET"], response_model=AuditSummary, tags=["audit"])
    application.add_api_route("/api/audit/stream", stream_audit, methods=["GET"], tags=["audit"])
    application.add_api_route("/api/audit", post_audit, methods=["POST"], response_model=AuditSummary, tags=["audit"])
    application.add_api_route("/api/tools", get_tools, methods=["GET"], tags=["audit"])
    application.add_api_route("/api/tool/{tool_id}/deep", get_tool_deep, methods=["GET"], response_model=DeepTelemetryReport, tags=["audit"])

    # Ports & Sockets
    application.add_api_route("/api/ports", get_ports, methods=["GET"], response_model=List[PortInfo], tags=["ports"])
    application.add_api_route("/api/ports/kill", post_kill_port, methods=["POST"], response_model=PortKillResult, tags=["ports"])

    # Project Auditor
    application.add_api_route("/api/project/audit", post_audit_project, methods=["POST"], response_model=ProjectAuditReport, tags=["project"])

    # Workstation Actions
    application.add_api_route("/api/action/open-file", open_file, methods=["POST"], tags=["actions"])
    application.add_api_route("/api/action/reveal-file", reveal_file, methods=["POST"], tags=["actions"])
    application.add_api_route("/api/action/open-folder", open_folder, methods=["POST"], tags=["actions"])
    application.add_api_route("/api/action/select-folder", post_select_folder, methods=["POST"], tags=["actions"])
    application.add_api_route("/api/action/apply-fix", post_apply_fix, methods=["POST"], tags=["actions"])

    # Search Engine Query, Telemetry & Manual Re-indexing
    application.add_api_route("/api/search", get_search_query, methods=["GET"], tags=["search"])
    application.add_api_route("/api/search/query", post_search_query, methods=["POST"], tags=["search"])
    application.add_api_route("/api/search/query", get_search_query, methods=["GET"], tags=["search"])
    application.add_api_route("/api/search/status", get_search_status, methods=["GET"], tags=["search"])
    application.add_api_route("/api/search/reindex", trigger_reindex, methods=["POST"], tags=["search"])
    application.add_api_route("/api/search/realtime", toggle_realtime, methods=["POST"], tags=["search"])

    # DevSpotlight Desktop Client Management & Settings
    application.add_api_route("/api/spotlight/status", get_spotlight_status, methods=["GET"], tags=["spotlight"])
    application.add_api_route("/api/spotlight/launch", post_spotlight_launch, methods=["POST"], tags=["spotlight"])
    application.add_api_route("/api/spotlight/stop", post_spotlight_stop, methods=["POST"], tags=["spotlight"])
    application.add_api_route("/api/spotlight/settings", get_spotlight_settings, methods=["GET"], tags=["spotlight"])
    application.add_api_route("/api/spotlight/settings", post_spotlight_settings, methods=["POST"], tags=["spotlight"])
    application.add_api_route("/api/spotlight/open-config", post_spotlight_open_config, methods=["POST"], tags=["spotlight"])
    application.add_api_route("/api/spotlight/open-logs", post_spotlight_open_logs, methods=["POST"], tags=["spotlight"])


register_routes(app)

if hasattr(sys, "_MEIPASS"):
    DESIGN_DIR = Path(sys._MEIPASS) / "design"
    ASSETS_DIR = Path(sys._MEIPASS) / "assets"
    STATIC_DIR = Path(sys._MEIPASS) / "devtoolkit" / "server" / "static"
else:
    DESIGN_DIR = Path(__file__).resolve().parent.parent.parent / "design"
    ASSETS_DIR = Path(__file__).resolve().parent.parent.parent / "assets"
    STATIC_DIR = Path(__file__).resolve().parent / "static"

if DESIGN_DIR.exists():
    app.mount("/design", StaticFiles(directory=str(DESIGN_DIR)), name="design")

if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

@app.get("/favicon.ico", include_in_schema=False)
def favicon():
    favicon_path = ASSETS_DIR / "devtoolkit.ico"
    if favicon_path.exists():
        return FileResponse(favicon_path)
    return HTMLResponse(status_code=404)

FRONTEND_DIST = Path(__file__).resolve().parent.parent.parent / "frontend" / "dist"

if FRONTEND_DIST.exists():
    app.mount("/assets", StaticFiles(directory=str(FRONTEND_DIST / "assets")), name="assets")

    @app.get("/{full_path:path}")
    def serve_react_app(full_path: str):
        index_file = FRONTEND_DIST / "index.html"
        if index_file.exists():
            return HTMLResponse(content=index_file.read_text(encoding="utf-8"))
        return HTMLResponse(content="<h1>Frontend build not found</h1>", status_code=404)
else:
    @app.get("/", response_class=HTMLResponse)
    def serve_dashboard() -> str:
        return get_dashboard_html()

def run_server(port: int):
    uvicorn.run(app, host="127.0.0.1", port=port, log_level="warning")


def launch_ui(port: int = 4321, web_only: bool = False, dev: bool = False):
    """Launch or attach to background daemon and open native desktop window or browser."""
    from devtoolkit.client.desktop import launch_desktop_window

    launch_desktop_window(port=port, web_only=web_only, dev=dev)




__all__ = [
    "app",
    "run_server",
    "launch_ui",
    "serve_dashboard",
    "EMBEDDED_UI_HTML",
    "get_dashboard_html",
    "registry",
    "OpenFolderRequest",
    "SearchPathRequest",
    "AuditRequest",
    "KillPortRequest",
    "ProjectAuditRequest",
    "SelectFolderRequest",
    "ApplyFixRequest",
    "get_system",
    "get_health",
    "get_config",
    "post_search_path",
    "delete_search_path",
    "get_audit",
    "stream_audit",
    "get_tools",
    "get_tool_deep",
    "DeepTelemetryReport",
    "post_audit",
    "get_ports",
    "post_kill_port",
    "post_audit_project",
    "open_folder",
    "post_select_folder",
    "post_apply_fix",
    "post_close_action",
    "post_daemon_notify",
]

