# Living Codebase Registry & API Guide

This document maintains a living catalog of all modules, base classes, public interfaces, and extension points within `DevToolkit`.

---

## 1. Directory Structure

```
DevToolkit/
├── pyproject.toml                     # Package metadata, dependencies, scripts
├── README.md                          # Main developer & user documentation
├── .gitignore                         # Tailored exclusions for Python, Node, OS, IDE
├── agent/                             # Persistent AI agent knowledge base & session memory
│   ├── map.md                         # Architecture blueprints, lifecycles, execution flows
│   ├── codebase.md                    # Living registry of classes, interfaces, and modules
│   ├── decisions.md                   # Architecture Decision Records (ADRs)
│   ├── documentation.md               # Master Software Reference & Technical Manual
│   └── state.md                       # Session memory, checklist, and roadmap
├── devtoolkit/                        # Core Python package
│   ├── __init__.py
│   ├── __main__.py                    # Entrypoint for `python -m devtoolkit`
│   ├── core/                          # Engine kernel & discovery pipeline
│   │   ├── base.py                    # BaseInspector (inspect, deep_inspect) & BaseUtility abstractions
│   │   ├── config.py                  # User configuration management (~/.devtoolkit/config.yaml)
│   │   ├── discovery.py               # Unified 4-layer DiscoveryPipeline coordinator
│   │   ├── ecosystem.py               # Layer 3: Cross-tool ecosystem config resolvers (Studio, Flutter, Gradle)
│   │   ├── inventory.py               # Layer 2: OS Application Inventory & Windows Registry scanner
│   │   ├── models.py                  # Pydantic schemas (ToolReport, DiscoveredInstance, EnvVarStatus, DeepTelemetryReport)
│   │   ├── runner.py                  # SafeRunner: Subprocess execution with timeouts, path resolution & multi-instance discovery
│   │   ├── registry.py                # PluginRegistry: Dynamic inspector auto-discovery, multithreading & deep inspection
│   │   └── signatures.py              # Layer 4: Structural content signature matchers
│   ├── cli/                           # Command-line interface (Typer)
│   │   └── main.py                    # `devtoolkit inspect`, `devtoolkit doctor`, `devtoolkit ui`, `devtoolkit config`, `devtoolkit ports`, `devtoolkit project`
│   ├── formatters/                    # Output formatting layer
│   │   ├── table.py                   # Rich console tables and health badge formatting
│   │   ├── json_fmt.py                # Machine-readable JSON output
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
│   │       ├── ports.py               # PortManager & PortKiller: socket scanner & safe process killer
│   │       └── project_auditor.py     # ProjectAuditor: repository requirements vs machine readiness
│   └── server/                        # Modular FastAPI UI & API layer (Phase 6.1 refactored)
│       ├── __init__.py
│       ├── app.py                     # Decoupled server entrypoint & PyWebView desktop launcher
│       ├── models.py                  # API request & response Pydantic models
│       ├── ui.py                      # 3-layer template engine (importlib.resources -> _MEIPASS -> disk)
│       ├── routes/                    # Domain-driven route controllers
│       │   ├── actions.py             # Native Explorer launcher, folder picker dialog, fix executor
│       │   ├── audit.py               # Environment audit, SSE streaming generator & deep inspection
│       │   ├── ports.py               # Port listing & socket termination
│       │   ├── project.py             # Workspace readiness inspection
│       │   └── system.py              # Host telemetry & search path management
│       └── static/                    # Google Stitch pure static frontend assets
│           ├── __init__.py
│           ├── index.html             # Clean semantic layout structure
│           ├── styles.css             # Modular stylesheet & 7-zone inspector drawer styling
│           └── app.js                 # Complete client logic & 7-zone deep inspection drawer
├── scripts/
│   └── build_standalone.ps1           # Automated standalone PyInstaller .exe packaging
├── .github/
│   └── workflows/
│       └── build.yml                  # GitHub Actions CI for test, packaging & release
└── tests/                             # Automated test suite (156 passing unit tests)
    ├── test_batch1_inspectors.py      # Tests for Batch 1 inspectors (VS Code, .NET, Bun, GH, CMake, Ollama)
    ├── test_batch2_inspectors.py      # Tests for Batch 2 inspectors (Kubectl, Terraform, C++, PHP, CUDA, SQLite)
    ├── test_config.py                 # Tests for user configuration and custom search paths
    ├── test_deep_inspection.py        # Tests for Phase 7 deep inspection models & endpoints
    ├── test_discovery.py              # Tests for unified DiscoveryPipeline
    ├── test_inspectors.py             # Tests for tool inspection logic
    ├── test_inventory.py              # Tests for OS application inventory
    ├── test_ports.py                  # Tests for PortManager socket discovery and protection
    ├── test_project_auditor.py        # Tests for ProjectAuditor multi-manifest verification
    ├── test_registry.py               # Tests for dynamic plugin discovery & filtering
    ├── test_runner.py                 # Tests for SafeRunner timeouts & multi-binary path resolution
    ├── test_server.py                 # Tests for FastAPI server endpoints, SSE streaming & deep audit
    ├── test_signatures.py              # Tests for content signature detection
    └── test_tool_spec_validation.py   # Comprehensive specification & contract test suite across all 22 tools (96 tests)
```

---

## 2. Deep Tool Inspection & Process Flow API (Phase 7)

### Core Models ([`devtoolkit/core/models.py`](file:///d:/UtilitySoftware/devtoolkit/core/models.py))
- `DiscoveredInstance`: Represents a discovered tool binary/runtime on the machine.
  - `path`: Full path to binary or installation root.
  - `version`: Version string extracted for this specific instance.
  - `is_active`: `True` if this is the instance resolved first via system `PATH`.
  - `source`: Discovery origin (`"PATH"`, `"Registry"`, `"Program Files"`, `"VirtualEnv"`, `"Config Root"`).
- `EnvVarStatus`: Represents an environment variable relevant to the inspected tool.
  - `name`: Variable key (e.g. `JAVA_HOME`, `PYTHONPATH`, `GOROOT`, `DOTNET_ROOT`).
  - `value`: Current live environment string or `None` if unset.
  - `expected_target`: Recommended target path based on active tool installation.
  - `status`: One of `"aligned"`, `"divergent"`, or `"missing"`.
- `DeepTelemetryReport`: High-resolution telemetry payload returned during drawer expansion.
  - `raw_cli_dumps`: Key-value map of raw CLI tool outputs (`dotnet --info`, `go env -json`, etc.).
  - `all_instances`: List of all `DiscoveredInstance` records found across disk.
  - `env_vars`: List of all `EnvVarStatus` alignment checks.
  - `detailed_diagnostics`: Comprehensive warnings, security advisories, or performance tips.
  - `remediation_commands`: Actionable terminal commands with copyable snippets (no 1-click execution).
  - `probe_latency_ms`: Duration of the deep inspection run in milliseconds.

### Runner Multi-Instance Resolution ([`devtoolkit/core/runner.py`](file:///d:/UtilitySoftware/devtoolkit/core/runner.py))
- `SafeRunner.resolve_all_binaries(name: str) -> List[Path]`: Resolves all occurrences of a binary executable in PATH precedence order using native `where.exe` on Windows (and `which -a` on Unix), deduplicating symlinks and case variations.

### Base Inspector Deep Inspection ([`devtoolkit/core/base.py`](file:///d:/UtilitySoftware/devtoolkit/core/base.py))
- `BaseInspector.deep_inspect(self, runner: SafeRunner, base_report: Optional[ToolReport] = None) -> DeepTelemetryReport`: Standard signature across all 22 inspectors. Builds instances from `resolve_all_binaries`, evaluates monitored env vars, and executes diagnostic sub-commands with non-blocking timeouts.

### Plugin Registry Coordinator ([`devtoolkit/core/registry.py`](file:///d:/UtilitySoftware/devtoolkit/core/registry.py))
- `PluginRegistry.run_deep_inspection(tool_id: str) -> Optional[DeepTelemetryReport]`: Executes deep inspection on-demand for a single tool with non-blocking timeouts and attaches execution latency.

### REST API Endpoints ([`devtoolkit/server/routes/audit.py`](file:///d:/UtilitySoftware/devtoolkit/server/routes/audit.py))
- `GET /api/tool/{tool_id}/deep`: Fetches on-demand deep inspection telemetry for the slide-over Inspector Drawer.
- `GET /api/audit/stream`: Server-Sent Events (SSE) baseline audit stream for non-blocking (<50ms) initial page load.

---

## 3. Discovery Pipeline Public API

### `DiscoveryPipeline` ([`devtoolkit/core/discovery.py`](file:///d:/UtilitySoftware/devtoolkit/core/discovery.py))
- `discover_android_sdk() -> Optional[Path]`: Resolves Android SDK via Env -> OS Default -> Studio XML -> Flutter config -> Signature scan.
- `discover_android_studio() -> Optional[Path]`: Resolves Android Studio via Registry Uninstall -> Flutter config -> Signature scan.
- `discover_java_home() -> Optional[Path]`: Resolves JDK via `JAVA_HOME` -> Registry -> OS Inventory -> Gradle -> Flutter -> Studio JBR -> Signature scan.
- `discover_flutter_sdk() -> Optional[Path]`: Resolves Flutter SDK via `PATH` -> Signature scan.

### `OSInventory` ([`devtoolkit/core/inventory.py`](file:///d:/UtilitySoftware/devtoolkit/core/inventory.py))
- `get_installed_apps() -> List[InstalledApp]`: Enumerates all installed software on Windows without hardcoded drive letters.
- `find_app_locations(query: str) -> List[Path]`: Returns directory locations for any installed application.

### `EcosystemResolvers` ([`devtoolkit/core/ecosystem.py`](file:///d:/UtilitySoftware/devtoolkit/core/ecosystem.py))
- `resolve_android_sdk_from_studio() -> Optional[Path]`: Extracts SDK path from Android Studio's standard `%APPDATA%\Google\AndroidStudio*\options\android.sdk.path.xml`.
- `resolve_from_flutter(runner) -> dict`: Queries Flutter machine config for companion paths.
- `resolve_from_gradle() -> Optional[Path]`: Parses `~/.gradle/gradle.properties`.

### `Signatures` ([`devtoolkit/core/signatures.py`](file:///d:/UtilitySoftware/devtoolkit/core/signatures.py))
- `scan_roots_for_tools(roots: List[Path], max_depth: int = 2) -> Dict[str, List[Path]]`: Content-based detection for arbitrary un-registered directories.

---

## 4. Utilities Public API

### `PortManager` & `PortKiller` ([`devtoolkit/modules/utilities/ports.py`](file:///d:/UtilitySoftware/devtoolkit/modules/utilities/ports.py))
- `list_ports(dev_only: bool = False) -> List[PortInfo]`: Lists active TCP listening ports with process names, PIDs, addresses, and dev-port tags (`3000`, `5173`, `8080`, etc.).
- `kill_port(target_port: int, force: bool = False) -> PortKillResult`: Terminates occupying process via native OS `taskkill /PID <pid> /F` with hard-coded protection for critical system processes.

### `ProjectAuditor` ([`devtoolkit/modules/utilities/project_auditor.py`](file:///d:/UtilitySoftware/devtoolkit/modules/utilities/project_auditor.py))
- `audit_project(project_path: Path) -> ProjectAuditReport`: Scans repository manifests (`package.json`, `pyproject.toml`, `pubspec.yaml`, `build.gradle`, `Dockerfile`, `Cargo.toml`, `go.mod`), detects ecosystems, tests constraints against installed workstation runtimes, and outputs actionable setup commands.
