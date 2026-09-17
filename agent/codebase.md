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
│   └── state.md                       # Session memory, checklist, and roadmap
├── devtoolkit/                        # Core Python package
│   ├── __init__.py
│   ├── __main__.py                    # Entrypoint for `python -m devtoolkit`
│   ├── core/                          # Engine kernel & discovery pipeline
│   │   ├── base.py                    # BaseInspector and BaseUtility abstractions
│   │   ├── config.py                  # User configuration management (~/.devtoolkit/config.yaml)
│   │   ├── discovery.py               # Unified 4-layer DiscoveryPipeline coordinator
│   │   ├── ecosystem.py               # Layer 3: Cross-tool ecosystem config resolvers (Studio, Flutter, Gradle)
│   │   ├── inventory.py               # Layer 2: OS Application Inventory & Windows Registry scanner
│   │   ├── models.py                  # Pydantic schemas (ToolReport, HealthStatus, AuditSummary)
│   │   ├── runner.py                  # SafeRunner: Subprocess execution with timeouts & path resolution
│   │   ├── registry.py                # PluginRegistry: Dynamic inspector auto-discovery & multithreading
│   │   └── signatures.py              # Layer 4: Structural content signature matchers
│   ├── cli/                           # Command-line interface (Typer)
│   │   └── main.py                    # `devtoolkit inspect`, `devtoolkit doctor`, `devtoolkit ui`, `devtoolkit config`
│   ├── formatters/                    # Output formatting layer
│   │   ├── table.py                   # Rich console tables and health badge formatting
│   │   ├── json_fmt.py                # Machine-readable JSON output
│   │   └── yaml_fmt.py                # Machine-readable YAML output
│   ├── modules/
│   │   ├── inspectors/                # Pluggable tool inspectors
│   │   │   ├── android.py             # Android SDK, adb, emulator, build-tools, platforms
│   │   │   ├── android_studio.py      # Android Studio IDE, launcher, and bundled JBR
│   │   │   ├── docker.py              # Docker CLI, Docker Compose, engine daemon check
│   │   │   ├── flutter.py             # Flutter SDK, Dart SDK, release channel
│   │   │   ├── git.py                 # Git, GitHub CLI (gh), global user config
│   │   │   ├── golang.py              # Go compiler, GOPATH, GOROOT
│   │   │   ├── java.py                # Java JVM, javac (JDK), JAVA_HOME, bundled JBR
│   │   │   ├── node.py                # Node.js, npm, pnpm, yarn, corepack
│   │   │   ├── python.py              # Python, pip, uv, poetry, conda, pipenv
│   │   │   └── rust.py                # Rustc, Cargo, rustup toolchain
│   │   └── utilities/                 # Active developer workstation utilities
│   │       ├── ports.py               # PortManager & PortKiller: socket scanner & safe process killer
│   │       └── project_auditor.py     # ProjectAuditor: repository requirements vs machine readiness
│   └── server/                        # UI and API layer
│       └── app.py                     # FastAPI REST server, 4-tab modern UI & PyWebView desktop launcher
├── scripts/
│   └── build_standalone.ps1           # Automated standalone PyInstaller .exe packaging
├── .github/
│   └── workflows/
│       └── build.yml                  # GitHub Actions CI for test, packaging & release
└── tests/                             # Automated test suite (29 passing unit tests)
    ├── test_config.py                 # Tests for user configuration and custom search paths
    ├── test_discovery.py              # Tests for unified DiscoveryPipeline
    ├── test_inspectors.py             # Tests for tool inspection logic
    ├── test_inventory.py              # Tests for OS application inventory
    ├── test_ports.py                  # Tests for PortManager socket discovery and protection
    ├── test_project_auditor.py        # Tests for ProjectAuditor multi-manifest verification
    ├── test_registry.py               # Tests for dynamic plugin discovery & filtering
    ├── test_runner.py                 # Tests for SafeRunner timeouts & path resolution
    ├── test_server.py                 # Tests for FastAPI server endpoints and 4-tab UI rendering
    └── test_signatures.py              # Tests for content signature detection
```

---

## 2. Discovery Pipeline Public API

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

## 3. Utilities Public API

### `PortManager` & `PortKiller` ([`devtoolkit/modules/utilities/ports.py`](file:///d:/UtilitySoftware/devtoolkit/modules/utilities/ports.py))
- `list_ports(dev_only: bool = False) -> List[PortInfo]`: Lists active TCP listening ports with process names, PIDs, addresses, and dev-port tags (`3000`, `5173`, `8080`, etc.).
- `kill_port(target_port: int, force: bool = False) -> PortKillResult`: Terminates occupying process via native OS `taskkill /PID <pid> /F` with hard-coded protection for critical system processes.

### `ProjectAuditor` ([`devtoolkit/modules/utilities/project_auditor.py`](file:///d:/UtilitySoftware/devtoolkit/modules/utilities/project_auditor.py))
- `audit_project(project_path: Path) -> ProjectAuditReport`: Scans repository manifests (`package.json`, `pyproject.toml`, `pubspec.yaml`, `build.gradle`, `Dockerfile`, `Cargo.toml`, `go.mod`), detects ecosystems, tests constraints against installed workstation runtimes, and outputs actionable setup commands.

