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
            "description": i.description,
        }
        for i in inspectors
    ]


@app.post("/api/action/open-folder")
def open_folder(req: OpenFolderRequest):
    p = Path(req.path)
    if not p.exists():
        raise HTTPException(status_code=404, detail="Path does not exist on disk.")

    target = str(p if p.is_dir() else p.parent)
    if sys.platform == "win32":
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
<html lang="en" class="dark">
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
            brand: { 50: '#f5f3ff', 500: '#8b5cf6', 600: '#7c3aed', 700: '#6d28d9' },
            darkBg: '#090d16',
            cardBg: '#131b2e',
            borderDark: '#232f48'
          }
        }
      }
    }
  </script>
  <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css" />
  <style>
    body { background-color: #080c15; color: #f1f5f9; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; }
    .glass-card { background: rgba(19, 27, 46, 0.75); backdrop-filter: blur(14px); border: 1px solid rgba(255,255,255,0.07); }
    .glass-card:hover { border-color: rgba(139, 92, 246, 0.45); }
    .modal-backdrop { background: rgba(3, 7, 18, 0.85); backdrop-filter: blur(8px); }
    .tab-active { background-color: #7c3aed; color: #ffffff; box-shadow: 0 4px 12px rgba(124, 58, 237, 0.3); }
    .tab-inactive { color: #94a3b8; }
    .tab-inactive:hover { color: #ffffff; background-color: rgba(30, 41, 59, 0.6); }
  </style>
</head>
<body class="min-h-screen p-6">
  <div class="max-w-7xl mx-auto space-y-6">
    <!-- Top Header -->
    <div class="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-borderDark pb-5">
      <div class="flex items-center gap-3">
        <div class="w-11 h-11 rounded-xl bg-gradient-to-br from-violet-500 to-indigo-600 flex items-center justify-center shadow-lg shadow-violet-500/25 flex-shrink-0">
          <i class="fa-solid fa-bolt text-xl text-white"></i>
        </div>
        <div>
          <h1 class="text-2xl font-black tracking-tight text-white flex items-center gap-2">
            DevToolkit <span class="text-xs px-2 py-0.5 rounded-full bg-violet-500/20 text-violet-300 font-mono">v0.2.0</span>
          </h1>
          <p class="text-xs text-slate-400" id="sys-info">Inspecting local workstation environment...</p>
        </div>
      </div>

      <!-- Navigation Tabs -->
      <div class="flex items-center bg-slate-900/90 p-1.5 rounded-xl border border-slate-800 gap-1 overflow-x-auto">
        <button onclick="switchTab('env')" id="tab-btn-env" class="tab-btn tab-active px-3.5 py-2 rounded-lg text-xs font-semibold transition flex items-center gap-2">
          <i class="fa-solid fa-layer-group"></i>
          <span>Environment</span>
        </button>
        <button onclick="switchTab('ports')" id="tab-btn-ports" class="tab-btn tab-inactive px-3.5 py-2 rounded-lg text-xs font-semibold transition flex items-center gap-2">
          <i class="fa-solid fa-network-wired"></i>
          <span>Port Manager</span>
          <span id="nav-dev-badge" class="hidden px-1.5 py-0.5 rounded-full text-[10px] bg-violet-500/30 text-violet-200 font-mono"></span>
        </button>
        <button onclick="switchTab('project')" id="tab-btn-project" class="tab-btn tab-inactive px-3.5 py-2 rounded-lg text-xs font-semibold transition flex items-center gap-2">
          <i class="fa-solid fa-cubes"></i>
          <span>Project Auditor</span>
        </button>
        <button onclick="switchTab('settings')" id="tab-btn-settings" class="tab-btn tab-inactive px-3.5 py-2 rounded-lg text-xs font-semibold transition flex items-center gap-2">
          <i class="fa-solid fa-gear"></i>
          <span>Settings</span>
        </button>
      </div>

      <div class="flex items-center gap-2">
        <button onclick="refreshActiveTab()" id="refresh-btn" class="flex items-center gap-2 px-3.5 py-2 bg-slate-900 hover:bg-slate-800 text-slate-200 rounded-lg text-xs font-semibold transition border border-slate-700 shadow-sm">
          <i class="fa-solid fa-rotate" id="refresh-icon"></i>
          <span>Refresh</span>
        </button>
      </div>
    </div>

    <!-- TAB 1: ENVIRONMENT AUDITOR -->
    <div id="view-env" class="space-y-6">
      <!-- Summary Stats Bar -->
      <div class="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3" id="stats-container">
        <div class="glass-card rounded-xl p-3 text-center">
          <div class="text-xs text-slate-400 font-medium">Audited</div>
          <div class="text-xl font-bold text-white mt-1" id="stat-total">—</div>
        </div>
        <div class="glass-card rounded-xl p-3 text-center">
          <div class="text-xs text-emerald-400 font-medium">Installed</div>
          <div class="text-xl font-bold text-emerald-400 mt-1" id="stat-installed">—</div>
        </div>
        <div class="glass-card rounded-xl p-3 text-center">
          <div class="text-xs text-green-400 font-medium">Healthy</div>
          <div class="text-xl font-bold text-green-400 mt-1" id="stat-healthy">—</div>
        </div>
        <div class="glass-card rounded-xl p-3 text-center">
          <div class="text-xs text-amber-400 font-medium">Action Needed</div>
          <div class="text-xl font-bold text-amber-400 mt-1" id="stat-warning">—</div>
        </div>
        <div class="glass-card rounded-xl p-3 text-center">
          <div class="text-xs text-rose-400 font-medium">Errors</div>
          <div class="text-xl font-bold text-rose-400 mt-1" id="stat-error">—</div>
        </div>
        <div class="glass-card rounded-xl p-3 text-center">
          <div class="text-xs text-slate-500 font-medium">Not Found</div>
          <div class="text-xl font-bold text-slate-500 mt-1" id="stat-missing">—</div>
        </div>
      </div>

      <!-- Filter & Search Toolbar -->
      <div class="flex flex-col sm:flex-row items-center justify-between gap-3 bg-slate-900/60 p-2.5 rounded-xl border border-borderDark">
        <div class="flex items-center gap-1.5 overflow-x-auto w-full sm:w-auto" id="category-filters">
          <button onclick="setCategory('all')" class="filter-btn px-3 py-1.5 rounded-lg text-xs font-semibold bg-violet-600 text-white" data-cat="all">All</button>
          <button onclick="setCategory('runtime')" class="filter-btn px-3 py-1.5 rounded-lg text-xs font-semibold bg-slate-800 text-slate-300 hover:bg-slate-700" data-cat="runtime">Runtimes</button>
          <button onclick="setCategory('mobile')" class="filter-btn px-3 py-1.5 rounded-lg text-xs font-semibold bg-slate-800 text-slate-300 hover:bg-slate-700" data-cat="mobile">Mobile & SDKs</button>
          <button onclick="setCategory('ide')" class="filter-btn px-3 py-1.5 rounded-lg text-xs font-semibold bg-slate-800 text-slate-300 hover:bg-slate-700" data-cat="ide">IDEs</button>
          <button onclick="setCategory('vcs')" class="filter-btn px-3 py-1.5 rounded-lg text-xs font-semibold bg-slate-800 text-slate-300 hover:bg-slate-700" data-cat="vcs">VCS / Git</button>
          <button onclick="setCategory('container')" class="filter-btn px-3 py-1.5 rounded-lg text-xs font-semibold bg-slate-800 text-slate-300 hover:bg-slate-700" data-cat="container">Containers</button>
        </div>
        <div class="relative w-full sm:w-72">
          <i class="fa-solid fa-search absolute left-3 top-2.5 text-xs text-slate-400"></i>
          <input type="text" id="search-input" oninput="filterTools()" placeholder="Search SDK, runtime, path..." class="w-full pl-8 pr-3 py-1.5 bg-slate-950/80 border border-slate-700 rounded-lg text-xs text-white placeholder-slate-500 focus:outline-none focus:border-violet-500 transition" />
        </div>
      </div>

      <!-- Active Search Paths Banner -->
      <div id="search-paths-banner" class="hidden text-xs bg-slate-900/50 border border-slate-800 rounded-xl px-4 py-2.5 flex items-center justify-between">
        <div class="flex items-center gap-2">
          <i class="fa-solid fa-folder-tree text-violet-400"></i>
          <span class="text-slate-400">Custom Monitored Directories:</span>
          <span id="banner-paths-list" class="font-mono text-violet-300"></span>
        </div>
        <button onclick="switchTab('settings')" class="text-violet-400 hover:text-violet-300 font-medium">Manage Paths</button>
      </div>

      <!-- Cards Grid -->
      <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4" id="tools-grid"></div>
    </div>

    <!-- TAB 2: PORT MANAGER -->
    <div id="view-ports" class="space-y-6 hidden">
      <!-- Port Stats -->
      <div class="grid grid-cols-1 sm:grid-cols-3 gap-3">
        <div class="glass-card rounded-xl p-4 flex items-center gap-3">
          <div class="w-10 h-10 rounded-lg bg-blue-500/20 text-blue-400 flex items-center justify-center font-bold text-lg"><i class="fa-solid fa-satellite-dish"></i></div>
          <div>
            <div class="text-xs text-slate-400 font-medium">Listening Sockets</div>
            <div class="text-xl font-bold text-white mt-0.5" id="stat-ports-total">—</div>
          </div>
        </div>
        <div class="glass-card rounded-xl p-4 flex items-center gap-3">
          <div class="w-10 h-10 rounded-lg bg-violet-500/20 text-violet-400 flex items-center justify-center font-bold text-lg"><i class="fa-solid fa-code"></i></div>
          <div>
            <div class="text-xs text-slate-400 font-medium">Developer Ports Active</div>
            <div class="text-xl font-bold text-violet-400 mt-0.5" id="stat-ports-dev">—</div>
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

      <!-- Ports Toolbar -->
      <div class="flex flex-col sm:flex-row items-center justify-between gap-3 bg-slate-900/60 p-3 rounded-xl border border-borderDark">
        <div class="flex items-center gap-3 w-full sm:w-auto">
          <label class="inline-flex items-center gap-2 cursor-pointer text-xs font-semibold text-slate-300 bg-slate-800/80 px-3 py-1.5 rounded-lg border border-slate-700">
            <input type="checkbox" id="ports-dev-toggle" onchange="toggleDevPortsOnly()" class="rounded border-slate-600 text-violet-600 focus:ring-violet-500" />
            <span>Developer Ports Only</span>
          </label>
          <span class="text-xs text-slate-500 hidden sm:inline">• Highlights 3000, 5173, 8080, 27017, etc.</span>
        </div>
        <div class="relative w-full sm:w-72">
          <i class="fa-solid fa-search absolute left-3 top-2.5 text-xs text-slate-400"></i>
          <input type="text" id="ports-search-input" oninput="filterPortsTable()" placeholder="Filter port, process, PID..." class="w-full pl-8 pr-3 py-1.5 bg-slate-950/80 border border-slate-700 rounded-lg text-xs text-white placeholder-slate-500 focus:outline-none focus:border-violet-500 transition" />
        </div>
      </div>

      <!-- Ports Table Card -->
      <div class="glass-card rounded-xl border border-slate-800 overflow-hidden shadow-xl">
        <div class="overflow-x-auto">
          <table class="w-full text-left text-xs">
            <thead class="bg-slate-950/90 text-slate-400 uppercase tracking-wider text-[11px] border-b border-slate-800">
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
            <tbody id="ports-table-body" class="divide-y divide-slate-800/60 font-sans">
              <!-- Rendered rows -->
            </tbody>
          </table>
        </div>
      </div>
    </div>

    <!-- TAB 3: PROJECT AUDITOR -->
    <div id="view-project" class="space-y-6 hidden">
      <!-- Project Selection Card -->
      <div class="glass-card rounded-xl p-6 border border-slate-800 space-y-4">
        <div class="flex items-start justify-between gap-4">
          <div>
            <h2 class="text-lg font-bold text-white flex items-center gap-2">
              <i class="fa-solid fa-folder-magnifying-glass text-violet-400"></i>
              Project Workstation Readiness Auditor
            </h2>
            <p class="text-xs text-slate-400 mt-1">
              Select any project repository on your disk to verify if your workstation satisfies its SDK, runtime, compiler, and environment requirements.
            </p>
          </div>
        </div>

        <div class="flex flex-col sm:flex-row items-center gap-2 pt-2">
          <div class="relative flex-1 w-full">
            <i class="fa-regular fa-folder absolute left-3 top-3 text-xs text-slate-400"></i>
            <input type="text" id="project-path-input" placeholder="e.g. D:\\UtilitySoftware or D:\\Dev\\my-app" class="w-full pl-8 pr-3 py-2 bg-slate-950 border border-slate-700 rounded-lg text-xs font-mono text-white placeholder-slate-500 focus:outline-none focus:border-violet-500 transition" />
          </div>
          <button onclick="runProjectAudit()" id="btn-audit-project" class="w-full sm:w-auto px-5 py-2 bg-violet-600 hover:bg-violet-500 text-white rounded-lg text-xs font-bold transition flex items-center justify-center gap-2 shadow-sm">
            <i class="fa-solid fa-wand-magic-sparkles" id="audit-project-icon"></i>
            <span>Scan Project</span>
          </button>
        </div>

        <div class="flex items-center gap-2 text-[11px] text-slate-400">
          <span>Quick Preset:</span>
          <button onclick="setProjectInput('.')" class="px-2 py-0.5 rounded bg-slate-800 hover:bg-slate-700 text-slate-300 font-mono transition">Current Directory (.)</button>
        </div>
      </div>

      <!-- Audit Results Placeholder / Container -->
      <div id="project-results-container" class="space-y-4 hidden">
        <!-- Result Banner -->
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

        <!-- Requirements Checklist -->
        <div class="glass-card rounded-xl border border-slate-800 overflow-hidden">
          <div class="px-5 py-3.5 bg-slate-950/80 border-b border-slate-800 flex items-center justify-between">
            <h4 class="text-xs font-bold text-white uppercase tracking-wider flex items-center gap-2">
              <i class="fa-solid fa-list-check text-violet-400"></i>
              Prerequisites Checklist
            </h4>
          </div>
          <div class="overflow-x-auto">
            <table class="w-full text-left text-xs">
              <thead class="bg-slate-950/50 text-slate-400 uppercase tracking-wider text-[10px] border-b border-slate-800">
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

    <!-- TAB 4: SETTINGS & SEARCH PATHS -->
    <div id="view-settings" class="space-y-6 hidden">
      <!-- Monitored Search Directories -->
      <div class="glass-card rounded-xl p-6 border border-slate-800 space-y-5">
        <div class="flex items-center gap-3">
          <div class="w-9 h-9 rounded-lg bg-violet-600/20 text-violet-400 flex items-center justify-center font-bold">
            <i class="fa-solid fa-folder-tree"></i>
          </div>
          <div>
            <h2 class="text-base font-bold text-white">Monitored Search Directories (Layer 4)</h2>
            <p class="text-xs text-slate-400">Configure directories where DevToolkit recursively probes for SDKs by structural signature.</p>
          </div>
        </div>

        <div>
          <label class="block text-xs font-semibold text-slate-300 mb-1.5">Add Custom Directory Root</label>
          <div class="flex items-center gap-2">
            <input type="text" id="settings-path-input" placeholder="e.g. D:\\Dev or /opt/custom_sdks" class="flex-1 bg-slate-950 border border-slate-700 rounded-lg px-3 py-2 text-xs text-white placeholder-slate-500 font-mono focus:outline-none focus:border-violet-500" />
            <button onclick="submitSearchPath()" class="px-4 py-2 bg-violet-600 hover:bg-violet-500 text-white rounded-lg text-xs font-bold transition flex items-center gap-1.5">
              <i class="fa-solid fa-plus"></i>
              <span>Add Path</span>
            </button>
          </div>
          <div class="mt-2 flex items-center gap-2">
            <span class="text-[11px] text-slate-500">Quick Suggestion:</span>
            <button onclick="fillSettingsPath('D:\\\\Dev')" class="text-[11px] px-2 py-0.5 rounded bg-slate-800 hover:bg-slate-700 text-slate-300 font-mono transition">+ D:\Dev</button>
            <button onclick="fillSettingsPath('C:\\\\Dev')" class="text-[11px] px-2 py-0.5 rounded bg-slate-800 hover:bg-slate-700 text-slate-300 font-mono transition">+ C:\Dev</button>
          </div>
        </div>

        <div>
          <h3 class="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-2">Active Monitored Directories</h3>
          <div id="settings-paths-list" class="space-y-2 max-h-48 overflow-y-auto"></div>
        </div>

        <div class="p-4 rounded-xl bg-violet-500/10 border border-violet-500/20 text-xs text-violet-300 space-y-1">
          <div class="font-bold flex items-center gap-1.5"><i class="fa-solid fa-shield-halved"></i> Generalized Content Signature Discovery</div>
          <p class="text-slate-300 text-[11px]">DevToolkit avoids rigid hardcoded directory checks. When you add a root directory, it checks subfolders for binary signatures (e.g. <code>platform-tools/adb.exe</code> or <code>bin/javac.exe</code>) regardless of arbitrary naming.</p>
        </div>
      </div>

      <!-- System Environment Card -->
      <div class="glass-card rounded-xl p-6 border border-slate-800 space-y-4">
        <h3 class="text-sm font-bold text-white flex items-center gap-2">
          <i class="fa-solid fa-microchip text-slate-400"></i>
          Workstation System Overview
        </h3>
        <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3 text-xs">
          <div class="p-3 rounded-lg bg-slate-950/70 border border-slate-800">
            <div class="text-slate-500 font-medium">Operating System</div>
            <div class="font-bold text-white mt-1" id="sys-os">—</div>
          </div>
          <div class="p-3 rounded-lg bg-slate-950/70 border border-slate-800">
            <div class="text-slate-500 font-medium">Architecture</div>
            <div class="font-bold text-white mt-1" id="sys-arch">—</div>
          </div>
          <div class="p-3 rounded-lg bg-slate-950/70 border border-slate-800">
            <div class="text-slate-500 font-medium">Host Machine</div>
            <div class="font-bold text-white mt-1" id="sys-host">—</div>
          </div>
          <div class="p-3 rounded-lg bg-slate-950/70 border border-slate-800">
            <div class="text-slate-500 font-medium">Python Runtime</div>
            <div class="font-bold text-emerald-400 mt-1" id="sys-python">—</div>
          </div>
        </div>
      </div>
    </div>
  </div>

  <!-- Kill Port Confirmation Modal -->
  <div id="kill-modal" class="fixed inset-0 modal-backdrop z-50 flex items-center justify-center p-4 hidden">
    <div class="bg-slate-900 border border-slate-700 rounded-2xl max-w-md w-full p-6 shadow-2xl space-y-4 animate-in fade-in zoom-in-95 duration-150">
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
        <div class="flex justify-between"><span class="text-slate-500">Port:</span> <span class="text-violet-300 font-bold" id="modal-kill-port">:—</span></div>
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

  <!-- Toast Notification -->
  <div id="toast" class="fixed bottom-6 right-6 px-4 py-2.5 rounded-lg bg-emerald-600 text-white text-xs font-medium shadow-lg transform translate-y-20 opacity-0 transition duration-300 flex items-center gap-2 z-50">
    <i class="fa-solid fa-check"></i> <span id="toast-msg">Success</span>
  </div>

  <script>
    let activeTab = 'env';
    let allReports = [];
    let allPorts = [];
    let currentCategory = 'all';
    let currentConfig = { search_paths: [] };
    let pendingKill = null;

    function showToast(msg, isError = false) {
      const toast = document.getElementById('toast');
      document.getElementById('toast-msg').innerText = msg;
      toast.className = `fixed bottom-6 right-6 px-4 py-2.5 rounded-lg ${isError ? 'bg-rose-600' : 'bg-emerald-600'} text-white text-xs font-medium shadow-lg transform translate-y-0 opacity-100 transition duration-300 flex items-center gap-2 z-50`;
      setTimeout(() => {
        toast.className = 'fixed bottom-6 right-6 px-4 py-2.5 rounded-lg bg-emerald-600 text-white text-xs font-medium shadow-lg transform translate-y-20 opacity-0 transition duration-300 flex items-center gap-2 z-50';
      }, 2500);
    }

    function copyToClipboard(text, label) {
      navigator.clipboard.writeText(text);
      showToast('Copied ' + (label || 'content') + ' to clipboard!');
    }

    async function openFolder(path) {
      try {
        const res = await fetch('/api/action/open-folder', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ path })
        });
        if (res.ok) showToast('Opened folder in Explorer');
        else showToast('Failed to open folder', true);
      } catch (err) {
        showToast('Error opening folder', true);
      }
    }

    // Tab Navigation
    function switchTab(tab) {
      activeTab = tab;
      ['env', 'ports', 'project', 'settings'].forEach(t => {
        const btn = document.getElementById(`tab-btn-${t}`);
        const view = document.getElementById(`view-${t}`);
        if (t === tab) {
          btn.className = 'tab-btn tab-active px-3.5 py-2 rounded-lg text-xs font-semibold transition flex items-center gap-2';
          view.classList.remove('hidden');
        } else {
          btn.className = 'tab-btn tab-inactive px-3.5 py-2 rounded-lg text-xs font-semibold transition flex items-center gap-2';
          view.classList.add('hidden');
        }
      });

      if (tab === 'ports') fetchPorts();
      else if (tab === 'settings') { loadConfig(); loadSystemInfo(); }
    }

    function refreshActiveTab() {
      if (activeTab === 'env') fetchAudit();
      else if (activeTab === 'ports') fetchPorts();
      else if (activeTab === 'project') runProjectAudit();
      else if (activeTab === 'settings') { loadConfig(); loadSystemInfo(); }
    }

    // --- TAB 1: ENVIRONMENT AUDITOR ---
    function getBadge(status) {
      if (status === 'healthy') return '<span class="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-medium bg-emerald-500/10 text-emerald-400 border border-emerald-500/20"><span class="w-1.5 h-1.5 rounded-full bg-emerald-400"></span> Healthy</span>';
      if (status === 'warning') return '<span class="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-medium bg-amber-500/10 text-amber-400 border border-amber-500/20"><span class="w-1.5 h-1.5 rounded-full bg-amber-400"></span> Action Needed</span>';
      if (status === 'error') return '<span class="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-medium bg-rose-500/10 text-rose-400 border border-rose-500/20"><span class="w-1.5 h-1.5 rounded-full bg-rose-400"></span> Error</span>';
      return '<span class="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-medium bg-slate-800 text-slate-400 border border-slate-700"><span class="w-1.5 h-1.5 rounded-full bg-slate-500"></span> Not Detected</span>';
    }

    function setCategory(cat) {
      currentCategory = cat;
      document.querySelectorAll('.filter-btn').forEach(b => {
        if (b.getAttribute('data-cat') === cat) {
          b.className = 'filter-btn px-3 py-1.5 rounded-lg text-xs font-semibold bg-violet-600 text-white';
        } else {
          b.className = 'filter-btn px-3 py-1.5 rounded-lg text-xs font-semibold bg-slate-800 text-slate-300 hover:bg-slate-700';
        }
      });
      filterTools();
    }

    function filterTools() {
      const query = document.getElementById('search-input').value.toLowerCase().trim();
      const grid = document.getElementById('tools-grid');
      grid.innerHTML = '';

      const filtered = allReports.filter(r => {
        const matchesCat = (currentCategory === 'all' || r.category.toLowerCase() === currentCategory);
        const matchesQuery = !query ||
          r.name.toLowerCase().includes(query) ||
          (r.version && r.version.toLowerCase().includes(query)) ||
          (r.binary_path && r.binary_path.toLowerCase().includes(query)) ||
          (r.home_path && r.home_path.toLowerCase().includes(query));
        return matchesCat && matchesQuery;
      });

      if (filtered.length === 0) {
        grid.innerHTML = '<div class="col-span-full py-16 text-center text-slate-500 text-sm"><i class="fa-solid fa-ghost text-3xl mb-3 block"></i>No matching SDKs or runtimes found.</div>';
        return;
      }

      filtered.forEach(r => {
        const card = document.createElement('div');
        card.className = 'glass-card rounded-xl p-5 flex flex-col justify-between transition-all duration-200';

        const companionsHtml = (r.companions || []).map(c => `
          <span class="inline-flex items-center gap-1 text-[11px] px-2 py-0.5 rounded ${c.installed ? 'bg-slate-800 text-slate-300 border border-slate-700' : 'bg-slate-900/60 text-slate-500'}">
            <i class="fa-solid ${c.installed ? 'fa-check text-emerald-400' : 'fa-xmark text-slate-600'} text-[9px]"></i>
            ${c.name}${c.version ? ' <span class="text-slate-400 font-mono">' + c.version + '</span>' : ''}
          </span>
        `).join('');

        const diagnosticsHtml = (r.diagnostics || []).map(d => `
          <div class="mt-2.5 p-3 rounded-lg bg-amber-500/10 border border-amber-500/25 text-amber-300 text-xs space-y-1">
            <div class="font-medium flex items-center gap-1.5"><i class="fa-solid fa-triangle-exclamation"></i> ${d.message}</div>
            ${d.suggested_fix ? `
              <div class="flex items-center justify-between gap-2 pt-1 border-t border-amber-500/20 text-slate-300 text-[11px]">
                <span><span class="text-amber-400 font-semibold">Suggested Fix:</span> ${d.suggested_fix}</span>
                <button onclick="copyToClipboard('${d.suggested_fix.replace(/\\\\/g, '\\\\\\\\')}', 'fix')" title="Copy suggested fix" class="px-2 py-0.5 rounded bg-amber-500/20 hover:bg-amber-500/30 text-amber-200 text-[10px] font-semibold transition flex-shrink-0">
                  Copy
                </button>
              </div>
            ` : ''}
          </div>
        `).join('');

        let pathsHtml = '';
        if (r.home_path) {
          pathsHtml += `
            <div class="bg-slate-950/70 p-2.5 rounded-lg border border-slate-800 flex items-center justify-between gap-2">
              <div class="truncate text-slate-300 font-mono text-[11px]" title="Home: ${r.home_path}">
                <span class="text-violet-400 font-sans font-medium text-[10px] uppercase tracking-wider mr-1">Root:</span>${r.home_path}
              </div>
              <div class="flex items-center gap-1 flex-shrink-0">
                <button onclick="copyToClipboard('${r.home_path.replace(/\\\\/g, '\\\\\\\\')}', 'directory')" title="Copy path" class="p-1 hover:text-violet-400 text-slate-400 transition"><i class="fa-regular fa-copy text-xs"></i></button>
                <button onclick="openFolder('${r.home_path.replace(/\\\\/g, '\\\\\\\\')}')" title="Open folder" class="p-1 hover:text-violet-400 text-slate-400 transition"><i class="fa-regular fa-folder-open text-xs"></i></button>
              </div>
            </div>
          `;
        }

        if (r.binary_path && r.binary_path !== r.home_path) {
          pathsHtml += `
            <div class="bg-slate-950/70 p-2.5 rounded-lg border border-slate-800 flex items-center justify-between gap-2">
              <div class="truncate text-slate-300 font-mono text-[11px]" title="Binary: ${r.binary_path}">
                <span class="text-emerald-400 font-sans font-medium text-[10px] uppercase tracking-wider mr-1">Binary:</span>${r.binary_path}
              </div>
              <div class="flex items-center gap-1 flex-shrink-0">
                <button onclick="copyToClipboard('${r.binary_path.replace(/\\\\/g, '\\\\\\\\')}', 'binary')" title="Copy binary" class="p-1 hover:text-violet-400 text-slate-400 transition"><i class="fa-regular fa-copy text-xs"></i></button>
                <button onclick="openFolder('${r.binary_path.replace(/\\\\/g, '\\\\\\\\')}')" title="Open folder" class="p-1 hover:text-violet-400 text-slate-400 transition"><i class="fa-regular fa-folder-open text-xs"></i></button>
              </div>
            </div>
          `;
        }

        card.innerHTML = `
          <div>
            <div class="flex items-start justify-between gap-2 mb-3">
              <div>
                <h3 class="font-bold text-white text-base tracking-tight flex items-center gap-2">
                  ${r.name}
                  <span class="text-[10px] text-slate-400 uppercase tracking-wider font-mono font-medium px-1.5 py-0.5 bg-slate-800 rounded">${r.category}</span>
                </h3>
                <div class="text-xs font-mono font-semibold text-violet-400 mt-1">
                  ${r.version ? 'v' + r.version : (r.installed ? '<span class="text-slate-400 font-normal">Installed</span>' : '<span class="text-slate-500 font-normal">Not detected</span>')}
                </div>
              </div>
              <div>${getBadge(r.status)}</div>
            </div>

            <div class="space-y-2 mt-4 text-xs">
              ${pathsHtml || '<div class="text-xs text-slate-500 italic">No binary or home path resolved</div>'}

              ${r.companions && r.companions.length > 0 ? `
                <div class="pt-2">
                  <div class="text-[11px] font-medium text-slate-400 mb-1.5">Companion Tools:</div>
                  <div class="flex flex-wrap gap-1.5">${companionsHtml}</div>
                </div>
              ` : ''}

              ${diagnosticsHtml}
            </div>
          </div>
        `;
        grid.appendChild(card);
      });
    }

    async function fetchAudit() {
      const icon = document.getElementById('refresh-icon');
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

        const sys = data.system;
        document.getElementById('sys-info').innerText = `${sys.os_name} ${sys.os_release} (${sys.arch}) • Host: ${sys.hostname}`;

        filterTools();
      } catch (err) {
        showToast('Error auditing environment', true);
      } finally {
        icon.classList.remove('fa-spin');
      }
    }

    // --- TAB 2: PORT MANAGER ---
    async function fetchPorts() {
      const icon = document.getElementById('refresh-icon');
      icon.classList.add('fa-spin');
      try {
        const devOnly = document.getElementById('ports-dev-toggle').checked;
        const res = await fetch(`/api/ports?dev_only=${devOnly}`);
        allPorts = await res.json();

        // Calculate stats
        const devCount = allPorts.filter(p => p.is_dev_port).length;
        const critCount = allPorts.filter(p => p.is_system_critical).length;
        document.getElementById('stat-ports-total').innerText = allPorts.length;
        document.getElementById('stat-ports-dev').innerText = devCount;
        document.getElementById('stat-ports-crit').innerText = critCount;

        const navBadge = document.getElementById('nav-dev-badge');
        if (devCount > 0) {
          navBadge.innerText = `${devCount} Dev`;
          navBadge.classList.remove('hidden');
        } else {
          navBadge.classList.add('hidden');
        }

        renderPortsTable();
      } catch (err) {
        showToast('Error loading sockets', true);
      } finally {
        icon.classList.remove('fa-spin');
      }
    }

    function toggleDevPortsOnly() {
      fetchPorts();
    }

    function filterPortsTable() {
      renderPortsTable();
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
          ? `<span class="inline-flex items-center gap-1 font-mono font-bold text-violet-400 bg-violet-500/10 px-2 py-0.5 rounded border border-violet-500/20">:${p.port}</span>`
          : `<span class="font-mono font-bold text-slate-200">:${p.port}</span>`;

        const tagBadge = p.is_dev_port
          ? `<span class="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-semibold bg-violet-500/20 text-violet-300"><i class="fa-solid fa-code text-[9px]"></i> Dev Port</span>`
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

      if (isCritical) {
        warningEl.classList.remove('hidden');
      } else {
        warningEl.classList.add('hidden');
      }

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

    // --- TAB 3: PROJECT AUDITOR ---
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

        // Tags
        const typesContainer = document.getElementById('rep-detected-types');
        typesContainer.innerHTML = (data.detected_types || []).map(t =>
          `<span class="px-2 py-0.5 rounded-full text-[10px] font-bold bg-violet-500/20 text-violet-300 border border-violet-500/30">${t}</span>`
        ).join('');

        // Status badge
        const badgeEl = document.getElementById('rep-status-badge');
        if (data.ready_to_build) {
          badgeEl.innerHTML = '<span class="inline-flex items-center gap-1.5 px-3 py-1 rounded-lg text-xs font-bold bg-emerald-500/20 text-emerald-300 border border-emerald-500/30"><i class="fa-solid fa-check"></i> READY TO BUILD</span>';
        } else {
          badgeEl.innerHTML = '<span class="inline-flex items-center gap-1.5 px-3 py-1 rounded-lg text-xs font-bold bg-rose-500/20 text-rose-300 border border-rose-500/30"><i class="fa-solid fa-triangle-exclamation"></i> PREREQUISITES MISSING</span>';
        }

        // Checks table
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

        // Recommended actions
        const actionsCard = document.getElementById('project-actions-card');
        const actionsList = document.getElementById('project-actions-list');
        if (data.suggested_actions && data.suggested_actions.length > 0) {
          actionsCard.classList.remove('hidden');
          actionsList.innerHTML = data.suggested_actions.map(act => `
            <div class="flex items-center justify-between p-2.5 rounded-lg bg-slate-950/80 border border-amber-500/20 text-xs">
              <div class="font-mono text-slate-200 truncate mr-2"><code>${act}</code></div>
              <button onclick="copyToClipboard('${act.replace(/\\\\/g, '\\\\\\\\')}', 'command')" class="px-2.5 py-1 rounded bg-amber-500/20 hover:bg-amber-500/30 text-amber-200 text-[11px] font-semibold transition flex-shrink-0">
                Copy
              </button>
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

    // --- TAB 4: SETTINGS & SEARCH PATHS ---
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
            <i class="fa-regular fa-folder text-violet-400"></i>
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

    // Initialize Default View
    loadConfig();
    fetchAudit();
    setProjectInput('.');
  </script>
</body>
</html>
"""

