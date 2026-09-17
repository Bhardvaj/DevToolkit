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


class SearchPathRequest(BaseModel):
    path: str


class AuditRequest(BaseModel):
    categories: Optional[List[str]] = None
    tool_ids: Optional[List[str]] = None


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
  <title>DevToolkit ⚡ Workstation Environment Inspector</title>
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
          <p class="text-xs text-slate-400" id="sys-info">Inspecting local workstation environment...</p>
        </div>
      </div>
      <div class="flex items-center gap-2.5">
        <button onclick="openSettingsModal()" class="flex items-center gap-2 px-3.5 py-2 bg-slate-900 hover:bg-slate-800 text-slate-200 rounded-lg text-xs font-semibold transition border border-slate-700 shadow-sm">
          <i class="fa-solid fa-gear text-violet-400"></i>
          <span>Settings & Search Paths</span>
        </button>
        <button onclick="fetchAudit()" id="refresh-btn" class="flex items-center gap-2 px-4 py-2 bg-violet-600 hover:bg-violet-500 text-white rounded-lg text-xs font-semibold transition shadow-sm">
          <i class="fa-solid fa-rotate" id="refresh-icon"></i>
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
      <button onclick="openSettingsModal()" class="text-violet-400 hover:text-violet-300 font-medium">Manage Paths</button>
    </div>

    <!-- Cards Grid -->
    <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4" id="tools-grid">
      <!-- Generated Cards inserted dynamically -->
    </div>
  </div>

  <!-- Settings & Custom Search Paths Modal -->
  <div id="settings-modal" class="fixed inset-0 modal-backdrop z-50 flex items-center justify-center p-4 hidden">
    <div class="bg-slate-900 border border-slate-700 rounded-2xl max-w-xl w-full p-6 shadow-2xl space-y-5 animate-in fade-in zoom-in-95 duration-150">
      <div class="flex items-center justify-between border-b border-slate-800 pb-3">
        <div class="flex items-center gap-2.5">
          <div class="w-8 h-8 rounded-lg bg-violet-600/20 text-violet-400 flex items-center justify-center">
            <i class="fa-solid fa-folder-tree text-sm"></i>
          </div>
          <div>
            <h2 class="text-base font-bold text-white">Monitored Search Directories (Layer 4)</h2>
            <p class="text-[11px] text-slate-400">Configure directories where DevToolkit should scan for SDKs by content signature</p>
          </div>
        </div>
        <button onclick="closeSettingsModal()" class="text-slate-400 hover:text-white transition p-1"><i class="fa-solid fa-xmark text-lg"></i></button>
      </div>

      <!-- Add Search Path Input -->
      <div>
        <label class="block text-xs font-semibold text-slate-300 mb-1.5">Add Custom Directory Path</label>
        <div class="flex items-center gap-2">
          <input type="text" id="custom-path-input" placeholder="e.g. D:\\Dev or /opt/custom_sdks" class="flex-1 bg-slate-950 border border-slate-700 rounded-lg px-3 py-2 text-xs text-white placeholder-slate-500 font-mono focus:outline-none focus:border-violet-500" />
          <button onclick="submitSearchPath()" class="px-4 py-2 bg-violet-600 hover:bg-violet-500 text-white rounded-lg text-xs font-bold transition flex items-center gap-1.5">
            <i class="fa-solid fa-plus"></i>
            <span>Add Path</span>
          </button>
        </div>
        <div class="mt-2 flex items-center gap-2">
          <span class="text-[11px] text-slate-500">Quick Suggestion:</span>
          <button onclick="fillPresetPath('D:\\\\Dev')" class="text-[11px] px-2 py-0.5 rounded bg-slate-800 hover:bg-slate-700 text-slate-300 font-mono transition">+ D:\Dev</button>
          <button onclick="fillPresetPath('C:\\\\Dev')" class="text-[11px] px-2 py-0.5 rounded bg-slate-800 hover:bg-slate-700 text-slate-300 font-mono transition">+ C:\Dev</button>
        </div>
      </div>

      <!-- Configured Paths List -->
      <div>
        <h3 class="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-2">Active Monitored Directories</h3>
        <div id="configured-paths-list" class="space-y-2 max-h-48 overflow-y-auto">
          <!-- Populated by JS -->
        </div>
      </div>

      <!-- Explanation Card -->
      <div class="p-3 rounded-xl bg-violet-500/10 border border-violet-500/20 text-[11px] text-violet-300 space-y-1">
        <div class="font-bold flex items-center gap-1.5"><i class="fa-solid fa-shield-halved"></i> Generalized Content Signature Discovery</div>
        <p class="text-slate-300">When you add a directory, DevToolkit scans its subfolders using <strong>structural content signatures</strong> (e.g. searching for <code>platform-tools/adb</code> or <code>bin/javac</code>) rather than folder names. This works for zip extractions, custom drives, and portable SDKs.</p>
      </div>

      <div class="flex justify-end pt-2 border-t border-slate-800">
        <button onclick="closeSettingsModal()" class="px-4 py-2 bg-slate-800 hover:bg-slate-700 text-slate-200 rounded-lg text-xs font-medium transition">Done</button>
      </div>
    </div>
  </div>

  <div id="toast" class="fixed bottom-6 right-6 px-4 py-2.5 rounded-lg bg-emerald-600 text-white text-xs font-medium shadow-lg transform translate-y-20 opacity-0 transition duration-300 flex items-center gap-2 z-50">
    <i class="fa-solid fa-check"></i> <span id="toast-msg">Copied to clipboard</span>
  </div>

  <script>
    let allReports = [];
    let currentCategory = 'all';
    let currentConfig = { search_paths: [] };

    function showToast(msg) {
      const toast = document.getElementById('toast');
      document.getElementById('toast-msg').innerText = msg;
      toast.classList.remove('translate-y-20', 'opacity-0');
      setTimeout(() => {
        toast.classList.add('translate-y-20', 'opacity-0');
      }, 2500);
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

    function openSettingsModal() {
      document.getElementById('settings-modal').classList.remove('hidden');
      loadConfig();
    }

    function closeSettingsModal() {
      document.getElementById('settings-modal').classList.add('hidden');
    }

    function fillPresetPath(path) {
      document.getElementById('custom-path-input').value = path;
    }

    async function loadConfig() {
      try {
        const res = await fetch('/api/config');
        currentConfig = await res.json();
        renderConfigList();
      } catch (e) {
        console.error('Error loading config:', e);
      }
    }

    function renderConfigList() {
      const listEl = document.getElementById('configured-paths-list');
      const bannerEl = document.getElementById('search-paths-banner');
      const bannerListEl = document.getElementById('banner-paths-list');

      const paths = currentConfig.search_paths || [];
      if (paths.length === 0) {
        listEl.innerHTML = '<div class="text-xs text-slate-500 italic p-3 bg-slate-950/60 rounded-lg border border-slate-800 text-center">No custom search paths added yet. Using standard OS & ecosystem discovery.</div>';
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
      const input = document.getElementById('custom-path-input');
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
          showToast('Search path added! Refreshing audit...');
          await loadConfig();
          await fetchAudit();
        } else {
          const err = await res.json();
          showToast(err.detail || 'Directory does not exist');
        }
      } catch (e) {
        showToast('Error adding search path');
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
        showToast('Error removing path');
      }
    }

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

        // Path Display
        let pathsHtml = '';
        if (r.home_path) {
          pathsHtml += `
            <div class="bg-slate-950/70 p-2.5 rounded-lg border border-slate-800 flex items-center justify-between gap-2">
              <div class="truncate text-slate-300 font-mono text-[11px]" title="Home / Root: ${r.home_path}">
                <span class="text-violet-400 font-sans font-medium text-[10px] uppercase tracking-wider mr-1">Root:</span>${r.home_path}
              </div>
              <div class="flex items-center gap-1 flex-shrink-0">
                <button onclick="copyToClipboard('${r.home_path.replace(/\\\\/g, '\\\\\\\\')}', 'directory')" title="Copy path" class="p-1 hover:text-violet-400 text-slate-400 transition"><i class="fa-regular fa-copy text-xs"></i></button>
                <button onclick="openFolder('${r.home_path.replace(/\\\\/g, '\\\\\\\\')}')" title="Open containing folder" class="p-1 hover:text-violet-400 text-slate-400 transition"><i class="fa-regular fa-folder-open text-xs"></i></button>
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
                <button onclick="copyToClipboard('${r.binary_path.replace(/\\\\/g, '\\\\\\\\')}', 'binary')" title="Copy binary path" class="p-1 hover:text-violet-400 text-slate-400 transition"><i class="fa-regular fa-copy text-xs"></i></button>
                <button onclick="openFolder('${r.binary_path.replace(/\\\\/g, '\\\\\\\\')}')" title="Open containing folder" class="p-1 hover:text-violet-400 text-slate-400 transition"><i class="fa-regular fa-folder-open text-xs"></i></button>
              </div>
            </div>
          `;
        }

        if (!pathsHtml) {
          pathsHtml = '<div class="text-xs text-slate-500 italic">No binary or home path resolved</div>';
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
              ${pathsHtml}

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

    // Initial loads
    loadConfig();
    fetchAudit();
  </script>
</body>
</html>
"""
