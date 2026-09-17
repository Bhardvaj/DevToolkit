# Living Codebase Registry & API Guide

This document maintains a living catalog of all modules, base classes, public interfaces, and extension points within `DevToolkit`.

---

## 1. Directory Structure Overview

```
devtoolkit/
├── core/                  # Core engine kernel
│   ├── base.py            # BaseInspector, BaseUtility, HealthStatus, ToolReport
│   ├── runner.py          # SafeRunner: Subprocess execution with timeouts & path discovery
│   ├── registry.py        # Dynamic plugin discovery and dependency resolution
│   └── models.py          # Pydantic data schemas for inspection and audits
├── cli/                   # Typer CLI application and commands
│   ├── main.py            # Root CLI entrypoint
│   └── commands/          # CLI command implementations (inspect, doctor, ui)
├── formatters/            # Output presentation formats
│   ├── table.py           # Rich terminal table formatter
│   ├── json_fmt.py        # JSON serialization
│   └── yaml_fmt.py        # YAML serialization
├── modules/               # Pluggable feature modules
│   └── inspectors/        # Individual environment inspector providers
└── ui/                    # Front-end desktop interface (React / Tailwind)
```

---

## 2. Key Abstractions

### `core.base.BaseInspector`
Abstract base class that all tool and SDK detectors must implement:
- `id: str`: Unique slug (e.g. `"nodejs"`, `"flutter"`).
- `name: str`: Human-readable display label (e.g. `"Node.js"`).
- `category: str`: Tool grouping (`"runtime"`, `"vcs"`, `"mobile"`, `"container"`, `"database"`).
- `inspect(runner: SafeRunner) -> ToolReport`: Runs non-destructive probes and returns detected paths, versions, and companion status.
- `diagnose_health(report: ToolReport) -> HealthReport`: Evaluates configuration status, missing variables, or environment conflicts.

### `core.runner.SafeRunner`
Centralized helper for external process execution:
- `resolve_binary(name: str, extra_paths: list[str] = None) -> Optional[Path]`: Cross-platform binary resolution (`PATH`, Windows extensions, registry).
- `run_command(cmd: list[str], timeout: float = 3.0) -> CommandResult`: Executes read-only commands with strict timeout guarantees.

---

## 3. How to Add a New Inspector (Guide for Contributors & AI Agents)

Creating a new environment inspector requires creating a single file in `devtoolkit/modules/inspectors/<tool_name>.py`:

```python
from devtoolkit.core.base import BaseInspector, HealthStatus
from devtoolkit.core.models import ToolReport, DiagnosticIssue

class RustInspector(BaseInspector):
    id = "rust"
    name = "Rust / Cargo"
    category = "runtime"

    def inspect(self, runner) -> ToolReport:
        rustc_path = runner.resolve_binary("rustc")
        if not rustc_path:
            return ToolReport(id=self.id, name=self.name, installed=False)
            
        version_result = runner.run_command([str(rustc_path), "--version"])
        cargo_path = runner.resolve_binary("cargo")
        
        return ToolReport(
            id=self.id,
            name=self.name,
            installed=True,
            binary_path=str(rustc_path),
            version=version_result.stdout.strip(),
            companions={"cargo": str(cargo_path) if cargo_path else None},
            status=HealthStatus.HEALTHY if cargo_path else HealthStatus.WARNING
        )
```
The plugin will be automatically discovered by `PluginRegistry` without touching any other files.
