# DevToolkit ⚡

> **Extensible Workstation Environment Auditor, Port Manager, and Developer Productivity Suite.**  
> Built for engineers who need instant visibility into their SDKs, compilers, runtimes, listening ports, and project prerequisites — with a lightning-fast CLI and a stunning, responsive desktop UI.

[![Python](https://img.shields.io/badge/Python-3.11%2B-blue?logo=python)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.111%2B-009688?logo=fastapi)](https://fastapi.tiangolo.com)
[![PyWebView](https://img.shields.io/badge/Desktop-PyWebView%20%2F%20WebView2-purple)](https://pywebview.flowrl.com)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](https://opensource.org/licenses/MIT)
[![Release](https://img.shields.io/badge/Release-Standalone%20.exe-emerald)](https://github.com/Bhardvaj/DevToolkit/releases)

---

## 🚀 Key Features

- 🖥️ **Google Stitch Precision Desktop UI**:
  - Native PC software ergonomics (`h-screen overflow-hidden` container, smooth independent scrolling, native window wrapper).
  - Dark Obsidian elevation hierarchy (`#08090C`, `#0E1015`, `#141721`) with sharp `#1F2430` micro-borders.
  - Typography powered by Google `Geist` (structural UI) and `JetBrains Mono` (tabular numbers for paths, PIDs, ports, and versions).
  - Crisp geometric rules: 4px `rounded` corners across all buttons, inputs, tags, and chips with zero pill shapes.
  - Left fixed sidebar with Workspace Hub, real-time watcher status, active PATH entry count, and host telemetry.
  - Top breadcrumbs bar with instant global search (`Ctrl+K`), rescan, and 1-click Markdown/JSON report export.
  - Interactive metric stat cards with 2px progress tracks (*Audited Tools*, *Installed*, *Healthy*, *Action Needed*, *Critical Errors*, *Not Found*).
  - Progressive Server-Sent Events (SSE) streaming with skeleton shimmers for sub-50ms instant first paint.
  - 🔬 **Standardized 7-Zone Deep Tool Inspection**:
    - **Zone 1: Identity & Health Header**: Tool icon, name, category, health status, and live probe latency in ms.
    - **Zone 2: Primary Runtime & Quick Access**: Active binary path, 1-click "Open in Explorer", copy path, and discovery source badge.
    - **Zone 3: Multi-Instance & Precedence Discovery**: Detects all runtime instances via `where.exe`, classifying `Active (PATH)` vs. `Alternate` standby installations.
    - **Zone 4: Environment Variable Alignment Matrix**: Live audit of key environment variables (`JAVA_HOME`, `GOROOT`, `PYTHONPATH`, etc.) with `Aligned`, `Divergent`, or `Missing` indicators.
    - **Zone 5: Subsystems & Ecosystem Status**: Companion tools, package managers, and sub-runtime matrix.
    - **Zone 6: Remediation & Setup Commands**: Copyable terminal commands with a 1-click copy button (safe, non-mutating).
    - **Zone 7: Deep Diagnostics & CLI Telemetry**: Rich CLI diagnostic dumps (`dotnet --info`, `go env -json`, `git config -l --show-origin`), warnings, and JSON telemetry export.
    - **On-Demand Shimmer Loading**: Telemetry loads on-demand via `GET /api/tool/{tool_id}/deep` with skeleton shimmer loaders.
  - Modern Port Manager with Web/Database/Debug categorization, browser opening, process grouping, and protected OS safeguards.
  - Visual Project Auditor with readiness gauge, recent project history chips, and native Windows folder browser picker.

- 🏗️ **Modular Clean Architecture (Phase 6.1)**:
  - Decoupled server design: slim FastAPI application orchestrator (~70 lines).
  - Domain-specific APIRouters: `routes/system.py`, `routes/audit.py`, `routes/ports.py`, `routes/project.py`, `routes/actions.py`.
  - Clean frontend static assets (`devtoolkit/server/static/`) separating `index.html`, `styles.css`, and `app.js` with full syntax highlighting and live development reload.
  - Robust 3-layer template loader (`devtoolkit/server/ui.py`) delivering single-payload offline-capable HTML with zero runtime delay.

- 🔍 **4-Layer Generalized Discovery Pipeline (Zero Hardcoded Paths)**:
  - **Layer 1: Standard PATH & Environment Resolution**: Evaluates runtime binaries and official environment flags (`JAVA_HOME`, `ANDROID_HOME`, `DOCKER_HOST`, etc.).
  - **Layer 2: OS Uninstall Registry Inspection**: Probes 32-bit and 64-bit Windows Uninstall registries (`HKLM` & `HKCU`) to identify custom install directories regardless of PATH registration.
  - **Layer 3: Cross-Tool Ecosystem Discovery**: Inspects parent IDE configuration files (e.g. Android Studio `options/other.xml`, Flutter config, Gradle properties) to discover associated SDKs.
  - **Layer 4: Content Signature Fingerprinting**: Recursively scans user-configured root directories (e.g. `D:\Dev`, `C:\Dev`) for binary fingerprint signatures without rigid directory names.

- 🔌 **Workstation Utilities (Port Manager & Killer)**:
  - Scans all active TCP listening sockets via native operating system APIs.
  - Developer port highlighting for 3000, 5173, 8080, 27017, and more.
  - Hardened system process protection preventing accidental termination of `System`, `svchost.exe`, `csrss.exe`, etc.
  - Safe 1-click process termination with confirmation modal and force override options.

- 📦 **Project Workstation Readiness Auditor**:
  - Automatically parses project manifests: Node (`package.json`), Python (`pyproject.toml`, `requirements.txt`), Flutter (`pubspec.yaml`), Android (`build.gradle`), Docker (`Dockerfile`), Rust (`Cargo.toml`), and Go (`go.mod`).
  - Cross-references project dependencies against workstation SDKs and compilers in real-time.
  - Generates actionable prerequisite checklists with 1-click remediation commands.

- ⚡ **Dual-Mode Executable (`DevToolkit.exe`)**:
  - **Double-Click in Explorer**: Automatically launches the modern Desktop GUI window (or opens your default web browser).
  - **Terminal Invocations**: Seamlessly runs CLI subcommands (`inspect`, `doctor`, `ports`, `project`, `config`, `ui`, `--help`).

---

## 💻 Quick Start

### Option A: Standalone Executable (Recommended for Windows)
Download the latest portable `DevToolkit.exe` from [Releases](https://github.com/Bhardvaj/DevToolkit/releases):
- **Double-click** `DevToolkit.exe` to launch the Desktop GUI.
- Or drop it into your `PATH` to use the terminal CLI:
  ```powershell
  DevToolkit.exe inspect
  DevToolkit.exe ports --dev-only
  DevToolkit.exe project .
  ```

### Option B: From Source (Python 3.11+)

```powershell
# 1. Clone the repository
git clone https://github.com/Bhardvaj/DevToolkit.git
cd DevToolkit

# 2. Create and activate a virtual environment
python -m venv .venv
.\.venv\Scripts\activate

# 3. Install in editable mode with development dependencies
pip install -e ".[dev]"

# 4. Launch the Desktop UI
devtoolkit
```

---

## 🛠️ Complete CLI Command Reference

### 1. Workstation Audit (`devtoolkit inspect`)
Audit all installed SDKs, runtimes, IDEs, and development CLIs:
```powershell
# Full colored table audit
devtoolkit inspect

# Filter by category (runtime, vcs, mobile, container, ide)
devtoolkit inspect --category runtime --category mobile

# Filter by specific tool IDs
devtoolkit inspect --tool node --tool python --tool docker --tool git

# Export audit to JSON (terminal output or file)
devtoolkit inspect --format json
devtoolkit inspect --format json --output audit.json

# Export audit to YAML
devtoolkit inspect --format yaml --output audit.yaml
```

---

### 2. Environment Diagnostics ("Doctor") (`devtoolkit doctor`)
Inspect your environment for misconfigurations, missing SDK paths, broken symlinks, or unset environment variables:
```powershell
devtoolkit doctor
```
Outputs actionable health cards with suggested fix commands (e.g. `setx ANDROID_HOME "D:\Dev\android_sdk"`).

---

### 3. Port Manager & Killer (`devtoolkit ports`)
Inspect active listening TCP sockets and terminate lingering orphan processes:
```powershell
# List all active listening ports
devtoolkit ports

# Filter to common developer ports (3000, 5173, 8080, 27017, etc.)
devtoolkit ports --dev-only

# Quick kill: terminate process on a specific port
devtoolkit ports --kill 3000

# Safely kill port using dedicated subcommand
devtoolkit ports kill 5173

# Force kill system-flagged process (use caution!)
devtoolkit ports kill 8080 --force
```

---

### 4. Project Readiness Auditor (`devtoolkit project`)
Audit any local repository or workspace directory to verify if your workstation satisfies its SDK, runtime, compiler, and environment requirements:
```powershell
# Audit current working directory
devtoolkit project .

# Audit a specific repository directory
devtoolkit project D:\Dev\my-flutter-app

# Output results as structured JSON
devtoolkit project D:\Dev\my-node-app --format json
```

---

### 5. Custom Search Roots (`devtoolkit config`)
Manage Layer-4 recursive content signature directories:
```powershell
# List active custom search directories
devtoolkit config list

# Add a custom root folder where SDKs or portable tools reside
devtoolkit config add-path D:\Dev
devtoolkit config add-path C:\Tools
```

---

### 6. Desktop UI Launcher (`devtoolkit ui`)
Launch the modern graphical interface:
```powershell
# Launch in native desktop window (PyWebView with Edge Chromium backend)
devtoolkit ui

# Open directly in your default web browser
devtoolkit ui --web

# Specify custom port
devtoolkit ui --port 8080
```

> [!TIP]
> Running `devtoolkit` with no arguments or double-clicking `DevToolkit.exe` automatically launches the Desktop UI!

---

## ⌨️ Desktop UI Keyboard Accelerators

| Key Shortcut | Action |
| :--- | :--- |
| <kbd>Ctrl</kbd> + <kbd>K</kbd> | Focus global tool and path search bar |
| <kbd>R</kbd> or <kbd>Ctrl</kbd> + <kbd>R</kbd> | Rescan environment, sockets, and metrics |
| <kbd>1</kbd> | Switch to **Environment & Diagnostics** tab |
| <kbd>2</kbd> | Switch to **Port Manager** tab |
| <kbd>3</kbd> | Switch to **Project Workstation Auditor** tab |
| <kbd>4</kbd> | Switch to **Settings & Preferences** tab |
| <kbd>F</kbd> | Apply all safe environment variable fixes |
| <kbd>?</kbd> | Toggle Keyboard Shortcuts cheat modal |
| <kbd>Esc</kbd> | Close modals or blur active search input |

---

## 🏛️ The 4-Layer Discovery Engine

DevToolkit avoids brittle hardcoded paths. All tools are located using a resilient 4-layer fallback pipeline:

| Layer | Discovery Strategy | Description |
| :--- | :--- | :--- |
| **Layer 1** | Standard Environment | Queries `PATH`, `where.exe`, and conventional environment variables (`ANDROID_HOME`, `JAVA_HOME`, `DOCKER_HOST`, `NVM_HOME`). |
| **Layer 2** | Windows OS Registry | Reads `HKLM` and `HKCU` uninstall keys (both 64-bit and WOW6432Node) to locate installations missed by PATH. |
| **Layer 3** | Cross-Tool Ecosystem | Parses companion configuration files (e.g. Android Studio XML options, Flutter config, Gradle properties). |
| **Layer 4** | Content Signatures | Recursively inspects user-configured root directories (`D:\Dev`, `C:\Dev`) for binary file structures (e.g. `platform-tools/adb.exe`, `bin/javac.exe`). |

---

## 🔌 Authoring a Custom Inspector Plugin

Adding detection for a new SDK or CLI requires fewer than 25 lines of Python code in `devtoolkit/modules/inspectors/<tool>.py`:

```python
from devtoolkit.core.base import BaseInspector
from devtoolkit.core.models import ToolReport, HealthStatus
from devtoolkit.core.runner import SafeRunner

class DenoInspector(BaseInspector):
    id = "deno"
    name = "Deno Runtime"
    category = "runtime"
    categories = ["runtime", "web"]
    description = "Secure JavaScript and TypeScript runtime"

    def inspect(self, runner: SafeRunner) -> ToolReport:
        deno_bin = runner.resolve_binary("deno")
        if not deno_bin:
            return ToolReport(id=self.id, name=self.name, category=self.category, installed=False)

        res = runner.run_command([str(deno_bin), "--version"])
        return ToolReport(
            id=self.id,
            name=self.name,
            category=self.category,
            categories=self.categories,
            installed=True,
            version=res.stdout.split()[1] if res.ok and len(res.stdout.split()) > 1 else None,
            binary_path=str(deno_bin),
            status=HealthStatus.HEALTHY if res.ok else HealthStatus.WARNING,
        )
```

The plugin will be auto-discovered by `PluginRegistry` dynamically on the next audit!

---

## 🧪 Testing

Run the comprehensive unit test suite:
```powershell
pytest -v
```

---

## 📦 Building Standalone Portable Binary

Compile `DevToolkit.exe` locally using PyInstaller:
```powershell
powershell -ExecutionPolicy Bypass -File scripts/build_standalone.ps1
```
The output binary will be generated at `dist/DevToolkit.exe` (~20 MB), containing the embedded UI, FastAPI server, PyWebView runtime, and all inspectors in a single zero-dependency file.

---

## 🧠 AI Agent Knowledge Base

To ensure seamless context retention for contributors and AI pair programmers:
- [`agent/documentation.md`](./agent/documentation.md): Master Software Reference & Technical Manual.
- [`agent/map.md`](./agent/map.md): Architectural topology, lifecycles, and component boundaries.
- [`agent/codebase.md`](./agent/codebase.md): Living registry of classes, functions, and data schemas.
- [`agent/decisions.md`](./agent/decisions.md): Architecture Decision Records (ADRs).
- [`agent/state.md`](./agent/state.md): Active task status and session memory.

---

## 📄 License

MIT © Bhardvaj
