"""FastAPI local server and PyWebView desktop window launcher."""

import os
import sys
import threading
import time
import webbrowser
from pathlib import Path
from typing import List

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
import uvicorn

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
from devtoolkit.server.routes.actions import open_folder, post_apply_fix, post_select_folder
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
from devtoolkit.server.routes.search import get_search_status, trigger_reindex
from devtoolkit.server.routes.system import delete_search_path, get_config, get_system, post_search_path
from devtoolkit.server.ui import EMBEDDED_UI_HTML, get_dashboard_html

def warmup_search_engine_background():
    """Background worker to warm up the search index on server startup."""
    def _worker():
        try:
            from devtoolkit.core.config import load_config
            from devtoolkit.core.search import get_search_engine

            config = load_config()
            raw_roots = getattr(config, "search_paths", []) or []
            if not raw_roots:
                common_candidates = [Path("D:/Dev"), Path("C:/Dev")]
                raw_roots = [str(c) for c in common_candidates if c.exists() and c.is_dir()]
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


app = FastAPI(title="DevToolkit API", version="0.2.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def register_routes(application: FastAPI) -> None:
    """Register modular domain routes directly onto the FastAPI application."""
    # System & Configuration
    application.add_api_route("/api/config", get_config, methods=["GET"], tags=["system"])
    application.add_api_route("/api/config/search-paths", post_search_path, methods=["POST"], tags=["system"])
    application.add_api_route("/api/config/search-paths", delete_search_path, methods=["DELETE"], tags=["system"])
    application.add_api_route("/api/system", get_system, methods=["GET"], tags=["system"])

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
    application.add_api_route("/api/action/open-folder", open_folder, methods=["POST"], tags=["actions"])
    application.add_api_route("/api/action/select-folder", post_select_folder, methods=["POST"], tags=["actions"])
    application.add_api_route("/api/action/apply-fix", post_apply_fix, methods=["POST"], tags=["actions"])

    # Search Engine Telemetry & Manual Re-indexing
    application.add_api_route("/api/search/status", get_search_status, methods=["GET"], tags=["search"])
    application.add_api_route("/api/search/reindex", trigger_reindex, methods=["POST"], tags=["search"])


register_routes(app)

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
    """Launch server and open either native desktop window (PyWebView) or browser dashboard."""
    server_thread = threading.Thread(target=run_server, args=(port,), daemon=True)
    server_thread.start()

    time.sleep(0.8)
    url = f"http://127.0.0.1:{port}"

    if web_only or dev:
        print(f"⚡ DevToolkit Web Dashboard running at: {url}")
        webbrowser.open(url)
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print("\nShutting down DevToolkit.")
    else:
        try:
            import webview

            window = webview.create_window(
                title="DevToolkit ⚡ Workstation Environment Inspector",
                url=url,
                width=1140,
                height=780,
                min_size=(880, 600),
                text_select=True,
            )
            webview.start()
        except Exception as e:
            print(f"Note: Could not open native window ({e}). Falling back to default browser.")
            webbrowser.open(url)
            try:
                while True:
                    time.sleep(1)
            except KeyboardInterrupt:
                pass


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
]
