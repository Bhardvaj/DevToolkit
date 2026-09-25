# Project State & Session Memory

This document is continuously updated to reflect current project status, completed work, active tasks, and upcoming milestones. It allows any future AI session to instantly resume work with zero context loss.

---

## Current Status: Phase 10 Complete (Real-Time Live Updating & Settings Toggle Control)
- **Active Task**: Real-Time Live Updating (Native Win32 ReadDirectoryChangesW live filesystem change monitor, O(1) in-memory index additions, deletions, renames, and tree pruning, `POST /api/search/realtime` toggle endpoint, Settings UI switch with instant persistence, non-distracting clean `Ready (live)` status, and 181 passing tests) 100% complete with standalone binary `dist/DevToolkit.exe` (21.04 MB).
- **Architecture**: Decoupled Engine + 22 Comprehensive Tool Inspectors + 4-Layer Generalized Discovery + Standalone Everything-Class FastSearchEngine (`SearchIndex`, `ParallelPrunedCrawler`, `NTFSUSNReader`, `Win32DirectoryWatcher`) + Native Win32 RAM Telemetry (`K32GetProcessMemoryInfo`) + Modular Server Architecture + Google Stitch Precision UI + Live Search Engine Telemetry, Real-Time Updating & On-Demand Re-indexing + Multi-Instance Precedence Engine (`where.exe`) + Environment Variable Alignment Matrix + On-Demand Telemetry API (`GET /api/tool/{tool_id}/deep`) + Safe Copyable Remediations.
- **Repository**: Synced on GitHub at [https://github.com/Bhardvaj/DevToolkit](https://github.com/Bhardvaj/DevToolkit).

---

## Milestone Checklist: Phase 1 (Completed)
- [x] Step 1 - Step 7: Core Engine, 10 Tool Inspectors, 4-Layer Generalized Discovery, CLI, and FastAPI/PyWebView Dashboard.

---

## Milestone Checklist: Phase 2 (Completed)
- [x] Step 2.1: Port Manager & Killer (`devtoolkit/modules/utilities/ports.py`).
- [x] Step 2.2: Project Workstation Auditor (`devtoolkit/modules/utilities/project_auditor.py`).
- [x] Step 2.3: CLI Integration (`ports`, `project`, `config`).
- [x] Step 2.4: 4-Tab Web & Desktop Dashboard.
- [x] Step 2.5: Packaging & Manual GitHub Actions CI Automation.

---

## Milestone Checklist: Phase 3 (Completed)
- [x] Vertical Sidebar Navigation & Layout matching target design.
- [x] Native PC Software Ergonomics, Viewport Lock, and Desktop Keyboard Accelerators.
- [x] Dual-Mode Executable Entrypoint (`DevToolkit.exe`).
- [x] UI Ergonomics & Decluttering (cleaned header, sidebar, status bar, and card actions).
- [x] Native `os.startfile` Open in Explorer.
- [x] Multi-category architecture for all inspectors.

---

## Milestone Checklist: Phase 4 (Completed)
- [x] Batch 1 Inspectors (VS Code, .NET SDK, Bun, GitHub CLI, CMake, Ollama).
- [x] Batch 2 Inspectors (Kubectl, Terraform, C/C++ Compiler, PHP & Composer, NVIDIA CUDA Toolkit, SQLite).
- [x] Total of 22 built-in inspectors across 9 domain categories.
- [x] Companion subsystems status matrix across all tools.

---

## Milestone Checklist: Phase 5 (Completed)
- [x] **Uniform Compact Tool Cards & Slide-Over Inspector Drawer**:
  - Balanced uniform tool cards across all 22 tools preventing height disparity.
  - Smooth slide-over Inspector Drawer with backdrop blur displaying complete paths, native "Open in Explorer", copy actions, diagnostic warnings with 1-click remediation, companion subsystems status, and raw JSON export.
- [x] **Progressive Async Tool Loading & Skeleton Cards**:
  - Instant first paint (<50ms) rendering 22 skeleton cards with animated shimmer pulse.
  - Server-Sent Events (SSE) streaming (`/api/audit/stream`) with thread pool executor concurrency up to 32 workers so fast tools resolve in 50–200ms and snap into place dynamically.
  - Slower inspectors (Flutter, Java) display in-box scanning indicators until completion.
  - Resilient automatic fallback to batch fetch if SSE is interrupted.
- [x] **Interactive Metric Stat Filter Cards**:
  - 6 top metric cards (*Audited Tools*, *Installed*, *Healthy*, *Action Needed*, *Critical Errors*, *Not Found*) act as one-click toggles with active rings and an active status filter reset pill.
- [x] **Export Environment Report**:
  - Top header dropdown offering 1-click Markdown table export (clipboard), JSON summary copy, and direct `.md` report download.
- [x] **Port Manager Modernization & Background Pre-fetch**:
  - Automatic port categorization (*Web / HTTP*, *Database*, *Dev Debug*, *Service*).
  - 1-Click "Open in Browser" action (`http://localhost:<port>`) for active web and developer ports.
  - View mode toggle: Flat Sockets Table vs. Grouped by Process cards.
  - Background asynchronous pre-fetch on application load for instant zero-latency tab switching.
  - Visual spinning refresh feedback with toast notification and double-click prevention.
- [x] **Project Auditor Modernization & Native Folder Browser**:
  - Clean unpopulated initial state on startup.
  - Visual Readiness Scorecard with percentage meter, breakdown counters, and manifest tags.
  - Recent Projects history chips preserved in `localStorage` for 1-click re-scanning.
  - Native Windows Explorer folder selection dialog via `@app.post("/api/action/select-folder")` using background PowerShell `FolderBrowserDialog` (`creationflags=0x08000000`, no console window flashes; cross-platform fallbacks for macOS/Linux).
  - Dedicated "Browse..." button right next to the project input bar and monitored search roots in Settings.
  - 1-Click "Copy All Fix Commands" combining suggested setup actions into a copyable terminal script.
- [x] **Precision Flex Centering for Search & Input Bars**:
  - Replaced hardcoded vertical offsets with container flex centering: `absolute inset-y-0 flex items-center` with `leading-none` on `<kbd>` shortcut tags across Environment search, Port search, Project Auditor path input, and Settings root directory input.
  - Enhanced global `Ctrl+K` shortcut listener to focus the active search/input bar across all tabs.
- [x] **Dynamic System Telemetry & Sidebar Software Info Footer**:
  - Removed hardcoded version tag from top title; added a dedicated software info footer card in the sidebar displaying dynamic DevToolkit version (`v0.2.0`), active Python environment version, and runtime status heartbeat.
  - Dynamically detects and displays host operating system, release, and machine architecture (`#side-os-info`) and hostname (`#side-host-name`) via `/api/system`.
- [x] **Verification & Standalone Recompilation**:
  - All 52 unit tests passing (`52 passed in 32.19s`).
  - Standalone executable recompiled: `dist/DevToolkit.exe` (20.88 MB).
  - Smoke tests verified.

---

## Milestone Checklist: Phase 6 (Completed - Google Stitch Design Shift)
- [x] **Design Tokens & Tonal Palette**:
  - Implemented Obsidian Canvas `#08090C`, Surface Elevation 1 `#0E1015`, Surface Elevation 2 `#141721`, Micro-borders Subtle `#1F2430`, Strong `#2E3446`.
  - Added primary Emerald accent `#10B981` (hover `#059669` with dark `#08090C` typography on primary buttons) and semantic accents (Cyan `#06B6D4`, Violet `#8B5CF6`, Amber `#F59E0B`, Crimson `#EF4444`).
- [x] **Typography Overhaul**:
  - Integrated `Geist` (400, 500, 600, 700) for structural UI and headers.
  - Integrated `JetBrains Mono` (400, 500, 600) with tabular lining numbers (`font-feature-settings: "tnum" 1`) for all monospace data: paths, hashes, PIDs, ports, versions, counters, and shortcut chips.
- [x] **Geometry & Radii Rules**:
  - Completely purged `rounded-full` (9999px pills) across buttons, tags, chips, and table rows.
  - Standardized on 4px `rounded` for buttons, inputs, tags, badges, and chips; 6px `rounded-md` for cards; 8px `rounded-lg` for modals.
  - Preserved circular 1.5–2px indicator status dots.
- [x] **HTML Markup & Component Modernization**:
  - Sidebar: `#0E1015`, `#1F2430` micro-border, 4px rounded navigation items with emerald indicators, workstation host card, and `#141721` footer card.
  - Top Header: `#08090C`, breadcrumb with emerald dot, `.input-pro` search bar, `.btn-secondary-pro` Rescan and Export dropdown.
  - View 1 (Environment): 6 stat filter cards with 2px progress tracks, category bar with monospace counts, skeleton shimmer cards, and compact tool cards.
  - View 2 (Port Manager): 3 stat cards, filter bar with 3px radius custom checkbox, flat sockets table, and grouped process cards.
  - View 3 (Project Auditor): `.input-pro` path bar, `.btn-secondary-pro` Browse button, emerald "Scan Project" button, scorecard meter, and checklist table.
  - View 4 (Settings): Monitored search roots card, root inputs, and workstation overview metric boxes.
  - Modals & Drawers: `.modal-pro` with 32px depth and 1px inset highlight for Shortcuts/Help modal and Kill modal; Inspector Drawer slide-over with `#0E1015` surface.
- [x] **Client-Side JavaScript Renderers**:
  - Updated `showToast`, `switchTab`, `renderInspectorDrawer`, `getBadge`, `renderCategoryPills`, `renderToolCardInner`, `renderToolRowInner`, `renderGridView`, `renderListView`, `setPortViewMode`, `getPortCategory`, `renderPortsTable`, `renderPortsGrouped`, `renderRecentProjects`, `runProjectAudit`, and `renderSettingsList`.
- [x] **Automated Testing & Compilation**:
  - All 52/52 pytest tests passing in 31.91s.
  - Standalone binary recompiled: `dist/DevToolkit.exe` (20.88 MB).
  - High-resolution screenshots captured across all 6 views and mirrored to artifacts.

---

## Milestone Checklist: Phase 6.1 (Completed - Code Maintainability & Modularity Refactoring)
- [x] **Monolith Decomposition (`devtoolkit/server/app.py`)**:
  - Reduced `app.py` from 3,160 lines down to 134 lines (a 96% reduction).
  - Preserved 100% backward compatibility by re-exporting all route handlers, Pydantic models, and server symbols.
- [x] **Pydantic Schema Isolation (`devtoolkit/server/models.py`)**:
  - Centralized all server request and response schemas (`OpenFolderRequest`, `SearchPathRequest`, `AuditRequest`, `KillPortRequest`, `ProjectAuditRequest`, `SelectFolderRequest`, `ApplyFixRequest`).
- [x] **Domain-Driven API Routes (`devtoolkit/server/routes/`)**:
  - Modularized route handlers by functional domain:
    - `system.py`: Host telemetry, configuration, and search roots.
    - `audit.py`: Audit execution, SSE streaming generator, and tools discovery.
    - `ports.py`: Listening sockets and safe port termination.
    - `project.py`: Project workspace readiness inspection.
    - `actions.py`: Explorer launcher, native folder dialog, and environment fix runner.
- [x] **Clean Static Frontend Separation (`devtoolkit/server/static/`)**:
  - Extracted HTML layout into `index.html` (819 lines) with clean semantic structure.
  - Extracted CSS styling into `styles.css` (163 lines) with full syntax highlighting.
  - Extracted JavaScript logic into `app.js` (1,860 lines) with syntax highlighting and linting.
  - Added `devtoolkit/server/static/__init__.py` for Python package discovery.
- [x] **Robust Template Engine (`devtoolkit/server/ui.py`)**:
  - Implemented 3-layer asset resolution: `importlib.resources` -> `sys._MEIPASS` -> local filesystem fallback.
  - Inlines CSS and JS into HTML at serve time for single-payload, zero-latency, 100% offline-capable serving.
- [x] **Build Pipeline & Standalone Bundling**:
  - Updated `scripts/build_standalone.ps1` with `--collect-data "devtoolkit"`.
  - Recompiled standalone executable `dist/DevToolkit.exe` (20.88 MB).
  - Verified with smoke tests (`--help`, `config list`).
- [x] **Verification & Test Validation**:
  - All 52 unit tests passing cleanly in 31.54s.
  - Headless Chrome visual verification confirmed identical layout rendering across all 6 views.

---

## Milestone Checklist: Phase 7 (Batch 1 Completed - Deep Tool Inspection & 7-Zone Process Flow)
- [x] **Core Deep Telemetry Models & Runner Precedence**:
  - Extended `devtoolkit/core/models.py` with `DiscoveredInstance`, `EnvVarStatus`, `DeepTelemetryReport`, and `ToolReport.deep_report`.
  - Added `SafeRunner.resolve_all_binaries` in `devtoolkit/core/runner.py` using native `where.exe` on Windows (and `which -a` on Unix) to discover all instances and enforce PATH precedence.
  - Extended `BaseInspector.deep_inspect` in `devtoolkit/core/base.py` with default fallback telemetry.
  - Implemented `PluginRegistry.run_deep_inspection(tool_id)` with execution latency tracking in ms.
- [x] **On-Demand Deep Telemetry REST API**:
  - Added `GET /api/tool/{tool_id}/deep` in `devtoolkit/server/routes/audit.py` with 404 error handling for unknown tools.
  - Re-exported route in `devtoolkit/server/app.py`.
- [x] **Batch 1 Deep Inspector Overhauls (8 Core Tools)**:
  - **Python**: Resolves virtual environments, system PATH, Store stubs, Registry installs; evaluates `PYTHONPATH` & `PYTHONHOME`; runs `python -m sysconfig` (paths & platform) and `pip list --outdated --format=json`.
  - **Node.js**: Resolves active node vs NVM/Volta versions; checks `NODE_PATH` & `npm config get prefix`; runs `npm doctor` & global package versions.
  - **Git**: Resolves Git binaries and alternates (e.g. Git for Windows, scoop, winget); checks `GIT_EXEC_PATH` & `GIT_SSH`; dumps `git config --list --show-origin` and detects commit signing keys (`user.signingkey`).
  - **Docker**: Inspects engine status; runs `docker version`, `docker system df`, `docker compose version`; checks `DOCKER_HOST`, `DOCKER_TLS_VERIFY`, `DOCKER_CERT_PATH`.
  - **Java**: Resolves JDKs across `JAVA_HOME`, registry, Studio JBR, Gradle; parses `release` bytecode architecture; dumps `java -XshowSettings:properties -version` and `javac -version`.
  - **Go**: Resolves Go compiler instances; checks `GOROOT` & `GOPATH` alignment; runs `go env -json` and parses cache directories.
  - **Rust**: Resolves `rustc` and `cargo`; checks `RUSTUP_HOME` & `CARGO_HOME`; runs `rustup show` (active toolchain + targets) and `cargo --version --verbose`.
  - **.NET SDK**: Resolves `dotnet` SDKs and runtimes; checks `DOTNET_ROOT` & `DOTNET_MULTILEVEL_LOOKUP`; runs `dotnet --info` and `dotnet --list-sdks`.
- [x] **Standardized 7-Zone Slide-Over Inspector Drawer**:
  - **Zone 1: Identity & Health Header**: Tool icon, display name, category, health badge, version chip, and probe latency badge (`12ms`).
  - **Zone 2: Primary Runtime & Quick Access**: Monospace active path, "Open in Explorer" folder button, copy path button, and discovery source badge.
  - **Zone 3: Multi-Instance & Precedence Discovery**: Lists all discovered instances with `Active (PATH)` vs `Alternate` status badges, source, and instance path.
  - **Zone 4: Environment Variable Alignment Matrix**: Tabular matrix of relevant env vars displaying name, current value, recommended target, and status badges (`Aligned`, `Divergent`, `Missing`).
  - **Zone 5: Subsystems & Ecosystem Status**: Companion tools, sub-runtimes, package managers, and versions.
  - **Zone 6: Remediation & Setup Commands**: Strictly copyable terminal commands with a 1-click copy button (purged 1-click system execution for security).
  - **Zone 7: Deep Diagnostics & CLI Telemetry**: Tabbed interface switching between CLI Raw Outputs (colored pre code blocks), Warnings/Security advisories, and Raw JSON payload download.
- [x] **Client-Side UX & Shimmer Skeleton Loading**:
  - Implemented on-demand fetch in `app.js` with client-side caching per drawer open session.
  - Rendered animated shimmer skeleton placeholders while `GET /api/tool/{tool_id}/deep` resolves, guaranteeing non-blocking baseline startup.
- [x] **Verification & Standalone Recompilation**:
  - 56 passing unit tests (`56 passed in 39.17s`).
  - Standalone binary recompiled: `dist/DevToolkit.exe` (20.92 MB).
  - Screenshots captured and verified: Python, Node.js, .NET.

---

- [x] **Batch 2 Deep Inspector Overhauls (Remaining 14 Tools)**:
  - **Android SDK**: Resolves SDK platforms, build-tools, emulators; detects `ANDROID_HOME`, `ANDROID_SDK_ROOT`, `ANDROID_AVD_HOME`; discovers platform-tools, adb instances, and probes connected adb devices.
  - **Android Studio**: Resolves active Studio installs, Canary/Preview builds, bundled JetBrains Runtime (`jbr`); detects `STUDIO_JDK`, `JDK_HOME`, `JAVA_HOME`; audits Android SDK path and platform tools.
  - **Flutter SDK**: Resolves Flutter SDK and Dart runtime; discovers git clone vs zip installs; evaluates `FLUTTER_ROOT`, `PUB_CACHE`; checks git release channel, engine revision, and Dart cache.
  - **VS Code**: Resolves active VS Code installs, portable extracts, Insiders; detects `VSCODE_PORTABLE`, `VSCODE_GIT_ASKPASS_NODE`; audits user data directory and extensions path.
  - **Kubernetes CLI (kubectl)**: Resolves kubectl binaries; detects `KUBECONFIG`; parses current context, cluster URL, and client version (`kubectl version --client -o json`).
  - **Terraform / OpenTofu**: Resolves terraform and tofu binaries; evaluates `TF_CLI_CONFIG_FILE`, `TF_PLUGIN_CACHE_DIR`; checks provider cache directory and version.
  - **GitHub CLI (gh)**: Resolves gh binaries; checks `GH_TOKEN`, `GITHUB_TOKEN`, `GH_CONFIG_DIR`; runs `gh auth status` and reads configured active account.
  - **Ollama**: Resolves local Ollama binaries; evaluates `OLLAMA_HOST`, `OLLAMA_MODELS`; checks local model library directory and runs `ollama list`.
  - **CMake**: Resolves cmake and ninja binaries; evaluates `CMAKE_GENERATOR`, `CMAKE_BUILD_PARALLEL_LEVEL`; tests generator configuration.
  - **C/C++ Compiler**: Resolves gcc, g++, clang, clang++; detects MinGW, MSVC, LLVM; runs compiler version and target architecture diagnostics.
  - **NVIDIA CUDA Toolkit**: Resolves nvcc, nvidia-smi; evaluates `CUDA_PATH`, `CUDA_HOME`, `CUDA_PATH_V*`; runs `nvidia-smi` and queries driver / GPU hardware properties.
  - **PHP & Composer**: Resolves php and composer binaries; evaluates `PHP_INI_SCAN_DIR`, `COMPOSER_HOME`; runs `php -m` (loaded extensions) and composer version.
  - **Bun**: Resolves bun binaries; evaluates `BUN_INSTALL`; checks global prefix, global package installs, and version.
  - **SQLite**: Resolves sqlite3 binaries; queries compile-time options and active database engine properties.
- [x] **Verification & Standalone Recompilation**:
  - 58 passing unit tests (`58 passed in 58.56s`).
  - Standalone binary recompiled: `dist/DevToolkit.exe` (20.96 MB).
  - Screenshots captured across Batch 2 tools: VS Code, Android SDK, CMake.
- [x] **Comprehensive 22-Tool Specification & Contract Validation Test Suite**:
  - Authored `tests/test_tool_spec_validation.py` with 96 comprehensive tests spanning all 22 tools.
  - Parameterized tests for tool taxonomy, identity, and description verification matching `agent/documentation.md`.
  - Parameterized tests for live baseline `inspect()` contracts (Pydantic schema compliance, valid health status, companion objects, and diagnostics).
  - Parameterized tests for live `deep_inspect()` contracts (raw CLI dumps, multi-instance discovery with `is_active` precedence flag, and environment variable status validation against `{"aligned", "divergent", "missing"}`).
  - Parameterized tests for controlled `NOT_FOUND` fallback execution when binaries are unresolvable.
  - Domain-specific condition branch tests: Python missing pip, Node.js missing npm, Git missing identity, Docker daemon stopped, Java broken JAVA_HOME, C compiler missing C++, CMake missing Ninja, VS Code CLI missing from PATH.
- [x] **Settings Custom Search Path Removal Bug Fix & CLI Parity**:
  - Resolved bug where Windows paths (e.g. `C:\Users\...`, `D:\UtilitySoftware`, paths containing `\u`, `\t`, `\n`) could not be removed from the Settings tab due to inline JS attribute parsing and Unicode escape syntax errors.
  - Added `escapeHtml` utility and refactored UI to index-based removal `removeSearchPathByIndex(idx)` with payload `{ index, path }`.
  - Added `remove_search_path_by_index` and case/trailing-slash/normalization matching in `devtoolkit/core/config.py`.
  - Added `devtoolkit config remove-path` CLI command and wrapped console path prints with Rich `escape()`.
- [x] **Zero-Footprint Portable Configuration (`devtoolkit.config.yaml`)**:
  - Eliminated all host OS user profile pollution (`%USERPROFILE%\.devtoolkit` / `~/.devtoolkit`).
  - Switched configuration resolution strictly to `devtoolkit.config.yaml` located beside the executable (`Path(sys.executable).parent` when frozen, or `Path.cwd()` in development).
  - Code contains zero references or checks to host user home folders.
  - Manually cleaned up legacy `C:\Users\bhard\.devtoolkit`.

---

## Milestone Checklist: Phase 8 (Completed - Standalone Everything-Class Search Engine & Layer 4 Overhaul)
- [x] **Standalone FastSearchEngine Module (`devtoolkit/core/search/`)**:
  - **In-Memory Search Index (`SearchIndex`)**: Compact storage with $O(1)$ lowercase filename hash map lookups, regex, and wildcard (`fnmatchcase`) queries returning structured `SearchResult` records.
  - **Parallel Pruned Crawler (`ParallelPrunedCrawler`)**: Multi-threaded Win32 crawler with 16 worker threads using `os.scandir` and batch buffer accumulation. Aggressively prunes bloated non-developer subtrees (`.git`, `node_modules`, `WinSxS`, `DriverStore`, `Temp`, caches, etc.), reducing indexed nodes from millions to ~45k.
  - **NTFS USN Journal Direct Reader (`NTFSUSNReader`)**: Direct volume handle streaming via Win32 `DeviceIoControl` (`FSCTL_ENUM_USN_DATA`) with zero filesystem tree traversal when running with elevation, plus seamless non-admin fallback.
  - **Engine Coordinator (`FastSearchEngine`)**: Unified coordinator managing thread pools, root prioritization, and query matching. Completely decoupled with zero external dependencies (no reliance on Everything binary or external utilities).
- [x] **Layer 4 Decoupling & 22-Tool Signature Matrix (`devtoolkit/core/signatures.py`)**:
  - Expanded signature checkers to cover all 22 tools (added checkers for `python`, `node`, `git`, `docker`, `kubectl`, `terraform`, `gh`, `ollama`, `sqlite`, `bun`, `java`, `dotnet`, `flutter`, `android_sdk`, `android_studio`, `vscode`, `cmake`, `c_compiler`, `php`, `composer`, `cuda`, `rust`).
  - Added unified `TARGET_TOOL_BINARIES` mapping.
  - Rewrote `scan_roots_for_tools` to index roots using `FastSearchEngine` and batch query target binaries in <0.02ms, verifying candidate directory structures with signature checkers.
  - Live benchmark on `D:\Dev`: indexed 56,310 entries and verified 6 SDKs in **399.2ms** (vs. 12+ seconds previously).
- [x] **Live Search Engine Telemetry & Manual Re-indexing UI**:
  - **Memory & Process Footprint**: Implemented `estimate_memory_bytes()` on `SearchIndex` and native Win32 working set RAM calculation `get_process_ram_bytes()` via `K32GetProcessMemoryInfo` (zero external dependencies).
  - **Singleton & Engine State**: Added `get_search_engine()` global singleton provider, indexing lifecycle tracking (`is_indexing`, `last_indexed_at`), and `get_telemetry()`.
  - **API Endpoints**: Engineered `GET /api/search/status` (live telemetry) and `POST /api/search/reindex` (on-demand re-index across monitored roots).
  - **UI Integration**:
    - **Sidebar Footer**: Live search status (`Ready (<count> files • <duration>ms)`, `Indexing...`, `Idle`).
    - **Bottom Status Bar**: Displays real-time `PATH: <count>`, `Search RAM: <formatted>`, and live process `Process RAM: <formatted>`.
    - **Settings Tab**: Added dedicated **FastSearch Engine Telemetry** card featuring a 6-metric grid (Engine Strategy, Indexed Files, Indexed Folders, Build Latency, Index Memory, Process RAM) and an interactive **Re-index Now** button with spinning refresh animation and toast feedback.
- [x] **Verification & Standalone Recompilation**:
  - Authored comprehensive test suite in `tests/test_search_engine.py` and `tests/test_server.py`.
  - All 170 project tests pass (`170 passed in 99.13s`).
  - Replaced deprecated `@app.on_event("startup")` with modern FastAPI `lifespan` async context manager.
  - Resolved `AttributeError: 'DevToolkitConfig' object has no attribute 'search_roots'` in `devtoolkit/server/routes/search.py` by referencing `config.search_paths`.
  - Resolved 64-bit Windows handle truncation in `get_process_ram_bytes()` by declaring `GetCurrentProcess.restype = wintypes.HANDLE` and PSAPI `argtypes`/`restype`, restoring real-time Win32 process working set RAM reporting.
  - Implemented automatic background warmup indexing (`warmup_search_engine_background`) on server launch, preventing uninitialized "Idle / None / Never" startup state.
  - Added smart fallback search roots (`D:\Dev`, `C:\Dev`) in discovery pipeline and re-indexer when custom config search paths are unconfigured.
  - Standalone binary recompiled: `dist/DevToolkit.exe` (21.0 MB).

---

## Milestone Checklist: Phase 9 (Completed - Fast Search Utility Tab & Everything-Class Engine)
- [x] **Everything Search Query Parser & Engine (`devtoolkit/core/search/query.py`)**:
  - `EverythingQueryParser`: tokenizes queries respecting quotes, boolean AND (spaces), boolean OR (`|`), boolean NOT (`!`), and function directives (`ext:`, `size:`, `dm:`, `path:`, `folder:`, `file:`, `case:`, `regex:`).
  - Consistent prefix + term syntax support: seamlessly parses `folder:project`, `dir:tests`, `file:main`, `is:folder:app`, as well as `folder: project` without requiring a space.
  - Human-friendly size parser (`100mb`, `10kb`, `500b`, `1mb..10mb`) and presets (`empty`, `tiny`, `small`, `medium`, `large`, `huge`, `gigantic`).
  - Date modified filter ranges (`today`, `yesterday`, `past7`, `past30`, `thisweek`, `thismonth`, `thisyear`, `pastyear`, `YYYY`, `YYYY-MM`).
  - Relevance ranking: prioritizes match quality by default (exact name match > exact stem > prefix > word boundary `_`, `-`, `.` > substring > path; favoring cleaner filenames), with column sort applied on top if selected.
  - `execute_search()`: Sub-millisecond filtering across `SearchIndex` with multi-column sorting (relevance, name, path, size, mtime, ext), total indexed reporting, and memory-capped slicing.
- [x] **Server API Endpoints & Workstation Actions**:
  - `POST /api/search/query` and `GET /api/search/query` for structured query requests.
  - `POST /api/action/open-file`: Native Windows file launch via `os.startfile(path)`.
  - `POST /api/action/reveal-file`: Native Windows Explorer file reveal via `explorer.exe /select,"path"`.
- [x] **Comprehensive UI in Side Panel & Workspace**:
  - Added **Fast Search** navigation button directly below **Environment** in the sidebar.
  - **Status & Count Alignment**: Synchronized status and file counts across sidebar nav badge, sidebar footer, settings telemetry card, and search metrics bar. Removed confusing query match count overwrite on global sidebar badge.
  - **Monitored Roots Banner**: Added `#fs-monitored-paths-banner` in Fast Search view matching Environment view, listing active scanned roots with direct shortcut to Settings.
  - **Syntax Injection & Bidirectional Sync**: Scope, Size, Date Modified, and Quick Ext visual controls inject relative Everything syntax directly into the search bar (`folder:`, `file:`, `size:large`, `dm:today`, `ext:py`) leveraging the syntax parser, with instant bidirectional sync when typing.
  - **Search Control Center**: Prominent search bar with clear button (`Esc`), keyboard accelerator badge (`/`), and 4 modifier toggles (`Aa`, `\b`, `PATH`, `.*`).
  - **Category Filter Pills**: Quick filter bar for `All`, `Code`, `Executables`, `Documents`, `Archives`, `Folders`.
  - **Collapsible Syntax Cheat Sheet**: Interactive accordion detailing Everything search operators.
  - **Results Data Grid**: High-density sortable table with file-type icons, parent folder linking, double-click launch, hover actions (Open, Reveal, Copy), and pagination controls.
  - **Clean Toolbar**: Removed redundant "Copy Paths" button next to "Export CSV".
  - **Keyboard Accelerators**: `1` (Env), `2` (Search), `3` (Ports), `4` (Project), `5` (Settings), `/` (Focus Search), `↑ / ↓` (Navigate rows), `Enter` (Open), `Ctrl+C` (Copy path).
- [x] **Automated Testing & Standalone Build**:
  - Added unit tests in `tests/test_search_query.py` covering prefix-term syntax consistency and relevance ranking.
  - Full test suite: **177 / 177 passed in 100.20s**.
  - Recompiled standalone executable: `dist/DevToolkit.exe` (**21.02 MB**).

---

## Milestone Checklist: Phase 10 (Completed - Real-Time Live Updating & Settings Toggle Control)
- [x] **Zero-Dependency Win32 Filesystem Watcher (`devtoolkit/core/search/watcher.py`)**:
  - Direct Win32 `ReadDirectoryChangesW` kernel monitoring via `ctypes` without third-party dependencies (`watchdog`, `pywin32`).
  - Prunes developer churn folders (`.git`, `node_modules`, `build`, `dist`, `__pycache__`, `.venv`, `target`).
  - Handles `FILE_ACTION_ADDED`, `FILE_ACTION_REMOVED`, `FILE_ACTION_MODIFIED`, `FILE_ACTION_RENAMED_OLD_NAME`, `FILE_ACTION_RENAMED_NEW_NAME`.
  - Graceful teardown via `CancelIoEx` and `CloseHandle`.
- [x] **O(1) SearchIndex Mutations (`devtoolkit/core/search/index.py`)**:
  - Added `_path_map: Dict[str, int]` for instantaneous entry lookups, renames, and deletions.
  - Implemented swap-with-last contiguous array deletion to ensure zero memory compaction overhead during high-frequency filesystem events.
  - Case-preserving path storage with Windows case-insensitive fallback.
- [x] **FastSearchEngine Watcher Orchestration & Telemetry (`devtoolkit/core/search/engine.py`)**:
  - Manages watcher daemon threads across all active user-configured search roots.
  - Dynamic `enable_realtime(bool)` toggles background threads on demand.
  - Telemetry payload exposes `realtime_enabled`, `is_live`, and `active_watchers`.
- [x] **Server API Route & Config Persistence (`devtoolkit/server/routes/search.py`)**:
  - `POST /api/search/realtime`: toggles watcher state and persists `realtime_search: bool` in `devtoolkit.config.yaml`.
- [x] **UI Control & Non-Distracting Status (`index.html`, `app.js`)**:
  - Settings screen FastSearch card features a dedicated Real-Time Index Updating toggle switch with status pill (`Active (Live)`, `Enabled`, `Disabled`).
  - Clean text indicator: displays **`Ready (live)`** when real-time updates are active—**zero pulsing or blinking animations**, adhering strictly to user preferences.
  - 4-second background telemetry polling keeps indexed counts and status fresh during live file events.
- [x] **Automated Testing & Compilation**:
  - Created `tests/test_search_watcher.py` validating O(1) mutations, live filesystem event synchronization, engine lifecycle, and API endpoint.
  - All **181 / 181** tests passing.
  - Recompiled standalone executable: `dist/DevToolkit.exe` (**21.04 MB**).

---

## Milestone Checklist: Phase 11 (Completed - Security & Process Hardening)
- [x] Port killer safeguards protecting Windows critical services (`System`, `svchost.exe`, `csrss.exe`, `smss.exe`, `services.exe`, `lsass.exe`).
- [x] Confirmation guards and `--force` requirements for terminating system-bound ports.
- [x] Cross-platform process identification and graceful kill signal dispatch.

---

## Milestone Checklist: Phase 12 (Completed - CI/CD Automation & Dynamic Versioning)
- [x] Automated GitHub Actions CI workflow on pull requests (`.github/workflows/pr.yml`).
- [x] Post-merge pipeline (`.github/workflows/post-merge.yml`) and daily release packaging (`.github/workflows/build.yml`).
- [x] Dynamic semantic version resolution across CLI, API, UI, and compiled executable via `git describe` / dynamic stamping.
- [x] Strict branch protection and PR governance guidelines in `CONTRIBUTING.md`.

---

## Milestone Checklist: Phase 13 (Completed - Decoupled Daemon, System Tray & Python Native UI)
- [x] **Task 13 - 01**: Headless background daemon runner (`devtoolkit/daemon/server.py`), PID lockfile registry (`devtoolkit/daemon/manager.py`), CLI subcommands (`devtoolkit daemon start|stop|status`, `devtoolkit web`).
- [x] **Task 13 - 02**: Pure Win32 `ctypes` notification tray (`devtoolkit/daemon/tray.py`), balloon notifications, PyWebView window close interception (`devtoolkit/server/app.py`), configurable close actions (`ask` / `minimize` / `exit`).
- [x] **Task 13 - 03**: Python Native UI core architecture: decoupled HTTP/SSE client (`devtoolkit/client/api.py`), observable state store (`devtoolkit/client/state.py`), dark obsidian theme tokens (`devtoolkit/client/theme.py`), window shell (`devtoolkit/client/app.py`), CLI launcher (`devtoolkit native`).
- [x] **Task 13 - 04**: Python Native UI views & modals: Deep Tool Inspector modal (`ToolInspectorModal`), Port Manager view with process termination, Project Auditor with native folder picker, Fast Search with Explorer context menu, and Preferences / Settings view.
- [x] **Task 13 - 05**: Production packaging & cross-client integration: dual-window tray menu, PyInstaller standalone executable compilation (`dist/DevToolkit.exe` - **24.13 MB**), extended CI smoke tests, and documentation.
- [x] All 237 tests passing (100%).

## Milestone Checklist: Phase 14 (Active)
- [x] **Task 14 - 01**: Remove Tkinter Native UI and establish Clients architecture hub:
  - Removed Tkinter UI implementation (`devtoolkit/client/app.py`, `theme.py`, `dialogs/`, `views/`).
  - Retained and elevated decoupled Client SDK: `DevToolkitClient` (`devtoolkit/client/api.py`) and `ClientState` (`devtoolkit/client/state.py`).
  - Created dedicated `clients/README.md` integration specification and API catalogue for future UI applications (React, Vue, TUI, etc.).
  - Cleaned CLI (`devtoolkit/cli/main.py`), System Tray (`devtoolkit/daemon/tray.py`), PyInstaller build (`scripts/build_standalone.ps1`), and CI smoke tests (`pr.yml`, `post-merge.yml`).
  - Compiled slim standalone binary: `dist/DevToolkit.exe` (**21.11 MB**, down from 24.13 MB).
  - All 224 automated unit and integration tests passing (100%).





