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

app = FastAPI(title="DevToolkit API", version="0.1.0")

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


class AuditRequest(BaseModel):
    categories: Optional[List[str]] = None
    tool_ids: Optional[List[str]] = None


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


# Serve compiled React frontend if frontend/dist exists, otherwise serve embedded modern UI
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

    time.sleep(0.8)  # Wait briefly for FastAPI to initialize
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
                width=1120,
                height=760,
                min_size=(850, 580),
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


EMBEDDED_UI_HTML = """<!DOCTYPE html>
<html lang="en" class="dark">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>DevToolkit ⚡ Workstation Environment Inspector</title>
  <script src="https://cdn.tailwindcss.com"></script>
  <script>
    tailwind.config = {
      darkMode: 'class',
      theme: {
        extend: {
          colors: {
            brand: { 50: '#f5f3ff', 500: '#8b5cf6', 600: '#7c3aed', 700: '#6d28d9' },
            darkBg: '#0f172a',
            cardBg: '#1e293b',
            borderDark: '#334155'
          }
        }
      }
    }
  </script>
  <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css" />
  <style>
    body { background-color: #0b0f19; color: #f1f5f9; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; }
    .glass-card { background: rgba(30, 41, 59, 0.7); backdrop-filter: blur(12px); border: 1px solid rgba(255,255,255,0.08); }
    .glass-card:hover { border-color: rgba(139, 92, 246, 0.4); }
  </style>
</head>
<body class="min-h-screen p-6">
  <div class="max-w-7xl mx-auto space-y-6">
    <!-- Header -->
    <div class="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-borderDark pb-5">
      <div class="flex items-center gap-3">
        <div class="w-11 h-11 rounded-xl bg-gradient-to-br from-violet-500 to-indigo-600 flex items-center justify-center shadow-lg shadow-violet-500/25">
          <i class="fa-solid fa-bolt text-xl text-white"></i>
        </div>
        <div>
          <h1 class="text-2xl font-black tracking-tight text-white flex items-center gap-2">
            DevToolkit <span class="text-xs px-2 py-0.5 rounded-full bg-violet-500/20 text-violet-300 font-mono">v0.1.0</span>
          </h1>
          <p class="text-xs text-slate-400" id="sys-info">Inspecting local developer workstation...</p>
        </div>
      </div>
      <div class="flex items-center gap-3">
        <button onclick="fetchAudit()" id="refresh-btn" class="flex items-center gap-2 px-4 py-2 bg-violet-600 hover:bg-violet-500 text-white rounded-lg text-sm font-medium transition shadow-sm">
          <i class="fa-solid fa-rotate text-xs" id="refresh-icon"></i>
          <span>Refresh Audit</span>
        </button>
      </div>
    </div>

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
        <div class="text-xs text-amber-400 font-medium">Warnings</div>
        <div class="text-xl font-bold text-amber-400 mt-1" id="stat-warning">—</div>
      </div>
      <div class="glass-card rounded-xl p-3 text-center">
        <div class="text-xs text-rose-400 font-medium">Errors</div>
        <div class="text-xl font-bold text-rose-400 mt-1" id="stat-error">—</div>
      </div>
      <div class="glass-card rounded-xl p-3 text-center">
        <div class="text-xs text-slate-500 font-medium">Missing</div>
        <div class="text-xl font-bold text-slate-500 mt-1" id="stat-missing">—</div>
      </div>
    </div>

    <!-- Filter & Search Toolbar -->
    <div class="flex flex-col sm:flex-row items-center justify-between gap-3 bg-slate-900/60 p-2.5 rounded-xl border border-borderDark">
      <div class="flex items-center gap-1.5 overflow-x-auto w-full sm:w-auto" id="category-filters">
        <button onclick="setCategory('all')" class="filter-btn px-3 py-1.5 rounded-lg text-xs font-semibold bg-violet-600 text-white" data-cat="all">All</button>
        <button onclick="setCategory('runtime')" class="filter-btn px-3 py-1.5 rounded-lg text-xs font-semibold bg-slate-800 text-slate-300 hover:bg-slate-700" data-cat="runtime">Runtimes</button>
        <button onclick="setCategory('vcs')" class="filter-btn px-3 py-1.5 rounded-lg text-xs font-semibold bg-slate-800 text-slate-300 hover:bg-slate-700" data-cat="vcs">VCS / Git</button>
        <button onclick="setCategory('mobile')" class="filter-btn px-3 py-1.5 rounded-lg text-xs font-semibold bg-slate-800 text-slate-300 hover:bg-slate-700" data-cat="mobile">Mobile / SDKs</button>
        <button onclick="setCategory('container')" class="filter-btn px-3 py-1.5 rounded-lg text-xs font-semibold bg-slate-800 text-slate-300 hover:bg-slate-700" data-cat="container">Containers</button>
      </div>
      <div class="relative w-full sm:w-72">
        <i class="fa-solid fa-search absolute left-3 top-2.5 text-xs text-slate-400"></i>
        <input type="text" id="search-input" oninput="filterTools()" placeholder="Search SDK, runtime, path..." class="w-full pl-8 pr-3 py-1.5 bg-slate-950/80 border border-slate-700 rounded-lg text-xs text-white placeholder-slate-500 focus:outline-none focus:border-violet-500 transition" />
      </div>
    </div>

    <!-- Cards Grid -->
    <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4" id="tools-grid">
      <!-- Generated Cards inserted dynamically -->
    </div>
  </div>

  <div id="toast" class="fixed bottom-6 right-6 px-4 py-2.5 rounded-lg bg-emerald-600 text-white text-xs font-medium shadow-lg transform translate-y-20 opacity-0 transition duration-300 flex items-center gap-2">
    <i class="fa-solid fa-check"></i> <span id="toast-msg">Copied to clipboard</span>
  </div>

  <script>
    let allReports = [];
    let currentCategory = 'all';

    function showToast(msg) {
      const toast = document.getElementById('toast');
      document.getElementById('toast-msg').innerText = msg;
      toast.classList.remove('translate-y-20', 'opacity-0');
      setTimeout(() => {
        toast.classList.add('translate-y-20', 'opacity-0');
      }, 2200);
    }

    function copyToClipboard(text, label) {
      navigator.clipboard.writeText(text);
      showToast('Copied ' + (label || 'path') + ' to clipboard!');
    }

    async function openFolder(path) {
      try {
        const res = await fetch('/api/action/open-folder', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ path })
        });
        if (res.ok) {
          showToast('Opened folder in Explorer');
        } else {
          showToast('Failed to open folder');
        }
      } catch (err) {
        showToast('Error opening folder');
      }
    }

    function getBadge(status) {
      if (status === 'healthy') return '<span class="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-medium bg-emerald-500/10 text-emerald-400 border border-emerald-500/20"><span class="w-1.5 h-1.5 rounded-full bg-emerald-400"></span> Healthy</span>';
      if (status === 'warning') return '<span class="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-medium bg-amber-500/10 text-amber-400 border border-amber-500/20"><span class="w-1.5 h-1.5 rounded-full bg-amber-400"></span> Warning</span>';
      if (status === 'error') return '<span class="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-medium bg-rose-500/10 text-rose-400 border border-rose-500/20"><span class="w-1.5 h-1.5 rounded-full bg-rose-400"></span> Error</span>';
      return '<span class="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-medium bg-slate-800 text-slate-400 border border-slate-700"><span class="w-1.5 h-1.5 rounded-full bg-slate-500"></span> Not Installed</span>';
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
          (r.binary_path && r.binary_path.toLowerCase().includes(query));
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
          <div class="mt-2 p-2.5 rounded-lg bg-amber-500/10 border border-amber-500/20 text-amber-300 text-xs">
            <div class="font-medium flex items-center gap-1.5"><i class="fa-solid fa-triangle-exclamation"></i> ${d.message}</div>
            ${d.suggested_fix ? '<div class="mt-1 text-slate-300 text-[11px]"><span class="text-amber-400 font-medium">Fix:</span> ' + d.suggested_fix + '</div>' : ''}
          </div>
        `).join('');

        card.innerHTML = `
          <div>
            <div class="flex items-start justify-between gap-2 mb-3">
              <div>
                <h3 class="font-bold text-white text-base tracking-tight flex items-center gap-2">
                  ${r.name}
                  <span class="text-[10px] text-slate-400 uppercase tracking-wider font-mono font-medium px-1.5 py-0.5 bg-slate-800 rounded">${r.category}</span>
                </h3>
                <div class="text-xs font-mono font-semibold text-violet-400 mt-1">
                  ${r.version ? 'v' + r.version : '<span class="text-slate-500 font-normal">No version detected</span>'}
                </div>
              </div>
              <div>${getBadge(r.status)}</div>
            </div>

            <div class="space-y-2 mt-4 text-xs">
              ${r.binary_path ? `
                <div class="bg-slate-950/60 p-2.5 rounded-lg border border-slate-800 flex items-center justify-between gap-2">
                  <div class="truncate text-slate-300 font-mono text-[11px]" title="${r.binary_path}">
                    ${r.binary_path}
                  </div>
                  <div class="flex items-center gap-1 flex-shrink-0">
                    <button onclick="copyToClipboard('${r.binary_path.replace(/\\\\/g, '\\\\\\\\')}', 'path')" title="Copy path" class="p-1 hover:text-violet-400 text-slate-400 transition"><i class="fa-regular fa-copy text-xs"></i></button>
                    <button onclick="openFolder('${r.binary_path.replace(/\\\\/g, '\\\\\\\\')}')" title="Open containing folder" class="p-1 hover:text-violet-400 text-slate-400 transition"><i class="fa-regular fa-folder-open text-xs"></i></button>
                  </div>
                </div>
              ` : '<div class="text-xs text-slate-500 italic">Binary not found in system PATH</div>'}

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
      const refreshIcon = document.getElementById('refresh-icon');
      refreshIcon.classList.add('fa-spin');
      try {
        const res = await fetch('/api/audit');
        const data = await res.json();
        allReports = data.reports || [];

        // Update stats
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
        showToast('Error auditing environment');
      } finally {
        refreshIcon.classList.remove('fa-spin');
      }
    }

    // Initial audit load
    fetchAudit();
  </script>
</body>
</html>
"""
