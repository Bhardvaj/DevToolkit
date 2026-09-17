# Architecture Decision Records (ADR)

This file tracks major architectural choices, technical decisions, and trade-offs made during the evolution of `DevToolkit`.

---

## ADR-0001: Core Architecture & Presentation Decoupling
- **Date**: 2026-09-16
- **Status**: Accepted
- **Context**: The project requires both a responsive CLI and a modern, aesthetically pleasing UI with easy UX. Traditional Python GUI frameworks (Tkinter, PyQt, wxPython) are heavy and visually dated.
- **Decision**: Decouple the Core Engine (responsible for discovery, subprocess management, registry, and health checks) from the Presentation Layer. Enable both CLI operation and modern Web/Desktop UI without coupling business logic to GUI frameworks.
- **Consequences**:
  - Inspectors can be tested headlessly via standard unit tests.
  - Front-end developers or agents can build and iterate on modern UI components using web technologies (React/Tailwind) without wrestling with native desktop GUI toolkits.

---

## ADR-0002: Non-Blocking Subprocess Probe Timeouts
- **Date**: 2026-09-16
- **Status**: Accepted
- **Context**: Running external CLI binaries (`--version`) can hang indefinitely if a tool attempts an interactive prompt, network license check, or gets stuck in a broken pipe.
- **Decision**: All process probes must execute strictly through `SafeRunner` with a mandatory maximum timeout (default 3.0 seconds) and non-blocking stream capture.
- **Consequences**: The inspector is guaranteed never to hang, regardless of local environment misconfigurations.

---

## ADR-0003: Dynamic Plugin Discovery Pattern
- **Date**: 2026-09-16
- **Status**: Accepted
- **Context**: DevToolkit needs to support third-party or future modules (cache cleaners, port killers, environment variable editors) without modifying the core discovery loop.
- **Decision**: Implement a dynamic provider registry pattern. Modules placed in `devtoolkit/modules/` implementing `BaseInspector` or `BaseUtility` are registered dynamically via module scanning.
- **Consequences**: Adding new tool support is isolated to single-file additions with zero merge conflicts on core files.

---

## ADR-0004: Python + React/Tailwind Hybrid Architecture (PyWebView & FastAPI)
- **Date**: 2026-09-16
- **Status**: Accepted
- **Context**: The user requires a modern, beautiful UI with easy UX alongside maximum plugin authoring ergonomics ("Ultra-Extensible") and zero heavyweight runtime overhead.
- **Decision**: Adopt the Python Desktop + Web Hybrid architecture. The Core Engine and plugin system run in Python 3.14. The UI is built using React + Tailwind CSS + Lucide Icons, served locally via FastAPI and rendered in a native desktop window via PyWebView (Edge WebView2). The engine also directly powers the CLI (`devtoolkit inspect`) and local browser dashboard (`devtoolkit ui`).
- **Consequences**:
  - Zero additional SDK installations required (Python 3.14 and Node 24 already present).
  - Plugin creation remains as simple as writing a single ~15-line Python file.
  - Desktop memory usage is kept light (~40MB vs Electron's 150MB+).
