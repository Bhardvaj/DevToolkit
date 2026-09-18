import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
from devtoolkit.core.base import BaseInspector
from devtoolkit.core.inventory import OSInventory
from devtoolkit.core.models import (
    CompanionTool,
    DeepTelemetryReport,
    DiagnosticIssue,
    DiagnosticLevel,
    DiscoveredInstance,
    EnvVarStatus,
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

    def deep_inspect(self, runner: SafeRunner, base_report: Optional[ToolReport] = None) -> DeepTelemetryReport:
        base_rep = base_report if base_report is not None else self.inspect(runner)
        trace: list[str] = [f"Base inspection complete. installed={base_rep.installed}"]
        instances: list[DiscoveredInstance] = []
        seen_paths: set[str] = set()

        def _add_inst(p: Path, bin_p: Path | None, ver: str | None, src: str, active: bool, details: str | None = None):
            key = str(bin_p or p).lower() if sys.platform == "win32" else str(bin_p or p)
            if key not in seen_paths:
                seen_paths.add(key)
                instances.append(
                    DiscoveredInstance(
                        path=str(p),
                        binary_path=str(bin_p) if bin_p else None,
                        version=ver,
                        source=src,
                        is_active=active,
                        details=details,
                    )
                )

        # 1. System PATH binaries
        path_bins = runner.resolve_all_binaries("docker")
        trace.append(f"Found {len(path_bins)} 'docker' binary candidates in system PATH")
        for idx, pb in enumerate(path_bins):
            is_act = (idx == 0) and bool(base_rep.binary_path) and (str(pb).lower() == str(base_rep.binary_path).lower())
            ver = base_rep.version if is_act else None
            _add_inst(pb.parent, pb, ver, "PATH", is_act, "Active binary in system PATH" if is_act else "Alternate binary in PATH")

        # 2. Known Docker Desktop installation paths
        desktop_cands = [
            Path(r"C:\Program Files\Docker\Docker\resources\bin\docker.exe"),
            Path(r"C:\Program Files\Docker\Docker\Docker Desktop.exe"),
        ]
        for dc in desktop_cands:
            if dc.exists():
                is_act = bool(base_rep.binary_path) and (str(dc).lower() == str(base_rep.binary_path).lower())
                _add_inst(dc.parent, dc, None, "Registry", is_act, "Docker Desktop Resource Binary")

        # 3. Registry uninstall inventory
        reg_apps = OSInventory.find_app_locations("Docker Desktop")
        for reg_p in reg_apps:
            _add_inst(reg_p, None, None, "Registry", False, "Docker Desktop installation from Windows Registry")

        # 4. Monitored Environment Variables Alignment
        env_vars: list[EnvVarStatus] = []

        # DOCKER_HOST
        docker_host = runner.read_env("DOCKER_HOST")
        if docker_host:
            env_vars.append(
                EnvVarStatus(
                    name="DOCKER_HOST",
                    value=docker_host,
                    status="aligned",
                    message="Custom Docker daemon socket/endpoint configured",
                )
            )
        else:
            env_vars.append(
                EnvVarStatus(
                    name="DOCKER_HOST",
                    value=None,
                    status="aligned",
                    message="Using default named pipe (//./pipe/docker_engine) or local socket",
                )
            )

        # DOCKER_CONTEXT
        docker_context = runner.read_env("DOCKER_CONTEXT")
        if docker_context:
            env_vars.append(
                EnvVarStatus(
                    name="DOCKER_CONTEXT",
                    value=docker_context,
                    status="aligned",
                    message=f"Active context explicitly set to '{docker_context}'",
                )
            )

        # 5. Deep Domain Telemetry & Raw Dumps
        daemon_running = base_rep.metadata.get("daemon_running", False)
        telemetry: dict[str, Any] = {
            "daemon_running": daemon_running,
            "engine_state": "Running (Active)" if daemon_running else "Stopped / Unreachable",
        }

        raw_dumps: dict[str, str] = {}
        if base_rep.binary_path:
            # docker version
            ver_res = runner.run_command([base_rep.binary_path, "version"], timeout=2.5)
            if ver_res.ok and ver_res.stdout:
                raw_dumps["docker version"] = ver_res.stdout

            # docker context show
            ctx_res = runner.run_command([base_rep.binary_path, "context", "show"], timeout=2.0)
            if ctx_res.ok and ctx_res.stdout:
                telemetry["active_context"] = ctx_res.stdout.strip()

            # docker context ls
            ctx_ls_res = runner.run_command([base_rep.binary_path, "context", "ls"], timeout=2.5)
            if ctx_ls_res.ok and ctx_ls_res.stdout:
                raw_dumps["docker context ls"] = ctx_ls_res.stdout

            # docker info
            info_res = runner.run_command([base_rep.binary_path, "info"], timeout=3.5)
            if info_res.ok and info_res.stdout:
                raw_dumps["docker info"] = info_res.stdout
                for line in info_res.stdout.splitlines():
                    if "Containers:" in line:
                        telemetry["containers_count"] = line.split(":")[-1].strip()
                    elif "Operating System:" in line:
                        telemetry["daemon_os"] = line.split(":")[-1].strip()
                    elif "OSType:" in line:
                        telemetry["daemon_os_type"] = line.split(":")[-1].strip()
                    elif "Architecture:" in line:
                        telemetry["daemon_arch"] = line.split(":")[-1].strip()
            elif info_res.stderr:
                raw_dumps["docker info error"] = info_res.stderr

        return DeepTelemetryReport(
            tool_id=self.id,
            timestamp=datetime.now(timezone.utc).isoformat(),
            probe_latency_ms=0,
            instances=instances,
            env_vars=env_vars,
            telemetry=telemetry,
            raw_dumps=raw_dumps,
            discovery_trace=trace,
        )
