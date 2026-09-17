"""Docker & Containerization Environment Inspector."""

import re
from pathlib import Path
from devtoolkit.core.base import BaseInspector
from devtoolkit.core.models import (
    CompanionTool,
    DiagnosticIssue,
    DiagnosticLevel,
    HealthStatus,
    ToolReport,
)
from devtoolkit.core.runner import SafeRunner


class DockerInspector(BaseInspector):
    id = "docker"
    name = "Docker"
    category = "container"
    categories = ["container", "runtime"]
    description = "Docker container engine, Docker CLI, and Docker Compose"

    def inspect(self, runner: SafeRunner) -> ToolReport:
        docker_bin = runner.resolve_binary("docker")
        if not docker_bin:
            return ToolReport(
                id=self.id,
                name=self.name,
                category=self.category,
                categories=self.categories,
                installed=False,
                status=HealthStatus.NOT_FOUND,
            )

        # Output format: "Docker version 27.0.3, build 7d4bed8"
        res = runner.run_command([str(docker_bin), "--version"])
        version = None
        if res.ok and res.stdout:
            m = re.search(r"Docker version\s+([0-9.]+)", res.stdout)
            version = m.group(1) if m else res.stdout

        companions = []
        diagnostics = []

        # Check Docker Compose (plugin or standalone binary)
        compose_res = runner.run_command([str(docker_bin), "compose", "version"], timeout=2.0)
        compose_ver = None
        if compose_res.ok and compose_res.stdout:
            m = re.search(r"v?([0-9.]+)", compose_res.stdout)
            compose_ver = m.group(1) if m else compose_res.stdout
            companions.append(
                CompanionTool(
                    name="docker compose",
                    installed=True,
                    version=compose_ver,
                    binary_path=str(docker_bin),
                )
            )
        else:
            compose_standalone = runner.resolve_binary("docker-compose")
            if compose_standalone:
                c_res = runner.run_command([str(compose_standalone), "--version"])
                companions.append(
                    CompanionTool(
                        name="docker-compose",
                        installed=True,
                        version=c_res.stdout if c_res.ok else None,
                        binary_path=str(compose_standalone),
                    )
                )
            else:
                companions.append(CompanionTool(name="docker compose", installed=False))

        # Check if Docker Daemon is actively running (safe probe via `docker info`)
        info_res = runner.run_command([str(docker_bin), "info"], timeout=3.0)
        daemon_running = info_res.ok and "Server:" in info_res.stdout

        if not daemon_running:
            diagnostics.append(
                DiagnosticIssue(
                    level=DiagnosticLevel.WARNING,
                    message="Docker CLI is installed, but the Docker daemon / Docker Desktop engine is not running.",
                    suggested_fix="Launch Docker Desktop or start the Docker service.",
                )
            )

        status = HealthStatus.HEALTHY if daemon_running else HealthStatus.WARNING

        return ToolReport(
            id=self.id,
            name=self.name,
            category=self.category,
            categories=self.categories,
            installed=True,
            version=version,
            binary_path=str(docker_bin),
            home_path=str(docker_bin.parent),
            status=status,
            companions=companions,
            diagnostics=diagnostics,
            metadata={"daemon_running": daemon_running},
        )
