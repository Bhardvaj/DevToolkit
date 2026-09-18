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
from fastapi.responses import HTMLResponse, StreamingResponse
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


class SelectFolderRequest(BaseModel):
    initial_path: Optional[str] = None


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


@app.get("/api/audit/stream")
def stream_audit():
    import json

    def event_generator():
        for item in registry.stream_audit():
            yield f"data: {json.dumps(item)}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


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


@app.post("/api/action/select-folder")
def post_select_folder(req: Optional[SelectFolderRequest] = None):
    initial = (req.initial_path or "").strip().strip('"').strip("'") if req else ""
    if initial == ".":
        initial = str(Path(".").resolve())

    if sys.platform == "win32":
        try:
            clean_initial = initial.replace("'", "''")
            ps_script = f"""
Add-Type -AssemblyName System.Windows.Forms
$dialog = New-Object System.Windows.Forms.FolderBrowserDialog
$dialog.Description = 'Select project folder for DevToolkit'
$dialog.ShowNewFolderButton = $true
if ('{clean_initial}' -and (Test-Path '{clean_initial}')) {{
    $dialog.SelectedPath = '{clean_initial}'
}}
$form = New-Object System.Windows.Forms.Form
$form.TopMost = $true
if ($dialog.ShowDialog($form) -eq [System.Windows.Forms.DialogResult]::OK) {{
    [Console]::OutputEncoding = [System.Text.Encoding]::UTF8
    Write-Output $dialog.SelectedPath
}}
"""
            res = subprocess.run(
                ["powershell", "-NoProfile", "-WindowStyle", "Hidden", "-Command", ps_script],
                capture_output=True,
                text=True,
                timeout=60,
                creationflags=0x08000000,
            )
            selected = res.stdout.strip()
            if selected:
                return {"status": "ok", "path": str(Path(selected).resolve())}
            return {"status": "cancelled", "path": None}
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
    elif sys.platform == "darwin":
        try:
            cmd = ["osascript", "-e", 'POSIX path of (choose folder with prompt "Select project folder")']
            res = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
            selected = res.stdout.strip()
            if selected:
                return {"status": "ok", "path": str(Path(selected).resolve())}
            return {"status": "cancelled", "path": None}
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
    else:
        for prog in [["zenity", "--file-selection", "--directory", "--title=Select project folder"], ["kdialog", "--getexistingdirectory"]]:
            try:
                res = subprocess.run(prog, capture_output=True, text=True, timeout=60)
                selected = res.stdout.strip()
                if selected:
                    return {"status": "ok", "path": str(Path(selected).resolve())}
            except Exception:
                continue
        return {"status": "cancelled", "path": None}


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
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Geist:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500;600&display=swap" rel="stylesheet">
  <script src="https://cdn.tailwindcss.com"></script>
  <script>
    tailwind.config = {
      darkMode: 'class',
      theme: {
        extend: {
          colors: {
            canvas: '#08090C',
            surface1: '#0E1015',
            surface2: '#141721',
            borderSubtle: '#1F2430',
            borderStrong: '#2E3446',
            emeraldAccent: '#10B981',
            cyanAccent: '#06B6D4',
            violetAccent: '#8B5CF6',
            amberAccent: '#F59E0B',
            crimsonAccent: '#EF4444',
            textMain: '#F3F4F6',
            textMuted: '#94A3B8',
            textDim: '#475569'
          },
          fontFamily: {
            sans: ['Geist', '-apple-system', 'BlinkMacSystemFont', 'Segoe UI', 'Roboto', 'sans-serif'],
            mono: ['"JetBrains Mono"', 'monospace']
          }
        }
      }
    }
  </script>
  <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css" />
  <style>
    body {
      background-color: #08090C;
      color: #F3F4F6;
      font-family: 'Geist', -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
    }
    code, kbd, .font-mono {
      font-family: 'JetBrains Mono', monospace;
      font-feature-settings: "tnum" 1;
    }
    .card-pro, .glass-card {
      background-color: #0E1015;
      border: 1px solid #1F2430;
      border-radius: 6px;
      transition: all 0.18s ease-in-out;
    }
    .card-pro:hover, .glass-card:hover {
      border-color: #2E3446;
    }
    .btn-primary-pro {
      background-color: #10B981;
      color: #08090C;
      font-weight: 600;
      border-radius: 4px;
      transition: all 0.15s ease-in-out;
    }
    .btn-primary-pro:hover {
      background-color: #059669;
      color: #08090C;
    }
    .btn-primary-pro:active {
      transform: scale(0.98);
    }
    .btn-secondary-pro {
      background-color: #141721;
      border: 1px solid #1F2430;
      color: #F3F4F6;
      font-weight: 500;
      border-radius: 4px;
      transition: all 0.15s ease-in-out;
    }
    .btn-secondary-pro:hover {
      border-color: #2E3446;
      background-color: #1A1E2B;
      color: #FFFFFF;
    }
    .btn-secondary-pro:active {
      transform: scale(0.98);
    }
    .btn-destructive {
      background-color: rgba(239, 68, 68, 0.12);
      border: 1px solid rgba(239, 68, 68, 0.35);
      color: #EF4444;
      border-radius: 4px;
      font-weight: 600;
      transition: all 0.15s ease-in-out;
    }
    .btn-destructive:hover {
      background-color: #EF4444;
      border-color: #EF4444;
      color: #FFFFFF;
    }
    .input-pro {
      background-color: #0E1015;
      border: 1px solid #1F2430;
      color: #F3F4F6;
      border-radius: 4px;
      transition: border-color 0.15s ease-in-out, box-shadow 0.15s ease-in-out;
    }
    .input-pro:focus {
      outline: none;
      border-color: #10B981;
      box-shadow: 0 0 0 1px #10B981;
    }
    .kbd-pro {
      background-color: #141721;
      border: 1px solid #1F2430;
      color: #94A3B8;
      font-family: 'JetBrains Mono', monospace;
      font-feature-settings: "tnum" 1;
      border-radius: 4px;
      padding: 1px 5px;
      font-size: 10px;
      line-height: 1.2;
    }
    .modal-pro {
      background-color: #141721;
      border: 1px solid #2E3446;
      border-radius: 8px;
      box-shadow: 0 12px 32px -4px rgba(0, 0, 0, 0.7), 0 0 0 1px rgba(255, 255, 255, 0.04) inset;
    }
    .modal-backdrop {
      background: rgba(8, 9, 12, 0.82);
      backdrop-filter: blur(8px);
    }
    .custom-scrollbar::-webkit-scrollbar { width: 5px; height: 5px; }
    .custom-scrollbar::-webkit-scrollbar-track { background: transparent; }
    .custom-scrollbar::-webkit-scrollbar-thumb { background: #1F2430; border-radius: 4px; }
    .custom-scrollbar::-webkit-scrollbar-thumb:hover { background: #2E3446; }
    .nav-active {
      background-color: #141721;
      color: #FFFFFF;
      border: 1px solid rgba(16, 185, 129, 0.35);
      box-shadow: inset 2px 0 0 #10B981;
    }
    .nav-inactive {
      color: #94A3B8;
      border: 1px solid transparent;
    }
    .nav-inactive:hover {
      color: #F3F4F6;
      background-color: #141721;
      border-color: #1F2430;
    }
    .cat-active {
      background-color: #141721;
      color: #FFFFFF;
      border-color: rgba(16, 185, 129, 0.6);
      box-shadow: inset 0 -1px 0 #10B981;
    }
    .cat-inactive {
      color: #94A3B8;
      border-color: #1F2430;
      background-color: #0E1015;
    }
    .cat-inactive:hover {
      color: #F3F4F6;
      background-color: #141721;
      border-color: #2E3446;
    }
    .stat-filter-card {
      cursor: pointer;
      transition: all 0.18s ease-in-out;
      border: 1px solid #1F2430;
      background-color: #0E1015;
      border-radius: 6px;
    }
    .stat-filter-card:hover {
      border-color: #2E3446;
      background-color: #141721;
      transform: translateY(-1px);
      box-shadow: 0 4px 16px rgba(0, 0, 0, 0.45);
    }
    .stat-filter-active {
      border-color: #10B981 !important;
      background: #141721 !important;
      box-shadow: 0 0 0 1px #10B981, 0 4px 16px rgba(16, 185, 129, 0.18) !important;
    }
    .drawer-panel {
      transform: translateX(100%);
      transition: transform 0.28s cubic-bezier(0.16, 1, 0.3, 1);
    }
    .drawer-panel.open {
      transform: translateX(0);
    }
    @keyframes shimmer {
      0% { background-position: -200% 0; }
      100% { background-position: 200% 0; }
    }
    .skeleton-shimmer {
      background: linear-gradient(90deg, rgba(255,255,255,0.02) 25%, rgba(255,255,255,0.07) 50%, rgba(255,255,255,0.02) 75%);
      background-size: 200% 100%;
      animation: shimmer 1.8s infinite;
    }
  </style>
</head>
<body class="h-full w-full bg-[#08090C] text-[#F3F4F6] font-sans select-none overflow-hidden flex flex-col">

  <!-- Main Viewport Layout: Sidebar + Main Area -->
  <div class="flex flex-1 overflow-hidden">

    <!-- LEFT FIXED VERTICAL SIDEBAR -->
    <aside class="w-56 sm:w-64 bg-[#0E1015] border-r border-[#1F2430] flex flex-col justify-between p-3 sm:p-3.5 select-none flex-shrink-0 z-20">
      <div class="space-y-4 flex-1 overflow-y-auto custom-scrollbar pr-0.5">
        <!-- Brand Header -->
        <div class="flex items-center gap-3 px-1 pt-1">
          <div class="w-8 h-8 rounded bg-[#141721] border border-[#1F2430] flex items-center justify-center text-[#10B981] shadow flex-shrink-0">
            <i class="fa-solid fa-bolt text-sm"></i>
          </div>
          <div class="min-w-0">
            <h1 class="text-sm font-semibold tracking-tight text-[#F3F4F6] truncate">DevToolkit</h1>
            <div class="text-[11px] text-[#94A3B8] font-mono truncate" id="side-os-info">Detecting OS...</div>
          </div>
        </div>

        <!-- Host Card -->
        <div class="bg-[#141721] border border-[#1F2430] rounded px-2.5 py-1.5 flex items-center text-xs min-w-0">
          <span class="flex items-center gap-2 text-[#94A3B8] font-medium text-[11px] truncate">
            <span class="w-1.5 h-1.5 rounded-full bg-[#10B981] shadow-[0_0_6px_#10B981] flex-shrink-0"></span>
            Host: <span id="side-host-name" class="text-[#F3F4F6] font-mono font-semibold truncate">Detecting...</span>
          </span>
        </div>

        <!-- Navigation Group: WORKSPACE HUB -->
        <div>
          <div class="text-[10px] font-mono font-semibold text-[#475569] tracking-wider uppercase px-2 mb-1.5 mt-3">WORKSPACE HUB</div>
          <div class="space-y-1">
            <button onclick="switchTab('env')" id="nav-btn-env" class="w-full flex items-center justify-between px-2.5 py-2 rounded text-xs font-medium transition nav-active">
              <div class="flex items-center gap-2.5 truncate">
                <i class="fa-solid fa-table-cells-large text-xs flex-shrink-0 text-[#10B981]"></i>
                <span class="truncate">Environment</span>
              </div>
            </button>

            <button onclick="switchTab('ports')" id="nav-btn-ports" class="w-full flex items-center justify-between px-2.5 py-2 rounded text-xs font-medium transition nav-inactive">
              <div class="flex items-center gap-2.5 truncate">
                <i class="fa-solid fa-network-wired text-xs flex-shrink-0"></i>
                <span class="truncate">Port Manager</span>
              </div>
              <span id="side-ports-badge" class="px-1.5 py-0.2 rounded text-[10px] font-mono font-semibold bg-[#06B6D41A] text-[#06B6D4] border border-[#06B6D440] flex-shrink-0">0</span>
            </button>

            <button onclick="switchTab('project')" id="nav-btn-project" class="w-full flex items-center justify-between px-2.5 py-2 rounded text-xs font-medium transition nav-inactive">
              <div class="flex items-center gap-2.5 truncate">
                <i class="fa-solid fa-code-branch text-xs flex-shrink-0"></i>
                <span class="truncate">Project Auditor</span>
              </div>
            </button>
          </div>
        </div>

        <!-- Navigation Group: PREFERENCES -->
        <div>
          <div class="text-[10px] font-mono font-semibold text-[#475569] tracking-wider uppercase px-2 mb-1.5 mt-4">PREFERENCES</div>
          <div class="space-y-1">
            <button onclick="switchTab('settings')" id="nav-btn-settings" class="w-full flex items-center justify-between px-2.5 py-2 rounded text-xs font-medium transition nav-inactive">
              <div class="flex items-center gap-2.5 truncate">
                <i class="fa-solid fa-gear text-xs flex-shrink-0"></i>
                <span class="truncate">Settings</span>
              </div>
            </button>
          </div>
        </div>
      </div>

      <!-- SIDEBAR FOOTER: Software & Runtime Info -->
      <div class="pt-3 border-t border-[#1F2430] mt-auto flex-shrink-0">
        <div class="p-2.5 rounded-md bg-[#141721] border border-[#1F2430] space-y-2">
          <div class="flex items-center justify-between text-xs">
            <span class="text-[#F3F4F6] font-medium flex items-center gap-1.5 truncate">
              <i class="fa-solid fa-cube text-[#06B6D4] text-xs flex-shrink-0"></i>
              <span class="truncate">DevToolkit</span>
            </span>
            <span class="text-[10px] font-mono px-1.5 py-0.2 rounded bg-[#8B5CF61A] text-[#8B5CF6] font-semibold border border-[#8B5CF640] flex-shrink-0" id="side-app-version">v0.2.0</span>
          </div>
          <div class="flex items-center justify-between text-[11px] text-[#94A3B8] font-mono">
            <span class="text-[#475569] flex items-center gap-1">
              <i class="fa-brands fa-python text-[#F59E0B] text-[10px]"></i> Python
            </span>
            <span id="side-python-version" class="text-[#F3F4F6]">...</span>
          </div>
          <div class="flex items-center justify-between text-[10px] text-[#94A3B8] pt-1.5 border-t border-[#1F2430] font-sans">
            <span class="flex items-center gap-1.5 text-[#10B981] font-medium">
              <span class="w-1.5 h-1.5 rounded-full bg-[#10B981] animate-pulse"></span>
              Runtime Active
            </span>
            <button onclick="toggleHelpModal()" class="text-[#94A3B8] hover:text-[#F3F4F6] transition flex items-center gap-1" title="View Diagnostics & Shortcuts (?)">
              <i class="fa-solid fa-circle-question text-[10px]"></i> Help
            </button>
          </div>
        </div>
      </div>
    </aside>

    <!-- RIGHT MAIN CONTENT PANEL -->
    <div class="flex-1 flex flex-col overflow-hidden bg-[#08090C] min-w-0">

      <!-- Top Header: Breadcrumbs + Global Search + Actions -->
      <header class="h-12 px-4 sm:px-5 border-b border-[#1F2430] flex items-center justify-between bg-[#08090C]/95 backdrop-blur-md flex-shrink-0 z-10 gap-3">
        <!-- Breadcrumbs -->
        <div class="flex items-center gap-2 text-xs text-[#94A3B8] font-medium select-none min-w-0 truncate">
          <span class="text-[#475569] font-mono flex-shrink-0">toolkit</span>
          <span class="text-[#2E3446] flex-shrink-0">/</span>
          <span class="flex items-center gap-1.5 text-[#F3F4F6] font-semibold truncate" id="top-breadcrumb">
            <span class="w-1.5 h-1.5 rounded-full bg-[#10B981] shadow-[0_0_6px_#10B981] flex-shrink-0"></span>
            Environment & Diagnostics
          </span>
        </div>

        <!-- Global Search Bar & Actions -->
        <div class="flex items-center gap-2 sm:gap-2.5 flex-shrink-0">
          <div class="relative w-36 sm:w-64 md:w-80 lg:w-96 flex items-center" id="top-search-wrapper">
            <div class="absolute inset-y-0 left-0 pl-2.5 flex items-center pointer-events-none text-[#94A3B8] text-xs">
              <i class="fa-solid fa-search"></i>
            </div>
            <input type="text" id="global-search-input" oninput="onSearchChange()" placeholder="Search SDK, runtime, path..." class="input-pro w-full pl-8 pr-16 py-1 text-xs text-[#F3F4F6] placeholder-[#475569] font-sans" />
            <div class="absolute inset-y-0 right-0 pr-2 flex items-center pointer-events-none">
              <kbd class="kbd-pro hidden sm:inline">Ctrl+K</kbd>
            </div>
          </div>

          <button onclick="refreshActiveTab()" id="rescan-btn" class="btn-secondary-pro flex items-center gap-1.5 px-2.5 sm:px-3 py-1 text-xs font-medium flex-shrink-0">
            <i class="fa-solid fa-rotate text-xs" id="rescan-icon"></i>
            <span class="hidden sm:inline">Rescan</span>
            <span class="text-[10px] font-mono text-[#94A3B8]" id="rescan-timer">(now)</span>
          </button>

          <!-- Export Dropdown -->
          <div class="relative inline-block text-left" id="export-dropdown-wrapper">
            <button onclick="toggleExportMenu()" id="export-btn" class="btn-secondary-pro flex items-center gap-1.5 px-2.5 sm:px-3 py-1 text-xs font-medium flex-shrink-0" title="Export Environment Audit Report">
              <i class="fa-solid fa-file-export text-xs text-[#06B6D4]"></i>
              <span class="hidden md:inline">Export</span>
              <i class="fa-solid fa-chevron-down text-[9px] text-[#94A3B8]"></i>
            </button>
            <div id="export-menu" class="hidden absolute right-0 mt-1 w-48 rounded-md bg-[#141721] border border-[#2E3446] shadow-2xl z-50 py-1 text-xs text-[#94A3B8]">
              <button onclick="exportReport('md')" class="w-full text-left px-3 py-1.5 hover:bg-[#1A1E2B] hover:text-[#F3F4F6] flex items-center gap-2 transition">
                <i class="fa-solid fa-clipboard text-[#06B6D4]"></i> Copy Markdown Table
              </button>
              <button onclick="exportReport('json')" class="w-full text-left px-3 py-1.5 hover:bg-[#1A1E2B] hover:text-[#F3F4F6] flex items-center gap-2 transition">
                <i class="fa-solid fa-code text-[#8B5CF6]"></i> Copy JSON Summary
              </button>
              <button onclick="exportReport('download')" class="w-full text-left px-3 py-1.5 hover:bg-[#1A1E2B] hover:text-[#F3F4F6] flex items-center gap-2 transition border-t border-[#1F2430] mt-0.5 pt-1.5">
                <i class="fa-solid fa-download text-[#10B981]"></i> Download Report (.md)
              </button>
            </div>
          </div>

          <button onclick="toggleHelpModal()" class="p-1.5 hover:bg-[#141721] text-[#94A3B8] hover:text-[#F3F4F6] rounded transition flex-shrink-0" title="Shortcuts & Help (?)">
            <i class="fa-regular fa-circle-question text-sm"></i>
          </button>
        </div>
      </header>

      <!-- Scrollable Main Content -->
      <main class="flex-1 overflow-y-auto p-4 sm:p-6 space-y-5 sm:space-y-6 custom-scrollbar">

        <!-- ==================== VIEW 1: ENVIRONMENT AUDITOR ==================== -->
        <div id="view-env" class="space-y-5">

          <!-- 6 Horizontal Interactive Stat Filter Cards -->
          <div class="grid grid-cols-2 sm:grid-cols-3 xl:grid-cols-6 gap-3" id="stats-container">
            <!-- 1. Audited Tools -->
            <div onclick="toggleStatusFilter('all')" id="stat-card-all" class="card-pro stat-filter-card p-3 sm:p-3.5 flex flex-col justify-between relative overflow-hidden min-w-0" title="Click to show all tools">
              <div class="flex items-center justify-between gap-1 text-xs text-[#94A3B8] font-medium min-w-0">
                <span class="truncate">Audited Tools</span>
                <i class="fa-regular fa-pen-to-square text-[10px] text-[#475569] flex-shrink-0"></i>
              </div>
              <div class="flex items-baseline justify-between gap-2 my-2 min-w-0">
                <div class="text-xl sm:text-2xl font-bold font-mono text-[#F3F4F6] tracking-tight leading-none flex-shrink-0" id="stat-total">10</div>
                <div class="text-[10px] text-[#94A3B8] font-mono truncate text-right">100% total</div>
              </div>
              <div class="w-full h-0.5 rounded-full bg-[#1F2430] overflow-hidden">
                <div class="h-full bg-[#94A3B8] rounded-full w-full"></div>
              </div>
            </div>

            <!-- 2. Installed -->
            <div onclick="toggleStatusFilter('installed')" id="stat-card-installed" class="card-pro stat-filter-card p-3 sm:p-3.5 flex flex-col justify-between relative overflow-hidden min-w-0" title="Click to filter installed tools">
              <div class="flex items-center justify-between gap-1 text-xs text-[#94A3B8] font-medium min-w-0">
                <span class="truncate">Installed</span>
                <span class="w-1.5 h-1.5 rounded-full bg-[#10B981] shadow-[0_0_6px_#10B981] flex-shrink-0"></span>
              </div>
              <div class="flex items-baseline justify-between gap-2 my-2 min-w-0">
                <div class="text-xl sm:text-2xl font-bold font-mono text-[#F3F4F6] tracking-tight leading-none flex-shrink-0" id="stat-installed">—</div>
                <div class="text-[10px] text-[#10B981] font-mono truncate text-right" id="stat-coverage">— coverage</div>
              </div>
              <div class="w-full h-0.5 rounded-full bg-[#1F2430] overflow-hidden">
                <div class="h-full bg-[#10B981] rounded-full transition-all duration-500" id="stat-installed-bar" style="width: 70%"></div>
              </div>
            </div>

            <!-- 3. Healthy -->
            <div onclick="toggleStatusFilter('healthy')" id="stat-card-healthy" class="card-pro stat-filter-card p-3 sm:p-3.5 flex flex-col justify-between relative overflow-hidden min-w-0" title="Click to filter healthy tools">
              <div class="flex items-center justify-between gap-1 text-xs text-[#94A3B8] font-medium min-w-0">
                <span class="truncate">Healthy</span>
                <span class="text-[9px] font-mono px-1 py-0.2 rounded bg-[#10B9811A] text-[#10B981] font-semibold border border-[#10B98140] flex-shrink-0">Optimal</span>
              </div>
              <div class="flex items-baseline justify-between gap-2 my-2 min-w-0">
                <div class="text-xl sm:text-2xl font-bold font-mono text-[#F3F4F6] tracking-tight leading-none flex-shrink-0" id="stat-healthy">—</div>
                <div class="text-[10px] text-[#10B981] font-mono truncate text-right">Ready to build</div>
              </div>
              <div class="w-full h-0.5 rounded-full bg-[#1F2430] overflow-hidden">
                <div class="h-full bg-[#10B981] rounded-full transition-all duration-500" id="stat-healthy-bar" style="width: 60%"></div>
              </div>
            </div>

            <!-- 4. Action Needed -->
            <div onclick="toggleStatusFilter('warning')" id="stat-card-warning" class="card-pro stat-filter-card p-3 sm:p-3.5 flex flex-col justify-between relative overflow-hidden min-w-0" title="Click to filter tools with action needed">
              <div class="flex items-center justify-between gap-1 text-xs text-[#94A3B8] font-medium min-w-0">
                <span class="truncate">Action Needed</span>
                <span class="w-1.5 h-1.5 rounded-full bg-[#F59E0B] shadow-[0_0_6px_#F59E0B] flex-shrink-0"></span>
              </div>
              <div class="flex items-baseline justify-between gap-2 my-2 min-w-0">
                <div class="text-xl sm:text-2xl font-bold font-mono text-[#F3F4F6] tracking-tight leading-none flex-shrink-0" id="stat-warning">—</div>
                <div class="text-[10px] text-[#F59E0B] font-mono truncate text-right">Path & Var</div>
              </div>
              <div class="w-full h-0.5 rounded-full bg-[#1F2430] overflow-hidden">
                <div class="h-full bg-[#F59E0B] rounded-full transition-all duration-500" id="stat-warning-bar" style="width: 20%"></div>
              </div>
            </div>

            <!-- 5. Critical Errors -->
            <div onclick="toggleStatusFilter('error')" id="stat-card-error" class="card-pro stat-filter-card p-3 sm:p-3.5 flex flex-col justify-between relative overflow-hidden min-w-0" title="Click to filter tools with errors">
              <div class="flex items-center justify-between gap-1 text-xs text-[#94A3B8] font-medium min-w-0">
                <span class="truncate">Critical Errors</span>
                <span class="w-1.5 h-1.5 rounded-full bg-[#EF4444] flex-shrink-0"></span>
              </div>
              <div class="flex items-baseline justify-between gap-2 my-2 min-w-0">
                <div class="text-xl sm:text-2xl font-bold font-mono text-[#F3F4F6] tracking-tight leading-none flex-shrink-0" id="stat-error">—</div>
                <div class="text-[10px] text-[#94A3B8] font-mono truncate text-right">No crash flags</div>
              </div>
              <div class="w-full h-0.5 rounded-full bg-[#1F2430] overflow-hidden">
                <div class="h-full bg-[#EF4444] rounded-full transition-all duration-500" id="stat-error-bar" style="width: 0%"></div>
              </div>
            </div>

            <!-- 6. Not Found -->
            <div onclick="toggleStatusFilter('not_found')" id="stat-card-not_found" class="card-pro stat-filter-card p-3 sm:p-3.5 flex flex-col justify-between relative overflow-hidden min-w-0" title="Click to filter undetected tools">
              <div class="flex items-center justify-between gap-1 text-xs text-[#94A3B8] font-medium min-w-0">
                <span class="truncate">Not Found</span>
                <span class="w-1.5 h-1.5 rounded-full bg-[#475569] flex-shrink-0"></span>
              </div>
              <div class="flex items-baseline justify-between gap-2 my-2 min-w-0">
                <div class="text-xl sm:text-2xl font-bold font-mono text-[#F3F4F6] tracking-tight leading-none flex-shrink-0" id="stat-missing">—</div>
                <div class="text-[10px] text-[#475569] font-mono truncate text-right">Unconfigured</div>
              </div>
              <div class="w-full h-0.5 rounded-full bg-[#1F2430] overflow-hidden">
                <div class="h-full bg-[#475569] rounded-full transition-all duration-500" id="stat-missing-bar" style="width: 30%"></div>
              </div>
            </div>
          </div>

          <!-- Category Filter Pills + Status Pill + Layout Toggle & Sort Bar -->
          <div class="flex flex-col sm:flex-row items-center justify-between gap-2.5 bg-[#0E1015] p-2 rounded-md border border-[#1F2430]">
            <!-- Left: Filter Pills with Counts & Active Status Pill -->
            <div class="flex items-center gap-2 overflow-x-auto w-full sm:w-auto pb-1 sm:pb-0 custom-scrollbar">
              <div class="flex items-center gap-1.5" id="category-filters">
                <!-- Dynamically populated by renderCategoryPills() -->
              </div>

              <!-- Active Status Filter Indicator Pill -->
              <div id="active-status-pill-container" class="hidden items-center gap-1.5 pl-2 border-l border-[#1F2430]">
                <span id="active-status-pill" class="px-2 py-0.5 rounded text-xs font-mono font-semibold bg-[#10B9811A] text-[#10B981] border border-[#10B98140] flex items-center gap-1.5">
                  <span id="active-status-pill-label">Filter: Action Needed</span>
                  <button onclick="clearStatusFilter()" class="hover:text-white p-0.5" title="Clear status filter"><i class="fa-solid fa-xmark text-[10px]"></i></button>
                </span>
              </div>

              <button id="reset-filters-btn" onclick="resetAllFilters()" class="hidden px-2 py-0.5 text-[11px] font-mono font-semibold text-[#EF4444] hover:text-white bg-[#EF444415] hover:bg-[#EF4444] border border-[#EF444440] rounded transition flex items-center gap-1 flex-shrink-0">
                <i class="fa-solid fa-filter-circle-xmark text-[10px]"></i> Reset
              </button>
            </div>

            <!-- Right: Layout Switcher & Sort Selector -->
            <div class="flex items-center gap-2 w-full sm:w-auto justify-end flex-shrink-0">
              <div class="flex items-center bg-[#08090C] border border-[#1F2430] rounded p-0.5">
                <button onclick="setLayout('grid')" id="layout-grid-btn" class="p-1 rounded text-xs bg-[#141721] text-[#10B981] border border-[#10B98140] transition" title="Grid Layout">
                  <i class="fa-solid fa-table-cells-large"></i>
                </button>
                <button onclick="setLayout('list')" id="layout-list-btn" class="p-1 rounded text-xs text-[#94A3B8] hover:text-[#F3F4F6] transition" title="List Layout">
                  <i class="fa-solid fa-list-ul"></i>
                </button>
              </div>

              <select id="sort-select" onchange="onSortChange()" class="bg-[#08090C] border border-[#1F2430] rounded px-2.5 py-1 text-xs text-[#94A3B8] focus:outline-none focus:border-[#10B981] cursor-pointer font-sans">
                <option value="severity">Sort: Severity</option>
                <option value="name">Sort: Name</option>
                <option value="category">Sort: Category</option>
                <option value="status">Sort: Status</option>
              </select>
            </div>
          </div>

          <!-- Active Custom Search Paths Banner -->
          <div id="search-paths-banner" class="hidden text-xs bg-[#0E1015] border border-[#06B6D440] rounded-md px-3.5 py-2 flex items-center justify-between">
            <div class="flex items-center gap-2 truncate mr-3">
              <i class="fa-solid fa-folder-tree text-[#06B6D4] flex-shrink-0"></i>
              <span class="text-[#94A3B8] flex-shrink-0">Custom Monitored Directories:</span>
              <span id="banner-paths-list" class="font-mono text-[#06B6D4] truncate"></span>
            </div>
            <button onclick="switchTab('settings')" class="text-[#06B6D4] hover:text-white font-medium text-xs flex-shrink-0">Manage Paths &rarr;</button>
          </div>

          <!-- Tools Container: Grid View with standard gap-4 -->
          <div class="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4" id="tools-grid"></div>

          <!-- Tools Container: List View -->
          <div id="tools-list-container" class="hidden card-pro overflow-hidden shadow-xl">
            <div class="overflow-x-auto">
              <table class="w-full text-left text-xs">
                <thead class="bg-[#08090C] text-[#94A3B8] uppercase tracking-wider text-[10px] border-b border-[#1F2430] font-mono font-semibold">
                  <tr>
                    <th class="py-2.5 px-3.5">Tool</th>
                    <th class="py-2.5 px-3.5">Category</th>
                    <th class="py-2.5 px-3.5">Status</th>
                    <th class="py-2.5 px-3.5">Version</th>
                    <th class="py-2.5 px-3.5">Home / Root Path</th>
                    <th class="py-2.5 px-3.5">Binary Path</th>
                    <th class="py-2.5 px-3.5 text-right">Actions</th>
                  </tr>
                </thead>
                <tbody id="tools-list-tbody" class="divide-y divide-[#1F2430] font-sans"></tbody>
              </table>
            </div>
          </div>
        </div>

        <!-- ==================== VIEW 2: PORT MANAGER ==================== -->
        <div id="view-ports" class="space-y-5 hidden">
          <!-- Port Stats -->
          <div class="grid grid-cols-1 sm:grid-cols-3 gap-3">
            <div class="card-pro p-3.5 flex items-center gap-3">
              <div class="w-9 h-9 rounded bg-[#06B6D41A] text-[#06B6D4] border border-[#06B6D440] flex items-center justify-center font-bold text-base flex-shrink-0">
                <i class="fa-solid fa-satellite-dish"></i>
              </div>
              <div>
                <div class="text-xs text-[#94A3B8] font-medium">Listening Sockets</div>
                <div class="text-xl font-bold font-mono text-[#F3F4F6] mt-0.5" id="stat-ports-total">—</div>
              </div>
            </div>
            <div class="card-pro p-3.5 flex items-center gap-3">
              <div class="w-9 h-9 rounded bg-[#10B9811A] text-[#10B981] border border-[#10B98140] flex items-center justify-center font-bold text-base flex-shrink-0">
                <i class="fa-solid fa-code"></i>
              </div>
              <div>
                <div class="text-xs text-[#94A3B8] font-medium">Developer Ports Active</div>
                <div class="text-xl font-bold font-mono text-[#10B981] mt-0.5" id="stat-ports-dev">—</div>
              </div>
            </div>
            <div class="card-pro p-3.5 flex items-center gap-3">
              <div class="w-9 h-9 rounded bg-[#141721] text-[#94A3B8] border border-[#1F2430] flex items-center justify-center font-bold text-base flex-shrink-0">
                <i class="fa-solid fa-shield-halved"></i>
              </div>
              <div>
                <div class="text-xs text-[#94A3B8] font-medium">System Protected</div>
                <div class="text-xl font-bold font-mono text-[#94A3B8] mt-0.5" id="stat-ports-crit">—</div>
              </div>
            </div>
          </div>

          <!-- Ports Filter Bar -->
          <div class="flex flex-col sm:flex-row items-center justify-between gap-2.5 bg-[#0E1015] p-2.5 rounded-md border border-[#1F2430]">
            <div class="flex items-center gap-2.5 w-full sm:w-auto flex-wrap">
              <label class="inline-flex items-center gap-2 cursor-pointer text-xs font-medium text-[#F3F4F6] bg-[#141721] px-2.5 py-1 rounded border border-[#1F2430] hover:border-[#2E3446] transition">
                <input type="checkbox" id="ports-dev-toggle" onchange="fetchPorts(false)" class="rounded-[3px] border-[#2E3446] bg-[#0E1015] text-[#10B981] focus:ring-0 focus:ring-offset-0 w-3.5 h-3.5" />
                <span>Developer Ports Only</span>
              </label>

              <!-- View Mode Toggle: Flat Table vs Grouped by Process -->
              <div class="flex items-center bg-[#08090C] border border-[#1F2430] rounded p-0.5">
                <button onclick="setPortViewMode('flat')" id="port-view-flat-btn" class="px-2.5 py-1 rounded text-xs bg-[#141721] text-[#10B981] border border-[#10B98140] font-medium transition flex items-center gap-1.5" title="Flat Sockets Table">
                  <i class="fa-solid fa-list"></i>
                  <span class="hidden sm:inline">Flat View</span>
                </button>
                <button onclick="setPortViewMode('grouped')" id="port-view-grouped-btn" class="px-2.5 py-1 rounded text-xs text-[#94A3B8] hover:text-[#F3F4F6] font-medium transition flex items-center gap-1.5" title="Group by Process">
                  <i class="fa-solid fa-layer-group"></i>
                  <span class="hidden sm:inline">By Process</span>
                </button>
              </div>

              <button onclick="fetchPorts(true)" id="btn-refresh-ports" class="btn-secondary-pro px-3 py-1 text-xs font-medium transition flex items-center gap-1.5">
                <i id="ports-refresh-icon" class="fa-solid fa-rotate text-xs"></i>
                <span>Refresh</span>
              </button>
            </div>

            <div class="relative w-full sm:w-72 flex items-center">
              <div class="absolute inset-y-0 left-0 pl-2.5 flex items-center pointer-events-none text-[#94A3B8] text-xs">
                <i class="fa-solid fa-search"></i>
              </div>
              <input type="text" id="ports-search-input" oninput="renderPorts()" placeholder="Filter port, process, PID..." class="input-pro w-full pl-8 pr-16 py-1 text-xs text-[#F3F4F6] placeholder-[#475569] font-sans" />
              <div class="absolute inset-y-0 right-0 pr-2 flex items-center pointer-events-none">
                <kbd class="kbd-pro hidden sm:inline">Ctrl+K</kbd>
              </div>
            </div>
          </div>

          <!-- Mode 1: Flat Ports Table -->
          <div id="ports-flat-container" class="card-pro overflow-hidden shadow-xl">
            <div class="overflow-x-auto">
              <table class="w-full text-left text-xs">
                <thead class="bg-[#08090C] text-[#94A3B8] uppercase tracking-wider text-[10px] border-b border-[#1F2430] font-mono font-semibold">
                  <tr>
                    <th class="py-2.5 px-3.5">Port</th>
                    <th class="py-2.5 px-3.5">Classification</th>
                    <th class="py-2.5 px-3.5">Process Name</th>
                    <th class="py-2.5 px-3.5">PID</th>
                    <th class="py-2.5 px-3.5">Address</th>
                    <th class="py-2.5 px-3.5">Status</th>
                    <th class="py-2.5 px-3.5 text-right">Actions</th>
                  </tr>
                </thead>
                <tbody id="ports-table-body" class="divide-y divide-[#1F2430] font-sans"></tbody>
              </table>
            </div>
          </div>

          <!-- Mode 2: Grouped by Process Cards -->
          <div id="ports-grouped-container" class="space-y-3.5 hidden">
            <!-- Dynamically populated by renderPortsGrouped() -->
          </div>
        </div>

        <!-- ==================== VIEW 3: PROJECT AUDITOR ==================== -->
        <div id="view-project" class="space-y-5 hidden">
          <!-- Selection Card -->
          <div class="card-pro p-5 sm:p-6 space-y-4">
            <div class="flex items-start justify-between gap-4">
              <div>
                <h2 class="text-base font-semibold text-[#F3F4F6] flex items-center gap-2">
                  <i class="fa-solid fa-folder-tree text-[#10B981]"></i>
                  Project Workstation Readiness Auditor
                </h2>
                <p class="text-xs text-[#94A3B8] mt-1">
                  Select any workspace directory or project repository to verify if your workstation satisfies its SDK, runtime, compiler, and manifest requirements.
                </p>
              </div>
            </div>

            <div class="flex flex-col sm:flex-row items-center gap-2 pt-1">
              <div class="relative flex-1 w-full flex items-center">
                <div class="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none text-[#94A3B8] text-xs">
                  <i class="fa-regular fa-folder"></i>
                </div>
                <input type="text" id="project-path-input" onkeydown="if(event.key==='Enter') runProjectAudit()" placeholder="e.g. D:\\UtilitySoftware or D:\\Dev\\my-app" class="input-pro w-full pl-8 pr-20 py-2 text-xs font-mono text-[#F3F4F6] placeholder-[#475569]" />
                <div class="absolute inset-y-0 right-0 pr-2 flex items-center pointer-events-none">
                  <kbd class="kbd-pro hidden sm:inline">Enter ↵</kbd>
                </div>
              </div>
              <button onclick="browseProjectFolder()" id="btn-browse-project" class="btn-secondary-pro w-full sm:w-auto px-3.5 py-2 text-xs font-medium flex items-center justify-center gap-2 flex-shrink-0" title="Open Explorer to select project folder">
                <i class="fa-regular fa-folder-open text-[#06B6D4] text-xs" id="browse-folder-icon"></i>
                <span>Browse...</span>
              </button>
              <button onclick="runProjectAudit()" id="btn-audit-project" class="btn-primary-pro w-full sm:w-auto px-5 py-2 text-xs font-semibold flex items-center justify-center gap-2 shadow-sm flex-shrink-0">
                <i class="fa-solid fa-wand-magic-sparkles" id="audit-project-icon"></i>
                <span>Scan Project</span>
              </button>
            </div>

            <!-- Quick Presets & Recent History -->
            <div class="flex flex-wrap items-center gap-2 text-[11px] text-[#94A3B8] pt-1">
              <span class="text-[#475569] font-mono">Quick Presets:</span>
              <button onclick="setAndAuditProject('.')" class="btn-secondary-pro text-[11px] font-mono px-2 py-0.5 rounded">Current Workspace (.)</button>
              <div id="project-recent-chips" class="flex flex-wrap items-center gap-1.5"></div>
            </div>
          </div>

          <!-- Audit Results Container -->
          <div id="project-results-container" class="space-y-4 hidden">
            <!-- Header Card & Visual Readiness Scorecard -->
            <div id="project-header-card" class="card-pro p-5 sm:p-6 flex flex-col lg:flex-row lg:items-center justify-between gap-5">
              <div class="space-y-1.5 min-w-0">
                <div class="flex flex-wrap items-center gap-2">
                  <h3 class="text-lg font-bold text-[#F3F4F6] tracking-tight" id="rep-project-name">—</h3>
                  <div id="rep-detected-types" class="flex flex-wrap gap-1.5"></div>
                </div>
                <p class="text-xs font-mono text-[#94A3B8] truncate max-w-xl" id="rep-project-path">—</p>
              </div>

              <!-- Readiness Scorecard Gauge -->
              <div class="flex items-center gap-4 bg-[#08090C] p-3.5 rounded border border-[#1F2430] flex-shrink-0">
                <div class="text-center min-w-[65px]">
                  <div class="text-2xl font-bold font-mono" id="rep-score-pct">100%</div>
                  <div class="text-[9px] uppercase tracking-wider font-mono font-semibold text-[#475569]">Readiness</div>
                </div>
                <div class="w-32 hidden sm:block">
                  <div class="h-1.5 rounded-full bg-[#1F2430] overflow-hidden">
                    <div id="rep-score-bar" class="h-full bg-[#10B981] rounded-full transition-all duration-500" style="width: 100%"></div>
                  </div>
                  <div class="flex justify-between text-[10px] font-mono text-[#94A3B8] mt-1">
                    <span id="rep-satisfied-count">0 satisfied</span>
                    <span id="rep-missing-count">0 missing</span>
                  </div>
                </div>
                <div id="rep-status-badge" class="flex-shrink-0"></div>
              </div>
            </div>

            <!-- Requirements Checklist Table -->
            <div class="card-pro overflow-hidden shadow-xl">
              <div class="px-4 py-2.5 bg-[#08090C] border-b border-[#1F2430] flex items-center justify-between">
                <h4 class="text-xs font-mono font-semibold text-[#F3F4F6] uppercase tracking-wider flex items-center gap-2">
                  <i class="fa-solid fa-list-check text-[#10B981]"></i>
                  Prerequisites Checklist
                </h4>
              </div>
              <div class="overflow-x-auto">
                <table class="w-full text-left text-xs">
                  <thead class="bg-[#08090C]/60 text-[#94A3B8] uppercase tracking-wider text-[10px] border-b border-[#1F2430] font-mono font-semibold">
                    <tr>
                      <th class="py-2 px-3.5">Status</th>
                      <th class="py-2 px-3.5">Requirement</th>
                      <th class="py-2 px-3.5">Expected</th>
                      <th class="py-2 px-3.5">Detected</th>
                      <th class="py-2 px-3.5">Diagnostic Details</th>
                    </tr>
                  </thead>
                  <tbody id="project-checks-tbody" class="divide-y divide-[#1F2430] font-sans"></tbody>
                </table>
              </div>
            </div>

            <!-- Recommended Setup Actions -->
            <div id="project-actions-card" class="rounded-md p-4 space-y-3 hidden border border-[#F59E0B40] bg-[#F59E0B0A]">
              <div class="flex items-center justify-between gap-2 flex-wrap">
                <h4 class="text-xs font-semibold text-[#F59E0B] uppercase tracking-wider flex items-center gap-2 font-mono">
                  <i class="fa-solid fa-lightbulb"></i>
                  Recommended Setup Commands
                </h4>
                <button onclick="copyAllProjectActions()" class="btn-secondary-pro text-[#F59E0B] border-[#F59E0B40] px-2.5 py-1 text-xs font-medium flex items-center gap-1.5">
                  <i class="fa-regular fa-copy"></i>
                  <span>Copy All Fix Commands</span>
                </button>
              </div>
              <div id="project-actions-list" class="space-y-2"></div>
            </div>
          </div>
        </div>

        <!-- ==================== VIEW 4: SETTINGS & SEARCH ROOTS ==================== -->
        <div id="view-settings" class="space-y-5 hidden">
          <!-- Monitored Search Roots Card -->
          <div class="card-pro p-5 sm:p-6 space-y-4">
            <div class="flex items-center gap-3">
              <div class="w-8 h-8 rounded bg-[#10B9811A] text-[#10B981] border border-[#10B98140] flex items-center justify-center font-bold flex-shrink-0">
                <i class="fa-solid fa-folder-tree"></i>
              </div>
              <div>
                <h2 class="text-sm font-semibold text-[#F3F4F6]">Monitored Search Directories (Layer 4)</h2>
                <p class="text-xs text-[#94A3B8]">Configure root directories where DevToolkit recursively probes for SDKs by structural signature.</p>
              </div>
            </div>

            <div>
              <label class="block text-xs font-medium text-[#94A3B8] mb-1.5">Add Custom Root Directory</label>
              <div class="flex items-center gap-2">
                <div class="relative flex-1 flex items-center">
                  <div class="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none text-[#94A3B8] text-xs">
                    <i class="fa-regular fa-folder"></i>
                  </div>
                  <input type="text" id="settings-path-input" onkeydown="if(event.key==='Enter') submitSearchPath()" placeholder="e.g. D:\\Dev or /opt/custom_sdks" class="input-pro w-full pl-8 pr-3 py-1.5 text-xs text-[#F3F4F6] placeholder-[#475569] font-mono" />
                </div>
                <button onclick="browseSettingsFolder()" id="btn-browse-settings" class="btn-secondary-pro px-3.5 py-1.5 text-xs font-medium flex items-center gap-1.5 flex-shrink-0" title="Open Explorer to select folder">
                  <i class="fa-regular fa-folder-open text-[#06B6D4] text-xs"></i>
                  <span>Browse...</span>
                </button>
                <button onclick="submitSearchPath()" class="btn-primary-pro px-4 py-1.5 text-xs font-semibold flex items-center gap-1.5 flex-shrink-0">
                  <i class="fa-solid fa-plus"></i>
                  <span>Add Path</span>
                </button>
              </div>
              <div class="mt-2 flex items-center gap-2">
                <span class="text-[11px] text-[#475569] font-mono">Quick Suggestions:</span>
                <button onclick="fillSettingsPath('D:\\\\Dev')" class="btn-secondary-pro text-[11px] font-mono px-2 py-0.5 rounded">+ D:\Dev</button>
                <button onclick="fillSettingsPath('C:\\\\Dev')" class="btn-secondary-pro text-[11px] font-mono px-2 py-0.5 rounded">+ C:\Dev</button>
              </div>
            </div>

            <div>
              <h3 class="text-[10px] font-mono font-semibold text-[#475569] uppercase tracking-wider mb-2">Active Monitored Directories</h3>
              <div id="settings-paths-list" class="space-y-1.5 max-h-48 overflow-y-auto custom-scrollbar"></div>
            </div>

            <div class="p-3.5 rounded bg-[#06B6D410] border border-[#06B6D430] text-xs text-[#06B6D4] space-y-1">
              <div class="font-semibold flex items-center gap-1.5"><i class="fa-solid fa-shield-halved"></i> Generalized Content Signature Discovery</div>
              <p class="text-[#94A3B8] text-[11px]">DevToolkit avoids hardcoded paths. When you add a root folder, it recursively detects binary signatures (e.g. <code>platform-tools/adb.exe</code> or <code>bin/javac.exe</code>) regardless of naming conventions.</p>
            </div>
          </div>

          <!-- Workstation System Specs Card -->
          <div class="card-pro p-5 sm:p-6 space-y-3">
            <h3 class="text-sm font-semibold text-[#F3F4F6] flex items-center gap-2">
              <i class="fa-solid fa-microchip text-[#94A3B8]"></i>
              Workstation System Overview
            </h3>
            <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-2.5 text-xs">
              <div class="p-3 rounded bg-[#08090C] border border-[#1F2430]">
                <div class="text-[#475569] font-mono text-[10px] uppercase">Operating System</div>
                <div class="font-medium text-[#F3F4F6] mt-1" id="sys-os">—</div>
              </div>
              <div class="p-3 rounded bg-[#08090C] border border-[#1F2430]">
                <div class="text-[#475569] font-mono text-[10px] uppercase">Architecture</div>
                <div class="font-medium text-[#F3F4F6] mt-1" id="sys-arch">—</div>
              </div>
              <div class="p-3 rounded bg-[#08090C] border border-[#1F2430]">
                <div class="text-[#475569] font-mono text-[10px] uppercase">Host Machine</div>
                <div class="font-mono text-[#F3F4F6] mt-1 truncate" id="sys-host">—</div>
              </div>
              <div class="p-3 rounded bg-[#08090C] border border-[#1F2430]">
                <div class="text-[#475569] font-mono text-[10px] uppercase">Python Runtime</div>
                <div class="font-mono text-[#10B981] mt-1 truncate" id="sys-python">—</div>
              </div>
            </div>
          </div>
        </div>

      </main>

      <!-- PERSISTENT BOTTOM STATUS BAR -->
      <footer class="h-8 px-4 sm:px-5 bg-[#08090C] border-t border-[#1F2430] text-[11px] text-[#94A3B8] flex items-center justify-between flex-shrink-0 z-20 select-none font-mono">
        <div class="flex items-center gap-2 sm:gap-2.5 truncate">
          <span class="flex items-center gap-1.5 truncate">
            <span class="w-1.5 h-1.5 rounded-full bg-[#10B981] shadow-[0_0_6px_#10B981] flex-shrink-0"></span>
            Environment Watcher: <strong class="text-[#F3F4F6] font-medium truncate">Active</strong>
          </span>
          <span class="text-[#2E3446] hidden sm:inline">|</span>
          <span class="hidden sm:inline">PATH Entries: <strong class="text-[#F3F4F6]" id="status-path-count">25</strong></span>
          <span class="text-[#2E3446] hidden md:inline">|</span>
          <span class="hidden md:inline">RAM Footprint: <strong class="text-[#F3F4F6]" id="status-ram-count">114 MB</strong></span>
        </div>

        <div class="flex items-center gap-2 sm:gap-3 flex-shrink-0 font-sans">
          <button onclick="refreshActiveTab()" class="hover:text-[#F3F4F6] transition flex items-center gap-1 text-[#94A3B8]">
            <kbd class="kbd-pro">R</kbd>
            <span class="hidden sm:inline text-[11px]">Rescan</span>
          </button>
          <button onclick="toggleHelpModal()" class="hover:text-[#F3F4F6] transition flex items-center gap-1 text-[#94A3B8]">
            <kbd class="kbd-pro">?</kbd>
            <span class="text-[11px]">Help</span>
          </button>
        </div>
      </footer>

    </div>
  </div>

  <!-- SLIDE-OVER DETAIL DRAWER (INSPECTOR) -->
  <div id="inspector-drawer" class="fixed inset-0 z-50 overflow-hidden hidden" aria-labelledby="slide-over-title" role="dialog" aria-modal="true">
    <div id="inspector-backdrop" onclick="closeInspectorDrawer()" class="fixed inset-0 modal-backdrop transition-opacity duration-300 opacity-0"></div>
    <div class="fixed inset-y-0 right-0 max-w-full flex pl-6 sm:pl-10 pointer-events-none">
      <div id="inspector-panel" class="w-screen max-w-xl bg-[#0E1015] border-l border-[#1F2430] shadow-2xl flex flex-col drawer-panel pointer-events-auto z-10">
        <!-- Content dynamically rendered by renderInspectorDrawer() -->
        <div id="inspector-content" class="flex-1 flex flex-col overflow-hidden"></div>
      </div>
    </div>
  </div>

  <!-- MODAL 1: TERMINATE PROCESS ON PORT -->
  <div id="kill-modal" class="fixed inset-0 modal-backdrop z-50 flex items-center justify-center p-4 hidden">
    <div class="modal-pro max-w-md w-full p-5 space-y-4">
      <div class="flex items-center gap-3 text-[#EF4444]">
        <div class="w-9 h-9 rounded bg-[#EF44441A] border border-[#EF444440] flex items-center justify-center font-bold text-base flex-shrink-0">
          <i class="fa-solid fa-triangle-exclamation"></i>
        </div>
        <div>
          <h3 class="text-sm font-semibold text-[#F3F4F6]">Terminate Process on Port</h3>
          <p class="text-xs text-[#94A3B8]">This action will immediately stop the occupying process.</p>
        </div>
      </div>

      <div class="bg-[#08090C] p-3 rounded border border-[#1F2430] text-xs space-y-1.5 font-mono">
        <div class="flex justify-between"><span class="text-[#475569]">Port:</span> <span class="text-[#06B6D4] font-bold" id="modal-kill-port">:—</span></div>
        <div class="flex justify-between"><span class="text-[#475569]">Process:</span> <span class="text-[#F3F4F6]" id="modal-kill-name">—</span></div>
        <div class="flex justify-between"><span class="text-[#475569]">PID:</span> <span class="text-[#F59E0B]" id="modal-kill-pid">—</span></div>
      </div>

      <div id="modal-kill-warning" class="hidden p-3 rounded bg-[#EF444410] border border-[#EF444430] text-[#EF4444] text-xs space-y-1.5">
        <div class="font-semibold flex items-center gap-1.5"><i class="fa-solid fa-triangle-exclamation"></i> Operating System Warning</div>
        <p class="text-[11px] text-[#94A3B8]">This process is classified as system-critical. Force terminating it may disrupt system services or cause a reboot.</p>
        <label class="flex items-center gap-2 cursor-pointer pt-1">
          <input type="checkbox" id="modal-force-checkbox" class="rounded-[3px] border-[#EF4444] text-[#EF4444] focus:ring-0 w-3.5 h-3.5 bg-[#08090C]" />
          <span class="text-[11px] font-semibold text-[#EF4444]">I understand the risk, force terminate</span>
        </label>
      </div>

      <div class="flex justify-end gap-2 pt-2 border-t border-[#1F2430]">
        <button onclick="closeKillModal()" class="btn-secondary-pro px-3.5 py-1.5 text-xs font-medium">Cancel</button>
        <button onclick="submitKillPort()" id="btn-confirm-kill" class="btn-destructive px-3.5 py-1.5 text-xs flex items-center gap-1.5">
          <i class="fa-solid fa-power-off text-xs"></i>
          <span>Kill Process</span>
        </button>
      </div>
    </div>
  </div>

  <!-- MODAL 2: KEYBOARD SHORTCUTS & HELP -->
  <div id="help-modal" class="fixed inset-0 modal-backdrop z-50 flex items-center justify-center p-4 hidden">
    <div class="modal-pro max-w-lg w-full p-5 space-y-4">
      <div class="flex items-center justify-between border-b border-[#1F2430] pb-3">
        <div class="flex items-center gap-2.5">
          <div class="w-8 h-8 rounded bg-[#10B9811A] text-[#10B981] border border-[#10B98140] flex items-center justify-center font-bold">
            <i class="fa-solid fa-keyboard"></i>
          </div>
          <div>
            <h3 class="text-sm font-semibold text-[#F3F4F6]">DevToolkit Shortcuts & Navigation</h3>
            <p class="text-[11px] text-[#94A3B8]">Native desktop keyboard accelerators</p>
          </div>
        </div>
        <button onclick="toggleHelpModal()" class="text-[#94A3B8] hover:text-[#F3F4F6] transition p-1"><i class="fa-solid fa-xmark text-sm"></i></button>
      </div>

      <div class="space-y-1.5 text-xs">
        <div class="flex items-center justify-between p-2 rounded bg-[#08090C] border border-[#1F2430]">
          <span class="text-[#F3F4F6]">Focus Global Search</span>
          <kbd class="kbd-pro">Ctrl + K</kbd>
        </div>
        <div class="flex items-center justify-between p-2 rounded bg-[#08090C] border border-[#1F2430]">
          <span class="text-[#F3F4F6]">Rescan Environment & Sockets</span>
          <kbd class="kbd-pro">R</kbd>
        </div>
        <div class="flex items-center justify-between p-2 rounded bg-[#08090C] border border-[#1F2430]">
          <span class="text-[#F3F4F6]">Switch to Environment Tab</span>
          <kbd class="kbd-pro">1</kbd>
        </div>
        <div class="flex items-center justify-between p-2 rounded bg-[#08090C] border border-[#1F2430]">
          <span class="text-[#F3F4F6]">Switch to Port Manager Tab</span>
          <kbd class="kbd-pro">2</kbd>
        </div>
        <div class="flex items-center justify-between p-2 rounded bg-[#08090C] border border-[#1F2430]">
          <span class="text-[#F3F4F6]">Switch to Project Auditor Tab</span>
          <kbd class="kbd-pro">3</kbd>
        </div>
        <div class="flex items-center justify-between p-2 rounded bg-[#08090C] border border-[#1F2430]">
          <span class="text-[#F3F4F6]">Switch to Settings Tab</span>
          <kbd class="kbd-pro">4</kbd>
        </div>
        <div class="flex items-center justify-between p-2 rounded bg-[#08090C] border border-[#1F2430]">
          <span class="text-[#F3F4F6]">Close Modal / Blur Search</span>
          <kbd class="kbd-pro">Esc</kbd>
        </div>
      </div>

      <!-- Workstation Telemetry -->
      <div class="p-3 rounded bg-[#08090C] border border-[#1F2430] space-y-1.5 text-xs">
        <div class="text-[10px] font-mono font-semibold text-[#475569] tracking-wider uppercase flex items-center gap-1.5">
          <i class="fa-solid fa-server text-[#06B6D4]"></i> Workstation Telemetry
        </div>
        <div class="grid grid-cols-2 gap-2 text-[11px] font-mono">
          <div><span class="text-[#475569]">OS:</span> <span id="sys-os" class="text-[#F3F4F6]">...</span></div>
          <div><span class="text-[#475569]">Arch:</span> <span id="sys-arch" class="text-[#F3F4F6]">...</span></div>
          <div><span class="text-[#475569]">Host:</span> <span id="sys-host" class="text-[#F3F4F6]">...</span></div>
          <div><span class="text-[#475569]">Python:</span> <span id="sys-python" class="text-[#10B981]">...</span></div>
        </div>
      </div>

      <div class="pt-2 border-t border-[#1F2430] flex justify-end">
        <button onclick="toggleHelpModal()" class="btn-primary-pro px-4 py-1.5 text-xs font-semibold">Got it</button>
      </div>
    </div>
  </div>

  <!-- TOAST NOTIFICATION -->
  <div id="toast" class="fixed bottom-10 right-6 px-3.5 py-2 rounded bg-[#0E1015] border border-[#10B981] text-[#10B981] text-xs font-mono shadow-2xl transform translate-y-20 opacity-0 transition duration-300 flex items-center gap-2 z-50">
    <i class="fa-solid fa-check" id="toast-icon"></i> <span id="toast-msg">Success</span>
  </div>

  <!-- CLIENT-SIDE SCRIPT LOGIC -->
  <script>
    let activeTab = 'env';
    let allReports = [];
    let allPorts = [];
    let currentCategory = 'all';
    try {
      const savedCat = localStorage.getItem('devtoolkit_last_category');
      if (savedCat) currentCategory = savedCat;
    } catch (e) {}
    let currentStatusFilter = null; // null | 'all' | 'installed' | 'healthy' | 'warning' | 'error' | 'not_found'
    let currentLayout = 'grid';
    let currentSort = 'severity';
    let currentPortView = 'flat'; // 'flat' | 'grouped'
    let currentConfig = { search_paths: [] };
    let pendingKill = null;
    let lastScanTime = Date.now();
    let activeDrawerToolId = null;
    let currentProjectActions = [];

    function showToast(msg, isError = false) {
      const toast = document.getElementById('toast');
      const icon = document.getElementById('toast-icon');
      document.getElementById('toast-msg').innerText = msg;
      if (isError) {
        toast.className = 'fixed bottom-10 right-6 px-3.5 py-2 rounded bg-[#0E1015] border border-[#EF4444] text-[#EF4444] text-xs font-mono shadow-2xl transform translate-y-0 opacity-100 transition duration-200 flex items-center gap-2 z-50';
        icon.className = 'fa-solid fa-triangle-exclamation text-xs';
      } else {
        toast.className = 'fixed bottom-10 right-6 px-3.5 py-2 rounded bg-[#0E1015] border border-[#10B981] text-[#10B981] text-xs font-mono shadow-2xl transform translate-y-0 opacity-100 transition duration-200 flex items-center gap-2 z-50';
        icon.className = 'fa-solid fa-check text-xs';
      }
      setTimeout(() => {
        toast.className = 'fixed bottom-10 right-6 px-3.5 py-2 rounded bg-[#0E1015] border border-[#10B981] text-[#10B981] text-xs font-mono shadow-2xl transform translate-y-20 opacity-0 transition duration-200 flex items-center gap-2 z-50';
      }, 2800);
    }

    function copyToClipboard(text, label) {
      if (!text) return;
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
          showToast('Opened in File Explorer');
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
        if (t === tab) {
          btn.className = 'w-full flex items-center justify-between px-2.5 py-2 rounded text-xs font-medium transition nav-active';
          view.classList.remove('hidden');
        } else {
          btn.className = 'w-full flex items-center justify-between px-2.5 py-2 rounded text-xs font-medium transition nav-inactive';
          view.classList.add('hidden');
        }
      });

      // Show/hide top search bar & rescan button based on active tab (only visible on Environment tab)
      const searchWrapper = document.getElementById('top-search-wrapper');
      const rescanBtn = document.getElementById('rescan-btn');
      const exportWrapper = document.getElementById('export-dropdown-wrapper');
      if (tab === 'env') {
        if (searchWrapper) searchWrapper.classList.remove('hidden');
        if (rescanBtn) rescanBtn.classList.remove('hidden');
        if (exportWrapper) exportWrapper.classList.remove('hidden');
      } else {
        if (searchWrapper) searchWrapper.classList.add('hidden');
        if (rescanBtn) rescanBtn.classList.add('hidden');
        if (exportWrapper) exportWrapper.classList.add('hidden');
      }

      // Update Top Breadcrumb
      const bc = document.getElementById('top-breadcrumb');
      if (tab === 'env') {
        bc.innerHTML = '<span class="w-1.5 h-1.5 rounded-full bg-[#10B981] shadow-[0_0_6px_#10B981] flex-shrink-0"></span> Environment & Diagnostics';
      } else if (tab === 'ports') {
        bc.innerHTML = '<span class="w-1.5 h-1.5 rounded-full bg-[#06B6D4] shadow-[0_0_6px_#06B6D4] flex-shrink-0"></span> Port Manager & Sockets';
        fetchPorts();
      } else if (tab === 'project') {
        bc.innerHTML = '<span class="w-1.5 h-1.5 rounded-full bg-[#8B5CF6] shadow-[0_0_6px_#8B5CF6] flex-shrink-0"></span> Project Workstation Auditor';
        renderRecentProjects();
      } else if (tab === 'settings') {
        bc.innerHTML = '<span class="w-1.5 h-1.5 rounded-full bg-[#94A3B8] flex-shrink-0"></span> Preferences & Search Roots';
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

    // ==================== EXPORT REPORT LOGIC ====================
    function toggleExportMenu() {
      const menu = document.getElementById('export-menu');
      if (menu) menu.classList.toggle('hidden');
    }

    function closeExportMenu() {
      const menu = document.getElementById('export-menu');
      if (menu && !menu.classList.contains('hidden')) menu.classList.add('hidden');
    }

    document.addEventListener('click', (e) => {
      const wrapper = document.getElementById('export-dropdown-wrapper');
      if (wrapper && !wrapper.contains(e.target)) {
        closeExportMenu();
      }
    });

    function exportReport(type) {
      closeExportMenu();
      if (allReports.length === 0) {
        showToast('No audit data available to export', true);
        return;
      }

      if (type === 'json') {
        const payload = {
          generated_at: new Date().toISOString(),
          total_tools: allReports.length,
          reports: allReports
        };
        copyToClipboard(JSON.stringify(payload, null, 2), 'JSON report');
        return;
      }

      // Markdown Format
      const installed = allReports.filter(r => r.installed).length;
      const healthy = allReports.filter(r => r.status === 'healthy').length;
      const warning = allReports.filter(r => r.status === 'warning').length;

      let md = `# DevToolkit Workstation Environment Audit\n\n`;
      md += `- **Generated At**: ${new Date().toLocaleString()}\n`;
      md += `- **Tools Audited**: ${allReports.length} | **Installed**: ${installed} | **Healthy**: ${healthy} | **Action Needed**: ${warning}\n\n`;
      md += `| Tool | Categories | Status | Version | Root / Home Path | Binary Executable |\n`;
      md += `| :--- | :--- | :--- | :--- | :--- | :--- |\n`;

      allReports.forEach(r => {
        const cats = (r.categories && r.categories.length > 0) ? r.categories.join(', ') : r.category;
        const stat = r.status.toUpperCase();
        const ver = r.version ? ('v' + r.version) : (r.installed ? 'Installed' : 'Not Detected');
        const home = r.home_path ? `\`${r.home_path}\`` : '—';
        const bin = r.binary_path ? `\`${r.binary_path}\`` : '—';
        md += `| **${r.name}** | ${cats} | ${stat} | ${ver} | ${home} | ${bin} |\n`;
      });

      const warnings = allReports.filter(r => r.diagnostics && r.diagnostics.length > 0);
      if (warnings.length > 0) {
        md += `\n## Diagnostics & Action Items\n\n`;
        warnings.forEach(r => {
          md += `### ${r.name}\n`;
          r.diagnostics.forEach(d => {
            md += `- **Issue**: ${d.message}\n`;
            if (d.suggested_fix) {
              md += `  - **Suggested Fix**: \`${d.suggested_fix}\`\n`;
            }
          });
          md += `\n`;
        });
      }

      if (type === 'md') {
        copyToClipboard(md, 'Markdown report');
      } else if (type === 'download') {
        const blob = new Blob([md], { type: 'text/markdown' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `devtoolkit-audit-${new Date().toISOString().slice(0, 10)}.md`;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
        showToast('Downloaded audit report as Markdown');
      }
    }

    // ==================== SLIDE-OVER INSPECTOR DRAWER ====================
    function openInspectorDrawer(toolId) {
      activeDrawerToolId = toolId;
      renderInspectorDrawer(toolId);
      const drawer = document.getElementById('inspector-drawer');
      const backdrop = document.getElementById('inspector-backdrop');
      const panel = document.getElementById('inspector-panel');

      drawer.classList.remove('hidden');
      setTimeout(() => {
        backdrop.classList.remove('opacity-0');
        backdrop.classList.add('opacity-100');
        panel.classList.add('open');
      }, 10);
    }

    function closeInspectorDrawer() {
      const backdrop = document.getElementById('inspector-backdrop');
      const panel = document.getElementById('inspector-panel');
      const drawer = document.getElementById('inspector-drawer');

      backdrop.classList.remove('opacity-100');
      backdrop.classList.add('opacity-0');
      panel.classList.remove('open');

      setTimeout(() => {
        drawer.classList.add('hidden');
        activeDrawerToolId = null;
      }, 280);
    }

    function renderInspectorDrawer(toolId) {
      const container = document.getElementById('inspector-content');
      const r = allReports.find(x => x.id === toolId);
      if (!r) {
        container.innerHTML = '<div class="p-6 text-[#94A3B8]">Tool details not found.</div>';
        return;
      }
      if (r.scanning) {
        container.innerHTML = `
          <div class="p-8 text-center space-y-4">
            <div class="w-10 h-10 mx-auto rounded bg-[#06B6D41A] border border-[#06B6D440] flex items-center justify-center text-[#06B6D4] text-lg">
              <i class="fa-solid fa-circle-notch fa-spin"></i>
            </div>
            <div>
              <h3 class="text-[#F3F4F6] font-semibold text-sm">Inspecting ${r.name}...</h3>
              <p class="text-[#94A3B8] text-xs mt-1">Environment inspection is currently running for this tool.</p>
            </div>
          </div>
        `;
        return;
      }

      const toolCats = (r.categories && r.categories.length > 0) ? r.categories : [r.category];
      const categoriesHtml = toolCats.map(c => 
        `<span class="text-[10px] text-[#94A3B8] uppercase tracking-wider font-mono font-medium px-2 py-0.5 bg-[#141721] rounded border border-[#1F2430]">${c}</span>`
      ).join('');

      const cleanHome = (r.home_path || '').replace(/"/g, '&quot;');
      const cleanBin = (r.binary_path || '').replace(/"/g, '&quot;');

      // Diagnostics HTML
      let diagHtml = '';
      if (r.diagnostics && r.diagnostics.length > 0) {
        diagHtml = r.diagnostics.map(d => {
          const cleanFix = (d.suggested_fix || '').replace(/"/g, '&quot;');
          return `
            <div class="p-3.5 rounded bg-[#F59E0B0D] border border-[#F59E0B33] text-[#F59E0B] text-xs space-y-2.5">
              <div class="flex items-start gap-2 font-medium leading-relaxed">
                <i class="fa-solid fa-triangle-exclamation text-[#F59E0B] mt-0.5 text-xs flex-shrink-0"></i>
                <span>${d.message}</span>
              </div>
              ${d.suggested_fix ? `
                <div class="bg-[#08090C] p-2.5 rounded border border-[#1F2430] space-y-2">
                  <div class="text-[10px] uppercase font-mono tracking-wider font-semibold text-[#F59E0B]">Remediation Command:</div>
                  <div class="flex items-center justify-between gap-2 font-mono text-[11px] text-[#F3F4F6] min-w-0">
                    <code class="truncate">${d.suggested_fix}</code>
                    <div class="flex items-center gap-1.5 flex-shrink-0">
                      <button onclick="copyToClipboard(this.dataset.cmd, 'command')" data-cmd="${cleanFix}" class="btn-secondary-pro px-2 py-0.5 text-[10px] font-mono flex items-center gap-1">
                        <i class="fa-regular fa-copy"></i> Copy
                      </button>
                      <button onclick="applyFix(this.dataset.cmd)" data-cmd="${cleanFix}" class="btn-primary-pro px-2.5 py-0.5 text-[10px] font-semibold flex items-center gap-1">
                        <i class="fa-solid fa-wand-magic-sparkles"></i> Apply
                      </button>
                    </div>
                  </div>
                </div>
              ` : ''}
            </div>
          `;
        }).join('');
      } else if (r.status === 'healthy') {
        diagHtml = `
          <div class="p-3 rounded bg-[#10B9810D] border border-[#10B98133] text-[#10B981] text-xs flex items-center gap-2.5">
            <i class="fa-solid fa-circle-check text-sm text-[#10B981] flex-shrink-0"></i>
            <div>
              <div class="font-semibold">Workstation Ready</div>
              <div class="text-[11px] text-[#94A3B8] mt-0.5">All path registrations and core companions are operating optimally.</div>
            </div>
          </div>
        `;
      } else {
        diagHtml = `
          <div class="p-3 rounded bg-[#141721] border border-[#1F2430] text-[#94A3B8] text-xs flex items-center gap-2.5">
            <i class="fa-solid fa-circle-info text-sm text-[#475569] flex-shrink-0"></i>
            <div>
              <div class="font-semibold text-[#F3F4F6]">Tool Not Detected</div>
              <div class="text-[11px] text-[#94A3B8] mt-0.5">This tool was not detected in system PATH, registry, or custom search roots.</div>
            </div>
          </div>
        `;
      }

      // Companions HTML
      let companionsHtml = '';
      if (r.companions && r.companions.length > 0) {
        companionsHtml = `
          <div class="space-y-2">
            <div class="text-[10px] font-mono font-semibold text-[#475569] uppercase tracking-wider flex items-center justify-between">
              <span>Ecosystem Companions</span>
              <span class="font-mono text-[#94A3B8]">${r.companions.filter(c => c.installed).length}/${r.companions.length} Available</span>
            </div>
            <div class="grid grid-cols-1 sm:grid-cols-2 gap-2">
              ${r.companions.map(c => `
                <div class="p-2 rounded bg-[#08090C] border border-[#1F2430] flex items-center justify-between text-xs">
                  <div class="flex items-center gap-2 min-w-0">
                    <span class="w-4 h-4 rounded flex items-center justify-center text-[10px] ${c.installed ? 'bg-[#10B9811A] text-[#10B981]' : 'bg-[#141721] text-[#475569]'}">
                      <i class="fa-solid ${c.installed ? 'fa-check' : 'fa-xmark'}"></i>
                    </span>
                    <span class="font-medium text-[#F3F4F6] truncate">${c.name}</span>
                  </div>
                  <span class="font-mono text-[10px] text-[#94A3B8] flex-shrink-0">${c.version ? 'v' + c.version : (c.installed ? 'detected' : 'missing')}</span>
                </div>
              `).join('')}
            </div>
          </div>
        `;
      }

      container.innerHTML = `
        <!-- Drawer Header -->
        <div class="p-4 sm:p-5 border-b border-[#1F2430] flex items-start justify-between gap-3 bg-[#08090C]">
          <div class="flex items-center gap-3 min-w-0">
            <div class="w-10 h-10 rounded bg-[#141721] border border-[#1F2430] flex items-center justify-center text-xl flex-shrink-0 shadow">
              ${getToolIcon(r.id, r.category)}
            </div>
            <div class="min-w-0">
              <h2 class="text-base font-semibold text-[#F3F4F6] tracking-tight truncate">${r.name}</h2>
              <div class="flex items-center gap-2 mt-0.5">
                <span class="text-xs font-mono font-medium text-[#06B6D4]">${r.version ? 'v' + r.version : (r.installed ? 'Installed' : 'Not Detected')}</span>
                <span class="text-[#2E3446]">•</span>
                <div class="flex items-center gap-1">${categoriesHtml}</div>
              </div>
            </div>
          </div>
          <div class="flex items-center gap-2 flex-shrink-0">
            ${getBadge(r.status)}
            <button onclick="closeInspectorDrawer()" class="p-1.5 rounded text-[#94A3B8] hover:text-[#F3F4F6] hover:bg-[#141721] transition" title="Close Drawer (Esc)">
              <i class="fa-solid fa-xmark text-sm"></i>
            </button>
          </div>
        </div>

        <!-- Drawer Body -->
        <div class="flex-1 overflow-y-auto p-4 sm:p-5 space-y-5 custom-scrollbar font-sans">
          <!-- Diagnostics / Health Status Card -->
          <div class="space-y-1.5">
            <div class="text-[10px] font-mono font-semibold text-[#475569] uppercase tracking-wider">Health Status & Action Items</div>
            ${diagHtml}
          </div>

          <!-- Installation & Binary Locations -->
          <div class="space-y-2.5">
            <div class="text-[10px] font-mono font-semibold text-[#475569] uppercase tracking-wider">Paths & Filesystem Locations</div>
            
            <!-- Root Path -->
            <div class="bg-[#0E1015] p-3 rounded border border-[#1F2430] space-y-1.5">
              <div class="flex items-center justify-between text-[11px] text-[#94A3B8]">
                <span class="font-mono font-medium text-[#06B6D4] uppercase tracking-wider text-[10px]"><i class="fa-solid fa-folder text-xs mr-1"></i> Root / Home Directory</span>
                <div class="flex items-center gap-1">
                  ${r.home_path ? `
                    <button onclick="copyToClipboard('${cleanHome}', 'root path')" class="btn-secondary-pro px-2 py-0.5 text-[10px] flex items-center gap-1">
                      <i class="fa-regular fa-copy text-[9px]"></i> Copy
                    </button>
                    <button onclick="openFolder('${cleanHome}')" class="btn-secondary-pro px-2 py-0.5 text-[10px] flex items-center gap-1 hover:text-[#06B6D4]">
                      <i class="fa-regular fa-folder-open text-[9px]"></i> Open
                    </button>
                  ` : ''}
                </div>
              </div>
              <div class="font-mono text-xs text-[#F3F4F6] break-all select-text bg-[#08090C] p-2 rounded border border-[#1F2430]">
                ${r.home_path || '<span class="text-[#475569] italic">Not detected or not applicable</span>'}
              </div>
            </div>

            <!-- Binary Path -->
            <div class="bg-[#0E1015] p-3 rounded border border-[#1F2430] space-y-1.5">
              <div class="flex items-center justify-between text-[11px] text-[#94A3B8]">
                <span class="font-mono font-medium text-[#10B981] uppercase tracking-wider text-[10px]"><i class="fa-solid fa-terminal text-xs mr-1"></i> Primary Executable Binary</span>
                <div class="flex items-center gap-1">
                  ${r.binary_path ? `
                    <button onclick="copyToClipboard('${cleanBin}', 'binary path')" class="btn-secondary-pro px-2 py-0.5 text-[10px] flex items-center gap-1">
                      <i class="fa-regular fa-copy text-[9px]"></i> Copy
                    </button>
                    <button onclick="openFolder('${cleanBin}')" class="btn-secondary-pro px-2 py-0.5 text-[10px] flex items-center gap-1 hover:text-[#10B981]">
                      <i class="fa-regular fa-folder-open text-[9px]"></i> Open
                    </button>
                  ` : ''}
                </div>
              </div>
              <div class="font-mono text-xs text-[#F3F4F6] break-all select-text bg-[#08090C] p-2 rounded border border-[#1F2430]">
                ${r.binary_path || '<span class="text-[#475569] italic">Not detected in system PATH</span>'}
              </div>
            </div>
          </div>

          <!-- Companions -->
          ${companionsHtml}

          <!-- Metadata & Origin -->
          <div class="p-3.5 rounded bg-[#0E1015] border border-[#1F2430] space-y-1.5 text-xs">
            <div class="text-[10px] font-mono font-semibold text-[#475569] uppercase tracking-wider">Inspector Information</div>
            <div class="text-[#94A3B8] text-[11px] leading-relaxed">${r.description || 'Monitored development tool inspector in workstation environment suite.'}</div>
            <div class="pt-1.5 flex flex-wrap items-center gap-3 text-[11px] text-[#475569] font-mono">
              <span>Tool ID: <strong class="text-[#F3F4F6]">${r.id}</strong></span>
              <span>•</span>
              <span>Installed: <strong class="${r.installed ? 'text-[#10B981]' : 'text-[#94A3B8]'}">${r.installed ? 'Yes' : 'No'}</strong></span>
            </div>
          </div>

          <!-- Collapsible Raw JSON Data -->
          <details class="text-xs bg-[#0E1015] rounded border border-[#1F2430] p-2.5 group">
            <summary class="font-medium text-[#94A3B8] hover:text-[#F3F4F6] cursor-pointer flex items-center justify-between select-none">
              <span>View Raw Report (JSON)</span>
              <span class="text-[10px] text-[#06B6D4] group-open:rotate-180 transition-transform"><i class="fa-solid fa-chevron-down"></i></span>
            </summary>
            <div class="mt-2.5 space-y-2">
              <div class="flex justify-end">
                <button onclick="copyToClipboard(JSON.stringify(allReports.find(x => x.id === '${r.id}'), null, 2), 'raw JSON')" class="btn-secondary-pro px-2 py-0.5 text-[10px] font-mono">
                  Copy JSON
                </button>
              </div>
              <pre class="bg-[#08090C] p-2.5 rounded border border-[#1F2430] font-mono text-[10px] text-[#94A3B8] overflow-x-auto custom-scrollbar select-text">${JSON.stringify(r, null, 2)}</pre>
            </div>
          </details>
        </div>
      `;
    }

    // ==================== TAB 1: ENVIRONMENT & AUDITING ====================
    const DOMAIN_CATEGORIES = [
      { id: 'all', label: 'All', icon: 'fa-cubes' },
      { id: 'runtime', label: 'Runtimes', icon: 'fa-terminal', match: ['runtime', 'framework', 'language'] },
      { id: 'ide', label: 'IDEs & Editors', icon: 'fa-code', match: ['ide', 'editor'] },
      { id: 'build', label: 'Build & Tools', icon: 'fa-screwdriver-wrench', match: ['build', 'tools', 'compiler'] },
      { id: 'vcs', label: 'VCS & Git', icon: 'fa-code-branch', match: ['vcs', 'scm', 'cli'] },
      { id: 'mobile', label: 'Mobile & SDKs', icon: 'fa-mobile-screen', match: ['mobile', 'sdk'] },
      { id: 'container', label: 'Cloud & Containers', icon: 'fa-cloud', match: ['container', 'devops', 'cloud', 'iac'] },
      { id: 'database', label: 'Databases', icon: 'fa-database', match: ['database', 'cache', 'sql'] },
      { id: 'ai', label: 'AI & ML', icon: 'fa-brain', match: ['ai', 'ml', 'hardware'] },
    ];

    function getToolIcon(id, category) {
      if (id === 'docker') return '<i class="fa-brands fa-docker text-[#06B6D4]"></i>';
      if (id === 'android_studio') return '<i class="fa-brands fa-android text-[#10B981]"></i>';
      if (id === 'android') return '<i class="fa-solid fa-mobile-screen-button text-[#F59E0B]"></i>';
      if (id === 'node') return '<i class="fa-brands fa-node-js text-[#10B981]"></i>';
      if (id === 'git') return '<i class="fa-brands fa-git-alt text-[#F59E0B]"></i>';
      if (id === 'python') return '<i class="fa-brands fa-python text-[#F59E0B]"></i>';
      if (id === 'java') return '<i class="fa-brands fa-java text-[#EF4444]"></i>';
      if (id === 'flutter') return '<i class="fa-solid fa-feather-pointed text-[#06B6D4]"></i>';
      if (id === 'golang') return '<i class="fa-brands fa-golang text-[#06B6D4]"></i>';
      if (id === 'rust') return '<i class="fa-brands fa-rust text-[#F59E0B]"></i>';
      if (id === 'vscode') return '<i class="fa-solid fa-code text-[#06B6D4]"></i>';
      if (id === 'dotnet') return '<i class="fa-brands fa-microsoft text-[#8B5CF6]"></i>';
      if (id === 'bun') return '<i class="fa-solid fa-bread-slice text-[#F59E0B]"></i>';
      if (id === 'gh') return '<i class="fa-brands fa-github text-[#F3F4F6]"></i>';
      if (id === 'cmake') return '<i class="fa-solid fa-screwdriver-wrench text-[#EF4444]"></i>';
      if (id === 'ollama') return '<i class="fa-solid fa-brain text-[#8B5CF6]"></i>';
      if (id === 'kubectl') return '<i class="fa-solid fa-dharmachakra text-[#06B6D4]"></i>';
      if (id === 'terraform') return '<i class="fa-solid fa-layer-group text-[#8B5CF6]"></i>';
      if (id === 'c_compiler') return '<i class="fa-solid fa-c text-[#06B6D4]"></i>';
      if (id === 'php') return '<i class="fa-brands fa-php text-[#8B5CF6]"></i>';
      if (id === 'cuda') return '<i class="fa-solid fa-microchip text-[#10B981]"></i>';
      if (id === 'sqlite') return '<i class="fa-solid fa-database text-[#06B6D4]"></i>';
      if (category === 'runtime') return '<i class="fa-solid fa-terminal text-[#06B6D4]"></i>';
      if (category === 'ide') return '<i class="fa-solid fa-code text-[#8B5CF6]"></i>';
      if (category === 'build') return '<i class="fa-solid fa-screwdriver-wrench text-[#F59E0B]"></i>';
      if (category === 'ai') return '<i class="fa-solid fa-brain text-[#8B5CF6]"></i>';
      if (category === 'database') return '<i class="fa-solid fa-database text-[#06B6D4]"></i>';
      if (category === 'cloud') return '<i class="fa-solid fa-cloud text-[#06B6D4]"></i>';
      return '<i class="fa-solid fa-cube text-[#94A3B8]"></i>';
    }

    function getBadge(status) {
      if (status === 'scanning') {
        return '<span class="inline-flex items-center gap-1.5 px-2 py-0.5 rounded text-[10px] font-mono font-semibold bg-[#06B6D41A] text-[#06B6D4] border border-[#06B6D440] whitespace-nowrap animate-pulse"><i class="fa-solid fa-circle-notch fa-spin text-[9px]"></i> Scanning</span>';
      }
      if (status === 'healthy') {
        return '<span class="inline-flex items-center gap-1.5 px-2 py-0.5 rounded text-[10px] font-mono font-semibold bg-[#10B9811A] text-[#10B981] border border-[#10B98140] whitespace-nowrap"><span class="w-1.5 h-1.5 rounded-full bg-[#10B981] shadow-[0_0_6px_#10B981]"></span> Healthy</span>';
      }
      if (status === 'warning') {
        return '<span class="inline-flex items-center gap-1.5 px-2 py-0.5 rounded text-[10px] font-mono font-semibold bg-[#F59E0B1A] text-[#F59E0B] border border-[#F59E0B40] whitespace-nowrap"><i class="fa-solid fa-triangle-exclamation text-[9px]"></i> Action Needed</span>';
      }
      if (status === 'error') {
        return '<span class="inline-flex items-center gap-1.5 px-2 py-0.5 rounded text-[10px] font-mono font-semibold bg-[#EF44441A] text-[#EF4444] border border-[#EF444440] whitespace-nowrap"><i class="fa-solid fa-xmark text-[9px]"></i> Error</span>';
      }
      return '<span class="inline-flex items-center gap-1.5 px-2 py-0.5 rounded text-[10px] font-mono font-semibold bg-[#141721] text-[#94A3B8] border border-[#1F2430] whitespace-nowrap"><span class="w-1.5 h-1.5 rounded-full bg-[#475569]"></span> Not Detected</span>';
    }

    function toolMatchesCategory(r, cat) {
      if (!cat || cat === 'all') return true;
      const domain = DOMAIN_CATEGORIES.find(d => d.id === cat);
      const cats = (r.categories && r.categories.length > 0) 
        ? r.categories.map(c => c.toLowerCase()) 
        : [(r.category || '').toLowerCase()];
      
      if (domain && domain.match) {
        return domain.match.some(m => cats.includes(m.toLowerCase()) || cats.some(c => c.includes(m.toLowerCase())));
      }
      return cats.includes(cat.toLowerCase());
    }

    // Interactive Metric Stat Filter Cards
    function toggleStatusFilter(status) {
      if (status === 'all' || currentStatusFilter === status) {
        currentStatusFilter = null;
      } else {
        currentStatusFilter = status;
      }
      updateStatusFilterUI();
      renderTools();
    }

    function clearStatusFilter() {
      currentStatusFilter = null;
      updateStatusFilterUI();
      renderTools();
    }

    function resetAllFilters() {
      currentCategory = 'all';
      currentStatusFilter = null;
      const searchInput = document.getElementById('global-search-input');
      if (searchInput) searchInput.value = '';
      try {
        localStorage.setItem('devtoolkit_last_category', 'all');
      } catch (e) {}
      renderCategoryPills();
      updateStatusFilterUI();
      renderTools();
      showToast('Filters reset to default view');
    }

    function updateStatusFilterUI() {
      const cardIds = ['all', 'installed', 'healthy', 'warning', 'error', 'not_found'];
      cardIds.forEach(id => {
        const el = document.getElementById(`stat-card-${id}`);
        if (el) {
          if (currentStatusFilter === id) {
            el.classList.add('stat-filter-active');
          } else {
            el.classList.remove('stat-filter-active');
          }
        }
      });

      const pillContainer = document.getElementById('active-status-pill-container');
      const pillLabel = document.getElementById('active-status-pill-label');
      const resetBtn = document.getElementById('reset-filters-btn');

      const labels = {
        'installed': 'Installed Tools',
        'healthy': 'Healthy Only',
        'warning': 'Action Needed',
        'error': 'Errors Only',
        'not_found': 'Not Detected'
      };

      if (currentStatusFilter && labels[currentStatusFilter]) {
        pillLabel.innerText = `Status: ${labels[currentStatusFilter]}`;
        pillContainer.classList.remove('hidden');
        pillContainer.classList.add('flex');
      } else {
        pillContainer.classList.add('hidden');
        pillContainer.classList.remove('flex');
      }

      const query = (document.getElementById('global-search-input')?.value || '').trim();
      if (currentStatusFilter !== null || currentCategory !== 'all' || query.length > 0) {
        resetBtn.classList.remove('hidden');
      } else {
        resetBtn.classList.add('hidden');
      }
    }

    function renderCategoryPills() {
      const container = document.getElementById('category-filters');
      if (!container) return;

      container.innerHTML = DOMAIN_CATEGORIES.map(domain => {
        const count = domain.id === 'all' 
          ? allReports.length 
          : allReports.filter(r => toolMatchesCategory(r, domain.id)).length;
        const isActive = currentCategory === domain.id;
        const activeClass = 'cat-btn px-2.5 py-1 rounded text-xs font-medium bg-[#141721] text-white border border-[#10B98180] shadow-sm transition flex-shrink-0 flex items-center gap-1.5';
        const inactiveClass = 'cat-btn px-2.5 py-1 rounded text-xs font-medium text-[#94A3B8] hover:text-[#F3F4F6] hover:bg-[#141721] border border-transparent transition flex-shrink-0 flex items-center gap-1.5';
        
        return `
          <button onclick="setCategory('${domain.id}')" class="${isActive ? activeClass : inactiveClass}" data-cat="${domain.id}">
            <i class="fa-solid ${domain.icon} text-[10px] ${isActive ? 'text-[#10B981]' : 'text-[#475569]'}"></i>
            <span>${domain.label}</span>
            <span class="ml-0.5 text-[10px] font-mono ${isActive ? 'text-[#10B981] font-semibold' : 'text-[#475569]'}">${count}</span>
          </button>
        `;
      }).join('');
    }

    function setCategory(cat) {
      currentCategory = cat;
      try {
        localStorage.setItem('devtoolkit_last_category', cat);
      } catch (e) {}
      renderCategoryPills();
      updateStatusFilterUI();
      renderTools();
    }

    function setLayout(mode) {
      currentLayout = mode;
      const gridBtn = document.getElementById('layout-grid-btn');
      const listBtn = document.getElementById('layout-list-btn');
      const gridEl = document.getElementById('tools-grid');
      const listEl = document.getElementById('tools-list-container');

      if (mode === 'grid') {
        gridBtn.className = 'p-1 rounded text-xs bg-[#141721] text-[#10B981] border border-[#10B98140] transition';
        listBtn.className = 'p-1 rounded text-xs text-[#94A3B8] hover:text-[#F3F4F6] transition';
        gridEl.classList.remove('hidden');
        listEl.classList.add('hidden');
      } else {
        gridBtn.className = 'p-1 rounded text-xs text-[#94A3B8] hover:text-[#F3F4F6] transition';
        listBtn.className = 'p-1 rounded text-xs bg-[#141721] text-[#10B981] border border-[#10B98140] transition';
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
      updateStatusFilterUI();
      renderTools();
    }

    function renderTools() {
      const query = (document.getElementById('global-search-input')?.value || '').toLowerCase().trim();
      let filtered = allReports.filter(r => {
        const matchesCat = toolMatchesCategory(r, currentCategory);
        let matchesStatus = true;
        if (currentStatusFilter === 'installed') {
          matchesStatus = r.installed === true;
        } else if (currentStatusFilter) {
          matchesStatus = r.status === currentStatusFilter;
        }

        const cats = (r.categories && r.categories.length > 0) ? r.categories.map(c => c.toLowerCase()) : [r.category.toLowerCase()];
        const matchesQuery = !query ||
          r.name.toLowerCase().includes(query) ||
          r.id.toLowerCase().includes(query) ||
          cats.some(c => c.includes(query)) ||
          (r.version && r.version.toLowerCase().includes(query)) ||
          (r.binary_path && r.binary_path.toLowerCase().includes(query)) ||
          (r.home_path && r.home_path.toLowerCase().includes(query));
        return matchesCat && matchesStatus && matchesQuery;
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

      // If drawer is currently open, refresh its content in case audit changed
      if (activeDrawerToolId) {
        renderInspectorDrawer(activeDrawerToolId);
      }
    }

    let activeAuditSource = null;

    function renderToolCardInner(r) {
      const isScanning = Boolean(r.scanning);

      if (isScanning) {
        const toolCats = (r.categories && r.categories.length > 0) ? r.categories : [r.category || 'tool'];
        const categoriesHtml = toolCats.slice(0, 2).map(c => 
          `<span class="text-[9px] text-[#475569] uppercase tracking-wider font-mono font-medium px-1.5 py-0.5 bg-[#08090C] rounded border border-[#1F2430]">${c}</span>`
        ).join('') + (toolCats.length > 2 ? `<span class="text-[9px] text-[#475569] font-mono">+${toolCats.length - 2}</span>` : '');

        return `
          <div>
            <!-- Header: Icon, Name, Scanning Badge -->
            <div class="flex items-start justify-between gap-2.5 mb-2.5">
              <div class="flex items-center gap-2.5 min-w-0">
                <div class="w-9 h-9 rounded bg-[#08090C] border border-[#1F2430] flex items-center justify-center text-base flex-shrink-0 text-[#94A3B8]">
                  ${getToolIcon(r.id, r.category)}
                </div>
                <div class="min-w-0">
                  <h3 class="font-semibold text-[#F3F4F6] text-xs tracking-tight truncate" title="${r.name}">
                    ${r.name}
                  </h3>
                  <div class="flex items-center gap-1.5 mt-0.5">
                    <span class="relative flex h-1.5 w-1.5">
                      <span class="animate-ping absolute inline-flex h-full w-full rounded-full bg-[#06B6D4] opacity-75"></span>
                      <span class="relative inline-flex rounded-full h-1.5 w-1.5 bg-[#06B6D4]"></span>
                    </span>
                    <span class="text-[10px] font-mono text-[#06B6D4] font-medium">Scanning...</span>
                  </div>
                </div>
              </div>
              <div class="flex-shrink-0">
                <span class="inline-flex items-center gap-1.5 px-2 py-0.5 rounded text-[10px] font-mono font-semibold bg-[#06B6D41A] text-[#06B6D4] border border-[#06B6D440] whitespace-nowrap animate-pulse">
                  <i class="fa-solid fa-circle-notch fa-spin text-[9px]"></i> Scanning
                </span>
              </div>
            </div>

            <!-- Categories & Shimmer Path Skeleton -->
            <div class="space-y-2 my-2 text-xs">
              <div class="flex items-center gap-1 flex-wrap">
                ${categoriesHtml}
              </div>
              <div class="bg-[#08090C] px-2 py-1.5 rounded border border-[#1F2430] flex items-center gap-2">
                <i class="fa-solid fa-terminal text-[#475569] text-[9px]"></i>
                <div class="h-3 bg-[#141721] rounded skeleton-shimmer w-3/4"></div>
              </div>
            </div>
          </div>

          <!-- Bottom Footer Bar Skeleton -->
          <div class="pt-2 mt-1 border-t border-[#1F2430] flex items-center justify-between text-xs">
            <div class="flex items-center gap-1.5">
              <div class="h-3.5 w-14 bg-[#141721] rounded skeleton-shimmer"></div>
            </div>
            <span class="text-[10px] font-mono text-[#475569] flex items-center gap-1">
              <i class="fa-solid fa-spinner fa-spin text-[9px] text-[#06B6D4]"></i> running
            </span>
          </div>
        `;
      }

      // Completed card
      const toolCats = (r.categories && r.categories.length > 0) ? r.categories : [r.category];
      const categoriesHtml = toolCats.slice(0, 2).map(c => 
        `<span class="text-[9px] text-[#94A3B8] uppercase tracking-wider font-mono font-medium px-1.5 py-0.5 bg-[#08090C] rounded border border-[#1F2430]">${c}</span>`
      ).join('') + (toolCats.length > 2 ? `<span class="text-[9px] text-[#475569] font-mono">+${toolCats.length - 2}</span>` : '');

      const primaryPath = r.home_path || r.binary_path || '';
      const cleanPath = primaryPath.replace(/"/g, '&quot;');

      let companionPill = '';
      if (r.companions && r.companions.length > 0) {
        const installedComp = r.companions.filter(c => c.installed).length;
        companionPill = `
          <span class="inline-flex items-center gap-1 text-[10px] font-mono text-[#94A3B8] bg-[#08090C] px-1.5 py-0.2 rounded border border-[#1F2430]">
            <i class="fa-solid fa-layer-group text-[9px] text-[#8B5CF6]"></i> ${installedComp}/${r.companions.length}
          </span>
        `;
      }

      let diagStrip = '';
      if (r.diagnostics && r.diagnostics.length > 0) {
        diagStrip = `
          <span class="inline-flex items-center gap-1 text-[10px] font-mono font-medium text-[#F59E0B] bg-[#F59E0B1A] px-1.5 py-0.2 rounded border border-[#F59E0B40] truncate max-w-[130px]" title="${r.diagnostics[0].message}">
            <i class="fa-solid fa-triangle-exclamation text-[9px]"></i> Action
          </span>
        `;
      }

      return `
        <div>
          <!-- Header: Icon, Name, Version, Status -->
          <div class="flex items-start justify-between gap-2.5 mb-2.5">
            <div class="flex items-center gap-2.5 min-w-0">
              <div class="w-9 h-9 rounded bg-[#08090C] border border-[#1F2430] flex items-center justify-center text-base flex-shrink-0 group-hover:border-[#2E3446] group-hover:bg-[#141721] transition">
                ${getToolIcon(r.id, r.category)}
              </div>
              <div class="min-w-0">
                <h3 class="font-semibold text-[#F3F4F6] text-xs tracking-tight truncate group-hover:text-[#10B981] transition" title="${r.name}">
                  ${r.name}
                </h3>
                <div class="text-[11px] font-mono font-medium text-[#06B6D4] mt-0.5 truncate">
                  ${r.version ? 'v' + r.version : (r.installed ? '<span class="text-[#94A3B8] font-normal">Installed</span>' : '<span class="text-[#475569] font-normal">Not detected</span>')}
                </div>
              </div>
            </div>
            <div class="flex-shrink-0">
              ${getBadge(r.status)}
            </div>
          </div>

          <!-- Categories & Primary Path -->
          <div class="space-y-1.5 my-2 text-xs">
            <div class="flex items-center gap-1 flex-wrap">
              ${categoriesHtml}
            </div>
            <div class="bg-[#08090C] px-2 py-1 rounded border border-[#1F2430] flex items-center justify-between gap-1.5 min-w-0 text-[11px] font-mono text-[#94A3B8]" title="${cleanPath}">
              <div class="truncate flex items-center gap-1.5">
                <i class="fa-solid ${r.home_path ? 'fa-folder text-[#06B6D4]' : 'fa-terminal text-[#10B981]'} text-[9px] flex-shrink-0"></i>
                <span class="truncate">${primaryPath || '<span class="text-[#475569] italic">No path registered</span>'}</span>
              </div>
              ${primaryPath ? `
                <button onclick="event.stopPropagation(); copyToClipboard('${cleanPath}', 'path')" class="p-0.5 text-[#475569] hover:text-[#F3F4F6] transition flex-shrink-0" title="Copy path">
                  <i class="fa-regular fa-copy text-[9px]"></i>
                </button>
              ` : ''}
            </div>
          </div>
        </div>

        <!-- Bottom Footer Bar -->
        <div class="pt-2 mt-1 border-t border-[#1F2430] flex items-center justify-between text-xs">
          <div class="flex items-center gap-1.5 min-w-0">
            ${companionPill}
            ${diagStrip}
          </div>
          <span class="text-[11px] font-medium text-[#10B981] group-hover:translate-x-0.5 flex items-center gap-1 flex-shrink-0 transition">
            Inspect <i class="fa-solid fa-chevron-right text-[9px]"></i>
          </span>
        </div>
      `;
    }

    function renderToolRowInner(r) {
      const cleanHome = (r.home_path || '').replace(/"/g, '&quot;');
      const cleanBin = (r.binary_path || '').replace(/"/g, '&quot;');
      const toolCats = (r.categories && r.categories.length > 0) ? r.categories : [r.category];
      const catsDisplay = toolCats.join(', ');

      if (r.scanning) {
        return `
          <td class="py-2.5 px-3.5 font-semibold text-[#F3F4F6] flex items-center gap-2">
            <span class="w-6 h-6 rounded bg-[#08090C] border border-[#1F2430] flex items-center justify-center text-xs flex-shrink-0 text-[#94A3B8]">${getToolIcon(r.id, r.category)}</span>
            <span class="truncate max-w-[150px]">${r.name}</span>
          </td>
          <td class="py-2.5 px-3.5 uppercase text-[10px] font-mono text-[#94A3B8]">${catsDisplay}</td>
          <td class="py-2.5 px-3.5">
            <span class="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] bg-[#06B6D41A] text-[#06B6D4] border border-[#06B6D440] font-mono animate-pulse">
              <i class="fa-solid fa-circle-notch fa-spin text-[9px]"></i> Scanning
            </span>
          </td>
          <td class="py-2.5 px-3.5"><div class="h-3 w-12 bg-[#141721] rounded skeleton-shimmer"></div></td>
          <td class="py-2.5 px-3.5"><div class="h-3 w-28 bg-[#141721] rounded skeleton-shimmer"></div></td>
          <td class="py-2.5 px-3.5"><div class="h-3 w-28 bg-[#141721] rounded skeleton-shimmer"></div></td>
          <td class="py-2.5 px-3.5 text-right text-[#475569]">—</td>
        `;
      }

      return `
        <td class="py-2.5 px-3.5 font-semibold text-[#F3F4F6] flex items-center gap-2">
          <span class="w-6 h-6 rounded bg-[#08090C] border border-[#1F2430] flex items-center justify-center text-xs flex-shrink-0">${getToolIcon(r.id, r.category)}</span>
          <span class="truncate max-w-[150px]">${r.name}</span>
        </td>
        <td class="py-2.5 px-3.5 uppercase text-[10px] font-mono text-[#94A3B8]">${catsDisplay}</td>
        <td class="py-2.5 px-3.5">${getBadge(r.status)}</td>
        <td class="py-2.5 px-3.5 font-mono text-[#06B6D4]">${r.version ? 'v' + r.version : '—'}</td>
        <td class="py-2.5 px-3.5 font-mono text-[#94A3B8] truncate max-w-[180px]" title="${cleanHome}">${r.home_path || '<span class="text-[#475569]">—</span>'}</td>
        <td class="py-2.5 px-3.5 font-mono text-[#10B981] truncate max-w-[180px]" title="${cleanBin}">${r.binary_path || '<span class="text-[#475569]">—</span>'}</td>
        <td class="py-2.5 px-3.5 text-right">
          <button onclick="event.stopPropagation(); openInspectorDrawer('${r.id}')" class="btn-secondary-pro px-2.5 py-1 text-[11px] font-medium">Inspect</button>
        </td>
      `;
    }

    function renderGridView(tools) {
      const grid = document.getElementById('tools-grid');
      grid.innerHTML = '';

      if (tools.length === 0) {
        grid.innerHTML = `
          <div class="col-span-full py-16 text-center text-[#94A3B8] card-pro p-8">
            <i class="fa-solid fa-filter-circle-xmark text-3xl mb-3 text-[#475569] block"></i>
            <h4 class="text-sm font-semibold text-[#F3F4F6]">No Matching Tools or Runtimes</h4>
            <p class="text-xs text-[#94A3B8] mt-1 max-w-md mx-auto">No tools match your current search query and status filter.</p>
            <div class="mt-4">
              <button onclick="resetAllFilters()" class="btn-primary-pro px-4 py-1.5 text-xs font-semibold">
                Reset Search & Filters
              </button>
            </div>
          </div>
        `;
        return;
      }

      tools.forEach(r => {
        const card = document.createElement('div');
        card.id = `tool-card-${r.id}`;
        card.className = 'card-pro p-3.5 sm:p-4 flex flex-col justify-between hover:border-[#2E3446] hover:bg-[#141721] transition cursor-pointer group';
        card.onclick = () => { if (!r.scanning) openInspectorDrawer(r.id); };
        card.innerHTML = renderToolCardInner(r);
        grid.appendChild(card);
      });
    }

    function renderListView(tools) {
      const tbody = document.getElementById('tools-list-tbody');
      tbody.innerHTML = '';

      if (tools.length === 0) {
        tbody.innerHTML = `<tr><td colspan="7" class="py-12 text-center text-[#475569] font-mono italic">No tools found matching criteria.</td></tr>`;
        return;
      }

      tools.forEach(r => {
        const tr = document.createElement('tr');
        tr.id = `tool-row-${r.id}`;
        tr.className = 'hover:bg-[#141721] transition text-[#F3F4F6] cursor-pointer';
        tr.onclick = () => { if (!r.scanning) openInspectorDrawer(r.id); };
        tr.innerHTML = renderToolRowInner(r);
        tbody.appendChild(tr);
      });
    }

    function updateSingleToolInDom(report) {
      const card = document.getElementById(`tool-card-${report.id}`);
      if (card) {
        card.innerHTML = renderToolCardInner(report);
        card.onclick = () => { if (!report.scanning) openInspectorDrawer(report.id); };
      }
      const row = document.getElementById(`tool-row-${report.id}`);
      if (row) {
        row.innerHTML = renderToolRowInner(report);
        row.onclick = () => { if (!report.scanning) openInspectorDrawer(report.id); };
      }
    }

    function updateAuditMetrics() {
      const finished = allReports.filter(r => !r.scanning);
      const total = allReports.length || 1;
      const installed = finished.filter(r => r.installed).length;
      const healthy = finished.filter(r => r.status === 'healthy').length;
      const warning = finished.filter(r => r.status === 'warning').length;
      const error = finished.filter(r => r.status === 'error').length;
      const missing = finished.filter(r => r.status === 'not_found').length;

      document.getElementById('stat-total').innerText = total;
      document.getElementById('stat-installed').innerText = installed;
      document.getElementById('stat-healthy').innerText = healthy;
      document.getElementById('stat-warning').innerText = warning;
      document.getElementById('stat-error').innerText = error;
      document.getElementById('stat-missing').innerText = missing;

      const cov = Math.round((installed / total) * 100);
      document.getElementById('stat-coverage').innerText = `${cov}% coverage`;
      document.getElementById('stat-installed-bar').style.width = `${cov}%`;
      document.getElementById('stat-healthy-bar').style.width = `${Math.round((healthy / total) * 100)}%`;
      document.getElementById('stat-warning-bar').style.width = `${Math.round((warning / total) * 100)}%`;
      document.getElementById('stat-error-bar').style.width = `${Math.round((error / total) * 100)}%`;
      document.getElementById('stat-missing-bar').style.width = `${Math.round((missing / total) * 100)}%`;
    }

    function applySystemInfo(sys) {
      if (!sys) return;
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

    async function fetchAudit() {
      const icon = document.getElementById('rescan-icon');
      if (icon) icon.classList.add('fa-spin');

      if (activeAuditSource) {
        activeAuditSource.close();
        activeAuditSource = null;
      }

      try {
        // Step 1: Pre-populate or mark tools as scanning immediately
        if (!allReports || allReports.length === 0) {
          const toolsRes = await fetch('/api/tools');
          if (toolsRes.ok) {
            const initialTools = await toolsRes.json();
            allReports = initialTools.map(t => ({
              ...t,
              scanning: true,
              status: 'scanning',
              version: null,
              home_path: null,
              binary_path: null,
              companions: [],
              diagnostics: []
            }));
          }
        } else {
          allReports.forEach(r => { r.scanning = true; });
        }

        renderCategoryPills();
        updateStatusFilterUI();
        renderTools();
        updateAuditMetrics();

        // Step 2: Stream results asynchronously using EventSource
        if (window.EventSource) {
          await new Promise((resolve) => {
            const es = new EventSource('/api/audit/stream');
            activeAuditSource = es;

            es.onmessage = (event) => {
              try {
                const msg = JSON.parse(event.data);
                if (msg.type === 'init') {
                  if (msg.system) applySystemInfo(msg.system);
                } else if (msg.type === 'tool') {
                  const rep = msg.report;
                  const idx = allReports.findIndex(r => r.id === rep.id);
                  if (idx !== -1) {
                    allReports[idx] = rep;
                  } else {
                    allReports.push(rep);
                  }
                  updateSingleToolInDom(rep);
                  updateAuditMetrics();
                  if (activeDrawerToolId === rep.id) {
                    renderInspectorDrawer(activeDrawerToolId);
                  }
                } else if (msg.type === 'done') {
                  allReports.forEach(r => { delete r.scanning; });
                  if (msg.system) applySystemInfo(msg.system);
                  updateAuditMetrics();
                  renderCategoryPills();
                  if (searchQuery || activeStatusFilter || activeCategory !== 'all') {
                    renderTools();
                  }
                  es.close();
                  activeAuditSource = null;
                  resolve();
                }
              } catch (parseErr) {
                console.error('Error parsing SSE event', parseErr);
              }
            };

            es.onerror = async () => {
              es.close();
              activeAuditSource = null;
              // Fallback to standard fetch
              try {
                const res = await fetch('/api/audit');
                const data = await res.json();
                allReports = data.reports || [];
                if (data.system) applySystemInfo(data.system);
                renderCategoryPills();
                updateStatusFilterUI();
                renderTools();
                updateAuditMetrics();
              } catch (fallbackErr) {
                showToast('Error auditing environment', true);
              }
              resolve();
            };
          });
        } else {
          // Standard fetch fallback for environments without EventSource
          const res = await fetch('/api/audit');
          const data = await res.json();
          allReports = data.reports || [];
          if (data.system) applySystemInfo(data.system);
          renderCategoryPills();
          updateStatusFilterUI();
          renderTools();
          updateAuditMetrics();
        }
      } catch (err) {
        showToast('Error auditing environment', true);
      } finally {
        if (icon) icon.classList.remove('fa-spin');
      }
    }

    // ==================== TAB 2: PORT MANAGER ====================
    function setPortViewMode(mode) {
      currentPortView = mode;
      const flatBtn = document.getElementById('port-view-flat-btn');
      const groupedBtn = document.getElementById('port-view-grouped-btn');
      const flatContainer = document.getElementById('ports-flat-container');
      const groupedContainer = document.getElementById('ports-grouped-container');

      if (mode === 'flat') {
        flatBtn.className = 'px-2.5 py-1 rounded text-xs bg-[#10B981]/15 text-[#10B981] border border-[#10B981]/30 font-semibold transition flex items-center gap-1.5';
        groupedBtn.className = 'px-2.5 py-1 rounded text-xs text-slate-400 hover:text-white border border-transparent font-medium transition flex items-center gap-1.5';
        flatContainer.classList.remove('hidden');
        groupedContainer.classList.add('hidden');
      } else {
        flatBtn.className = 'px-2.5 py-1 rounded text-xs text-slate-400 hover:text-white border border-transparent font-medium transition flex items-center gap-1.5';
        groupedBtn.className = 'px-2.5 py-1 rounded text-xs bg-[#10B981]/15 text-[#10B981] border border-[#10B981]/30 font-semibold transition flex items-center gap-1.5';
        flatContainer.classList.add('hidden');
        groupedContainer.classList.remove('hidden');
      }
      renderPorts();
    }

    function getPortCategory(port) {
      const p = parseInt(port, 10);
      const webPorts = [80, 443, 3000, 3001, 3002, 4000, 4200, 4321, 5000, 5173, 5174, 8000, 8080, 8081, 8888, 9000, 9999];
      if (webPorts.includes(p)) {
        return { label: 'Web / HTTP', icon: 'fa-globe', badge: 'bg-[#06B6D4]/15 text-[#06B6D4] border-[#06B6D4]/30' };
      }
      const dbPorts = [3306, 5432, 6379, 27017, 1433, 9042, 1521, 5984, 8529];
      if (dbPorts.includes(p)) {
        return { label: 'Database', icon: 'fa-database', badge: 'bg-[#10B981]/15 text-[#10B981] border-[#10B981]/30' };
      }
      const devPorts = [9229, 5005, 5858, 2345, 9003];
      if (devPorts.includes(p)) {
        return { label: 'Dev Debug', icon: 'fa-bug', badge: 'bg-[#8B5CF6]/15 text-[#8B5CF6] border-[#8B5CF6]/30' };
      }
      return { label: 'Service', icon: 'fa-network-wired', badge: 'bg-[#141721] text-slate-400 border-[#1F2430]' };
    }

    function isWebPort(port, isDevPort) {
      const p = parseInt(port, 10);
      const webPorts = [80, 443, 3000, 3001, 3002, 4000, 4200, 4321, 5000, 5173, 5174, 8000, 8080, 8081, 8888, 9000, 9999];
      return webPorts.includes(p) || isDevPort;
    }

    async function fetchPorts(isUserClick = false) {
      const icon = document.getElementById('ports-refresh-icon');
      const btn = document.getElementById('btn-refresh-ports');
      if (icon) icon.classList.add('fa-spin');
      if (btn) btn.disabled = true;
      try {
        const devToggle = document.getElementById('ports-dev-toggle');
        const devOnly = devToggle ? devToggle.checked : false;
        const res = await fetch(`/api/ports?dev_only=${devOnly}`);
        allPorts = await res.json();

        const devCount = allPorts.filter(p => p.is_dev_port).length;
        const critCount = allPorts.filter(p => p.is_system_critical).length;
        const statTotal = document.getElementById('stat-ports-total');
        const statDev = document.getElementById('stat-ports-dev');
        const statCrit = document.getElementById('stat-ports-crit');
        if (statTotal) statTotal.innerText = allPorts.length;
        if (statDev) statDev.innerText = devCount;
        if (statCrit) statCrit.innerText = critCount;

        const sideBadge = document.getElementById('side-ports-badge');
        if (sideBadge) sideBadge.innerText = devCount > 0 ? devCount : allPorts.length;

        renderPorts();
        if (isUserClick) {
          showToast(`Sockets updated (${allPorts.length} listening)`);
        }
      } catch (err) {
        showToast('Error loading sockets', true);
      } finally {
        if (icon) icon.classList.remove('fa-spin');
        if (btn) btn.disabled = false;
      }
    }

    function renderPorts() {
      if (currentPortView === 'flat') {
        renderPortsTable();
      } else {
        renderPortsGrouped();
      }
    }

    function getFilteredPorts() {
      const query = (document.getElementById('ports-search-input')?.value || '').toLowerCase().trim();
      return allPorts.filter(p => {
        if (!query) return true;
        return (
          p.port.toString().includes(query) ||
          p.process_name.toLowerCase().includes(query) ||
          p.pid.toString().includes(query) ||
          p.address.includes(query)
        );
      });
    }

    function renderPortsTable() {
      const tbody = document.getElementById('ports-table-body');
      tbody.innerHTML = '';
      const filtered = getFilteredPorts();

      if (filtered.length === 0) {
        tbody.innerHTML = `<tr><td colspan="7" class="py-12 text-center text-slate-500 italic font-mono text-xs">No listening sockets found matching criteria.</td></tr>`;
        return;
      }

      filtered.forEach(p => {
        const tr = document.createElement('tr');
        tr.className = 'hover:bg-[#141721]/60 transition text-slate-300 border-b border-[#1F2430]/50';

        const portBadge = p.is_dev_port
          ? `<span class="inline-flex items-center gap-1 font-mono font-semibold text-[#06B6D4] bg-[#06B6D4]/10 px-2 py-0.5 rounded border border-[#06B6D4]/25">:${p.port}</span>`
          : `<span class="font-mono font-semibold text-slate-200">:${p.port}</span>`;

        const cat = getPortCategory(p.port);
        const tagBadge = `<span class="inline-flex items-center gap-1.5 px-2 py-0.5 rounded text-[10px] font-semibold font-mono border ${cat.badge}"><i class="fa-solid ${cat.icon} text-[9px]"></i> ${cat.label}</span>`;

        const statusBadge = p.is_system_critical
          ? `<span class="text-rose-400 font-medium inline-flex items-center gap-1.5 text-xs"><i class="fa-solid fa-shield-halved text-[10px]"></i> Protected OS</span>`
          : `<span class="text-[#10B981] font-medium inline-flex items-center gap-1.5 text-xs"><i class="fa-solid fa-user text-[10px]"></i> User Process</span>`;

        const browserBtn = isWebPort(p.port, p.is_dev_port)
          ? `<a href="http://localhost:${p.port}" target="_blank" class="btn-secondary-pro text-[11px] py-1 px-2.5 inline-flex items-center gap-1" title="Open in browser"><i class="fa-solid fa-arrow-up-right-from-square text-[9px] text-[#10B981]"></i> Open</a>`
          : '';

        const actionBtn = p.is_system_critical
          ? `<button onclick="openKillModal(${p.port}, '${p.process_name}', ${p.pid}, true)" class="px-2.5 py-1 bg-[#141721] hover:bg-rose-950/40 text-slate-400 hover:text-rose-300 rounded text-[11px] font-medium transition border border-[#1F2430]">Protected</button>`
          : `<button onclick="openKillModal(${p.port}, '${p.process_name}', ${p.pid}, false)" class="btn-destructive text-[11px] py-1 px-2.5">Kill</button>`;

        tr.innerHTML = `
          <td class="py-3 px-4 font-mono">${portBadge}</td>
          <td class="py-3 px-4">${tagBadge}</td>
          <td class="py-3 px-4 font-semibold text-white truncate max-w-[180px]" title="${p.process_name}">${p.process_name}</td>
          <td class="py-3 px-4 font-mono text-amber-400">${p.pid}</td>
          <td class="py-3 px-4 font-mono text-slate-400">${p.address}</td>
          <td class="py-3 px-4">${statusBadge}</td>
          <td class="py-3 px-4 text-right">
            <div class="flex items-center justify-end gap-1.5">
              ${browserBtn}
              ${actionBtn}
            </div>
          </td>
        `;
        tbody.appendChild(tr);
      });
    }

    function renderPortsGrouped() {
      const container = document.getElementById('ports-grouped-container');
      container.innerHTML = '';
      const filtered = getFilteredPorts();

      if (filtered.length === 0) {
        container.innerHTML = `<div class="card-pro p-12 text-center text-slate-500 italic font-mono text-xs">No listening sockets found matching criteria.</div>`;
        return;
      }

      // Group by process_name + PID
      const groups = {};
      filtered.forEach(p => {
        const key = `${p.process_name} (PID ${p.pid})`;
        if (!groups[key]) {
          groups[key] = {
            process_name: p.process_name,
            pid: p.pid,
            is_system_critical: p.is_system_critical,
            sockets: []
          };
        }
        groups[key].sockets.push(p);
      });

      Object.values(groups).forEach(g => {
        const card = document.createElement('div');
        card.className = 'card-pro p-4 sm:p-5 space-y-3.5';

        const killBtn = g.is_system_critical
          ? `<button onclick="openKillModal(${g.sockets[0].port}, '${g.process_name}', ${g.pid}, true)" class="px-2.5 py-1 bg-[#141721] hover:bg-rose-950/40 text-slate-400 hover:text-rose-300 rounded text-[11px] font-medium transition border border-[#1F2430]">Protected</button>`
          : `<button onclick="openKillModal(${g.sockets[0].port}, '${g.process_name}', ${g.pid}, false)" class="btn-destructive text-[11px] py-1 px-2.5">Kill Process</button>`;

        const socketsHtml = g.sockets.map(p => {
          const cat = getPortCategory(p.port);
          const browserLink = isWebPort(p.port, p.is_dev_port)
            ? `<a href="http://localhost:${p.port}" target="_blank" class="text-[10px] text-[#10B981] hover:underline font-mono font-semibold flex items-center gap-1 ml-1"><i class="fa-solid fa-arrow-up-right-from-square text-[9px]"></i> Open</a>`
            : '';

          return `
            <div class="bg-[#08090C] p-2.5 rounded border border-[#1F2430] flex items-center justify-between gap-2 text-xs">
              <div class="flex items-center gap-2 min-w-0">
                <span class="font-mono font-semibold ${p.is_dev_port ? 'text-[#06B6D4]' : 'text-slate-200'}">:${p.port}</span>
                <span class="inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[10px] font-semibold font-mono border ${cat.badge}">${cat.label}</span>
                <span class="font-mono text-[10px] text-slate-500 truncate">${p.address}</span>
              </div>
              <div class="flex items-center gap-2 flex-shrink-0">
                ${browserLink}
              </div>
            </div>
          `;
        }).join('');

        card.innerHTML = `
          <div class="flex items-center justify-between gap-3 border-b border-[#1F2430] pb-3">
            <div class="flex items-center gap-2.5 min-w-0">
              <div class="w-8 h-8 rounded bg-[#141721] border border-[#1F2430] flex items-center justify-center text-xs font-bold text-[#10B981] flex-shrink-0">
                <i class="fa-solid fa-microchip"></i>
              </div>
              <div class="min-w-0">
                <div class="font-semibold text-white text-sm truncate">${g.process_name}</div>
                <div class="flex items-center gap-2 text-[10px] text-slate-400 font-mono">
                  <span>PID: <strong class="text-amber-400">${g.pid}</strong></span>
                  <span>•</span>
                  <span>${g.sockets.length} listening socket(s)</span>
                </div>
              </div>
            </div>
            <div>${killBtn}</div>
          </div>
          <div class="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-2">
            ${socketsHtml}
          </div>
        `;
        container.appendChild(card);
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
    function getRecentProjects() {
      try {
        const list = JSON.parse(localStorage.getItem('devtoolkit_recent_projects') || '[]');
        return Array.isArray(list) ? list : [];
      } catch (e) {
        return [];
      }
    }

    function addRecentProject(path) {
      if (!path || path === '.') return;
      try {
        let list = getRecentProjects().filter(p => p !== path);
        list.unshift(path);
        if (list.length > 4) list = list.slice(0, 4);
        localStorage.setItem('devtoolkit_recent_projects', JSON.stringify(list));
        renderRecentProjects();
      } catch (e) {}
    }

    function clearRecentProjects() {
      try {
        localStorage.removeItem('devtoolkit_recent_projects');
        renderRecentProjects();
        showToast('Cleared recent projects history');
      } catch (e) {}
    }

    function renderRecentProjects() {
      const container = document.getElementById('project-recent-chips');
      if (!container) return;
      const recents = getRecentProjects();
      if (recents.length === 0) {
        container.innerHTML = '';
        return;
      }
      container.innerHTML = recents.map(p => {
        const cleanP = p.replace(/\\/g, '\\\\').replace(/'/g, "\\'");
        return `
          <button onclick="setAndAuditProject('${cleanP}')" class="px-2 py-0.5 rounded bg-[#141721] hover:bg-[#141721]/80 hover:border-[#10B981]/50 text-slate-300 font-mono text-[11px] truncate max-w-[180px] transition border border-[#1F2430]" title="${p}">
            ${p}
          </button>
        `;
      }).join('') + `
        <button onclick="clearRecentProjects()" class="text-slate-500 hover:text-rose-400 p-1 transition" title="Clear recent paths">
          <i class="fa-regular fa-trash-can text-[10px]"></i>
        </button>
      `;
    }

    function setAndAuditProject(val) {
      document.getElementById('project-path-input').value = val;
      runProjectAudit();
    }

    async function browseProjectFolder() {
      const btn = document.getElementById('btn-browse-project');
      const icon = document.getElementById('browse-folder-icon');
      const input = document.getElementById('project-path-input');
      const originalIcon = icon ? icon.className : 'fa-regular fa-folder-open text-[#10B981] text-xs';

      try {
        if (icon) icon.className = 'fa-solid fa-spinner fa-spin text-[#10B981] text-xs';
        if (btn) btn.disabled = true;

        const currentVal = input ? input.value.trim() : '';
        const res = await fetch('/api/action/select-folder', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ initial_path: currentVal || '.' })
        });

        if (res.ok) {
          const data = await res.json();
          if (data.status === 'ok' && data.path) {
            input.value = data.path;
            showToast(`Selected: ${data.path}`);
            runProjectAudit();
          }
        }
      } catch (err) {
        console.error('Failed to select folder:', err);
      } finally {
        if (icon) icon.className = originalIcon;
        if (btn) btn.disabled = false;
      }
    }

    function copyAllProjectActions() {
      if (!currentProjectActions || currentProjectActions.length === 0) {
        showToast('No actions available to copy');
        return;
      }
      const scriptText = currentProjectActions.join('\n');
      copyToClipboard(scriptText, 'all setup commands');
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
        addRecentProject(data.project_path);
        resultsContainer.classList.remove('hidden');

        document.getElementById('rep-project-name').innerText = data.project_name;
        document.getElementById('rep-project-path').innerText = data.project_path;

        const typesContainer = document.getElementById('rep-detected-types');
        typesContainer.innerHTML = (data.detected_types || []).map(t =>
          `<span class="px-2 py-0.5 rounded text-[10px] font-semibold font-mono bg-[#10B981]/15 text-[#10B981] border border-[#10B981]/30 uppercase tracking-wider">${t}</span>`
        ).join('');

        // Readiness Score Calculation & Scorecard
        const totalChecks = (data.checks || []).length;
        const satisfiedChecks = (data.checks || []).filter(c => c.satisfied).length;
        const missingChecks = totalChecks - satisfiedChecks;
        const scorePct = totalChecks > 0 ? Math.round((satisfiedChecks / totalChecks) * 100) : 100;

        const scorePctEl = document.getElementById('rep-score-pct');
        const scoreBarEl = document.getElementById('rep-score-bar');
        scorePctEl.innerText = `${scorePct}%`;
        scoreBarEl.style.width = `${scorePct}%`;

        if (scorePct === 100) {
          scorePctEl.className = 'text-2xl font-bold font-mono text-[#10B981]';
          scoreBarEl.className = 'h-full bg-[#10B981] rounded transition-all duration-500';
        } else if (scorePct >= 60) {
          scorePctEl.className = 'text-2xl font-bold font-mono text-amber-400';
          scoreBarEl.className = 'h-full bg-amber-400 rounded transition-all duration-500';
        } else {
          scorePctEl.className = 'text-2xl font-bold font-mono text-rose-400';
          scoreBarEl.className = 'h-full bg-rose-500 rounded transition-all duration-500';
        }

        document.getElementById('rep-satisfied-count').innerText = `${satisfiedChecks} satisfied`;
        document.getElementById('rep-missing-count').innerText = `${missingChecks} missing`;

        const badgeEl = document.getElementById('rep-status-badge');
        if (data.ready_to_build) {
          badgeEl.innerHTML = '<span class="inline-flex items-center gap-1.5 px-2.5 py-1 rounded text-xs font-semibold font-mono bg-[#10B981]/15 text-[#10B981] border border-[#10B981]/30"><i class="fa-solid fa-check text-[11px]"></i> READY TO BUILD</span>';
        } else {
          badgeEl.innerHTML = '<span class="inline-flex items-center gap-1.5 px-2.5 py-1 rounded text-xs font-semibold font-mono bg-rose-500/15 text-rose-400 border border-rose-500/30"><i class="fa-solid fa-triangle-exclamation text-[11px]"></i> PREREQS MISSING</span>';
        }

        const tbody = document.getElementById('project-checks-tbody');
        tbody.innerHTML = '';
        (data.checks || []).forEach(c => {
          const tr = document.createElement('tr');
          tr.className = 'hover:bg-[#141721]/60 text-slate-300 border-b border-[#1F2430]/50';
          const stat = c.satisfied
            ? '<span class="text-[#10B981] font-semibold inline-flex items-center gap-1 font-mono text-xs"><i class="fa-solid fa-check text-[10px]"></i> Satisfied</span>'
            : '<span class="text-rose-400 font-semibold inline-flex items-center gap-1 font-mono text-xs"><i class="fa-solid fa-xmark text-[10px]"></i> Missing</span>';
          tr.innerHTML = `
            <td class="py-2.5 px-4">${stat}</td>
            <td class="py-2.5 px-4 font-semibold text-white">${c.name}</td>
            <td class="py-2.5 px-4 font-mono text-slate-400 text-xs">${c.required}</td>
            <td class="py-2.5 px-4 font-mono text-[#06B6D4] text-xs">${c.detected || '<span class="text-slate-500">None</span>'}</td>
            <td class="py-2.5 px-4 text-slate-300 text-xs">${c.message}</td>
          `;
          tbody.appendChild(tr);
        });

        // Recommended actions
        currentProjectActions = data.suggested_actions || [];
        const actionsCard = document.getElementById('project-actions-card');
        const actionsList = document.getElementById('project-actions-list');
        if (currentProjectActions.length > 0) {
          actionsCard.classList.remove('hidden');
          actionsList.innerHTML = currentProjectActions.map(act => {
            const cleanCmd = act.replace(/\\/g, '\\\\').replace(/'/g, "\\'");
            return `
              <div class="flex items-center justify-between p-2.5 rounded bg-[#08090C] border border-[#1F2430] text-xs">
                <div class="font-mono text-slate-200 truncate mr-2"><code>${act}</code></div>
                <button onclick="copyToClipboard('${cleanCmd}', 'command')" class="btn-secondary-pro text-[11px] py-1 px-2.5 font-mono flex-shrink-0">Copy</button>
              </div>
            `;
          }).join('');
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
        listEl.innerHTML = '<div class="text-xs text-slate-500 italic p-3 bg-[#08090C] rounded border border-[#1F2430] text-center font-mono">No custom search roots configured. Standard OS & ecosystem discovery is active.</div>';
        bannerEl.classList.add('hidden');
        return;
      }

      bannerEl.classList.remove('hidden');
      bannerListEl.innerText = paths.join(', ');

      listEl.innerHTML = paths.map(p => `
        <div class="flex items-center justify-between p-2.5 bg-[#08090C] rounded border border-[#1F2430] text-xs">
          <div class="flex items-center gap-2 font-mono text-slate-200 truncate" title="${p}">
            <i class="fa-regular fa-folder text-[#10B981]"></i>
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

    async function browseSettingsFolder() {
      const input = document.getElementById('settings-path-input');
      try {
        const currentVal = input ? input.value.trim() : '';
        const res = await fetch('/api/action/select-folder', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ initial_path: currentVal || '' })
        });

        if (res.ok) {
          const data = await res.json();
          if (data.status === 'ok' && data.path) {
            input.value = data.path;
          }
        }
      } catch (err) {
        console.error('Failed to select settings folder:', err);
      }
    }

    async function loadSystemInfo() {
      try {
        const res = await fetch('/api/system');
        const sys = await res.json();

        // Dynamically update Sidebar OS info & Host name
        const sideOs = document.getElementById('side-os-info');
        if (sideOs) {
          sideOs.innerText = `${sys.os_name} ${sys.os_release} (${sys.arch})`;
          sideOs.title = `${sys.os_name} ${sys.os_release} ${sys.os_version} [${sys.arch}]`;
        }
        const sideHost = document.getElementById('side-host-name');
        if (sideHost) {
          sideHost.innerText = sys.hostname;
          sideHost.title = sys.hostname;
        }
        const sideAppVer = document.getElementById('side-app-version');
        if (sideAppVer && sys.app_version) {
          sideAppVer.innerText = `v${sys.app_version}`;
        }
        const sidePyVer = document.getElementById('side-python-version');
        if (sidePyVer) {
          sidePyVer.innerText = sys.python_version || 'Active';
        }

        // Workstation Telemetry in Help modal
        const sysOs = document.getElementById('sys-os');
        if (sysOs) sysOs.innerText = `${sys.os_name} ${sys.os_release}`;
        const sysArch = document.getElementById('sys-arch');
        if (sysArch) sysArch.innerText = sys.arch;
        const sysHost = document.getElementById('sys-host');
        if (sysHost) sysHost.innerText = sys.hostname;
        const sysPython = document.getElementById('sys-python');
        if (sysPython) sysPython.innerText = sys.python_version || 'Active';
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
      const activeTag = document.activeElement ? document.activeElement.tagName.toLowerCase() : '';
      const isInput = activeTag === 'input' || activeTag === 'textarea';

      if (e.key === 'Escape') {
        closeExportMenu();
        if (activeDrawerToolId) {
          closeInspectorDrawer();
          return;
        }
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
        } else if (activeTab === 'project') {
          const projInput = document.getElementById('project-path-input');
          if (projInput) projInput.focus();
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
    loadSystemInfo();
    fetchPorts(false);
    fetchAudit();
    const projInput = document.getElementById('project-path-input');
    if (projInput) projInput.value = '';
    renderRecentProjects();

    // Deep Link & Query Param Support
    try {
      const urlParams = new URLSearchParams(window.location.search);
      const initialTab = urlParams.get('tab');
      if (initialTab && ['env', 'ports', 'project', 'settings'].includes(initialTab)) {
        switchTab(initialTab);
      }
      const initialAudit = urlParams.get('audit');
      if (initialAudit) {
        setAndAuditProject(initialAudit);
      }
      const initialDrawer = urlParams.get('drawer');
      if (initialDrawer) {
        setTimeout(() => openInspectorDrawer(initialDrawer), 1200);
      }
      const initialHelp = urlParams.get('help');
      if (initialHelp === 'true' || initialHelp === '1') {
        toggleHelpModal();
      }
    } catch (e) {
      console.error('Deep link parsing error:', e);
    }
  </script>
</body>
</html>
"""
