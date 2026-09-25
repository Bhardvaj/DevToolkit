# DevToolkit Clients Architecture & Integration Hub ⚡

> **Decoupled Client Ecosystem**: This directory serves as the architecture hub and workspace for frontends, desktop clients, terminal user interfaces (TUIs), and custom dashboard applications that consume data and endpoints provided by the **DevToolkit** background daemon.

---

## 🏛️ Decoupled Architecture Overview

DevToolkit is engineered with a strict separation of concerns between its core data engine and client presentation layers:

```
┌────────────────────────────────────────────────────────────────────────┐
│                        DevToolkit Core Daemon                          │
│        (FastAPI + Uvicorn + 4-Layer Discovery + Sockets + USN)         │
│                 REST Endpoints  •  SSE Event Stream                    │
└───────────────────▲────────────────────────────────▲───────────────────┘
                    │                                │
                    ▼                                ▼
       ┌─────────────────────────┐      ┌─────────────────────────┐
       │   Embedded Desktop UI   │      │   Web Browser Dashboard │
       │ (PyWebView + Stitch UI) │      │ (http://127.0.0.1:4321) │
       └─────────────────────────┘      └─────────────────────────┘
                    │                                │
                    └────────────────┬───────────────┘
                                     │
                    ┌────────────────┴────────────────┐
                    │                                 │
                    ▼                                 ▼
       ┌─────────────────────────┐      ┌─────────────────────────┐
       │   Python Client SDK     │      │   Custom Client Apps    │
       │  (`devtoolkit.client`)  │      │ (clients/*: TUI, React) │
       └─────────────────────────┘      └─────────────────────────┘
```

1. **Headless Background Daemon**: Runs locally on `http://127.0.0.1:4321` (configurable) as a detached background service or system tray process.
2. **REST & Streaming API**: Standardized HTTP endpoints and Server-Sent Events (SSE) stream tool discoveries, active ports, project readiness, and filesystem searches.
3. **Decoupled Clients**: Any UI framework, scripting environment, or desktop tool can connect to the daemon to render real-time workstation insights.

---

## 📦 Python Client SDK (`devtoolkit.client`)

For Python-based clients, utilities, and scripts, DevToolkit provides a zero-dependency, standard-library-based HTTP client and reactive state store:

```python
from devtoolkit.client import DevToolkitClient, ClientState

# 1. Initialize client connected to daemon
client = DevToolkitClient(port=4321, host="127.0.0.1")

# 2. Check daemon liveness
if client.is_alive():
    print("✓ Connected to DevToolkit Daemon")

# 3. Synchronous data retrieval
tools = client.get_tools()
ports = client.get_ports(dev_only=True)
project_audit = client.run_project_audit("D:/MyProject")

# 4. Asynchronous worker dispatch with callbacks
client.run_async(
    task=lambda: client.get_tool_deep("node"),
    callback=lambda report: print(f"Node telemetry: {report['version']}"),
    errback=lambda err: print(f"Audit error: {err}")
)
```

### Observable Reactive Store (`ClientState`)
```python
state = ClientState()

# Subscribe to tool updates
state.subscribe("tools", lambda tools: print(f"Received {len(tools)} tools"))

# Mutate state (thread-safe, notifies subscribers)
state.set_tools(tools)
```

---

## 🌐 Daemon Endpoints Reference

All client applications can interact directly with the DevToolkit daemon via standard HTTP requests:

### 1. System Telemetry & Liveness
- `GET /api/system` - Workstation hostname, OS, release, machine architecture, Python version.
- `GET /api/system/health` - Daemon health status, active worker threads, and uptime.
- `POST /api/system/close-action` - Set window close behavior (`ask`, `minimize`, `exit`).

### 2. Workstation Tool Audit & Diagnostics
- `GET /api/audit` - Retrieve all audited SDKs, compilers, runtimes, and development CLIs.
- `POST /api/audit` - Trigger an immediate background environment re-scan.
- `GET /api/audit/stream` - Progressive Server-Sent Events (SSE) stream emitting audited tools as they resolve in real-time.
- `GET /api/tool/{tool_id}/deep` - Retrieve 7-zone deep telemetry (multi-instances, environment variables, subsystems, diagnostic dumps).

### 3. Sockets & Port Manager
- `GET /api/ports` - Active TCP listening sockets, PIDs, process names, and developer port tags.
- `POST /api/ports/kill/{port}` - Terminate the process listening on the specified port.
  - Body: `{"force": true}` (safeguards protect core Windows OS services).

### 4. Project Readiness Auditor
- `POST /api/project/audit` - Audit workspace directory against workstation toolchains.
  - Body: `{"path": "D:/Dev/my-repo"}`
  - Returns: Build readiness boolean, detected project frameworks, prerequisites checklist, and remediation commands.

### 5. Fast Filesystem Search Engine
- `POST /api/search/query` - Execute high-speed search across indexed developer roots.
  - Body: `{"query": "main.py", "regex": false, "case_sensitive": false, "full_path": false}`
- `GET /api/search/status` - Search engine status, total indexed files, RAM consumption, and live watcher status.
- `POST /api/search/reindex` - Trigger an asynchronous re-indexing of all configured search roots.
- `POST /api/search/realtime` - Toggle Win32 real-time filesystem watcher updates.

### 6. Desktop System Actions
- `POST /api/action/open-file` - Open a file using the operating system's default handler (`{"path": "..."}`).
- `POST /api/action/reveal-file` - Open File Explorer with the specified file selected (`{"path": "..."}`).
- `POST /api/action/open-folder` - Open containing folder in File Explorer (`{"path": "..."}`).
- `POST /api/action/select-folder` - Launch native OS folder chooser dialog.
- `POST /api/daemon/notify` - Display native system tray balloon notification (`{"title": "...", "message": "..."}`).

---

## 🛠️ Adding a New Client Application

To add a new UI application or dashboard inside `clients/`:

1. Create a dedicated directory under `clients/` (e.g. `clients/terminal-tui/`, `clients/desktop-qt/`, or `clients/web-mobile/`).
2. Implement your UI using any technology stack:
   - **Terminal User Interface (TUI)**: e.g. using Python `Textual` or `Rich`.
   - **Modern Web**: React, Vue, Svelte, or Next.js communicating with the daemon's REST/SSE API.
   - **Desktop UI**: Qt/QML (PySide6), Flutter, or Electron.
3. Include a `README.md` and startup script in your client directory detailing how to launch and connect to the daemon.
