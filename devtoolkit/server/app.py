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
    get_health,
    get_system,
    post_close_action,
    post_daemon_notify,
    post_search_path,
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
    application.add_api_route("/api/config/close-action", post_close_action, methods=["POST"], tags=["system"])
    application.add_api_route("/api/config/search-paths", post_search_path, methods=["POST"], tags=["system"])
    application.add_api_route("/api/config/search-paths", delete_search_path, methods=["DELETE"], tags=["system"])
    application.add_api_route("/api/system", get_system, methods=["GET"], tags=["system"])
    application.add_api_route("/api/health", get_health, methods=["GET"], tags=["system"])
    application.add_api_route("/api/daemon/notify", post_daemon_notify, methods=["POST"], tags=["system"])


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
    application.add_api_route("/api/search/query", post_search_query, methods=["POST"], tags=["search"])
    application.add_api_route("/api/search/query", get_search_query, methods=["GET"], tags=["search"])
    application.add_api_route("/api/search/status", get_search_status, methods=["GET"], tags=["search"])
    application.add_api_route("/api/search/reindex", trigger_reindex, methods=["POST"], tags=["search"])
    application.add_api_route("/api/search/realtime", toggle_realtime, methods=["POST"], tags=["search"])


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
    """Launch or attach to background daemon and open native desktop window or browser."""
    from devtoolkit.daemon.manager import is_daemon_alive, start_daemon

    # Check if a native window is already active on Windows
    if not web_only and not dev and sys.platform == "win32":
        try:
            from devtoolkit.daemon.tray import find_existing_window, restore_window_by_hwnd

            hwnd = find_existing_window("DevToolkit ⚡ Workstation Environment Inspector")
            if hwnd:
                restore_window_by_hwnd(hwnd)
                return
        except Exception:
            pass

    if not is_daemon_alive(port=port):
        try:
            start_daemon(port=port)
        except Exception as e:
            # Fallback: run server in-process background thread
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
            print("\nExiting DevToolkit client.")
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

            def _notify_tray():
                try:
                    import json
                    import urllib.request
                    data = json.dumps({
                        "title": "DevToolkit",
                        "message": "DevToolkit minimized to system tray. Click the tray icon anytime to restore.",
                    }).encode("utf-8")
                    req = urllib.request.Request(
                        f"http://127.0.0.1:{port}/api/daemon/notify",
                        data=data,
                        headers={"Content-Type": "application/json", "User-Agent": "DevToolkit-UI"},
                        method="POST",
                    )
                    urllib.request.urlopen(req, timeout=1.0)
                except Exception:
                    pass

            def on_closing() -> bool:
                from devtoolkit.core.config import load_config
                from devtoolkit.daemon.manager import is_daemon_alive, stop_daemon

                if not is_daemon_alive(port=port):
                    return True

                cfg = load_config()
                action = getattr(cfg, "close_action", "ask")

                if action == "minimize":
                    try:
                        window.hide()
                        _notify_tray()
                    except Exception:
                        pass
                    return False

                if action == "exit":
                    stop_daemon()
                    return True

                if sys.platform == "win32":
                    import ctypes

                    MB_YESNOCANCEL = 0x00000003
                    MB_ICONQUESTION = 0x00000020
                    MB_TOPMOST = 0x00040000
                    MB_SETFOREGROUND = 0x00010000
                    IDYES = 6
                    IDNO = 7

                    text = (
                        "DevToolkit background daemon is currently active.\n\n"
                        "Would you like to minimize to the System Tray to keep services running in background, "
                        "or exit completely?\n\n"
                        "• [Yes] Minimize to System Tray\n"
                        "• [No] Exit Completely (Stop all background services)\n"
                        "• [Cancel] Stay in DevToolkit"
                    )
                    title = "DevToolkit"

                    res = ctypes.windll.user32.MessageBoxW(
                        None, text, title, MB_YESNOCANCEL | MB_ICONQUESTION | MB_TOPMOST | MB_SETFOREGROUND
                    )

                    if res == IDYES:
                        try:
                            window.hide()
                            _notify_tray()
                        except Exception:
                            pass
                        return False
                    elif res == IDNO:
                        stop_daemon()
                        return True
                    else:
                        return False

                stop_daemon()
                return True

            window.events.closing += on_closing
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

