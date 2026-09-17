# DevToolkit ⚡

> An extensible, developer-focused utility software for environment auditing, system health diagnostics, and developer workflows with a modern desktop UI and fast CLI.

---

## 🚀 Overview

`DevToolkit` is built to inspect, diagnose, and streamline developer workstations. It automatically audits installed runtimes, SDKs, CLIs, and environmental configurations across Windows, macOS, and Linux.

### Key Capabilities
- **Automated Environment Auditing**: Instant discovery of Node.js, Python, Git, Docker, Go, Rust, Java/JDK, Android SDK, Flutter, and companion package managers.
- **Health & Diagnostic Checks**: Detect path collisions, missing system variables (`ANDROID_HOME`, `JAVA_HOME`), and broken symlinks.
- **Pluggable Architecture**: Add new inspection providers, cache cleaners, or port utilities without altering the core engine.
- **Dual Interface**: A clean terminal CLI for automation/scripting, alongside a modern, sleek desktop UI for interactive workstation management.

---

## 🛠️ Architecture & Agent Knowledge Base

To ensure frictionless collaboration between human developers and AI assistants, persistent architectural blueprints and living design registries are maintained in the [`agent/`](./agent/) directory:

- [**`agent/map.md`**](./agent/map.md): System architecture, execution lifecycles, and module boundaries.
- [**`agent/codebase.md`**](./agent/codebase.md): Module registry, public APIs, and plugin creation guide.
- [**`agent/decisions.md`**](./agent/decisions.md): Architecture Decision Records (ADRs) tracking design choices and trade-offs.
- [**`agent/state.md`**](./agent/state.md): Project status, roadmap, completed milestones, and session memory.

---

## 💻 Local Development

### Prerequisites
- Python 3.11+ (Python 3.14 recommended)
- Node.js v20+ (for front-end UI assets)
- Git

### Setup Instructions
*(Detailed step-by-step instructions will be populated as the core modules are scaffolded.)*

---

## 📄 License
MIT
