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
│   ├── core/                          # Engine kernel
│   │   ├── base.py                    # BaseInspector and BaseUtility abstractions
│   │   ├── models.py                  # Pydantic schemas (ToolReport, HealthStatus, AuditSummary)
│   │   ├── runner.py                  # SafeRunner: Subprocess execution with timeouts & path resolution
│   │   └── registry.py                # PluginRegistry: Dynamic inspector auto-discovery & multithreading
│   ├── cli/                           # Command-line interface (Typer)
│   │   └── main.py                    # `devtoolkit inspect`, `devtoolkit doctor`, `devtoolkit ui`
│   ├── formatters/                    # Output formatting layer
│   │   ├── table.py                   # Rich console tables and health badge formatting
│   │   ├── json_fmt.py                # Machine-readable JSON output
│   │   └── yaml_fmt.py                # Machine-readable YAML output
│   ├── modules/
│   │   └── inspectors/                # Pluggable tool inspectors
│   │       ├── node.py                # Node.js, npm, pnpm, yarn, corepack
│   │       ├── python.py              # Python, pip, uv, poetry, conda, pipenv
│   │       ├── git.py                 # Git, GitHub CLI (gh), global user config
│   │       ├── docker.py              # Docker CLI, Docker Compose, engine daemon check
│   │       ├── golang.py              # Go compiler, GOPATH, GOROOT
│   │       ├── rust.py                # Rustc, Cargo, rustup toolchain
│   │       ├── java.py                # JVM, javac (JDK), JAVA_HOME, Windows Registry
│   │       ├── android.py             # Android SDK, adb, emulator, ANDROID_HOME
│   │       ├── android_studio.py      # Android Studio IDE, JBR (OpenJDK 21), build numbers
│   │       └── flutter.py             # Flutter SDK, Dart SDK, release channel
│   └── server/                        # UI and API layer
│       └── app.py                     # FastAPI REST server & PyWebView desktop launcher
└── tests/                             # Automated test suite
    ├── test_runner.py                 # Tests for SafeRunner timeouts & path resolution
    ├── test_registry.py               # Tests for dynamic plugin discovery & filtering
    ├── test_inspectors.py             # Tests for tool inspection logic
    └── test_server.py                 # Tests for FastAPI server endpoints and UI rendering
```

---

## 2. Core Abstractions & Models

### `core.models.ToolReport`
Standard data contract returned by all inspectors:
```python
class ToolReport(BaseModel):
    id: str                                    # e.g., "node", "flutter"
    name: str                                  # e.g., "Node.js", "Flutter SDK"
    category: str                              # "runtime", "vcs", "mobile", "container"
    installed: bool                            # True if binary or home folder resolved
    version: Optional[str]                     # Normalized semantic version
    binary_path: Optional[str]                 # Absolute executable path
    home_path: Optional[str]                   # SDK home or root folder
    status: HealthStatus                       # HEALTHY, WARNING, ERROR, NOT_FOUND
    companions: List[CompanionTool]            # Companion tools (e.g., npm, cargo, dart)
    diagnostics: List[DiagnosticIssue]         # Actionable issues and suggested fixes
    metadata: Dict[str, Any]                   # Environment metadata (channel, prefix, etc.)
```

### `core.runner.SafeRunner`
Subprocess and path resolution kernel:
- `run_command(cmd, timeout=3.0, env=None) -> CommandResult`: Enforces non-blocking execution and strict timeout.
- `resolve_binary(name, extra_paths=None) -> Optional[Path]`: Resolves binaries across `PATH`, extra paths, and Windows extensions (`.exe`, `.cmd`, `.bat`).
- `read_env(var_name) -> Optional[str]`: Safe retrieval of environment variables.
- `query_winreg(key_path, value_name) -> Optional[str]`: Windows registry query (`HKLM` and `HKCU`).

### `core.registry.PluginRegistry`
Dynamic module discovery and concurrent auditor:
- `discover_inspectors()`: Iterates `devtoolkit.modules.inspectors` and instantiates all `BaseInspector` subclasses.
- `run_audit(categories=None, tool_ids=None, max_workers=8) -> AuditSummary`: Executes inspection probes concurrently in a thread pool.

---

## 3. How to Add a New Inspector (< 20 Lines of Code)

To add support for another tool (e.g., `bun`):
1. Create `devtoolkit/modules/inspectors/bun.py`:
```python
from devtoolkit.core.base import BaseInspector
from devtoolkit.core.models import ToolReport, HealthStatus
from devtoolkit.core.runner import SafeRunner

class BunInspector(BaseInspector):
    id = "bun"
    name = "Bun"
    category = "runtime"

    def inspect(self, runner: SafeRunner) -> ToolReport:
        binary = runner.resolve_binary("bun")
        if not binary:
            return ToolReport(id=self.id, name=self.name, category=self.category, installed=False)
        
        res = runner.run_command([str(binary), "--version"])
        return ToolReport(
            id=self.id,
            name=self.name,
            category=self.category,
            installed=True,
            version=res.stdout if res.ok else None,
            binary_path=str(binary),
            status=HealthStatus.HEALTHY if res.ok else HealthStatus.WARNING,
        )
```
2. The plugin will be automatically discovered by `PluginRegistry` without editing any registry or configuration files.
