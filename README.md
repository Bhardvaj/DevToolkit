# DevToolkit ⚡

> An extensible, developer-focused workstation utility for environment auditing, system health diagnostics, and developer workflows with a modern UI and fast CLI.

[![Python](https://img.shields.io/badge/Python-3.11%2B-blue?logo=python)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.111%2B-009688?logo=fastapi)](https://fastapi.tiangolo.com)
[![PyWebView](https://img.shields.io/badge/Desktop-PyWebView-purple)](https://pywebview.flowrl.com)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](https://opensource.org/licenses/MIT)

---

## 🚀 Key Features

- **Automated Workstation Auditing**: Detects installed SDKs, runtimes, and development CLIs:
  - **Runtimes**: Node.js, Python, Go, Rust, Java/JDK
  - **VCS**: Git, GitHub CLI (`gh`)
  - **Containers**: Docker Engine, Docker Compose
  - **Mobile SDKs**: Android SDK (`adb`, `emulator`), Flutter SDK (`dart`)
- **Actionable Diagnostics ("Doctor")**: Detects missing companion tools (e.g. `npm`, `pip`, `cargo`), unset environment variables (`JAVA_HOME`, `ANDROID_HOME`), or path mismatches with suggested fixes.
- **Ultra-Extensible Architecture**: Pluggable provider system. Adding a new tool audit takes < 20 lines of Python code in `devtoolkit/modules/inspectors/`.
- **Dual Interface**:
  - **Terminal CLI**: Rich colored tables, health badges, and JSON/YAML serialization.
  - **Modern UI**: Dark-mode interface running in a native desktop window (PyWebView with Edge WebView2) or local browser dashboard (`localhost:4321`).

---

## 💻 Quick Start

### 1. Prerequisites
- Python 3.11+ (Python 3.14 recommended)
- Git

### 2. Installation

Clone the repository and set up a virtual environment:

```powershell
git clone https://github.com/Bhardvaj/DevToolkit.git
cd DevToolkit

# Create and activate virtual environment
python -m venv .venv
.\.venv\Scripts\activate

# Install dependencies
pip install -e .
```

---

## 🛠️ CLI Usage

### Audit Environment
Run a full workstation audit with colored terminal table:
```powershell
devtoolkit inspect
```

Filter by category (`runtime`, `vcs`, `mobile`, `container`):
```powershell
devtoolkit inspect --category runtime --category mobile
```

Filter by specific tools:
```powershell
devtoolkit inspect --tool node --tool python --tool flutter
```

### Export Results (JSON / YAML)
Export machine-readable data for CI/CD or setup automation:
```powershell
# Output JSON to terminal or save to file
devtoolkit inspect --format json
devtoolkit inspect --format json --output audit.json

# Output YAML
devtoolkit inspect --format yaml
```

### Run Environment Doctor
Check for misconfigurations, missing SDK paths, or broken environments:
```powershell
devtoolkit doctor
```

### Launch Desktop UI / Web Dashboard
Launch the modern UI in a native desktop window:
```powershell
devtoolkit ui
```

Or open directly in your web browser:
```powershell
devtoolkit ui --web
```

---

## 🔌 Authoring a New Inspector Plugin

Adding detection for a new SDK or CLI is straightforward. Create a new file in `devtoolkit/modules/inspectors/<tool>.py`:

```python
from devtoolkit.core.base import BaseInspector
from devtoolkit.core.models import ToolReport, HealthStatus
from devtoolkit.core.runner import SafeRunner

class BunInspector(BaseInspector):
    id = "bun"
    name = "Bun"
    category = "runtime"
    description = "Bun JavaScript/TypeScript runtime and package manager"

    def inspect(self, runner: SafeRunner) -> ToolReport:
        bun_bin = runner.resolve_binary("bun")
        if not bun_bin:
            return ToolReport(id=self.id, name=self.name, category=self.category, installed=False)

        res = runner.run_command([str(bun_bin), "--version"])
        return ToolReport(
            id=self.id,
            name=self.name,
            category=self.category,
            installed=True,
            version=res.stdout if res.ok else None,
            binary_path=str(bun_bin),
            status=HealthStatus.HEALTHY if res.ok else HealthStatus.WARNING,
        )
```

The new inspector will be dynamically discovered by `PluginRegistry` automatically.

---

## 🧪 Running Tests

```powershell
pytest
```

---

## 🧠 AI Agent Knowledge Base

To ensure frictionless collaboration between AI assistants and contributors:
- [`agent/map.md`](./agent/map.md): Architectural design, lifecycles, and component boundaries.
- [`agent/codebase.md`](./agent/codebase.md): Living registry of modules, classes, and APIs.
- [`agent/decisions.md`](./agent/decisions.md): Architecture Decision Records (ADRs).
- [`agent/state.md`](./agent/state.md): Active task status and session memory.

---

## 📄 License
MIT
