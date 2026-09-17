"""FastAPI local server and PyWebView desktop window launcher."""

import os
import subprocess
import sys
import threading
import time
import webbrowser
from pathlib import Path
from typing import List, Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import uvicorn

from devtoolkit.core.models import AuditSummary
from devtoolkit.core.registry import PluginRegistry
from devtoolkit.core.runner import SafeRunner
from devtoolkit.modules.utilities.ports import PortInfo, PortKillResult, PortManager
from devtoolkit.modules.utilities.project_auditor import ProjectAuditReport, ProjectAuditor

app = FastAPI(title="DevToolkit API", version="0.2.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

registry = PluginRegistry()


class OpenFolderRequest(BaseModel):
    path: str


class SearchPathRequest(BaseModel):
    path: str


class AuditRequest(BaseModel):
    categories: Optional[List[str]] = None
    tool_ids: Optional[List[str]] = None


class KillPortRequest(BaseModel):
    port: int
    force: bool = False


class ProjectAuditRequest(BaseModel):
    path: str



@app.get("/api/config")
def get_config():
    from devtoolkit.core.config import load_config
    return load_config()


@app.post("/api/config/search-paths")
def post_search_path(req: SearchPathRequest):
    from devtoolkit.core.config import add_search_path, load_config
    p = Path(req.path).expanduser().resolve()
    if not p.exists() or not p.is_dir():
        raise HTTPException(status_code=400, detail=f"Directory '{req.path}' does not exist on disk.")
    added = add_search_path(str(p))
    return {"status": "ok", "added": added, "config": load_config()}


@app.delete("/api/config/search-paths")
def delete_search_path(req: SearchPathRequest):
    from devtoolkit.core.config import remove_search_path, load_config
    removed = remove_search_path(req.path)
    return {"status": "ok", "removed": removed, "config": load_config()}


@app.get("/api/system")
def get_system():
    return SafeRunner().get_system_info()


@app.get("/api/audit", response_model=AuditSummary)
def get_audit():
    return registry.run_audit()


@app.post("/api/audit", response_model=AuditSummary)
def post_audit(req: AuditRequest):
    return registry.run_audit(categories=req.categories, tool_ids=req.tool_ids)


@app.get("/api/tools")
def get_tools():
    inspectors = registry.list_inspectors()
    return [
        {
            "id": i.id,
            "name": i.name,
            "category": i.category,
            "categories": getattr(i, "categories", [i.category]),
            "description": i.description,
        }
        for i in inspectors
    ]


@app.post("/api/action/open-folder")
def open_folder(req: OpenFolderRequest):
    raw_path = req.path.strip().strip('"').strip("'")
    p = Path(raw_path)
    if not p.exists():
        raise HTTPException(status_code=404, detail=f"Path '{raw_path}' does not exist on disk.")

    target = str(p if p.is_dir() else p.parent)
    if sys.platform == "win32":
        try:
            os.startfile(target)
        except Exception:
            subprocess.run(["explorer.exe", target])
    elif sys.platform == "darwin":
        subprocess.run(["open", target])
    else:
        subprocess.run(["xdg-open", target])

    return {"status": "ok", "opened": target}


@app.get("/api/ports", response_model=List[PortInfo])
def get_ports(dev_only: bool = False):
    pm = PortManager()
    return pm.list_ports(dev_only=dev_only)


@app.post("/api/ports/kill", response_model=PortKillResult)
def post_kill_port(req: KillPortRequest):
    pm = PortManager()
    return pm.kill_port(req.port, force=req.force)


@app.post("/api/project/audit", response_model=ProjectAuditReport)
def post_audit_project(req: ProjectAuditRequest):
    auditor = ProjectAuditor()
    return auditor.audit_project(Path(req.path))


class ApplyFixRequest(BaseModel):
    command: str


@app.post("/api/action/apply-fix")
def post_apply_fix(req: ApplyFixRequest):
    cmd_str = req.command.strip()
    if not cmd_str:
        raise HTTPException(status_code=400, detail="Empty command")

    # Safe guard: only automatically execute setx on Windows
    if sys.platform == "win32" and cmd_str.lower().startswith("setx "):
        import shlex
        try:
            parts = shlex.split(cmd_str)
            res = SafeRunner().run_command(parts, timeout=3.0)
            if res.ok:
                return {"status": "ok", "message": f"Applied fix successfully: {cmd_str}"}
            else:
                return {"status": "error", "message": res.stderr or "Command failed"}
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    return {"status": "info", "message": f"Command copied. Execute in terminal: {cmd_str}"}


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
    def serve_dashboard():
        return EMBEDDED_UI_HTML


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


EMBEDDED_UI_HTML = r"""<!DOCTYPE html>
<html lang="en" class="dark h-full">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>DevToolkit ⚡ Workstation Suite</title>
  <script src="https://cdn.tailwindcss.com"></script>
  <script>
    tailwind.config = {
      darkMode: 'class',
      theme: {
        extend: {
          colors: {
            brand: { 50: '#f5f3ff', 500: '#3b82f6', 600: '#2563eb', 700: '#1d4ed8' },
            darkBg: '#070a13',
            sidebarBg: '#0a0f1d',
            headerBg: '#090d19',
            cardBg: '#0c1322',
            borderDark: '#1e293b'
          }
        }
      }
    }
  </script>
  <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css" />
  <style>
    body { background-color: #070a13; color: #f1f5f9; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; }
    .glass-card { background: rgba(12, 19, 34, 0.85); backdrop-filter: blur(12px); border: 1px solid rgba(255,255,255,0.07); }
    .glass-card:hover { border-color: rgba(96, 165, 250, 0.35); }
    .modal-backdrop { background: rgba(3, 7, 18, 0.85); backdrop-filter: blur(8px); }
    .custom-scrollbar::-webkit-scrollbar { width: 6px; height: 6px; }
    .custom-scrollbar::-webkit-scrollbar-track { background: transparent; }
    .custom-scrollbar::-webkit-scrollbar-thumb { background: #1e293b; border-radius: 9999px; }
    .custom-scrollbar::-webkit-scrollbar-thumb:hover { background: #334155; }
    .nav-active { background-color: #131d36; color: #ffffff; border-color: rgba(59, 130, 246, 0.45); box-shadow: 0 4px 14px rgba(37, 99, 235, 0.15); }
    .nav-inactive { color: #94a3b8; border-color: transparent; }
    .nav-inactive:hover { color: #f1f5f9; background-color: rgba(30, 41, 59, 0.45); }
    .cat-active { background-color: #1e293b; color: #ffffff; border-color: #3b82f6; }
    .cat-inactive { color: #94a3b8; border-color: #1e293b; }
    .cat-inactive:hover { color: #ffffff; background-color: rgba(30, 41, 59, 0.4); }
  </style>
</head>
<body class="h-full w-full bg-darkBg text-slate-100 font-sans select-none overflow-hidden flex flex-col">

  <!-- Main Viewport Layout: Sidebar + Main Area -->
  <div class="flex flex-1 overflow-hidden">

    <!-- LEFT FIXED VERTICAL SIDEBAR -->
    <aside class="w-56 sm:w-64 bg-sidebarBg border-r border-slate-800/80 flex flex-col p-3 sm:p-3.5 select-none flex-shrink-0 z-20">
      <div class="space-y-4">
        <!-- Brand Header -->
        <div class="flex items-center gap-3 px-1.5 pt-1">
          <div class="w-9 h-9 rounded-xl bg-gradient-to-br from-blue-500 to-indigo-600 flex items-center justify-center text-white shadow-lg shadow-blue-500/25 flex-shrink-0">
            <i class="fa-solid fa-bolt text-lg"></i>
          </div>
          <div class="min-w-0">
            <div class="flex items-center gap-2">
              <h1 class="text-base font-black tracking-tight text-white truncate">DevToolkit</h1>
              <span class="text-[10px] font-mono px-1.5 py-0.2 rounded bg-indigo-500/20 text-indigo-300 font-semibold border border-indigo-500/30 flex-shrink-0">v0.2.0</span>
            </div>
            <div class="text-[11px] text-slate-400 font-medium truncate" id="side-os-info">Windows 11 (x64)</div>
          </div>
        </div>

        <!-- Host Pill -->
        <div class="bg-[#0e1526] border border-slate-800/90 rounded-lg px-3 py-1.5 flex items-center text-xs min-w-0">
          <span class="flex items-center gap-2 text-slate-300 font-medium text-[11px] truncate">
            <span class="w-2 h-2 rounded-full bg-emerald-400 shadow-[0_0_6px_#34d399] flex-shrink-0"></span>
            Host: <span id="side-host-name" class="text-white font-semibold truncate">DEXTER-2</span>
          </span>
        </div>

        <!-- Navigation Group: WORKSPACE HUB -->
        <div>
          <div class="text-[10px] font-bold text-slate-500 tracking-wider uppercase px-2 mb-1.5 mt-3">WORKSPACE HUB</div>
          <div class="space-y-1">
            <button onclick="switchTab('env')" id="nav-btn-env" class="w-full flex items-center justify-between px-3 py-2 rounded-xl text-xs font-semibold transition border nav-active">
              <div class="flex items-center gap-2.5 truncate">
                <i class="fa-solid fa-table-cells-large text-blue-400 flex-shrink-0"></i>
                <span class="truncate">Environment</span>
              </div>
              <span class="w-2 h-2 rounded-full bg-blue-400 shadow-[0_0_8px_#60a5fa] flex-shrink-0" id="dot-env"></span>
            </button>

            <button onclick="switchTab('ports')" id="nav-btn-ports" class="w-full flex items-center justify-between px-3 py-2 rounded-xl text-xs font-semibold transition border nav-inactive">
              <div class="flex items-center gap-2.5 truncate">
                <i class="fa-solid fa-network-wired flex-shrink-0"></i>
                <span class="truncate">Port Manager</span>
              </div>
              <span id="side-ports-badge" class="px-2 py-0.5 rounded-full text-[10px] font-mono font-bold bg-blue-500/20 text-blue-300 border border-blue-500/30 flex-shrink-0">0</span>
            </button>

            <button onclick="switchTab('project')" id="nav-btn-project" class="w-full flex items-center justify-between px-3 py-2 rounded-xl text-xs font-semibold transition border nav-inactive">
              <div class="flex items-center gap-2.5 truncate">
                <i class="fa-solid fa-code-branch flex-shrink-0"></i>
                <span class="truncate">Project Auditor</span>
              </div>
            </button>
          </div>
        </div>

        <!-- Navigation Group: PREFERENCES -->
        <div>
          <div class="text-[10px] font-bold text-slate-500 tracking-wider uppercase px-2 mb-1.5 mt-4">PREFERENCES</div>
          <div class="space-y-1">
            <button onclick="switchTab('settings')" id="nav-btn-settings" class="w-full flex items-center justify-between px-3 py-2 rounded-xl text-xs font-semibold transition border nav-inactive">
              <div class="flex items-center gap-2.5 truncate">
                <i class="fa-solid fa-gear flex-shrink-0"></i>
                <span class="truncate">Settings</span>
              </div>
            </button>
          </div>
        </div>
      </div>
    </aside>

    <!-- RIGHT MAIN CONTENT PANEL -->
    <div class="flex-1 flex flex-col overflow-hidden bg-darkBg min-w-0">

      <!-- Top Header: Breadcrumbs + Global Search + Actions -->
      <header class="h-14 px-4 sm:px-6 border-b border-slate-800/80 flex items-center justify-between bg-[#090d19]/90 backdrop-blur-md flex-shrink-0 z-10 gap-3">
        <!-- Breadcrumbs -->
        <div class="flex items-center gap-2 text-xs text-slate-400 font-medium select-none min-w-0 truncate">
          <span class="text-slate-500 font-mono flex-shrink-0">toolkit</span>
          <span class="text-slate-600 flex-shrink-0">/</span>
          <span class="flex items-center gap-1.5 text-white font-semibold truncate" id="top-breadcrumb">
            <span class="w-1.5 h-1.5 rounded-full bg-blue-400 shadow-[0_0_6px_#60a5fa] flex-shrink-0"></span>
            Environment & Diagnostics
          </span>
        </div>

        <!-- Global Search Bar & Actions -->
        <div class="flex items-center gap-2 sm:gap-3 flex-shrink-0">
          <div class="relative w-36 sm:w-64 md:w-80 lg:w-96" id="top-search-wrapper">
            <i class="fa-solid fa-search absolute left-3 top-2.5 text-xs text-slate-400"></i>
            <input type="text" id="global-search-input" oninput="onSearchChange()" placeholder="Search SDK, runtime, path..." class="w-full pl-8 pr-14 sm:pr-16 py-1.5 bg-[#070a13] border border-slate-800/90 rounded-lg text-xs text-white placeholder-slate-500 focus:outline-none focus:border-blue-500 transition font-sans" />
            <kbd class="absolute right-2 top-2 px-1.5 py-0.5 rounded bg-slate-800/80 border border-slate-700/80 text-[10px] font-mono text-slate-400 hidden sm:inline">Ctrl+K</kbd>
          </div>

          <button onclick="refreshActiveTab()" id="rescan-btn" class="flex items-center gap-1.5 sm:gap-2 px-2.5 sm:px-3.5 py-1.5 bg-[#0e1526] hover:bg-[#131d36] text-slate-200 border border-slate-700/80 rounded-lg text-xs font-semibold transition shadow-sm flex-shrink-0">
            <i class="fa-solid fa-rotate text-xs" id="rescan-icon"></i>
            <span class="hidden sm:inline">Rescan</span>
            <span class="text-[10px] font-mono text-slate-400" id="rescan-timer">(now)</span>
          </button>

          <button onclick="toggleHelpModal()" class="p-2 hover:bg-slate-800/60 text-slate-400 hover:text-white rounded-lg transition flex-shrink-0" title="Shortcuts & Help (?)">
            <i class="fa-regular fa-circle-question text-sm"></i>
          </button>
        </div>
      </header>

      <!-- Scrollable Main Content -->
      <main class="flex-1 overflow-y-auto p-4 sm:p-6 space-y-5 sm:space-y-6 custom-scrollbar">

        <!-- ==================== VIEW 1: ENVIRONMENT AUDITOR ==================== -->
        <div id="view-env" class="space-y-6">

          <!-- 6 Horizontal Stat Cards (Responsive: 2 cols on mobile, 3 cols on medium/narrow, 6 cols on xl desktop) -->
          <div class="grid grid-cols-2 sm:grid-cols-3 xl:grid-cols-6 gap-3 sm:gap-4" id="stats-container">
            <!-- 1. Audited Tools -->
            <div class="glass-card rounded-xl p-3.5 sm:p-4 flex flex-col justify-between relative overflow-hidden min-w-0">
              <div class="flex items-center justify-between gap-1 text-xs text-slate-400 font-medium min-w-0">
                <span class="truncate">Audited Tools</span>
                <i class="fa-regular fa-pen-to-square text-[11px] text-slate-500 flex-shrink-0"></i>
              </div>
              <div class="flex items-baseline justify-between gap-2 my-2 min-w-0">
                <div class="text-xl sm:text-2xl font-black text-white tracking-tight leading-none flex-shrink-0" id="stat-total">10</div>
                <div class="text-[10px] sm:text-[11px] text-slate-400 font-mono truncate text-right">100% total</div>
              </div>
              <div class="w-full h-1 rounded-full bg-slate-800 overflow-hidden">
                <div class="h-full bg-slate-500 rounded-full w-full"></div>
              </div>
            </div>

            <!-- 2. Installed -->
            <div class="glass-card rounded-xl p-3.5 sm:p-4 flex flex-col justify-between relative overflow-hidden min-w-0">
              <div class="flex items-center justify-between gap-1 text-xs text-slate-400 font-medium min-w-0">
                <span class="truncate">Installed</span>
                <span class="w-2 h-2 rounded-full bg-emerald-400 shadow-[0_0_6px_#34d399] flex-shrink-0"></span>
              </div>
              <div class="flex items-baseline justify-between gap-2 my-2 min-w-0">
                <div class="text-xl sm:text-2xl font-black text-white tracking-tight leading-none flex-shrink-0" id="stat-installed">—</div>
                <div class="text-[10px] sm:text-[11px] text-emerald-400 font-mono truncate text-right" id="stat-coverage">— coverage</div>
              </div>
              <div class="w-full h-1 rounded-full bg-slate-800 overflow-hidden">
                <div class="h-full bg-emerald-500 rounded-full transition-all duration-500" id="stat-installed-bar" style="width: 70%"></div>
              </div>
            </div>

            <!-- 3. Healthy -->
            <div class="glass-card rounded-xl p-3.5 sm:p-4 flex flex-col justify-between relative overflow-hidden min-w-0">
              <div class="flex items-center justify-between gap-1 text-xs text-slate-400 font-medium min-w-0">
                <span class="truncate">Healthy</span>
                <span class="text-[10px] px-1.5 py-0.2 rounded bg-emerald-500/20 text-emerald-300 font-semibold border border-emerald-500/30 flex-shrink-0">Optimal</span>
              </div>
              <div class="flex items-baseline justify-between gap-2 my-2 min-w-0">
                <div class="text-xl sm:text-2xl font-black text-white tracking-tight leading-none flex-shrink-0" id="stat-healthy">—</div>
                <div class="text-[10px] sm:text-[11px] text-emerald-400 font-mono truncate text-right">Ready to build</div>
              </div>
              <div class="w-full h-1 rounded-full bg-slate-800 overflow-hidden">
                <div class="h-full bg-emerald-400 rounded-full transition-all duration-500" id="stat-healthy-bar" style="width: 60%"></div>
              </div>
            </div>

            <!-- 4. Action Needed -->
            <div class="glass-card rounded-xl p-3.5 sm:p-4 flex flex-col justify-between relative overflow-hidden min-w-0">
              <div class="flex items-center justify-between gap-1 text-xs text-slate-400 font-medium min-w-0">
                <span class="truncate">Action Needed</span>
                <span class="w-2 h-2 rounded-full bg-amber-400 shadow-[0_0_6px_#fbbf24] flex-shrink-0"></span>
              </div>
              <div class="flex items-baseline justify-between gap-2 my-2 min-w-0">
                <div class="text-xl sm:text-2xl font-black text-white tracking-tight leading-none flex-shrink-0" id="stat-warning">—</div>
                <div class="text-[10px] sm:text-[11px] text-amber-400 font-mono truncate text-right">Path & Var</div>
              </div>
              <div class="w-full h-1 rounded-full bg-slate-800 overflow-hidden">
                <div class="h-full bg-amber-400 rounded-full transition-all duration-500" id="stat-warning-bar" style="width: 20%"></div>
              </div>
            </div>

            <!-- 5. Critical Errors -->
            <div class="glass-card rounded-xl p-3.5 sm:p-4 flex flex-col justify-between relative overflow-hidden min-w-0">
              <div class="flex items-center justify-between gap-1 text-xs text-slate-400 font-medium min-w-0">
                <span class="truncate">Critical Errors</span>
                <span class="w-2 h-2 rounded-full bg-slate-500 flex-shrink-0"></span>
              </div>
              <div class="flex items-baseline justify-between gap-2 my-2 min-w-0">
                <div class="text-xl sm:text-2xl font-black text-white tracking-tight leading-none flex-shrink-0" id="stat-error">—</div>
                <div class="text-[10px] sm:text-[11px] text-slate-400 font-mono truncate text-right">No crash flags</div>
              </div>
              <div class="w-full h-1 rounded-full bg-slate-800 overflow-hidden">
                <div class="h-full bg-rose-500 rounded-full transition-all duration-500" id="stat-error-bar" style="width: 0%"></div>
              </div>
            </div>

            <!-- 6. Not Found -->
            <div class="glass-card rounded-xl p-3.5 sm:p-4 flex flex-col justify-between relative overflow-hidden min-w-0">
              <div class="flex items-center justify-between gap-1 text-xs text-slate-400 font-medium min-w-0">
                <span class="truncate">Not Found</span>
                <span class="w-2 h-2 rounded-full bg-slate-600 flex-shrink-0"></span>
              </div>
              <div class="flex items-baseline justify-between gap-2 my-2 min-w-0">
                <div class="text-xl sm:text-2xl font-black text-white tracking-tight leading-none flex-shrink-0" id="stat-missing">—</div>
                <div class="text-[10px] sm:text-[11px] text-slate-400 font-mono truncate text-right">Unconfigured</div>
              </div>
              <div class="w-full h-1 rounded-full bg-slate-800 overflow-hidden">
                <div class="h-full bg-slate-700 rounded-full transition-all duration-500" id="stat-missing-bar" style="width: 30%"></div>
              </div>
            </div>
          </div>

          <!-- Category Filter Pills + Layout Toggle & Sort Bar -->
          <div class="flex flex-col sm:flex-row items-center justify-between gap-3 bg-[#0a0f1e]/70 p-2.5 rounded-xl border border-slate-800/80">
            <!-- Left: Filter Pills with Counts -->
            <div class="flex items-center gap-1.5 overflow-x-auto w-full sm:w-auto pb-1 sm:pb-0 custom-scrollbar" id="category-filters">
              <button onclick="setCategory('all')" class="cat-btn px-3 py-1.5 rounded-lg text-xs font-semibold bg-[#131d36] text-white border border-blue-500/40 shadow-sm transition flex-shrink-0" data-cat="all">
                All <span class="ml-1 text-[10px] text-blue-300 font-mono" id="cat-count-all">0</span>
              </button>
              <button onclick="setCategory('runtime')" class="cat-btn px-3 py-1.5 rounded-lg text-xs font-semibold text-slate-400 hover:text-white hover:bg-slate-800/50 border border-transparent transition flex-shrink-0" data-cat="runtime">
                Runtimes <span class="ml-1 text-[10px] text-slate-500 font-mono" id="cat-count-runtime">0</span>
              </button>
              <button onclick="setCategory('mobile')" class="cat-btn px-3 py-1.5 rounded-lg text-xs font-semibold text-slate-400 hover:text-white hover:bg-slate-800/50 border border-transparent transition flex-shrink-0" data-cat="mobile">
                Mobile & SDKs <span class="ml-1 text-[10px] text-slate-500 font-mono" id="cat-count-mobile">0</span>
              </button>
              <button onclick="setCategory('ide')" class="cat-btn px-3 py-1.5 rounded-lg text-xs font-semibold text-slate-400 hover:text-white hover:bg-slate-800/50 border border-transparent transition flex-shrink-0" data-cat="ide">
                IDEs & Editors <span class="ml-1 text-[10px] text-slate-500 font-mono" id="cat-count-ide">0</span>
              </button>
              <button onclick="setCategory('vcs')" class="cat-btn px-3 py-1.5 rounded-lg text-xs font-semibold text-slate-400 hover:text-white hover:bg-slate-800/50 border border-transparent transition flex-shrink-0" data-cat="vcs">
                VCS / Git <span class="ml-1 text-[10px] text-slate-500 font-mono" id="cat-count-vcs">0</span>
              </button>
              <button onclick="setCategory('container')" class="cat-btn px-3 py-1.5 rounded-lg text-xs font-semibold text-slate-400 hover:text-white hover:bg-slate-800/50 border border-transparent transition flex-shrink-0" data-cat="container">
                Containers <span class="ml-1 text-[10px] text-slate-500 font-mono" id="cat-count-container">0</span>
              </button>
            </div>

            <!-- Right: Layout Switcher & Sort Selector -->
            <div class="flex items-center gap-2.5 w-full sm:w-auto justify-end flex-shrink-0">
              <div class="flex items-center bg-slate-900 border border-slate-800 rounded-lg p-0.5">
                <button onclick="setLayout('grid')" id="layout-grid-btn" class="p-1.5 rounded-md text-xs bg-blue-600/30 text-blue-400 hover:text-white transition" title="Grid Layout">
                  <i class="fa-solid fa-table-cells-large"></i>
                </button>
                <button onclick="setLayout('list')" id="layout-list-btn" class="p-1.5 rounded-md text-xs text-slate-400 hover:text-white transition" title="List Layout">
                  <i class="fa-solid fa-list-ul"></i>
                </button>
              </div>

              <select id="sort-select" onchange="onSortChange()" class="bg-slate-900 border border-slate-800 rounded-lg px-2.5 py-1.5 text-xs text-slate-300 focus:outline-none focus:border-blue-500 cursor-pointer">
                <option value="severity">Sort: Severity</option>
                <option value="name">Sort: Name</option>
                <option value="category">Sort: Category</option>
                <option value="status">Sort: Status</option>
              </select>
            </div>
          </div>

          <!-- Active Custom Search Paths Banner -->
          <div id="search-paths-banner" class="hidden text-xs bg-[#0c1322] border border-blue-500/30 rounded-xl px-4 py-2.5 flex items-center justify-between">
            <div class="flex items-center gap-2 truncate mr-3">
              <i class="fa-solid fa-folder-tree text-blue-400 flex-shrink-0"></i>
              <span class="text-slate-400 flex-shrink-0">Custom Monitored Directories:</span>
              <span id="banner-paths-list" class="font-mono text-blue-300 truncate"></span>
            </div>
            <button onclick="switchTab('settings')" class="text-blue-400 hover:text-blue-300 font-semibold text-xs flex-shrink-0">Manage Paths &rarr;</button>
          </div>

          <!-- Tools Container: Grid View with standard gap-5 lg:gap-6 -->
          <div class="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-5 lg:gap-6" id="tools-grid"></div>

          <!-- Tools Container: List View -->
          <div id="tools-list-container" class="hidden glass-card rounded-xl border border-slate-800 overflow-hidden shadow-xl">
            <div class="overflow-x-auto">
              <table class="w-full text-left text-xs">
                <thead class="bg-slate-950/90 text-slate-400 uppercase tracking-wider text-[10px] border-b border-slate-800 font-semibold">
                  <tr>
                    <th class="py-3 px-4">Tool</th>
                    <th class="py-3 px-4">Category</th>
                    <th class="py-3 px-4">Status</th>
                    <th class="py-3 px-4">Version</th>
                    <th class="py-3 px-4">Home / Root Path</th>
                    <th class="py-3 px-4">Binary Path</th>
                    <th class="py-3 px-4 text-right">Actions</th>
                  </tr>
                </thead>
                <tbody id="tools-list-tbody" class="divide-y divide-slate-800/60 font-sans"></tbody>
              </table>
            </div>
          </div>
        </div>

        <!-- ==================== VIEW 2: PORT MANAGER ==================== -->
        <div id="view-ports" class="space-y-6 hidden">
          <!-- Port Stats -->
          <div class="grid grid-cols-1 sm:grid-cols-3 gap-3.5">
            <div class="glass-card rounded-xl p-4 flex items-center gap-3">
              <div class="w-10 h-10 rounded-lg bg-blue-500/20 text-blue-400 flex items-center justify-center font-bold text-lg"><i class="fa-solid fa-satellite-dish"></i></div>
              <div>
                <div class="text-xs text-slate-400 font-medium">Listening Sockets</div>
                <div class="text-xl font-bold text-white mt-0.5" id="stat-ports-total">—</div>
              </div>
            </div>
            <div class="glass-card rounded-xl p-4 flex items-center gap-3">
              <div class="w-10 h-10 rounded-lg bg-indigo-500/20 text-indigo-400 flex items-center justify-center font-bold text-lg"><i class="fa-solid fa-code"></i></div>
              <div>
                <div class="text-xs text-slate-400 font-medium">Developer Ports Active</div>
                <div class="text-xl font-bold text-indigo-400 mt-0.5" id="stat-ports-dev">—</div>
              </div>
            </div>
            <div class="glass-card rounded-xl p-4 flex items-center gap-3">
              <div class="w-10 h-10 rounded-lg bg-slate-500/20 text-slate-400 flex items-center justify-center font-bold text-lg"><i class="fa-solid fa-shield-halved"></i></div>
              <div>
                <div class="text-xs text-slate-400 font-medium">System Protected</div>
                <div class="text-xl font-bold text-slate-300 mt-0.5" id="stat-ports-crit">—</div>
              </div>
            </div>
          </div>

          <!-- Ports Filter Bar -->
          <div class="flex flex-col sm:flex-row items-center justify-between gap-3 bg-[#0a0f1e]/70 p-3 rounded-xl border border-slate-800/80">
            <div class="flex items-center gap-3 w-full sm:w-auto">
              <label class="inline-flex items-center gap-2 cursor-pointer text-xs font-semibold text-slate-300 bg-slate-800/80 px-3 py-1.5 rounded-lg border border-slate-700 hover:bg-slate-700/80 transition">
                <input type="checkbox" id="ports-dev-toggle" onchange="fetchPorts()" class="rounded border-slate-600 text-blue-600 focus:ring-blue-500" />
                <span>Developer Ports Only</span>
              </label>
              <button onclick="fetchPorts()" class="px-3 py-1.5 bg-[#0e1526] hover:bg-[#131d36] text-slate-300 hover:text-white border border-slate-700/80 rounded-lg text-xs font-semibold transition flex items-center gap-1.5 shadow-sm">
                <i class="fa-solid fa-rotate text-xs"></i>
                <span>Refresh</span>
              </button>
              <span class="text-xs text-slate-500 hidden sm:inline">• Highlights 3000, 5173, 8080, 27017, etc.</span>
            </div>
            <div class="relative w-full sm:w-72">
              <i class="fa-solid fa-search absolute left-3 top-2.5 text-xs text-slate-400"></i>
              <input type="text" id="ports-search-input" oninput="renderPortsTable()" placeholder="Filter port, process, PID..." class="w-full pl-8 pr-3 py-1.5 bg-[#070a13] border border-slate-800/90 rounded-lg text-xs text-white placeholder-slate-500 focus:outline-none focus:border-blue-500 transition" />
            </div>
          </div>

          <!-- Ports Table -->
          <div class="glass-card rounded-xl border border-slate-800 overflow-hidden shadow-xl">
            <div class="overflow-x-auto">
              <table class="w-full text-left text-xs">
                <thead class="bg-slate-950/90 text-slate-400 uppercase tracking-wider text-[10px] border-b border-slate-800 font-semibold">
                  <tr>
                    <th class="py-3 px-4">Port</th>
                    <th class="py-3 px-4">Tag</th>
                    <th class="py-3 px-4">Process Name</th>
                    <th class="py-3 px-4">PID</th>
                    <th class="py-3 px-4">Address</th>
                    <th class="py-3 px-4">Status</th>
                    <th class="py-3 px-4 text-right">Action</th>
                  </tr>
                </thead>
                <tbody id="ports-table-body" class="divide-y divide-slate-800/60 font-sans"></tbody>
              </table>
            </div>
          </div>
        </div>

        <!-- ==================== VIEW 3: PROJECT AUDITOR ==================== -->
        <div id="view-project" class="space-y-6 hidden">
          <!-- Selection Card -->
          <div class="glass-card rounded-xl p-6 border border-slate-800 space-y-4">
            <div class="flex items-start justify-between gap-4">
              <div>
                <h2 class="text-lg font-bold text-white flex items-center gap-2">
                  <i class="fa-solid fa-folder-tree text-blue-400"></i>
                  Project Workstation Readiness Auditor
                </h2>
                <p class="text-xs text-slate-400 mt-1">
                  Select any workspace directory or project repo on your disk to verify if your workstation satisfies its SDK, runtime, compiler, and environment requirements.
                </p>
              </div>
            </div>

            <div class="flex flex-col sm:flex-row items-center gap-2 pt-2">
              <div class="relative flex-1 w-full">
                <i class="fa-regular fa-folder absolute left-3 top-3 text-xs text-slate-400"></i>
                <input type="text" id="project-path-input" placeholder="e.g. D:\\UtilitySoftware or D:\\Dev\\my-app" class="w-full pl-8 pr-3 py-2 bg-[#070a13] border border-slate-700/80 rounded-lg text-xs font-mono text-white placeholder-slate-500 focus:outline-none focus:border-blue-500 transition" />
              </div>
              <button onclick="runProjectAudit()" id="btn-audit-project" class="w-full sm:w-auto px-5 py-2 bg-blue-600 hover:bg-blue-500 text-white rounded-lg text-xs font-bold transition flex items-center justify-center gap-2 shadow-sm">
                <i class="fa-solid fa-wand-magic-sparkles" id="audit-project-icon"></i>
                <span>Scan Project</span>
              </button>
            </div>

            <div class="flex items-center gap-2 text-[11px] text-slate-400">
              <span>Quick Preset:</span>
              <button onclick="setProjectInput('.')" class="px-2 py-0.5 rounded bg-slate-800 hover:bg-slate-700 text-slate-300 font-mono transition">Current Directory (.)</button>
            </div>
          </div>

          <!-- Audit Results Container -->
          <div id="project-results-container" class="space-y-4 hidden">
            <!-- Header Card -->
            <div id="project-header-card" class="glass-card rounded-xl p-5 flex flex-col md:flex-row md:items-center justify-between gap-4">
              <div>
                <div class="flex items-center gap-2">
                  <h3 class="text-lg font-bold text-white" id="rep-project-name">—</h3>
                  <div id="rep-detected-types" class="flex flex-wrap gap-1.5"></div>
                </div>
                <p class="text-xs font-mono text-slate-400 mt-1" id="rep-project-path">—</p>
              </div>
              <div id="rep-status-badge"></div>
            </div>

            <!-- Requirements Checklist Table -->
            <div class="glass-card rounded-xl border border-slate-800 overflow-hidden">
              <div class="px-5 py-3.5 bg-slate-950/80 border-b border-slate-800 flex items-center justify-between">
                <h4 class="text-xs font-bold text-white uppercase tracking-wider flex items-center gap-2">
                  <i class="fa-solid fa-list-check text-blue-400"></i>
                  Prerequisites Checklist
                </h4>
              </div>
              <div class="overflow-x-auto">
                <table class="w-full text-left text-xs">
                  <thead class="bg-slate-950/50 text-slate-400 uppercase tracking-wider text-[10px] border-b border-slate-800 font-semibold">
                    <tr>
                      <th class="py-2.5 px-4">Status</th>
                      <th class="py-2.5 px-4">Requirement</th>
                      <th class="py-2.5 px-4">Expected</th>
                      <th class="py-2.5 px-4">Detected</th>
                      <th class="py-2.5 px-4">Diagnostic Details</th>
                    </tr>
                  </thead>
                  <tbody id="project-checks-tbody" class="divide-y divide-slate-800/60"></tbody>
                </table>
              </div>
            </div>

            <!-- Recommended Setup Actions -->
            <div id="project-actions-card" class="glass-card rounded-xl p-5 space-y-3 hidden border-amber-500/30 bg-amber-500/5">
              <h4 class="text-xs font-bold text-amber-400 uppercase tracking-wider flex items-center gap-2">
                <i class="fa-solid fa-lightbulb"></i>
                Recommended Setup Commands
              </h4>
              <div id="project-actions-list" class="space-y-2"></div>
            </div>
          </div>
        </div>

        <!-- ==================== VIEW 4: SETTINGS & SEARCH ROOTS ==================== -->
        <div id="view-settings" class="space-y-6 hidden">
          <!-- Monitored Search Roots Card -->
          <div class="glass-card rounded-xl p-6 border border-slate-800 space-y-5">
            <div class="flex items-center gap-3">
              <div class="w-9 h-9 rounded-lg bg-blue-600/20 text-blue-400 flex items-center justify-center font-bold">
                <i class="fa-solid fa-folder-tree"></i>
              </div>
              <div>
                <h2 class="text-base font-bold text-white">Monitored Search Directories (Layer 4)</h2>
                <p class="text-xs text-slate-400">Configure root directories where DevToolkit recursively probes for SDKs by structural signature.</p>
              </div>
            </div>

            <div>
              <label class="block text-xs font-semibold text-slate-300 mb-1.5">Add Custom Root Directory</label>
              <div class="flex items-center gap-2">
                <input type="text" id="settings-path-input" placeholder="e.g. D:\\Dev or /opt/custom_sdks" class="flex-1 bg-[#070a13] border border-slate-700/80 rounded-lg px-3 py-2 text-xs text-white placeholder-slate-500 font-mono focus:outline-none focus:border-blue-500" />
                <button onclick="submitSearchPath()" class="px-4 py-2 bg-blue-600 hover:bg-blue-500 text-white rounded-lg text-xs font-bold transition flex items-center gap-1.5 shadow-sm">
                  <i class="fa-solid fa-plus"></i>
                  <span>Add Path</span>
                </button>
              </div>
              <div class="mt-2 flex items-center gap-2">
                <span class="text-[11px] text-slate-500">Quick Suggestions:</span>
                <button onclick="fillSettingsPath('D:\\\\Dev')" class="text-[11px] px-2 py-0.5 rounded bg-slate-800 hover:bg-slate-700 text-slate-300 font-mono transition">+ D:\Dev</button>
                <button onclick="fillSettingsPath('C:\\\\Dev')" class="text-[11px] px-2 py-0.5 rounded bg-slate-800 hover:bg-slate-700 text-slate-300 font-mono transition">+ C:\Dev</button>
              </div>
            </div>

            <div>
              <h3 class="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-2">Active Monitored Directories</h3>
              <div id="settings-paths-list" class="space-y-2 max-h-48 overflow-y-auto custom-scrollbar"></div>
            </div>

            <div class="p-4 rounded-xl bg-blue-500/10 border border-blue-500/20 text-xs text-blue-300 space-y-1">
              <div class="font-bold flex items-center gap-1.5"><i class="fa-solid fa-shield-halved"></i> Generalized Content Signature Discovery</div>
              <p class="text-slate-300 text-[11px]">DevToolkit avoids hardcoded paths. When you add a root folder, it recursively detects binary signatures (e.g. <code>platform-tools/adb.exe</code> or <code>bin/javac.exe</code>) regardless of naming conventions.</p>
            </div>
          </div>

          <!-- Workstation System Specs Card -->
          <div class="glass-card rounded-xl p-6 border border-slate-800 space-y-4">
            <h3 class="text-sm font-bold text-white flex items-center gap-2">
              <i class="fa-solid fa-microchip text-slate-400"></i>
              Workstation System Overview
            </h3>
            <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3 text-xs">
              <div class="p-3 rounded-lg bg-[#070a13] border border-slate-800">
                <div class="text-slate-500 font-medium">Operating System</div>
                <div class="font-bold text-white mt-1" id="sys-os">—</div>
              </div>
              <div class="p-3 rounded-lg bg-[#070a13] border border-slate-800">
                <div class="text-slate-500 font-medium">Architecture</div>
                <div class="font-bold text-white mt-1" id="sys-arch">—</div>
              </div>
              <div class="p-3 rounded-lg bg-[#070a13] border border-slate-800">
                <div class="text-slate-500 font-medium">Host Machine</div>
                <div class="font-bold text-white mt-1" id="sys-host">—</div>
              </div>
              <div class="p-3 rounded-lg bg-[#070a13] border border-slate-800">
                <div class="text-slate-500 font-medium">Python Runtime</div>
                <div class="font-bold text-emerald-400 mt-1" id="sys-python">—</div>
              </div>
            </div>
          </div>
        </div>

      </main>

      <!-- PERSISTENT BOTTOM STATUS BAR -->
      <footer class="h-9 px-4 sm:px-5 bg-[#080d18] border-t border-slate-800/80 text-[11px] text-slate-400 flex items-center justify-between flex-shrink-0 z-20 select-none">
        <div class="flex items-center gap-2 sm:gap-2.5 truncate">
          <span class="flex items-center gap-1.5 truncate">
            <span class="w-2 h-2 rounded-full bg-emerald-400 shadow-[0_0_6px_#34d399] flex-shrink-0"></span>
            Environment Watcher: <strong class="text-slate-200 font-semibold truncate">Active</strong>
          </span>
          <span class="text-slate-700 hidden sm:inline">|</span>
          <span class="font-mono hidden sm:inline">PATH Entries: <strong class="text-slate-200" id="status-path-count">25</strong></span>
          <span class="text-slate-700 hidden md:inline">|</span>
          <span class="font-mono hidden md:inline">RAM Footprint: <strong class="text-slate-200" id="status-ram-count">114 MB</strong></span>
        </div>

        <div class="flex items-center gap-2 sm:gap-3 flex-shrink-0">
          <button onclick="refreshActiveTab()" class="hover:text-white transition flex items-center gap-1">
            <kbd class="px-1.5 py-0.2 rounded bg-slate-800 border border-slate-700 text-[10px] font-mono text-slate-300">R</kbd>
            <span class="hidden sm:inline">Rescan</span>
          </button>
          <button onclick="toggleHelpModal()" class="hover:text-white transition flex items-center gap-1">
            <kbd class="px-1.5 py-0.2 rounded bg-slate-800 border border-slate-700 text-[10px] font-mono text-slate-300">?</kbd>
            <span>Help</span>
          </button>
        </div>
      </footer>

    </div>
  </div>

  <!-- MODAL 1: TERMINATE PROCESS ON PORT -->
  <div id="kill-modal" class="fixed inset-0 modal-backdrop z-50 flex items-center justify-center p-4 hidden">
    <div class="bg-slate-900 border border-slate-700 rounded-2xl max-w-md w-full p-6 shadow-2xl space-y-4">
      <div class="flex items-center gap-3 text-rose-400">
        <div class="w-10 h-10 rounded-xl bg-rose-500/20 flex items-center justify-center font-bold text-lg flex-shrink-0">
          <i class="fa-solid fa-triangle-exclamation"></i>
        </div>
        <div>
          <h3 class="text-base font-bold text-white">Terminate Process on Port</h3>
          <p class="text-xs text-slate-400">This action will immediately stop the occupying process.</p>
        </div>
      </div>

      <div class="bg-slate-950 p-3 rounded-xl border border-slate-800 text-xs space-y-1.5 font-mono">
        <div class="flex justify-between"><span class="text-slate-500">Port:</span> <span class="text-blue-300 font-bold" id="modal-kill-port">:—</span></div>
        <div class="flex justify-between"><span class="text-slate-500">Process:</span> <span class="text-white" id="modal-kill-name">—</span></div>
        <div class="flex justify-between"><span class="text-slate-500">PID:</span> <span class="text-yellow-400" id="modal-kill-pid">—</span></div>
      </div>

      <div id="modal-kill-warning" class="hidden p-3 rounded-xl bg-rose-500/10 border border-rose-500/25 text-rose-300 text-xs space-y-2">
        <div class="font-bold flex items-center gap-1.5"><i class="fa-solid fa-triangle-exclamation"></i> Operating System Warning</div>
        <p class="text-[11px] text-slate-300">This process is classified as system-critical. Force terminating it may disrupt system services or cause a reboot.</p>
        <label class="flex items-center gap-2 cursor-pointer pt-1">
          <input type="checkbox" id="modal-force-checkbox" class="rounded border-rose-500 text-rose-600 focus:ring-rose-500" />
          <span class="text-[11px] font-bold text-rose-400">I understand the risk, force terminate</span>
        </label>
      </div>

      <div class="flex justify-end gap-2 pt-2 border-t border-slate-800">
        <button onclick="closeKillModal()" class="px-4 py-2 bg-slate-800 hover:bg-slate-700 text-slate-300 rounded-lg text-xs font-semibold transition">Cancel</button>
        <button onclick="submitKillPort()" id="btn-confirm-kill" class="px-4 py-2 bg-rose-600 hover:bg-rose-500 text-white rounded-lg text-xs font-bold transition flex items-center gap-1.5 shadow-sm">
          <i class="fa-solid fa-power-off"></i>
          <span>Kill Process</span>
        </button>
      </div>
    </div>
  </div>

  <!-- MODAL 2: KEYBOARD SHORTCUTS & HELP -->
  <div id="help-modal" class="fixed inset-0 modal-backdrop z-50 flex items-center justify-center p-4 hidden">
    <div class="bg-slate-900 border border-slate-700 rounded-2xl max-w-lg w-full p-6 shadow-2xl space-y-4">
      <div class="flex items-center justify-between border-b border-slate-800 pb-3">
        <div class="flex items-center gap-2.5">
          <div class="w-8 h-8 rounded-lg bg-blue-600/20 text-blue-400 flex items-center justify-center font-bold">
            <i class="fa-solid fa-keyboard"></i>
          </div>
          <div>
            <h3 class="text-sm font-bold text-white">DevToolkit Shortcuts & Navigation</h3>
            <p class="text-[11px] text-slate-400">Native desktop keyboard accelerators</p>
          </div>
        </div>
        <button onclick="toggleHelpModal()" class="text-slate-400 hover:text-white transition p-1"><i class="fa-solid fa-xmark text-sm"></i></button>
      </div>

      <div class="space-y-2 text-xs">
        <div class="flex items-center justify-between p-2 rounded-lg bg-slate-950/70 border border-slate-800">
          <span class="text-slate-300">Focus Global Search</span>
          <kbd class="px-2 py-0.5 rounded bg-slate-800 text-blue-300 font-mono text-[11px] border border-slate-700">Ctrl + K</kbd>
        </div>
        <div class="flex items-center justify-between p-2 rounded-lg bg-slate-950/70 border border-slate-800">
          <span class="text-slate-300">Rescan Environment & Sockets</span>
          <kbd class="px-2 py-0.5 rounded bg-slate-800 text-blue-300 font-mono text-[11px] border border-slate-700">R</kbd>
        </div>
        <div class="flex items-center justify-between p-2 rounded-lg bg-slate-950/70 border border-slate-800">
          <span class="text-slate-300">Switch to Environment Tab</span>
          <kbd class="px-2 py-0.5 rounded bg-slate-800 text-blue-300 font-mono text-[11px] border border-slate-700">1</kbd>
        </div>
        <div class="flex items-center justify-between p-2 rounded-lg bg-slate-950/70 border border-slate-800">
          <span class="text-slate-300">Switch to Port Manager Tab</span>
          <kbd class="px-2 py-0.5 rounded bg-slate-800 text-blue-300 font-mono text-[11px] border border-slate-700">2</kbd>
        </div>
        <div class="flex items-center justify-between p-2 rounded-lg bg-slate-950/70 border border-slate-800">
          <span class="text-slate-300">Switch to Project Auditor Tab</span>
          <kbd class="px-2 py-0.5 rounded bg-slate-800 text-blue-300 font-mono text-[11px] border border-slate-700">3</kbd>
        </div>
        <div class="flex items-center justify-between p-2 rounded-lg bg-slate-950/70 border border-slate-800">
          <span class="text-slate-300">Switch to Settings Tab</span>
          <kbd class="px-2 py-0.5 rounded bg-slate-800 text-blue-300 font-mono text-[11px] border border-slate-700">4</kbd>
        </div>
        <div class="flex items-center justify-between p-2 rounded-lg bg-slate-950/70 border border-slate-800">
          <span class="text-slate-300">Close Modal / Blur Search</span>
          <kbd class="px-2 py-0.5 rounded bg-slate-800 text-blue-300 font-mono text-[11px] border border-slate-700">Esc</kbd>
        </div>
      </div>

      <div class="pt-2 border-t border-slate-800 flex justify-end">
        <button onclick="toggleHelpModal()" class="px-4 py-1.5 bg-blue-600 hover:bg-blue-500 text-white rounded-lg text-xs font-semibold transition">Got it</button>
      </div>
    </div>
  </div>

  <!-- TOAST NOTIFICATION -->
  <div id="toast" class="fixed bottom-12 right-6 px-4 py-2.5 rounded-lg bg-emerald-600 text-white text-xs font-medium shadow-2xl transform translate-y-20 opacity-0 transition duration-300 flex items-center gap-2 z-50">
    <i class="fa-solid fa-check" id="toast-icon"></i> <span id="toast-msg">Success</span>
  </div>

  <!-- CLIENT-SIDE SCRIPT LOGIC -->
  <script>
    let activeTab = 'env';
    let allReports = [];
    let allPorts = [];
    let currentCategory = 'all';
    let currentLayout = 'grid';
    let currentSort = 'severity';
    let currentConfig = { search_paths: [] };
    let pendingKill = null;
    let lastScanTime = Date.now();

    function showToast(msg, isError = false) {
      const toast = document.getElementById('toast');
      const icon = document.getElementById('toast-icon');
      document.getElementById('toast-msg').innerText = msg;
      if (isError) {
        toast.className = 'fixed bottom-12 right-6 px-4 py-2.5 rounded-lg bg-rose-600 text-white text-xs font-medium shadow-2xl transform translate-y-0 opacity-100 transition duration-300 flex items-center gap-2 z-50';
        icon.className = 'fa-solid fa-triangle-exclamation';
      } else {
        toast.className = 'fixed bottom-12 right-6 px-4 py-2.5 rounded-lg bg-emerald-600 text-white text-xs font-medium shadow-2xl transform translate-y-0 opacity-100 transition duration-300 flex items-center gap-2 z-50';
        icon.className = 'fa-solid fa-check';
      }
      setTimeout(() => {
        toast.className = 'fixed bottom-12 right-6 px-4 py-2.5 rounded-lg bg-emerald-600 text-white text-xs font-medium shadow-2xl transform translate-y-20 opacity-0 transition duration-300 flex items-center gap-2 z-50';
      }, 2800);
    }

    function copyToClipboard(text, label) {
      navigator.clipboard.writeText(text);
      showToast('Copied ' + (label || 'content') + ' to clipboard!');
    }

    async function openFolder(path) {
      if (!path) return;
      try {
        const res = await fetch('/api/action/open-folder', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ path })
        });
        const data = await res.json();
        if (res.ok) {
          showToast('Opened folder in Explorer');
        } else {
          showToast(data.detail || 'Failed to open folder', true);
        }
      } catch (err) {
        showToast('Error opening folder', true);
      }
    }

    async function applyFix(command) {
      try {
        const res = await fetch('/api/action/apply-fix', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ command })
        });
        const data = await res.json();
        if (data.status === 'ok') {
          showToast(data.message);
          setTimeout(() => fetchAudit(), 1000);
        } else {
          navigator.clipboard.writeText(command);
          showToast(data.message || 'Copied command to clipboard');
        }
      } catch (e) {
        navigator.clipboard.writeText(command);
        showToast('Copied command to clipboard');
      }
    }

    // Tab Switching
    function switchTab(tab) {
      activeTab = tab;
      const tabs = ['env', 'ports', 'project', 'settings'];
      tabs.forEach(t => {
        const btn = document.getElementById(`nav-btn-${t}`);
        const view = document.getElementById(`view-${t}`);
        const dot = document.getElementById(`dot-${t}`);
        if (t === tab) {
          btn.className = 'w-full flex items-center justify-between px-3 py-2 rounded-xl text-xs font-semibold transition border nav-active';
          if (dot) dot.classList.remove('hidden');
          view.classList.remove('hidden');
        } else {
          btn.className = 'w-full flex items-center justify-between px-3 py-2 rounded-xl text-xs font-semibold transition border nav-inactive';
          if (dot) dot.classList.add('hidden');
          view.classList.add('hidden');
        }
      });

      // Show/hide top search bar & rescan button based on active tab (only visible on Environment tab)
      const searchWrapper = document.getElementById('top-search-wrapper');
      const rescanBtn = document.getElementById('rescan-btn');
      if (tab === 'env') {
        if (searchWrapper) searchWrapper.classList.remove('hidden');
        if (rescanBtn) rescanBtn.classList.remove('hidden');
      } else {
        if (searchWrapper) searchWrapper.classList.add('hidden');
        if (rescanBtn) rescanBtn.classList.add('hidden');
      }

      // Update Top Breadcrumb
      const bc = document.getElementById('top-breadcrumb');
      if (tab === 'env') {
        bc.innerHTML = '<span class="w-1.5 h-1.5 rounded-full bg-blue-400 shadow-[0_0_6px_#60a5fa] flex-shrink-0"></span> Environment & Diagnostics';
      } else if (tab === 'ports') {
        bc.innerHTML = '<span class="w-1.5 h-1.5 rounded-full bg-indigo-400 shadow-[0_0_6px_#818cf8] flex-shrink-0"></span> Port Manager & Sockets';
        fetchPorts();
      } else if (tab === 'project') {
        bc.innerHTML = '<span class="w-1.5 h-1.5 rounded-full bg-emerald-400 shadow-[0_0_6px_#34d399] flex-shrink-0"></span> Project Workstation Auditor';
      } else if (tab === 'settings') {
        bc.innerHTML = '<span class="w-1.5 h-1.5 rounded-full bg-slate-400 flex-shrink-0"></span> Preferences & Search Roots';
        loadConfig();
        loadSystemInfo();
      }
    }

    function refreshActiveTab() {
      lastScanTime = Date.now();
      updateTimerDisplay();
      if (activeTab === 'env') fetchAudit();
      else if (activeTab === 'ports') fetchPorts();
      else if (activeTab === 'project') runProjectAudit();
      else if (activeTab === 'settings') { loadConfig(); loadSystemInfo(); }
    }

    function updateTimerDisplay() {
      const elapsedSec = Math.round((Date.now() - lastScanTime) / 1000);
      const timerEl = document.getElementById('rescan-timer');
      if (elapsedSec < 60) {
        timerEl.innerText = '(now)';
      } else {
        timerEl.innerText = `(${Math.floor(elapsedSec / 60)}m)`;
      }
    }
    setInterval(updateTimerDisplay, 30000);

    // ==================== TAB 1: ENVIRONMENT & AUDITING ====================
    function getToolIcon(id, category) {
      if (id === 'docker') return '<i class="fa-brands fa-docker text-blue-400"></i>';
      if (id === 'android_studio') return '<i class="fa-brands fa-android text-emerald-400"></i>';
      if (id === 'android') return '<i class="fa-solid fa-mobile-screen-button text-amber-400"></i>';
      if (id === 'node') return '<i class="fa-brands fa-node-js text-emerald-400"></i>';
      if (id === 'git') return '<i class="fa-brands fa-git-alt text-orange-400"></i>';
      if (id === 'python') return '<i class="fa-brands fa-python text-yellow-400"></i>';
      if (id === 'java') return '<i class="fa-brands fa-java text-red-400"></i>';
      if (id === 'flutter') return '<i class="fa-solid fa-feather-pointed text-cyan-400"></i>';
      if (id === 'golang') return '<i class="fa-brands fa-golang text-cyan-400"></i>';
      if (id === 'rust') return '<i class="fa-brands fa-rust text-amber-500"></i>';
      if (category === 'runtime') return '<i class="fa-solid fa-terminal text-blue-400"></i>';
      if (category === 'ide') return '<i class="fa-solid fa-code text-indigo-400"></i>';
      return '<i class="fa-solid fa-cube text-slate-400"></i>';
    }

    function getBadge(status) {
      if (status === 'healthy') {
        return '<span class="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-[11px] font-semibold bg-emerald-500/10 text-emerald-400 border border-emerald-500/30 whitespace-nowrap"><span class="w-1.5 h-1.5 rounded-full bg-emerald-400 shadow-[0_0_6px_#34d399]"></span> Healthy</span>';
      }
      if (status === 'warning') {
        return '<span class="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-[11px] font-semibold bg-amber-500/15 text-amber-300 border border-amber-500/30 whitespace-nowrap"><i class="fa-solid fa-triangle-exclamation text-[10px]"></i> Action Needed</span>';
      }
      if (status === 'error') {
        return '<span class="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-[11px] font-semibold bg-rose-500/15 text-rose-300 border border-rose-500/30 whitespace-nowrap"><i class="fa-solid fa-xmark text-[10px]"></i> Error</span>';
      }
      return '<span class="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-[11px] font-semibold bg-slate-800/80 text-slate-400 border border-slate-700/80 whitespace-nowrap"><span class="w-1.5 h-1.5 rounded-full bg-slate-500"></span> Not Detected</span>';
    }

    function setCategory(cat) {
      currentCategory = cat;
      document.querySelectorAll('.cat-btn').forEach(b => {
        if (b.getAttribute('data-cat') === cat) {
          b.className = 'cat-btn px-3 py-1.5 rounded-lg text-xs font-semibold bg-[#131d36] text-white border border-blue-500/40 shadow-sm transition flex-shrink-0';
        } else {
          b.className = 'cat-btn px-3 py-1.5 rounded-lg text-xs font-semibold text-slate-400 hover:text-white hover:bg-slate-800/50 border border-transparent transition flex-shrink-0';
        }
      });
      renderTools();
    }

    function setLayout(mode) {
      currentLayout = mode;
      const gridBtn = document.getElementById('layout-grid-btn');
      const listBtn = document.getElementById('layout-list-btn');
      const gridEl = document.getElementById('tools-grid');
      const listEl = document.getElementById('tools-list-container');

      if (mode === 'grid') {
        gridBtn.className = 'p-1.5 rounded-md text-xs bg-blue-600/30 text-blue-400 hover:text-white transition';
        listBtn.className = 'p-1.5 rounded-md text-xs text-slate-400 hover:text-white transition';
        gridEl.classList.remove('hidden');
        listEl.classList.add('hidden');
      } else {
        gridBtn.className = 'p-1.5 rounded-md text-xs text-slate-400 hover:text-white transition';
        listBtn.className = 'p-1.5 rounded-md text-xs bg-blue-600/30 text-blue-400 hover:text-white transition';
        gridEl.classList.add('hidden');
        listEl.classList.remove('hidden');
      }
      renderTools();
    }

    function onSortChange() {
      currentSort = document.getElementById('sort-select').value;
      renderTools();
    }

    function onSearchChange() {
      renderTools();
    }

    function onGlobalSearch() {
      renderTools();
    }

    function toolMatchesCategory(r, cat) {
      if (cat === 'all') return true;
      const cats = (r.categories && r.categories.length > 0) ? r.categories.map(c => c.toLowerCase()) : [r.category.toLowerCase()];
      if (cat === 'mobile') {
        return cats.includes('mobile') || cats.includes('sdk');
      }
      return cats.includes(cat.toLowerCase());
    }

    function updateCategoryCounts() {
      document.getElementById('cat-count-all').innerText = allReports.length;
      ['runtime', 'mobile', 'ide', 'vcs', 'container'].forEach(c => {
        const count = allReports.filter(r => toolMatchesCategory(r, c)).length;
        const el = document.getElementById(`cat-count-${c}`);
        if (el) el.innerText = count;
      });
    }

    function renderTools() {
      const query = document.getElementById('global-search-input').value.toLowerCase().trim();
      let filtered = allReports.filter(r => {
        const matchesCat = toolMatchesCategory(r, currentCategory);
        const cats = (r.categories && r.categories.length > 0) ? r.categories.map(c => c.toLowerCase()) : [r.category.toLowerCase()];
        const matchesQuery = !query ||
          r.name.toLowerCase().includes(query) ||
          r.id.toLowerCase().includes(query) ||
          cats.some(c => c.includes(query)) ||
          (r.version && r.version.toLowerCase().includes(query)) ||
          (r.binary_path && r.binary_path.toLowerCase().includes(query)) ||
          (r.home_path && r.home_path.toLowerCase().includes(query));
        return matchesCat && matchesQuery;
      });

      // Sort logic
      filtered.sort((a, b) => {
        if (currentSort === 'severity') {
          const weight = { 'error': 4, 'warning': 3, 'not_found': 2, 'healthy': 1 };
          return (weight[b.status] || 0) - (weight[a.status] || 0);
        } else if (currentSort === 'name') {
          return a.name.localeCompare(b.name);
        } else if (currentSort === 'category') {
          return a.category.localeCompare(b.category);
        } else if (currentSort === 'status') {
          return a.status.localeCompare(b.status);
        }
        return 0;
      });

      if (currentLayout === 'grid') {
        renderGridView(filtered);
      } else {
        renderListView(filtered);
      }
    }

    function renderGridView(tools) {
      const grid = document.getElementById('tools-grid');
      grid.innerHTML = '';

      if (tools.length === 0) {
        grid.innerHTML = '<div class="col-span-full py-20 text-center text-slate-500 text-sm"><i class="fa-solid fa-ghost text-3xl mb-3 block"></i>No matching SDKs, runtimes, or tools found.</div>';
        return;
      }

      tools.forEach(r => {
        const card = document.createElement('div');
        card.className = 'glass-card rounded-2xl p-5 sm:p-6 flex flex-col justify-between transition-all duration-200 border border-slate-800/80 hover:border-slate-700/90 shadow-xl';

        // Paths block with Copy and Open Folder for both ROOT and BINARY (no run button)
        let pathsHtml = '';
        if (r.home_path) {
          const cleanHome = r.home_path.replace(/"/g, '&quot;');
          pathsHtml += `
            <div class="bg-[#070b16] p-2.5 rounded-lg border border-slate-800/80 flex items-center justify-between gap-2 min-w-0">
              <div class="truncate text-slate-300 font-mono text-[11px]" title="ROOT: ${cleanHome}">
                <span class="text-blue-400 font-sans font-bold text-[10px] uppercase tracking-wider mr-1">ROOT:</span>${r.home_path}
              </div>
              <div class="flex items-center gap-1.5 flex-shrink-0">
                <button onclick="copyToClipboard(this.dataset.path, 'root path')" data-path="${cleanHome}" title="Copy path" class="p-1.5 hover:text-blue-400 text-slate-400 transition"><i class="fa-regular fa-copy text-xs"></i></button>
                <button onclick="openFolder(this.dataset.path)" data-path="${cleanHome}" title="Open folder" class="p-1.5 hover:text-blue-400 text-slate-400 transition"><i class="fa-regular fa-folder-open text-xs"></i></button>
              </div>
            </div>
          `;
        }
        if (r.binary_path && r.binary_path !== r.home_path) {
          const cleanBin = r.binary_path.replace(/"/g, '&quot;');
          pathsHtml += `
            <div class="bg-[#070b16] p-2.5 rounded-lg border border-slate-800/80 flex items-center justify-between gap-2 min-w-0">
              <div class="truncate text-slate-300 font-mono text-[11px]" title="BINARY: ${cleanBin}">
                <span class="text-emerald-400 font-sans font-bold text-[10px] uppercase tracking-wider mr-1">BINARY:</span>${r.binary_path}
              </div>
              <div class="flex items-center gap-1.5 flex-shrink-0">
                <button onclick="copyToClipboard(this.dataset.path, 'binary path')" data-path="${cleanBin}" title="Copy binary" class="p-1.5 hover:text-emerald-400 text-slate-400 transition"><i class="fa-regular fa-copy text-xs"></i></button>
                <button onclick="openFolder(this.dataset.path)" data-path="${cleanBin}" title="Open folder" class="p-1.5 hover:text-emerald-400 text-slate-400 transition"><i class="fa-regular fa-folder-open text-xs"></i></button>
              </div>
            </div>
          `;
        }

        // Companions block
        const companionsHtml = (r.companions || []).map(c => `
          <span class="inline-flex items-center gap-1.5 text-[11px] px-2.5 py-1 rounded-md ${c.installed ? 'bg-slate-800/90 text-slate-300 border border-slate-700/80' : 'bg-slate-900/60 text-slate-600'}">
            <i class="fa-solid ${c.installed ? 'fa-check text-emerald-400' : 'fa-xmark text-slate-600'} text-[10px]"></i>
            <span class="font-medium">${c.name}</span>
            ${c.version ? '<span class="text-slate-400 font-mono text-[10px]">' + c.version + '</span>' : ''}
          </span>
        `).join('');

        // Diagnostics block
        const diagnosticsHtml = (r.diagnostics || []).map(d => {
          const cleanCmd = (d.suggested_fix || '').replace(/"/g, '&quot;');
          return `
          <div class="mt-3.5 p-3.5 rounded-xl bg-amber-500/10 border border-amber-500/30 text-amber-300 text-xs space-y-2.5">
            <div class="font-medium flex items-start gap-2 leading-snug">
              <i class="fa-solid fa-triangle-exclamation text-amber-400 mt-0.5 flex-shrink-0"></i>
              <span>${d.message}</span>
            </div>
            ${d.suggested_fix ? `
              <div class="space-y-2 pt-1">
                <div class="bg-slate-950 p-2.5 rounded-lg border border-amber-500/20 flex items-center justify-between gap-2 font-mono text-[11px] text-slate-200 min-w-0">
                  <code class="truncate">${d.suggested_fix}</code>
                  <button onclick="copyToClipboard(this.dataset.cmd, 'command')" data-cmd="${cleanCmd}" class="px-2 py-0.5 rounded bg-amber-500/20 hover:bg-amber-500/30 text-amber-200 text-[10px] font-bold flex-shrink-0 transition">Copy</button>
                </div>
                <div class="flex justify-end pt-1">
                  <button onclick="applyFix(this.dataset.cmd)" data-cmd="${cleanCmd}" class="px-3.5 py-1.5 bg-amber-500 hover:bg-amber-400 text-slate-950 rounded-lg text-xs font-bold transition flex items-center gap-1.5 shadow-sm">
                    <i class="fa-solid fa-bolt text-[10px]"></i>
                    <span>Apply System Fix</span>
                  </button>
                </div>
              </div>
            ` : ''}
          </div>
        `}).join('');

        // Multiple categories badges
        const toolCats = (r.categories && r.categories.length > 0) ? r.categories : [r.category];
        const categoriesHtml = toolCats.map(c => 
          `<span class="text-[10px] text-slate-400 uppercase tracking-wider font-mono font-semibold px-2 py-0.5 bg-slate-800/90 rounded border border-slate-700/60">${c}</span>`
        ).join('');

        card.innerHTML = `
          <div>
            <div class="flex items-start justify-between gap-3 mb-4">
              <div class="flex items-center gap-3 min-w-0">
                <div class="w-11 h-11 rounded-xl bg-[#0e1526] border border-slate-700/60 flex items-center justify-center text-lg flex-shrink-0 shadow-inner">
                  ${getToolIcon(r.id, r.category)}
                </div>
                <div class="min-w-0">
                  <h3 class="font-bold text-white text-base tracking-tight truncate flex items-center gap-2" title="${r.name}">
                    ${r.name}
                  </h3>
                  <div class="text-xs font-mono font-semibold text-blue-400 mt-0.5 truncate">
                    ${r.version ? 'v' + r.version : (r.installed ? '<span class="text-slate-400 font-normal">Installed</span>' : '<span class="text-slate-500 font-normal">Not detected</span>')}
                  </div>
                </div>
              </div>
              <div class="flex flex-col items-end gap-1.5 flex-shrink-0">
                <div class="flex flex-wrap gap-1 justify-end max-w-[150px]">
                  ${categoriesHtml}
                </div>
                ${getBadge(r.status)}
              </div>
            </div>

            <div class="space-y-2.5 my-3.5 text-xs">
              ${pathsHtml || '<div class="text-xs text-slate-500 italic p-2.5 bg-[#070b16] rounded-lg border border-slate-800/60">No binary or home path resolved in system</div>'}

              ${r.companions && r.companions.length > 0 ? `
                <div class="pt-2">
                  <div class="text-[10px] font-bold text-slate-500 uppercase tracking-wider mb-2">COMPANION SUBSYSTEMS:</div>
                  <div class="flex flex-wrap gap-2">${companionsHtml}</div>
                </div>
              ` : ''}

              ${diagnosticsHtml}
            </div>
          </div>
        `;
        grid.appendChild(card);
      });
    }

    function renderListView(tools) {
      const tbody = document.getElementById('tools-list-tbody');
      tbody.innerHTML = '';

      if (tools.length === 0) {
        tbody.innerHTML = `<tr><td colspan="7" class="py-12 text-center text-slate-500 italic">No tools found matching criteria.</td></tr>`;
        return;
      }

      tools.forEach(r => {
        const tr = document.createElement('tr');
        tr.className = 'hover:bg-slate-800/40 transition text-slate-300';
        const cleanHome = (r.home_path || '').replace(/"/g, '&quot;');
        const cleanBin = (r.binary_path || '').replace(/"/g, '&quot;');
        const toolCats = (r.categories && r.categories.length > 0) ? r.categories : [r.category];
        const catsDisplay = toolCats.join(', ');

        tr.innerHTML = `
          <td class="py-3 px-4 font-bold text-white flex items-center gap-2">
            <span class="w-6 h-6 rounded bg-slate-800 flex items-center justify-center text-xs flex-shrink-0">${getToolIcon(r.id, r.category)}</span>
            <span class="truncate max-w-[150px]">${r.name}</span>
          </td>
          <td class="py-3 px-4 uppercase text-[10px] font-mono text-slate-400">${catsDisplay}</td>
          <td class="py-3 px-4">${getBadge(r.status)}</td>
          <td class="py-3 px-4 font-mono text-blue-300">${r.version ? 'v' + r.version : '—'}</td>
          <td class="py-3 px-4 font-mono text-slate-400 truncate max-w-[180px]" title="${cleanHome}">${r.home_path || '<span class="text-slate-600">—</span>'}</td>
          <td class="py-3 px-4 font-mono text-emerald-400 truncate max-w-[180px]" title="${cleanBin}">${r.binary_path || '<span class="text-slate-600">—</span>'}</td>
          <td class="py-3 px-4 text-right">
            ${r.home_path ? `<button onclick="openFolder(this.dataset.path)" data-path="${cleanHome}" class="p-1.5 text-slate-400 hover:text-blue-400 transition" title="Open in Explorer"><i class="fa-regular fa-folder-open text-xs"></i></button>` : ''}
            ${r.binary_path ? `<button onclick="copyToClipboard(this.dataset.path, 'binary')" data-path="${cleanBin}" class="p-1.5 text-slate-400 hover:text-emerald-400 transition" title="Copy binary"><i class="fa-regular fa-copy text-xs"></i></button>` : ''}
          </td>
        `;
        tbody.appendChild(tr);
      });
    }

    async function fetchAudit() {
      const icon = document.getElementById('rescan-icon');
      icon.classList.add('fa-spin');
      try {
        const res = await fetch('/api/audit');
        const data = await res.json();
        allReports = data.reports || [];

        document.getElementById('stat-total').innerText = data.total_tools;
        document.getElementById('stat-installed').innerText = data.installed_count;
        document.getElementById('stat-healthy').innerText = data.healthy_count;
        document.getElementById('stat-warning').innerText = data.warning_count;
        document.getElementById('stat-error').innerText = data.error_count;
        document.getElementById('stat-missing').innerText = data.not_found_count;

        const total = data.total_tools || 1;
        const coveragePct = Math.round((data.installed_count / total) * 100);
        document.getElementById('stat-coverage').innerText = `${coveragePct}% coverage`;
        document.getElementById('stat-installed-bar').style.width = `${coveragePct}%`;
        document.getElementById('stat-healthy-bar').style.width = `${Math.round((data.healthy_count / total) * 100)}%`;
        document.getElementById('stat-warning-bar').style.width = `${Math.round((data.warning_count / total) * 100)}%`;
        document.getElementById('stat-error-bar').style.width = `${Math.round((data.error_count / total) * 100)}%`;
        document.getElementById('stat-missing-bar').style.width = `${Math.round((data.not_found_count / total) * 100)}%`;

        // Update system info
        const sys = data.system;
        if (sys) {
          const sideOs = document.getElementById('side-os-info');
          if (sideOs) sideOs.innerText = `${sys.os_name} ${sys.os_release} (${sys.arch})`;
          const sideHost = document.getElementById('side-host-name');
          if (sideHost) sideHost.innerText = sys.hostname || 'LOCAL';
          if (sys.path_count) {
            const statusPath = document.getElementById('status-path-count');
            if (statusPath) statusPath.innerText = sys.path_count;
          }
          if (sys.ram_footprint_mb) {
            const statusRam = document.getElementById('status-ram-count');
            if (statusRam) statusRam.innerText = `${sys.ram_footprint_mb} MB`;
          }
        }

        updateCategoryCounts();
        renderTools();
      } catch (err) {
        showToast('Error auditing environment', true);
      } finally {
        icon.classList.remove('fa-spin');
      }
    }

    // ==================== TAB 2: PORT MANAGER ====================
    function setPortsDevToggle(state) {
      document.getElementById('ports-dev-toggle').checked = state;
      fetchPorts();
    }

    async function fetchPorts() {
      try {
        const devOnly = document.getElementById('ports-dev-toggle').checked;
        const res = await fetch(`/api/ports?dev_only=${devOnly}`);
        allPorts = await res.json();

        const devCount = allPorts.filter(p => p.is_dev_port).length;
        const critCount = allPorts.filter(p => p.is_system_critical).length;
        document.getElementById('stat-ports-total').innerText = allPorts.length;
        document.getElementById('stat-ports-dev').innerText = devCount;
        document.getElementById('stat-ports-crit').innerText = critCount;

        const sideBadge = document.getElementById('side-ports-badge');
        sideBadge.innerText = devCount > 0 ? devCount : allPorts.length;

        renderPortsTable();
      } catch (err) {
        showToast('Error loading sockets', true);
      }
    }

    function renderPortsTable() {
      const tbody = document.getElementById('ports-table-body');
      const query = document.getElementById('ports-search-input').value.toLowerCase().trim();
      tbody.innerHTML = '';

      const filtered = allPorts.filter(p => {
        if (!query) return true;
        return (
          p.port.toString().includes(query) ||
          p.process_name.toLowerCase().includes(query) ||
          p.pid.toString().includes(query) ||
          p.address.includes(query)
        );
      });

      if (filtered.length === 0) {
        tbody.innerHTML = `<tr><td colspan="7" class="py-12 text-center text-slate-500 italic">No listening sockets found matching criteria.</td></tr>`;
        return;
      }

      filtered.forEach(p => {
        const tr = document.createElement('tr');
        tr.className = 'hover:bg-slate-800/40 transition text-slate-300';

        const portBadge = p.is_dev_port
          ? `<span class="inline-flex items-center gap-1 font-mono font-bold text-blue-400 bg-blue-500/10 px-2 py-0.5 rounded border border-blue-500/25">:${p.port}</span>`
          : `<span class="font-mono font-bold text-slate-200">:${p.port}</span>`;

        const tagBadge = p.is_dev_port
          ? `<span class="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-semibold bg-blue-500/20 text-blue-300"><i class="fa-solid fa-code text-[9px]"></i> Dev Port</span>`
          : `<span class="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] text-slate-500 bg-slate-900 border border-slate-800">Service</span>`;

        const statusBadge = p.is_system_critical
          ? `<span class="text-rose-400 font-medium inline-flex items-center gap-1"><i class="fa-solid fa-lock text-[10px]"></i> System Critical</span>`
          : `<span class="text-emerald-400 font-medium inline-flex items-center gap-1"><i class="fa-solid fa-user text-[10px]"></i> User Process</span>`;

        const actionBtn = p.is_system_critical
          ? `<button onclick="openKillModal(${p.port}, '${p.process_name}', ${p.pid}, true)" class="px-2.5 py-1 bg-slate-800 hover:bg-rose-950 text-slate-400 hover:text-rose-300 rounded text-[11px] font-semibold transition border border-slate-700">Protected</button>`
          : `<button onclick="openKillModal(${p.port}, '${p.process_name}', ${p.pid}, false)" class="px-2.5 py-1 bg-rose-600/80 hover:bg-rose-600 text-white rounded text-[11px] font-semibold transition shadow-sm">Kill</button>`;

        tr.innerHTML = `
          <td class="py-3 px-4 font-mono">${portBadge}</td>
          <td class="py-3 px-4">${tagBadge}</td>
          <td class="py-3 px-4 font-semibold text-white truncate max-w-[180px]" title="${p.process_name}">${p.process_name}</td>
          <td class="py-3 px-4 font-mono text-yellow-400">${p.pid}</td>
          <td class="py-3 px-4 font-mono text-slate-400">${p.address}</td>
          <td class="py-3 px-4">${statusBadge}</td>
          <td class="py-3 px-4 text-right">${actionBtn}</td>
        `;
        tbody.appendChild(tr);
      });
    }

    function openKillModal(port, processName, pid, isCritical) {
      pendingKill = { port, isCritical };
      document.getElementById('modal-kill-port').innerText = `:${port}`;
      document.getElementById('modal-kill-name').innerText = processName;
      document.getElementById('modal-kill-pid').innerText = pid;

      const warningEl = document.getElementById('modal-kill-warning');
      const forceBox = document.getElementById('modal-force-checkbox');
      forceBox.checked = false;

      if (isCritical) warningEl.classList.remove('hidden');
      else warningEl.classList.add('hidden');

      document.getElementById('kill-modal').classList.remove('hidden');
    }

    function closeKillModal() {
      document.getElementById('kill-modal').classList.add('hidden');
      pendingKill = null;
    }

    async function submitKillPort() {
      if (!pendingKill) return;
      const force = document.getElementById('modal-force-checkbox').checked;

      try {
        const res = await fetch('/api/ports/kill', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ port: pendingKill.port, force })
        });
        const data = await res.json();
        closeKillModal();

        if (data.success) {
          showToast(data.message);
          await fetchPorts();
        } else {
          showToast(data.message, true);
        }
      } catch (err) {
        showToast('Error killing process', true);
      }
    }

    // ==================== TAB 3: PROJECT AUDITOR ====================
    function setProjectInput(val) {
      document.getElementById('project-path-input').value = val;
    }

    async function runProjectAudit() {
      const input = document.getElementById('project-path-input');
      const pathVal = input.value.trim() || '.';
      const btn = document.getElementById('btn-audit-project');
      const icon = document.getElementById('audit-project-icon');
      const resultsContainer = document.getElementById('project-results-container');

      icon.className = 'fa-solid fa-spinner fa-spin';
      btn.disabled = true;

      try {
        const res = await fetch('/api/project/audit', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ path: pathVal })
        });
        if (!res.ok) {
          const err = await res.json();
          showToast(err.detail || 'Directory not found', true);
          return;
        }

        const data = await res.json();
        resultsContainer.classList.remove('hidden');

        document.getElementById('rep-project-name').innerText = data.project_name;
        document.getElementById('rep-project-path').innerText = data.project_path;

        const typesContainer = document.getElementById('rep-detected-types');
        typesContainer.innerHTML = (data.detected_types || []).map(t =>
          `<span class="px-2 py-0.5 rounded-full text-[10px] font-bold bg-blue-500/20 text-blue-300 border border-blue-500/30">${t}</span>`
        ).join('');

        const badgeEl = document.getElementById('rep-status-badge');
        if (data.ready_to_build) {
          badgeEl.innerHTML = '<span class="inline-flex items-center gap-1.5 px-3 py-1 rounded-lg text-xs font-bold bg-emerald-500/20 text-emerald-300 border border-emerald-500/30"><i class="fa-solid fa-check"></i> READY TO BUILD</span>';
        } else {
          badgeEl.innerHTML = '<span class="inline-flex items-center gap-1.5 px-3 py-1 rounded-lg text-xs font-bold bg-rose-500/20 text-rose-300 border border-rose-500/30"><i class="fa-solid fa-triangle-exclamation"></i> PREREQUISITES MISSING</span>';
        }

        const tbody = document.getElementById('project-checks-tbody');
        tbody.innerHTML = '';
        (data.checks || []).forEach(c => {
          const tr = document.createElement('tr');
          tr.className = 'hover:bg-slate-800/40 text-slate-300';
          const stat = c.satisfied
            ? '<span class="text-emerald-400 font-bold inline-flex items-center gap-1"><i class="fa-solid fa-check text-[10px]"></i> Satisfied</span>'
            : '<span class="text-rose-400 font-bold inline-flex items-center gap-1"><i class="fa-solid fa-xmark text-[10px]"></i> Missing</span>';
          tr.innerHTML = `
            <td class="py-2.5 px-4">${stat}</td>
            <td class="py-2.5 px-4 font-bold text-white">${c.name}</td>
            <td class="py-2.5 px-4 font-mono text-slate-400">${c.required}</td>
            <td class="py-2.5 px-4 font-mono text-cyan-300">${c.detected || '<span class="text-slate-500">None</span>'}</td>
            <td class="py-2.5 px-4 text-slate-300">${c.message}</td>
          `;
          tbody.appendChild(tr);
        });

        const actionsCard = document.getElementById('project-actions-card');
        const actionsList = document.getElementById('project-actions-list');
        if (data.suggested_actions && data.suggested_actions.length > 0) {
          actionsCard.classList.remove('hidden');
          actionsList.innerHTML = data.suggested_actions.map(act => `
            <div class="flex items-center justify-between p-2.5 rounded-lg bg-slate-950/80 border border-amber-500/20 text-xs">
              <div class="font-mono text-slate-200 truncate mr-2"><code>${act}</code></div>
              <button onclick="copyToClipboard('${act.replace(/\\\\/g, '\\\\\\\\')}', 'command')" class="px-2.5 py-1 rounded bg-amber-500/20 hover:bg-amber-500/30 text-amber-200 text-[11px] font-semibold transition flex-shrink-0">Copy</button>
            </div>
          `).join('');
        } else {
          actionsCard.classList.add('hidden');
        }
      } catch (err) {
        showToast('Error auditing project', true);
      } finally {
        icon.className = 'fa-solid fa-wand-magic-sparkles';
        btn.disabled = false;
      }
    }

    // ==================== TAB 4: SETTINGS & SEARCH ROOTS ====================
    function fillSettingsPath(p) {
      document.getElementById('settings-path-input').value = p;
    }

    async function loadConfig() {
      try {
        const res = await fetch('/api/config');
        currentConfig = await res.json();
        renderSettingsList();
      } catch (e) {
        console.error('Error loading config:', e);
      }
    }

    function renderSettingsList() {
      const listEl = document.getElementById('settings-paths-list');
      const bannerEl = document.getElementById('search-paths-banner');
      const bannerListEl = document.getElementById('banner-paths-list');

      const paths = currentConfig.search_paths || [];
      if (paths.length === 0) {
        listEl.innerHTML = '<div class="text-xs text-slate-500 italic p-3 bg-slate-950/60 rounded-lg border border-slate-800 text-center">No custom search roots configured. Standard OS & ecosystem discovery is active.</div>';
        bannerEl.classList.add('hidden');
        return;
      }

      bannerEl.classList.remove('hidden');
      bannerListEl.innerText = paths.join(', ');

      listEl.innerHTML = paths.map(p => `
        <div class="flex items-center justify-between p-2.5 bg-slate-950/80 rounded-lg border border-slate-800 text-xs">
          <div class="flex items-center gap-2 font-mono text-slate-200 truncate" title="${p}">
            <i class="fa-regular fa-folder text-blue-400"></i>
            <span class="truncate">${p}</span>
          </div>
          <button onclick="removeSearchPath('${p.replace(/\\\\/g, '\\\\\\\\')}')" class="p-1 hover:text-rose-400 text-slate-500 transition" title="Remove path">
            <i class="fa-solid fa-trash-can text-xs"></i>
          </button>
        </div>
      `).join('');
    }

    async function submitSearchPath() {
      const input = document.getElementById('settings-path-input');
      const path = input.value.trim();
      if (!path) return;

      try {
        const res = await fetch('/api/config/search-paths', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ path })
        });
        if (res.ok) {
          input.value = '';
          showToast('Search path added! Refreshing...');
          await loadConfig();
          await fetchAudit();
        } else {
          const err = await res.json();
          showToast(err.detail || 'Directory does not exist', true);
        }
      } catch (e) {
        showToast('Error adding search path', true);
      }
    }

    async function removeSearchPath(path) {
      try {
        const res = await fetch('/api/config/search-paths', {
          method: 'DELETE',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ path })
        });
        if (res.ok) {
          showToast('Search path removed');
          await loadConfig();
          await fetchAudit();
        }
      } catch (e) {
        showToast('Error removing path', true);
      }
    }

    async function loadSystemInfo() {
      try {
        const res = await fetch('/api/system');
        const sys = await res.json();
        document.getElementById('sys-os').innerText = `${sys.os_name} ${sys.os_release}`;
        document.getElementById('sys-arch').innerText = sys.arch;
        document.getElementById('sys-host').innerText = sys.hostname;
        document.getElementById('sys-python').innerText = sys.python_version || 'Active';
      } catch (e) {
        console.error('Error loading system info:', e);
      }
    }

    // Modal Helper
    function toggleHelpModal() {
      const modal = document.getElementById('help-modal');
      modal.classList.toggle('hidden');
    }

    // Keyboard Shortcuts Listeners
    window.addEventListener('keydown', (e) => {
      // Don't intercept if user is typing in an input
      const activeTag = document.activeElement ? document.activeElement.tagName.toLowerCase() : '';
      const isInput = activeTag === 'input' || activeTag === 'textarea';

      if (e.key === 'Escape') {
        closeKillModal();
        const help = document.getElementById('help-modal');
        if (!help.classList.contains('hidden')) help.classList.add('hidden');
        if (isInput) document.activeElement.blur();
        return;
      }

      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'k') {
        e.preventDefault();
        if (activeTab === 'env') {
          const searchInput = document.getElementById('global-search-input');
          if (searchInput) searchInput.focus();
        } else if (activeTab === 'ports') {
          const portsSearch = document.getElementById('ports-search-input');
          if (portsSearch) portsSearch.focus();
        }
        return;
      }

      if (!isInput) {
        if (e.key.toLowerCase() === 'r') {
          e.preventDefault();
          refreshActiveTab();
        } else if (e.key === '?') {
          e.preventDefault();
          toggleHelpModal();
        } else if (e.key === '1') {
          switchTab('env');
        } else if (e.key === '2') {
          switchTab('ports');
        } else if (e.key === '3') {
          switchTab('project');
        } else if (e.key === '4') {
          switchTab('settings');
        }
      }
    });

    // Initialize Default View
    loadConfig();
    fetchAudit();
    setProjectInput('.');
  </script>
</body>
</html>
"""
