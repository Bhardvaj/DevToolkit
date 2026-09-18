# Architecture Decision Records (ADR)

This file tracks major architectural choices, technical decisions, and trade-offs made during the evolution of `DevToolkit`.

---

## ADR-0001: Core Architecture & Presentation Decoupling
- **Date**: 2026-09-16
- **Status**: Accepted
- **Context**: The project requires both a responsive CLI and a modern, aesthetically pleasing UI with easy UX. Traditional Python GUI frameworks (Tkinter, PyQt, wxPython) are heavy and visually dated.
- **Decision**: Decouple the Core Engine (responsible for discovery, subprocess management, registry, and health checks) from the Presentation Layer. Enable both CLI operation and modern Web/Desktop UI without coupling business logic to GUI frameworks.
- **Consequences**:
  - Inspectors can be tested headlessly via standard unit tests.
  - Front-end developers or agents can build and iterate on modern UI components using web technologies (React/Tailwind) without wrestling with native desktop GUI toolkits.

---

## ADR-0002: Non-Blocking Subprocess Probe Timeouts
- **Date**: 2026-09-16
- **Status**: Accepted
- **Context**: Running external CLI binaries (`--version`) can hang indefinitely if a tool attempts an interactive prompt, network license check, or gets stuck in a broken pipe.
- **Decision**: All process probes must execute strictly through `SafeRunner` with a mandatory maximum timeout (default 3.0 seconds) and non-blocking stream capture.
- **Consequences**: The inspector is guaranteed never to hang, regardless of local environment misconfigurations.

---

## ADR-0003: Dynamic Plugin Discovery Pattern
- **Date**: 2026-09-16
- **Status**: Accepted
- **Context**: DevToolkit needs to support third-party or future modules (cache cleaners, port killers, environment variable editors) without modifying the core discovery loop.
- **Decision**: Implement a dynamic provider registry pattern. Modules placed in `devtoolkit/modules/` implementing `BaseInspector` or `BaseUtility` are registered dynamically via module scanning.
- **Consequences**: Adding new tool support is isolated to single-file additions with zero merge conflicts on core files.

---

## ADR-0004: Python + React/Tailwind Hybrid Architecture (PyWebView & FastAPI)
- **Date**: 2026-09-16
- **Status**: Accepted
- **Context**: The user requires a modern, beautiful UI with easy UX alongside maximum plugin authoring ergonomics ("Ultra-Extensible") and zero heavyweight runtime overhead.
- **Decision**: Adopt the Python Desktop + Web Hybrid architecture. The Core Engine and plugin system run in Python 3.14. The UI is built using React + Tailwind CSS + Lucide Icons, served locally via FastAPI and rendered in a native desktop window via PyWebView (Edge WebView2). The engine also directly powers the CLI (`devtoolkit inspect`) and local browser dashboard (`devtoolkit ui`).
- **Consequences**:
  - Zero additional SDK installations required (Python 3.14 and Node 24 already present).
  - Plugin creation remains as simple as writing a single ~15-line Python file.
  - Desktop memory usage is kept light (~40MB vs Electron's 150MB+).

---

## ADR-0005: 4-Layer Generalized Discovery Pipeline
- **Date**: 2026-09-17
- **Status**: Accepted
- **Context**: Hardcoding custom filesystem paths (like `D:\Dev\` or `C:\Dev\`) is an anti-pattern: it breaks portability, fails across different machines, and creates brittle assumptions.
- **Decision**: Implement a 4-Layer Discovery Pipeline:
  1. Standard OS Environment (PATH, official environment variables).
  2. Dynamic OS Application Inventory (Windows Registry Uninstall & App Paths hives).
  3. Cross-Tool Ecosystem Metadata (Flutter machine config, Android Studio APPDATA options XMLs, Gradle properties).
  4. User-Configured Search Roots (`~/.devtoolkit/config.yaml`) with Structural Content Signatures (detecting tools by binary fingerprints, not folder names).
- **Consequences**:
  - Tool detection works automatically on any machine, partition, or drive layout.
  - Zero hardcoded paths in core engine or inspector plugins.
  - Users can easily monitor arbitrary custom directories via `devtoolkit config add-path <dir>` or the UI.

---

## ADR-0006: Native Windows Socket & Process Management with Zero Extra Dependencies
- **Date**: 2026-09-17
- **Status**: Accepted
- **Context**: Port inspection and process termination typically pull in heavy third-party C-extensions like `psutil`, which complicate cross-compilation, Python 3.14 wheels, and single-file bundling.
- **Decision**: Use standard OS built-in commands (`netstat -ano -p tcp`, `tasklist /FO CSV`, `taskkill /PID <pid> /F`) routed through `SafeRunner` (and `lsof` / `kill` on Unix). Maintain a whitelist of critical Windows system processes (`System`, `svchost.exe`, `csrss.exe`, etc.) to prevent accidental termination.
- **Consequences**:
  - Zero new pip dependencies introduced.
  - 100% portable on vanilla Windows installations.
  - High performance with execution time < 100ms.

---

## ADR-0007: Multi-Ecosystem Repository Manifest Inspection
- **Date**: 2026-09-17
- **Status**: Accepted
- **Context**: Developers need to know whether their machine can build a cloned project without having to run builds and fail cryptically halfway through.
- **Decision**: Implement `ProjectAuditor` to inspect declarative project manifests (`package.json`, `pyproject.toml`, `pubspec.yaml`, `build.gradle`, `Dockerfile`, `Cargo.toml`, `go.mod`). Match requirements against the machine's live audit summary gathered from `PluginRegistry`. Output structured requirement checks (`RequirementCheck`) with actionable setup commands.
- **Consequences**:
  - Provides a fast, non-mutating readiness check before compilation or running scripts.
  - Generates clear, copy-pasteable terminal commands to resolve missing dependencies.

---

## ADR-0008: Server Decomposition & Pure Static Frontend Asset Separation
- **Date**: 2026-09-18
- **Status**: Accepted
- **Context**: `devtoolkit/server/app.py` grew into a 3,160-line monolith containing API endpoints, Pydantic models, inline HTML layout strings, embedded CSS, and 1,800+ lines of raw inline JavaScript. This degraded maintainability, prevented linting/syntax highlighting, and made incremental UI work fragile.
- **Decision**: Decompose the server module into domain-driven components:
  1. `models.py`: Dedicated API request and response schemas.
  2. `routes/`: Modular APIRouters (`system.py`, `audit.py`, `ports.py`, `project.py`, `actions.py`).
  3. `ui.py`: Robust 3-layer template engine (`importlib.resources` -> `sys._MEIPASS` -> filesystem) with zero runtime dependencies.
  4. `static/`: Pure `index.html`, `styles.css`, and `app.js` with full syntax highlighting.
  5. `app.py`: Clean 134-line coordinator with full backward-compatibility re-exports.
- **Consequences**:
  - Full IDE syntax highlighting, formatting, and static analysis for HTML/CSS/JS.
  - Single-payload, zero-latency inlining preserved at serve-time for 100% offline desktop reliability.
  - Core codebase modularity drastically improved without changing UI or behavior.

---

## ADR-0009: On-Demand Deep Tool Inspection & Standardized 7-Zone Process Flow
- **Date**: 2026-09-18
- **Status**: Accepted
- **Context**: In Phase 5, tool card clicks revealed basic details, but lacked deep insight into multi-instance conflicts (e.g. multiple Python/Node versions on PATH vs Program Files or zip extracts), environment variable alignment (`JAVA_HOME`, `GOROOT`, `DOTNET_ROOT`), raw CLI diagnostics (`dotnet --info`, `go env`), and actionable copyable commands. Furthermore, running comprehensive diagnostic sub-commands on every tool during baseline audit would severely slow down initial page load.
- **Decision**:
  1. Standardize a consistent 7-Zone Process Flow layout inside the slide-over Inspector Drawer:
     - Zone 1: Identity & Health Header (icon, title, status, version, category, latency).
     - Zone 2: Primary Runtime & Quick Access (path, folder open, copy path, source).
     - Zone 3: Multi-Instance & Precedence Discovery (active PATH vs alternates with source badges).
     - Zone 4: Environment Variable Alignment Matrix (aligned, divergent, missing with expected targets).
     - Zone 5: Subsystems & Ecosystem Status (companion tools, versions, availability).
     - Zone 6: Remediation & Setup Commands (strictly copyable terminal commands with 1-click copy button, no 1-click system mutation).
     - Zone 7: Deep Diagnostics & CLI Telemetry (tabs for diagnostic CLI dumps, security/perf warnings, raw JSON export).
  2. Implement an on-demand REST endpoint `GET /api/tool/{tool_id}/deep` triggered only upon opening the drawer. Initial page load remains ultra-fast (<50ms via SSE), while the drawer shows an animated shimmer skeleton until deep telemetry arrives.
- **Consequences**:
  - Fast baseline dashboard startup is completely preserved.
  - Multi-instance conflicts and path shadowing are immediately visible and actionable.
  - Safe user control: no automatic system mutations without explicit terminal review.


