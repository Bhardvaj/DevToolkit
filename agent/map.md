# System Architecture Map & Execution Blueprint

This document serves as the authoritative high-level technical map for `DevToolkit`. Any developer or AI agent entering this project should read this document to understand system boundaries, module interactions, process lifecycles, and data flows.

---

## 1. High-Level Architecture

DevToolkit follows a **Decoupled Client-Daemon Architecture**:
- **Background Daemon**: The central host service managing the local FastAPI REST server, Server-Sent Events (SSE), live telemetry, the standalone Fast Search Engine, and the native Windows notification tray.
- **Client Presentation Layer**: Decoupled clients interacting over HTTP/SSE. Includes the native desktop window (`PyWebView` Edge Chromium), web dashboards, CLI commands, and future lightweight client tools.
- **Unified Entrypoint**: `devtoolkit.entry:main` runs windowless under Windows GUI subsystem, automatically checking for existing instances, starting or connecting to the daemon, and activating the desktop window without console flashes.
- **Zero Host Pollution**: All runtime state (`daemon.json`), user settings (`devtoolkit.config.yaml`), and rotating logs (`daemon.log`, `client.log`) are stored strictly beside the portable executable. `Path.home() / ".devtoolkit"` is never touched.

```mermaid
graph TD
    subgraph UI_Layer [Presentation Layer / Clients]
        DesktopUI[Desktop Client - PyWebView Edge Chromium]
        LocalWeb[Browser Dashboard - http://127.0.0.1:4321]
        CLI[Terminal CLI - Typer / Rich via devtoolkit.cli]
        ClientSDK[Client SDK - devtoolkit.client.api & state]
    end

    subgraph Entry_Layer [Unified Launcher - devtoolkit.entry]
        EntryPoint[devtoolkit.entry:main - Windowless PE Subsystem]
        HWNDCheck[Win32 FindWindowW & Single-Instance Restore]
    end

    subgraph Daemon_Layer [Background Daemon Service]
        DaemonManager[daemon/manager.py - Detached Process Spawner]
        DaemonServer[daemon/server.py - Lifespan & Service Coordinator]
        ActivityTracker[daemon/activity.py - Thread-Safe Scan/Index State]
        SystemTray[daemon/tray.py - Pure Win32 Shell_NotifyIcon Tray]
    end

    subgraph Server_Layer [FastAPI REST & Telemetry Server]
        FastAPIApp[server/app.py - Modular Application Coordinator]
        AuditRouter[routes/audit.py - SSE Streaming & Deep Inspection]
        SearchRouter[routes/search.py - Fast Search Query & Re-indexing]
        PortsRouter[routes/ports.py - Sockets & Safe Process Killer]
        ProjectRouter[routes/project.py - Manifest Readiness Auditor]
        SystemRouter[routes/system.py - Telemetry, Activity & Config]
        ActionsRouter[routes/actions.py - Explorer Launch & Dialogs]
        StaticUI[static/ index.html, styles.css, app.js]
    end

    subgraph Search_Engine [FastSearchEngine - Everything Class]
        SearchIndex[SearchIndex - In-Memory O 1 Hash & Array Index]
        USNReader[NTFSUSNReader - FSCTL_ENUM_USN_DATA when Elevated]
        Crawler[ParallelPrunedCrawler - Multi-Threaded Win32 Pruned Walk]
        Watcher[LiveDirectoryWatcher - ReadDirectoryChangesW Live Sync]
    end

    subgraph Core_Engine [DevToolkit Kernel]
        Registry[PluginRegistry - Dynamic Inspector Discovery & Threadpool]
        SafeRunner[SafeRunner - Subprocess Timeouts & where.exe Multi-Binary]
        ConfigEngine[Portable Config - devtoolkit.config.yaml beside exe]
        LoggingEngine[Co-located Logging - daemon.log & client.log]
    end

    subgraph Plugins [22 Pluggable Tool Inspectors]
        P_Core[Batch 1: Python, Node, Git, Docker, Java, Go, Rust, .NET]
        P_Extended[Batch 2: Android SDK/Studio, Flutter, VS Code, Bun, GH, CMake, Ollama, Kubectl, Terraform, C++, PHP, CUDA, SQLite]
    end

    EntryPoint --> HWNDCheck
    HWNDCheck -->|Already Running| DesktopUI
    HWNDCheck -->|Not Running| DaemonManager
    DaemonManager --> DaemonServer
    DaemonServer --> FastAPIApp
    DaemonServer --> SystemTray
    DaemonServer --> ActivityTracker

    DesktopUI --> ClientSDK
    ClientSDK --> FastAPIApp
    LocalWeb --> FastAPIApp
    CLI --> Registry

    FastAPIApp --> AuditRouter
    FastAPIApp --> SearchRouter
    FastAPIApp --> PortsRouter
    FastAPIApp --> ProjectRouter
    FastAPIApp --> SystemRouter
    FastAPIApp --> ActionsRouter

    AuditRouter --> Registry
    SearchRouter --> Search_Engine
    PortsRouter --> SafeRunner
    ProjectRouter --> Registry
    SystemRouter --> ConfigEngine
    SystemRouter --> ActivityTracker

    Registry --> Plugins
    Plugins --> SafeRunner
    Search_Engine --> USNReader
    Search_Engine --> Crawler
    Search_Engine --> Watcher
    Search_Engine --> SearchIndex
```

---

## 2. On-Demand Deep Inspection & 7-Zone Process Flow

DevToolkit separates fast baseline discovery from rich deep telemetry so the initial dashboard render is instant (<50ms) while user-requested tools can be inspected with forensic detail.

```mermaid
sequenceDiagram
    autonumber
    actor User
    participant Browser as UI (app.js)
    participant Server as FastAPI (routes/audit.py)
    participant Reg as PluginRegistry
    participant Insp as Inspector (e.g. PythonInspector)
    participant OS as SafeRunner & OS CLI

    User->>Browser: Click Tool Card (e.g. Python)
    Browser->>Browser: Open Slide-Over Drawer with Baseline Data
    Browser->>Browser: Render Shimmer Skeleton for Deep Telemetry
    Browser->>Server: GET /api/tool/python/deep
    Server->>Reg: run_deep_inspection("python")
    Reg->>Insp: deep_inspect(base_report, runner)
    Insp->>OS: resolve_all_binaries("python") -> where.exe
    OS-->>Insp: [C:\.venv\Scripts\python.exe, C:\Python314\python.exe]
    Insp->>OS: Test environment variables (PYTHONPATH, PYTHONHOME)
    Insp->>OS: Run diagnostic sub-commands (sysconfig, pip list)
    OS-->>Insp: CLI stdout / stderr dumps
    Insp-->>Reg: DeepTelemetryReport (latency, instances, env_vars, dumps, fixes)
    Reg-->>Server: Return DeepTelemetryReport
    Server-->>Browser: JSON 200 OK
    Browser->>Browser: Cache report in memory
    Browser->>Browser: Swap Skeleton with 7-Zone Forensic Layout
```

### The Standardized 7-Zone Inspector Drawer Layout

1. **Zone 1: Identity & Health Header**: Tool icon, tool name, domain category, health badge (`Healthy`, `Action Needed`, `Not Found`), resolved version, and probe execution latency in milliseconds.
2. **Zone 2: Primary Runtime & Quick Access**: Monospace active binary path, one-click "Open in Explorer" folder button, copy path button, and discovery source badge (`PATH`, `Registry`, etc.).
3. **Zone 3: Multi-Instance & Precedence Discovery**: Comprehensive listing of all detected instances across the machine, labeling the active binary (`Active (PATH)`) versus secondary runtimes (`Alternate` / standby) with source origin tags.
4. **Zone 4: Environment Variable Alignment Matrix**: Tabular breakdown of runtime environment variables (`JAVA_HOME`, `PYTHONPATH`, `GOROOT`, `DOTNET_ROOT`), current values, recommended targets, and health badges (`Aligned`, `Divergent`, `Missing`).
5. **Zone 5: Subsystems & Ecosystem Status**: Companion tools and package managers (e.g., pip, uv, poetry, conda) with operational statuses and versions.
6. **Zone 6: Remediation & Setup Commands**: Strictly copyable terminal commands with a 1-click copy button to resolve path misalignments or missing packages (zero 1-click system mutations).
7. **Zone 7: Deep Diagnostics & CLI Telemetry**: Tabbed forensic view containing CLI stdout dumps (e.g., `dotnet --info`, `go env -json`, `git config -l --show-origin`), actionable diagnostic warnings, and full JSON payload export.

---

## 3. FastSearchEngine Architecture (Everything-Class)

DevToolkit embeds a zero-dependency, sub-millisecond search engine modeled after Voidtools Everything:

```mermaid
flowchart LR
    ScanTrigger[Startup Warmup / Manual Reindex] --> RootCheck{Are Roots Whole Drives?}
    RootCheck -->|Elevated Windows Drive| USN[NTFSUSNReader - DeviceIoControl FSCTL_ENUM_USN_DATA]
    RootCheck -->|Standard Directory / Non-Admin| Crawler[ParallelPrunedCrawler - 16 Workers]
    USN --> Index[SearchIndex - O 1 In-Memory Map]
    Crawler --> Index
    Index --> QueryAPI[POST /api/search/query]
    LiveWatcher[LiveDirectoryWatcher - ReadDirectoryChangesW] -->|Disk Events| Index
```

- **NTFS USN Change Journal Reader**: Directly streams NTFS master volume metadata via `DeviceIoControl(FSCTL_ENUM_USN_DATA)` when running as Administrator, indexing whole drives (e.g. `C:\`, `D:\`) in <500ms.
- **Parallel Pruned Crawler**: Multi-threaded pruned Win32 directory scanner with 16 worker threads, aggressively skipping developer caches (`node_modules`, `.git`, `.venv`, `__pycache__`) and system junctions.
- **Live Directory Watcher**: Native Win32 `ReadDirectoryChangesW` kernel monitoring running on background daemon threads. Automatically detects file additions, modifications, renames, and deletions in O(1) time without rescanning disk.
- **Intelligent Root Fallbacks**: If user search paths are unconfigured, automatically indexes local fixed drives (`D:\`, `C:\`) on Windows so search works immediately out-of-the-box. In test runs (`DEVTOOLKIT_TESTING=1`), drive crawling is disabled to keep tests fast (<60s).

---

## 4. The 4 Discovery Layers

1. **Layer 1: Standard OS & Environment**:
   - Standard `PATH` resolution (`shutil.which`) with Windows extensions (`.exe`, `.cmd`, `.bat`).
   - Official environment variables (`ANDROID_HOME`, `JAVA_HOME`, `GOROOT`, `CARGO_HOME`).
   - Standard default OS folders (`%LOCALAPPDATA%\Android\Sdk`, `~/Android/Sdk`).

2. **Layer 2: OS Application Inventory**:
   - Reads official Windows Registry `Uninstall` and `App Paths` hives (`HKLM` and `HKCU`).
   - Dynamically resolves installation paths and versions directly from software installer metadata, regardless of which drive or folder the user chose during setup.

3. **Layer 3: Cross-Tool Ecosystem Metadata**:
   - Reads cross-tool configuration files maintained by developer tools:
     - **Android Studio**: `%APPDATA%\Google\AndroidStudio*\options\android.sdk.path.xml` & `jdk.table.xml`.
     - **Flutter**: `flutter config --machine` JSON configuration.
     - **Gradle**: `~/.gradle/gradle.properties` (`org.gradle.java.home`).

4. **Layer 4: User-Configured Search Roots & Content Signatures**:
   - Portable user config: `devtoolkit.config.yaml` beside executable.
   - Structural Content Signatures (identifying SDKs by files, not folder names):
     - **Android SDK**: `platform-tools/adb*` + `build-tools/` or `platforms/`.
     - **JDK**: `bin/javac*` or `release` with `JAVA_VERSION`.
     - **Android Studio**: `product-info.json` (`productCode == "AI"`) or `bin/studio64.exe`.
     - **Flutter SDK**: `bin/flutter*` + `packages/flutter/`.
     - **Rust**: `bin/rustc*` + `bin/cargo*`.
     - **Go**: `bin/go*` + `pkg/tool/`.

---

## 5. Module Boundaries & Safety Guarantees

- **Zero Host Pollution**: All runtime state files (`daemon.json`), user settings (`devtoolkit.config.yaml`), and rotating logs (`daemon.log`, `client.log`) reside strictly beside the executable or in the repo root. The user's home profile directory is never written to.
- **Zero Terminal Window Flashes**: Compiled with `--windowed` PE GUI subsystem and spawned using `CREATE_NO_WINDOW = 0x08000000 | DETACHED_PROCESS`.
- **Zero Hardcoded Paths**: No inspector or runner file may contain arbitrary drive or folder assumptions (e.g. `D:\Dev`). All discoveries must flow through the 4-layer pipeline.
- **Read-Only Inspection**: All subprocess probes strictly execute non-destructive queries (`--version`, `-v`) with mandatory timeouts (default 3.0s).
- **Non-Mutating Remediations**: Tool remediations are presented as copyable terminal commands with a 1-click clipboard button rather than automatic silent system mutations.
- **Extensible Plugins**: Adding a new inspector requires only adding a `BaseInspector` subclass into `devtoolkit/modules/inspectors/`.
