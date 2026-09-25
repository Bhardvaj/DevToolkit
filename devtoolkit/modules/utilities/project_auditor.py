"""Project Workstation Auditor: Verifies if a machine meets repository prerequisites."""

import json
import re
from pathlib import Path
from typing import List, Optional
from pydantic import BaseModel, Field

from devtoolkit.core.registry import PluginRegistry
from devtoolkit.core.runner import SafeRunner


class RequirementCheck(BaseModel):
    name: str
    required: str
    detected: Optional[str] = None
    satisfied: bool = False
    message: str


class ProjectAuditReport(BaseModel):
    project_name: str
    project_path: str
    detected_types: List[str] = Field(default_factory=list)
    ready_to_build: bool = True
    checks: List[RequirementCheck] = Field(default_factory=list)
    suggested_actions: List[str] = Field(default_factory=list)


class ProjectAuditor:
    """Audits local workspace projects against workstation runtimes and SDKs."""

    def __init__(self, runner: Optional[SafeRunner] = None, registry: Optional[PluginRegistry] = None):
        self.runner = runner or SafeRunner(default_timeout=3.0)
        self.registry = registry or PluginRegistry(self.runner)

    def audit_project(
        self,
        project_path: Path,
        audit_summary: Optional[AuditSummary] = None,
    ) -> ProjectAuditReport:
        p_dir = Path(project_path).expanduser().resolve()
        if not p_dir.exists() or not p_dir.is_dir():
            return ProjectAuditReport(
                project_name=p_dir.name,
                project_path=str(p_dir),
                ready_to_build=False,
                checks=[
                    RequirementCheck(
                        name="Project Directory",
                        required="Existing Directory",
                        detected="Not Found",
                        satisfied=False,
                        message=f"Directory '{p_dir}' does not exist.",
                    )
                ],
            )

        checks: List[RequirementCheck] = []
        detected_types: List[str] = []
        suggested_actions: List[str] = []
        required_tools: set = set()

        # 1. Node.js & Web Project Check
        pkg_json = p_dir / "package.json"
        if pkg_json.exists():
            detected_types.append("Node.js / Frontend")
            required_tools.add("node")

        # 2. Python Project Check
        pyproject = p_dir / "pyproject.toml"
        req_txt = p_dir / "requirements.txt"
        if pyproject.exists() or req_txt.exists():
            detected_types.append("Python")
            required_tools.add("python")

        # 3. Flutter / Dart Project Check
        pubspec = p_dir / "pubspec.yaml"
        if pubspec.exists():
            detected_types.append("Flutter / Dart")
            required_tools.add("flutter")

        # 4. Android Project Check
        build_gradle = p_dir / "build.gradle"
        build_gradle_kts = p_dir / "build.gradle.kts"
        app_build_gradle = p_dir / "app" / "build.gradle"
        if build_gradle.exists() or build_gradle_kts.exists() or app_build_gradle.exists():
            detected_types.append("Android")
            required_tools.update(["android", "java"])

        # 5. Docker Project Check
        dockerfile = p_dir / "Dockerfile"
        compose_file = p_dir / "docker-compose.yml"
        compose_yaml = p_dir / "compose.yaml"
        if dockerfile.exists() or compose_file.exists() or compose_yaml.exists():
            detected_types.append("Docker")
            required_tools.add("docker")

        # 6. Rust Project Check
        cargo_toml = p_dir / "Cargo.toml"
        if cargo_toml.exists():
            detected_types.append("Rust")
            required_tools.add("rust")

        # 7. Go Project Check
        go_mod = p_dir / "go.mod"
        if go_mod.exists():
            detected_types.append("Go")
            required_tools.add("golang")

        # Gather machine environment only for required tools
        if audit_summary is not None:
            summary = audit_summary
        elif required_tools:
            summary = self.registry.run_audit(tool_ids=list(required_tools))
        else:
            summary = None

        installed_tools = {r.id: r for r in summary.reports if r.installed} if summary else {}

        # Run checks for detected types
        if pkg_json.exists():
            self._check_node_project(pkg_json, installed_tools, checks, suggested_actions)

        if pyproject.exists() or req_txt.exists():
            self._check_python_project(pyproject, req_txt, installed_tools, checks, suggested_actions)

        if pubspec.exists():
            self._check_flutter_project(pubspec, installed_tools, checks, suggested_actions)

        if build_gradle.exists() or build_gradle_kts.exists() or app_build_gradle.exists():
            self._check_android_project(p_dir, installed_tools, checks, suggested_actions)

        if dockerfile.exists() or compose_file.exists() or compose_yaml.exists():
            self._check_docker_project(installed_tools, checks, suggested_actions)

        if cargo_toml.exists():
            self._check_rust_project(cargo_toml, installed_tools, checks, suggested_actions)

        if go_mod.exists():
            self._check_go_project(go_mod, installed_tools, checks, suggested_actions)

        if not detected_types:
            checks.append(
                RequirementCheck(
                    name="Generic Workspace",
                    required="Standard Development Files",
                    detected="No known project manifest",
                    satisfied=True,
                    message="No known framework manifests (package.json, pyproject.toml, pubspec.yaml, etc.) found.",
                )
            )

        ready = all(c.satisfied for c in checks)
        return ProjectAuditReport(
            project_name=p_dir.name,
            project_path=str(p_dir),
            detected_types=detected_types,
            ready_to_build=ready,
            checks=checks,
            suggested_actions=suggested_actions,
        )

    def _check_node_project(self, pkg_path: Path, tools: dict, checks: list, actions: list):
        node_tool = tools.get("node")
        if not node_tool:
            checks.append(
                RequirementCheck(
                    name="Node.js Runtime",
                    required="Installed",
                    detected="Missing",
                    satisfied=False,
                    message="Node.js is not installed on this machine.",
                )
            )
            actions.append("Install Node.js (https://nodejs.org).")
            return

        checks.append(
            RequirementCheck(
                name="Node.js Runtime",
                required="Installed",
                detected=f"v{node_tool.version}",
                satisfied=True,
                message=f"Node.js v{node_tool.version} is installed.",
            )
        )

        try:
            data = json.loads(pkg_path.read_text(encoding="utf-8"))
            engines = data.get("engines", {})
            req_node = engines.get("node")
            if req_node:
                checks.append(
                    RequirementCheck(
                        name="Node.js Version Engine",
                        required=req_node,
                        detected=f"v{node_tool.version}",
                        satisfied=True,  # Informational check
                        message=f"Project specifies Node.js engine '{req_node}' (current: v{node_tool.version}).",
                    )
                )

            pkg_mgr = data.get("packageManager", "")
            if "pnpm" in pkg_mgr:
                has_pnpm = any(c.name == "pnpm" and c.installed for c in node_tool.companions)
                checks.append(
                    RequirementCheck(
                        name="pnpm Package Manager",
                        required=pkg_mgr,
                        detected="Available" if has_pnpm else "Missing",
                        satisfied=has_pnpm,
                        message="Project uses pnpm." if has_pnpm else "Project uses pnpm, but pnpm is not in PATH.",
                    )
                )
                if not has_pnpm:
                    actions.append("Run 'corepack enable' or 'npm install -g pnpm'.")
        except Exception:
            pass

    def _check_python_project(self, pyproject: Path, req_txt: Path, tools: dict, checks: list, actions: list):
        py_tool = tools.get("python")
        if not py_tool:
            checks.append(
                RequirementCheck(
                    name="Python Interpreter",
                    required="Installed",
                    detected="Missing",
                    satisfied=False,
                    message="Python is not installed on this machine.",
                )
            )
            actions.append("Install Python 3 (https://python.org).")
            return

        checks.append(
            RequirementCheck(
                name="Python Interpreter",
                required="Installed",
                detected=f"v{py_tool.version}",
                satisfied=True,
                message=f"Python v{py_tool.version} is installed.",
            )
        )

        # Check virtualenv existence in project folder
        p_dir = pyproject.parent if pyproject.exists() else req_txt.parent
        has_venv = any((p_dir / v).exists() for v in [".venv", "venv", "env"])
        checks.append(
            RequirementCheck(
                name="Project Virtual Environment",
                required="Active or Local .venv",
                detected="Found" if has_venv else "Missing",
                satisfied=has_venv,
                message="Local virtual environment (.venv) found." if has_venv else "No local .venv found in project root.",
            )
        )
        if not has_venv:
            actions.append("Create a virtual environment: 'python -m venv .venv'.")

    def _check_flutter_project(self, pubspec: Path, tools: dict, checks: list, actions: list):
        flutter_tool = tools.get("flutter")
        if not flutter_tool:
            checks.append(
                RequirementCheck(
                    name="Flutter SDK",
                    required="Installed",
                    detected="Missing",
                    satisfied=False,
                    message="Flutter SDK is not found on this machine.",
                )
            )
            actions.append("Install Flutter SDK (https://flutter.dev).")
            return

        checks.append(
            RequirementCheck(
                name="Flutter SDK",
                required="Installed",
                detected=f"v{flutter_tool.version or 'detected'}",
                satisfied=True,
                message=f"Flutter SDK is available ({flutter_tool.home_path}).",
            )
        )

    def _check_android_project(self, p_dir: Path, tools: dict, checks: list, actions: list):
        android_sdk = tools.get("android")
        java_tool = tools.get("java")

        has_sdk = android_sdk and android_sdk.installed
        checks.append(
            RequirementCheck(
                name="Android SDK",
                required="Installed",
                detected=str(android_sdk.home_path) if has_sdk else "Missing",
                satisfied=bool(has_sdk),
                message="Android SDK resolved on disk." if has_sdk else "Android SDK is not installed.",
            )
        )

        has_java = java_tool and java_tool.installed
        checks.append(
            RequirementCheck(
                name="Java / JDK (Gradle Build)",
                required="Installed JDK",
                detected=f"v{java_tool.version}" if has_java else "Missing",
                satisfied=bool(has_java),
                message=f"JDK {java_tool.version} detected." if has_java else "JDK required for Gradle build is not found.",
            )
        )

        android_home_set = self.runner.read_env("ANDROID_HOME") is not None
        checks.append(
            RequirementCheck(
                name="ANDROID_HOME Variable",
                required="Configured",
                detected="Set" if android_home_set else "Unset",
                satisfied=android_home_set,
                message="ANDROID_HOME is configured." if android_home_set else "ANDROID_HOME is unset; Gradle builds may fail.",
            )
        )
        if not android_home_set and has_sdk:
            actions.append(f"Set ANDROID_HOME environment variable to '{android_sdk.home_path}'.")

    def _check_docker_project(self, tools: dict, checks: list, actions: list):
        docker_tool = tools.get("docker")
        if not docker_tool:
            checks.append(
                RequirementCheck(
                    name="Docker CLI",
                    required="Installed",
                    detected="Missing",
                    satisfied=False,
                    message="Docker CLI is not installed.",
                )
            )
            actions.append("Install Docker Desktop (https://docker.com).")
            return

        checks.append(
            RequirementCheck(
                name="Docker CLI",
                required="Installed",
                detected=f"v{docker_tool.version or 'detected'}",
                satisfied=True,
                message="Docker CLI is installed.",
            )
        )

        daemon_running = docker_tool.metadata.get("daemon_running", False)
        checks.append(
            RequirementCheck(
                name="Docker Daemon",
                required="Running Engine",
                detected="Running" if daemon_running else "Stopped",
                satisfied=daemon_running,
                message="Docker engine is active." if daemon_running else "Docker CLI found, but Docker daemon is stopped.",
            )
        )
        if not daemon_running:
            actions.append("Start Docker Desktop or Docker service.")

    def _check_rust_project(self, cargo_path: Path, tools: dict, checks: list, actions: list):
        rust_tool = tools.get("rust")
        has_rust = rust_tool and rust_tool.installed
        checks.append(
            RequirementCheck(
                name="Rust Toolchain (Cargo)",
                required="Installed",
                detected=f"v{rust_tool.version}" if has_rust else "Missing",
                satisfied=bool(has_rust),
                message="Rustc and Cargo are installed." if has_rust else "Cargo is not found on this machine.",
            )
        )
        if not has_rust:
            actions.append("Install Rust via rustup (https://rustup.rs).")

    def _check_go_project(self, go_mod: Path, tools: dict, checks: list, actions: list):
        go_tool = tools.get("golang")
        has_go = go_tool and go_tool.installed
        checks.append(
            RequirementCheck(
                name="Go Toolchain",
                required="Installed",
                detected=f"v{go_tool.version}" if has_go else "Missing",
                satisfied=bool(has_go),
                message="Go compiler is installed." if has_go else "Go runtime is not found on this machine.",
            )
        )
        if not has_go:
            actions.append("Install Go compiler (https://go.dev).")

