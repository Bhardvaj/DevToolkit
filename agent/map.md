# System Architecture Map & Execution Blueprint

This document serves as the high-level technical map for `DevToolkit`. Any developer or AI agent entering this project should read this document to understand the system layout, module boundaries, data flows, runtime lifecycles, and deep inspection process flow.

---

## 1. High-Level Architecture

DevToolkit decouples the **Core Auditing Engine** from the **Presentation Layer** (CLI and Modern Desktop UI) and implements a **Generalized 4-Layer Discovery Pipeline** that avoids hardcoded machine paths.

```mermaid
graph TD
    subgraph UI_Layer [Presentation Layer]
        CLI[Terminal CLI - Typer + Rich]
        DesktopUI[Modern Desktop UI - PyWebView Edge Chromium]
        LocalWeb[Local Web Dashboard - FastAPI / Starlette]
    end

    subgraph Server_Layer [Modular Server Layer]
        ServerApp[server/app.py Coordinator]
        AuditRouter[routes/audit.py - SSE & Deep Telemetry]
        SystemRouter[routes/system.py - Telemetry & Search Roots]
        PortsRouter[routes/ports.py - Sockets & Killer]
        ProjectRouter[routes/project.py - Manifest Auditor]
        ActionsRouter[routes/actions.py - Explorer & Dialogs]
        StaticUI[static/ index.html, styles.css, app.js]
    end

    subgraph Discovery_Engine [4-Layer Discovery Pipeline]
        L1[Layer 1: Standard Environment & PATH]
        L2[Layer 2: OS Application Inventory & Registry]
        L3[Layer 3: Cross-Tool Ecosystem Metadata]
        L4[Layer 4: User Search Roots & Content Signatures]
        DiscoveryPipeline[DiscoveryPipeline Coordinator]
    end

    subgraph Core_Engine [DevToolkit Kernel]
        Registry[PluginRegistry - Baseline Audit & Deep Inspection]
        SafeRunner[SafeRunner - Timeouts, where.exe & PATH Precedence]
        ConfigEngine[User Config Engine - ~/.devtoolkit/config.yaml]
    end

    subgraph Plugins [22 Pluggable Tool Inspectors]
        P_Core[Batch 1: Python, Node, Git, Docker, Java, Go, Rust, .NET]
        P_Extended[Batch 2: VS Code, Bun, GH, CMake, Ollama, Kubectl, Terraform, C++, PHP, CUDA, SQLite, Android SDK/Studio, Flutter]
    end

    CLI --> Registry
    DesktopUI --> LocalWeb
    LocalWeb --> ServerApp
    ServerApp --> AuditRouter
    ServerApp --> SystemRouter
    ServerApp --> PortsRouter
    ServerApp --> ProjectRouter
    ServerApp --> ActionsRouter

    AuditRouter --> Registry
    PortsRouter --> SafeRunner
    ProjectRouter --> Registry
    SystemRouter --> ConfigEngine

    Registry --> Plugins
    Plugins --> SafeRunner
    SafeRunner --> DiscoveryPipeline
    DiscoveryPipeline --> L1
    DiscoveryPipeline --> L2
    DiscoveryPipeline --> L3
    DiscoveryPipeline --> L4
    L4 --> ConfigEngine
```

---

## 2. On-Demand Deep Inspection & 7-Zone Process Flow (Phase 7)

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

## 3. The 4 Discovery Layers

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
   - User config: `~/.devtoolkit/config.yaml` (`devtoolkit config add-path <dir>`).
   - Structural Content Signatures (identifying SDKs by files, not folder names):
     - **Android SDK**: `platform-tools/adb*` + `build-tools/` or `platforms/`.
     - **JDK**: `bin/javac*` or `release` with `JAVA_VERSION`.
     - **Android Studio**: `product-info.json` (`productCode == "AI"`) or `bin/studio64.exe`.
     - **Flutter SDK**: `bin/flutter*` + `packages/flutter/`.
     - **Rust**: `bin/rustc*` + `bin/cargo*`.
     - **Go**: `bin/go*` + `pkg/tool/`.

---

## 4. Module Boundaries & Safety Guarantees

- **Zero Hardcoded Paths**: No inspector or runner file may contain arbitrary drive or folder assumptions (e.g. `D:\Dev`). All discoveries must flow through the 4-layer pipeline.
- **Read-Only Inspection**: All subprocess probes strictly execute non-destructive queries (`--version`, `-v`) with mandatory timeouts (default 3.0s).
- **Non-Mutating Remediations**: Tool remediations are presented as copyable terminal commands with a 1-click clipboard button rather than automatic silent system mutations.
- **Extensible Plugins**: Adding a new inspector requires only adding a `BaseInspector` subclass into `devtoolkit/modules/inspectors/`.
