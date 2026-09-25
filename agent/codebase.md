# Living Codebase Registry & API Guide

This document maintains an authoritative, living catalog of all modules, base classes, public interfaces, and extension points within `DevToolkit`.

---

## 1. Directory Structure

```
DevToolkit/
├── pyproject.toml                     # Package metadata, dependencies, scripts, entry points
├── README.md                          # Main developer & user documentation
├── .gitignore                         # Tailored exclusions for Python, Node, OS, logs, daemon.json
├── devtoolkit.config.yaml             # Portable user settings & monitored search paths
├── daemon.log                         # Rotating background daemon service log (auto-created)
├── client.log                         # Rotating embedded UI/desktop client log (auto-created)
├── agent/                             # Persistent AI agent knowledge base & session memory
│   ├── map.md                         # Architecture blueprints, lifecycles, execution flows
│   ├── codebase.md                    # Living registry of classes, interfaces, and modules
│   ├── decisions.md                   # Architecture Decision Records (ADRs)
│   ├── documentation.md               # Master Software Reference & Technical Manual
│   └── state.md                       # Session memory, checklist, and roadmap
├── assets/                            # Brand assets compiled into binary
│   ├── icon.ico                       # Multi-resolution Windows executable and tray icon (16-256px)
│   └── icon.png                       # High-resolution PNG logo
├── design/                            # Source UI/UX design specifications
│   ├── DESIGN.md                      # Obsidian design system guidelines
│   ├── Icon_design/                   # HTML/CSS code & screen for static icon
│   └── Icon_loading_design/           # HTML/CSS code & screen for loading icon
├── devtoolkit/                        # Core Python package
│   ├── __init__.py                    # Version declaration
│   ├── __main__.py                    # CLI forwarding to devtoolkit.entry:main
│   ├── entry.py                       # Unified windowless entry point (PE GUI subsystem)
│   ├── client/                        # Decoupled Client Presentation SDK
│   │   ├── __init__.py
│   │   ├── api.py                     # DevToolkitClient: HTTP REST & SSE communication layer
│   │   ├── desktop.py                 # PyWebView Edge Chromium desktop window runner
│   │   └── state.py                   # ClientStateStore: Reactive in-memory state store
│   ├── daemon/                        # Background Daemon Service & Native System Tray
│   │   ├── __init__.py
│   │   ├── activity.py                # ActivityTracker: Thread-safe scan & index progress
│   │   ├── manager.py                 # Detached process spawner & daemon.json state lifecycle
│   │   ├── models.py                  # DaemonState, DaemonStatusResponse
│   │   ├── server.py                  # DaemonServer: Headless lifespan & tray coordinator
│   │   └── tray.py                    # Pure Win32 ctypes system tray (Shell_NotifyIcon)
│   ├── core/                          # Engine kernel & discovery pipeline
│   │   ├── __init__.py
│   │   ├── base.py                    # BaseInspector (inspect, deep_inspect) & BaseUtility
│   │   ├── config.py                  # Portable configuration management (devtoolkit.config.yaml)
│   │   ├── discovery.py               # Unified 4-layer DiscoveryPipeline coordinator
│   │   ├── ecosystem.py               # Layer 3: Cross-tool ecosystem config resolvers
│   │   ├── inventory.py               # Layer 2: OS Application Inventory & Registry scanner
│   │   ├── logging.py                 # Centralized co-located logging (daemon.log, client.log)
│   │   ├── models.py                  # Core Pydantic schemas (ToolReport, DiscoveredInstance)
│   │   ├── registry.py                # PluginRegistry: Dynamic auto-discovery & deep inspection
│   │   ├── runner.py                  # SafeRunner: Subprocess execution, timeouts & where.exe
│   │   ├── search/                    # Standalone Everything-class search engine
│   │   │   ├── __init__.py            # Exports FastSearchEngine, SearchIndex, SearchResult
│   │   │   ├── crawler.py             # Parallel multi-threaded Win32 pruned directory crawler
│   │   │   ├── engine.py              # FastSearchEngine coordinator & fallback resolution
│   │   │   ├── index.py               # Compact in-memory search index with O(1) hash maps
│   │   │   ├── models.py              # SearchResult, SearchQuery, IndexStats
│   │   │   ├── usn.py                 # NTFS USN Journal reader (FSCTL_ENUM_USN_DATA)
│   │   │   └── watcher.py             # LiveDirectoryWatcher (Win32 ReadDirectoryChangesW)
│   │   └── signatures.py              # Layer 4: Structural signature matchers across all 22 tools
│   ├── cli/                           # Command-line interface (Typer + Rich)
│   │   ├── __init__.py
│   │   └── main.py                    # `inspect`, `doctor`, `ports`, `project`, `config`, `daemon`
│   ├── formatters/                    # Output formatting layer
│   │   ├── json_fmt.py                # Machine-readable JSON output
│   │   ├── table.py                   # Rich console tables and health badge formatting
│   │   └── yaml_fmt.py                # Machine-readable YAML output
│   ├── modules/
│   │   ├── inspectors/                # 22 Pluggable tool inspectors across 9 categories
│   │   │   ├── android.py             # Android SDK, adb, emulator, build-tools, platforms
│   │   │   ├── android_studio.py      # Android Studio IDE, launcher, and bundled JBR
│   │   │   ├── bun.py                 # Bun JS runtime & package manager
│   │   │   ├── cmake.py               # CMake build system
│   │   │   ├── c_compiler.py          # C/C++ compilers (MSVC cl.exe, GCC, Clang)
│   │   │   ├── cuda.py                # NVIDIA CUDA Toolkit & nvcc compiler
│   │   │   ├── docker.py              # Docker CLI, Docker Compose, engine daemon check
│   │   │   ├── dotnet.py              # .NET SDK, CLI, runtimes & workloads
│   │   │   ├── flutter.py             # Flutter SDK, Dart SDK, release channel
│   │   │   ├── gh.py                  # GitHub CLI (gh), authentication & extensions
│   │   │   ├── git.py                 # Git, global user config, credential helpers
│   │   │   ├── golang.py              # Go compiler, GOPATH, GOROOT
│   │   │   ├── java.py                # Java JVM, javac (JDK), JAVA_HOME, bundled JBR
│   │   │   ├── kubectl.py             # Kubernetes CLI & cluster contexts
│   │   │   ├── node.py                # Node.js, npm, pnpm, yarn, corepack
│   │   │   ├── ollama.py              # Ollama local LLM runtime & models
│   │   │   ├── php.py                 # PHP runtime & Composer package manager
│   │   │   ├── python.py              # Python, pip, uv, poetry, conda, pipenv
│   │   │   ├── rust.py                # Rustc, Cargo, rustup toolchain
│   │   │   ├── sqlite.py              # SQLite3 CLI & shell
│   │   │   ├── terraform.py           # Terraform infrastructure CLI
│   │   │   └── vscode.py              # Visual Studio Code editor & extensions
│   │   └── utilities/                 # Active developer workstation utilities
│   │       ├── ports.py               # PortManager & PortKiller: socket scanner & process killer
│   │       └── project_auditor.py     # ProjectAuditor: repository requirements vs readiness
│   └── server/                        # Modular FastAPI UI & API layer
│       ├── __init__.py
│       ├── app.py                     # Decoupled server orchestrator & search warmup
│       ├── models.py                  # API request & response Pydantic models
│       ├── ui.py                      # 3-layer template engine (resources -> MEIPASS -> disk)
│       ├── routes/                    # Domain-driven route controllers
│       │   ├── actions.py             # Native Explorer launcher & folder picker dialog
│       │   ├── audit.py               # Environment audit, SSE streaming & deep inspection
│       │   ├── ports.py               # Port listing & socket termination
│       │   ├── project.py             # Workspace readiness inspection
│       │   ├── search.py              # Fast Search query, telemetry, reindex, & realtime toggle
│       │   └── system.py              # Host telemetry, daemon activity, & search path config
│       └── static/                    # Google Stitch pure static frontend assets
│           ├── __init__.py
│           ├── app.js                 # Complete client logic, SSE handler, & search views
│           ├── index.html             # Clean semantic layout structure
│           └── styles.css             # Modular stylesheet & 7-zone inspector drawer styling
├── scripts/
│   ├── build_standalone.ps1           # Automated standalone PyInstaller .exe packaging
│   └── generate_icons.py              # Multi-resolution ICO and PNG generation utility
├── tests/                             # Comprehensive automated test suite (234 passing tests)
│   ├── conftest.py                    # Session test isolation (DEVTOOLKIT_TESTING=1)
│   ├── test_activity.py               # Tests for ActivityTracker state mutations
│   ├── test_batch1_inspectors.py      # Tests for Batch 1 inspectors
│   ├── test_batch2_inspectors.py      # Tests for Batch 2 inspectors
│   ├── test_client_api.py             # Tests for DevToolkitClient REST & SSE calls
│   ├── test_client_state.py           # Tests for ClientStateStore reactive state
│   ├── test_config.py                 # Tests for portable config & search path mutations
│   ├── test_daemon.py                 # Tests for DaemonServer, manager, & portable state
│   ├── test_deep_inspection.py        # Tests for Phase 7 deep inspection models & endpoints
│   ├── test_discovery.py              # Tests for unified DiscoveryPipeline
│   ├── test_entry.py                  # Tests for entrypoint argument dispatch
│   ├── test_inspectors.py             # Tests for tool inspection logic
│   ├── test_inventory.py              # Tests for OS application inventory
│   ├── test_logging.py                # Tests for co-located rotating file logging
│   ├── test_ports.py                  # Tests for PortManager socket discovery & protection
│   ├── test_project_auditor.py        # Tests for ProjectAuditor multi-manifest verification
│   ├── test_registry.py               # Tests for dynamic plugin discovery & filtering
│   ├── test_runner.py                 # Tests for SafeRunner timeouts & multi-binary resolution
│   ├── test_search_engine.py          # Tests for FastSearchEngine, SearchIndex, and USN reader
│   ├── test_search_query.py           # Tests for search query parser and category filters
│   ├── test_search_watcher.py         # Tests for LiveDirectoryWatcher & real-time sync
│   ├── test_server.py                 # Tests for FastAPI server endpoints & re-indexing
│   ├── test_signatures.py             # Tests for content signature detection
│   ├── test_tool_spec_validation.py   # Specification & contract tests across all 22 tools
│   └── test_tray.py                   # Tests for system tray notification helpers
└── dist/
    ├── DevToolkit.exe                 # Single-file portable executable (28.5 MB, Windowless GUI)
    ├── devtoolkit.config.yaml         # Co-located user configuration
    └── assets/                        # Co-located icon assets
```

---

## 2. Core Public APIs & Modules

### Unified Entry Point ([`devtoolkit/entry.py`](file:///D:/UtilitySoftware/devtoolkit/entry.py))
- `main(argv=None) -> int`: Single application entry point. Handles:
  - HWND-based single-instance detection on Windows (`find_existing_window`, `restore_window_by_hwnd`).
  - Terminal console attachment via `kernel32.AttachConsole(-1)` when invoked with CLI commands.
  - Starting the detached background daemon if not already alive.
  - Spawning the PyWebView desktop window.
  - Supporting flags: `--headless`, `--web-only`, `--port <int>`, `--version`, `--help`.

### Background Daemon Service ([`devtoolkit/daemon/`](file:///D:/UtilitySoftware/devtoolkit/daemon/))
- `devtoolkit.daemon.server.DaemonServer`: Coordinates FastAPI server lifespan, background search engine warmup, and pure Win32 system tray.
- `devtoolkit.daemon.manager`:
  - `start_daemon(port, host) -> DaemonState`: Spawns detached daemon with `CREATE_NO_WINDOW = 0x08000000 | DETACHED_PROCESS`.
  - `stop_daemon() -> bool`: Gracefully stops active daemon by PID.
  - `get_daemon_status() -> DaemonStatusResponse`: Probes daemon health via PID check and HTTP ping.
  - `get_daemon_state_path() -> Path`: Returns `daemon.json` path beside `devtoolkit.config.yaml`.
- `devtoolkit.daemon.activity.ActivityTracker`:
  - Thread-safe tracking of background operations (`is_scanning`, `is_indexing`, messages, timestamps, counts).
  - Queried via `GET /api/daemon/activity` and synced with system tray status.
- `devtoolkit.daemon.tray.SystemTrayIcon`:
  - Native Win32 `Shell_NotifyIconW` notification tray icon using custom static icon.
  - Context menu with live spinner indicators: Open Dashboard, Re-scan Environment, Search Engine Re-index, Documentation, Exit.

### Client Presentation SDK ([`devtoolkit/client/`](file:///D:/UtilitySoftware/devtoolkit/client/))
- `DevToolkitClient(base_url)`:
  - `get_system()`, `get_tools()`, `get_audit()`, `stream_audit(on_chunk)`
  - `get_deep_telemetry(tool_id)`
  - `get_ports()`, `kill_port(port, force)`
  - `audit_project(path)`
  - `get_search_status()`, `search_query(params)`, `trigger_reindex(roots)`
- `ClientStateStore`: Observable reactive state store with listeners for multi-client UI development.
- `devtoolkit.client.desktop.launch_desktop_window(port, title)`: Launches PyWebView Edge Chromium window configured with native window styling and close-action interception.

### Fast Search Engine ([`devtoolkit/core/search/`](file:///D:/UtilitySoftware/devtoolkit/core/search/))
- `FastSearchEngine`:
  - `index_roots(roots)`: Multi-threaded hybrid indexing using NTFS USN Journal (elevated) or `ParallelPrunedCrawler`.
  - `search(query) -> List[SearchResult]`: Sub-millisecond indexed queries with category, size, date, regex, and pattern matching.
  - `enable_realtime(bool)`: Activates `LiveDirectoryWatcher` on active roots.
  - `get_telemetry() -> Dict`: Telemetry including memory usage, process RAM (`K32GetProcessMemoryInfo`), status, and active watchers.
- `SearchIndex`: Compact in-memory array and hash map (`_path_map`) with O(1) mutations and swap-with-last deletion.

### Portable Configuration & Logging ([`devtoolkit/core/`](file:///D:/UtilitySoftware/devtoolkit/core/))
- `devtoolkit.core.config`:
  - `get_app_dir() -> Path`: Returns executable folder when frozen (`sys.frozen`), else current working directory.
  - `get_config_path() -> Path`: Resolves `devtoolkit.config.yaml` strictly beside executable.
  - `load_config() -> DevToolkitConfig`, `save_config(config)`.
  - `add_search_path(path)`, `remove_search_path(path)`.
- `devtoolkit.core.logging`:
  - `setup_daemon_logging(level) -> Path`: Sets up rotating `daemon.log` (5 MB, 3 backups) beside config file.
  - `setup_client_logging(level) -> Path`: Sets up rotating `client.log` beside config file.

---

## 3. Discovery Pipeline & Tool Inspection API

### Core Models ([`devtoolkit/core/models.py`](file:///D:/UtilitySoftware/devtoolkit/core/models.py))
- `ToolReport`: Baseline audit record (id, name, categories, installed, status, version, home_path, binary_path, diagnostics).
- `DiscoveredInstance`: Discovered binary instance on disk (path, version, is_active, source).
- `EnvVarStatus`: Environment variable audit (name, value, expected_target, status: `aligned` | `divergent` | `missing`).
- `DeepTelemetryReport`: High-resolution telemetry payload returned during 7-zone drawer expansion.

### Base Inspector Abstraction ([`devtoolkit/core/base.py`](file:///D:/UtilitySoftware/devtoolkit/core/base.py))
- `BaseInspector.inspect(runner: SafeRunner) -> ToolReport`: Fast baseline probe with strict non-blocking timeout.
- `BaseInspector.deep_inspect(runner: SafeRunner, base_report: Optional[ToolReport]) -> DeepTelemetryReport`: Standard 7-zone deep telemetry probe across all 22 inspectors.

### Discovery Pipeline Coordinator ([`devtoolkit/core/discovery.py`](file:///D:/UtilitySoftware/devtoolkit/core/discovery.py))
- `DiscoveryPipeline`: Coordinates Layer 1 (PATH/Env), Layer 2 (Windows Registry via `OSInventory`), Layer 3 (Cross-tool ecosystem via `EcosystemResolvers`), and Layer 4 (FastSearchEngine structural content signatures).
