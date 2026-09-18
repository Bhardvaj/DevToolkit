"""Ollama Local AI Runtime Inspector."""

import os
import re
import sys
from pathlib import Path
from typing import List, Optional

from devtoolkit.core.base import BaseInspector
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


class OllamaInspector(BaseInspector):
    id = "ollama"
    name = "Ollama"
    category = "ai"
    categories = ["ai", "tools"]
    description = "Local LLM inference server, model runner, and CLI"

    def inspect(self, runner: SafeRunner) -> ToolReport:
        ollama_bin = runner.resolve_binary("ollama")
        user_bin = None

        if not ollama_bin and sys.platform == "win32":
            local_app = os.environ.get("LOCALAPPDATA")
            if local_app:
                cand = Path(local_app) / "Programs" / "Ollama" / "ollama.exe"
                if cand.is_file():
                    user_bin = cand

        active_bin = ollama_bin or user_bin
        if not active_bin:
            return ToolReport(
                id=self.id,
                name=self.name,
                category=self.category,
                categories=self.categories,
                installed=False,
                status=HealthStatus.NOT_FOUND,
            )

        # Version probe: `ollama --version`
        res = runner.run_command([str(active_bin), "--version"])
        version = None
        if res.ok and res.stdout.strip():
            # "ollama version is 0.5.7"
            m = re.search(r"version is\s+([\d\.]+)", res.stdout)
            version = m.group(1) if m else res.stdout.splitlines()[0].strip()

        # Probe daemon and model listing: `ollama list`
        list_res = runner.run_command([str(active_bin), "list"], timeout_seconds=3)
        daemon_online = list_res.ok
        model_names = []
        if list_res.ok and list_res.stdout.strip():
            # Output lines like: NAME ID SIZE MODIFIED
            lines = [line.strip() for line in list_res.stdout.splitlines() if line.strip()]
            if len(lines) > 1:
                for line in lines[1:]:
                    parts = line.split()
                    if parts:
                        model_names.append(parts[0])

        companions: List[CompanionTool] = []
        companions.append(
            CompanionTool(
                name="daemon",
                installed=daemon_online,
                version="Online (:11434)" if daemon_online else "Offline",
            )
        )
        companions.append(
            CompanionTool(
                name="models",
                installed=len(model_names) > 0,
                version=f"{len(model_names)} installed" if daemon_online else None,
            )
        )

        diagnostics: List[DiagnosticIssue] = []

        is_on_path = runner.resolve_binary("ollama") is not None
        if not is_on_path and user_bin:
            diagnostics.append(
                DiagnosticIssue(
                    level=DiagnosticLevel.WARNING,
                    message="Ollama is installed in local app data, but not added to your system PATH.",
                    suggested_fix=f'Add "{user_bin.parent}" to your PATH environment variable.',
                )
            )

        if not daemon_online:
            diagnostics.append(
                DiagnosticIssue(
                    level=DiagnosticLevel.INFO,
                    message="Ollama inference server is currently not running.",
                    suggested_fix="Launch Ollama from the Start Menu or run 'ollama serve' in background.",
                )
            )

        ollama_models_dir = os.environ.get("OLLAMA_MODELS")
        metadata = {
            "daemon_online": daemon_online,
            "models_count": len(model_names),
            "models": model_names[:5],
            "models_dir": ollama_models_dir or str(Path.home() / ".ollama" / "models"),
        }

        status = HealthStatus.HEALTHY if is_on_path else HealthStatus.WARNING

        return ToolReport(
            id=self.id,
            name=self.name,
            category=self.category,
            categories=self.categories,
            installed=True,
            version=version,
            binary_path=str(active_bin),
            home_path=str(active_bin.parent),
            status=status,
            companions=companions,
            diagnostics=diagnostics,
            metadata=metadata,
        )

    def deep_inspect(self, runner: SafeRunner, base_report: Optional[ToolReport] = None) -> DeepTelemetryReport:
        if base_report is None:
            base_report = self.inspect(runner)
        from datetime import datetime
        raw_dumps = {}
        trace = ["Starting Ollama local AI deep inspection probe"]
        instances: List[DiscoveredInstance] = []
        env_vars: List[EnvVarStatus] = []
        detailed_diag: List[DiagnosticIssue] = list(base_report.diagnostics)
        remediations: List[str] = []

        seen_bins = set()

        # Primary resolved binary
        if base_report.binary_path:
            p_bin = Path(base_report.binary_path)
            seen_bins.add(str(p_bin).lower())
            instances.append(
                DiscoveredInstance(
                    path=str(p_bin.parent),
                    binary_path=str(p_bin),
                    version=base_report.version,
                    source="Active / Resolved",
                    is_active=True,
                    details=f"Active Ollama runtime (daemon online: {base_report.metadata.get('daemon_online')})",
                )
            )

        # Multi-instance discovery across PATH
        for o_bin in runner.resolve_all_binaries("ollama"):
            if str(o_bin).lower() not in seen_bins:
                seen_bins.add(str(o_bin).lower())
                is_act = bool(base_report.binary_path and str(o_bin).lower() == str(base_report.binary_path).lower())
                ver_str = None
                res_v = runner.run_command([str(o_bin), "--version"], timeout=2.0)
                if res_v.ok and res_v.stdout:
                    m = re.search(r"version is\s+([\d\.]+)", res_v.stdout)
                    ver_str = m.group(1) if m else None
                instances.append(
                    DiscoveredInstance(
                        path=str(o_bin.parent),
                        binary_path=str(o_bin),
                        version=ver_str,
                        source="PATH",
                        is_active=is_act,
                        details="System PATH Ollama CLI",
                    )
                )

        # Check LocalAppData on Windows
        if sys.platform == "win32":
            local_app = os.environ.get("LOCALAPPDATA")
            if local_app:
                cand_o = Path(local_app) / "Programs" / "Ollama" / "ollama.exe"
                if cand_o.is_file() and str(cand_o).lower() not in seen_bins:
                    seen_bins.add(str(cand_o).lower())
                    instances.append(
                        DiscoveredInstance(
                            path=str(cand_o.parent),
                            binary_path=str(cand_o),
                            version=base_report.version,
                            source="LocalAppData",
                            is_active=False,
                            details="Ollama user application directory",
                        )
                    )

        trace.append(f"Discovered {len(instances)} Ollama instances")

        # 2. Environment Variables Alignment
        models_dir = runner.read_env("OLLAMA_MODELS")
        default_models = str(Path.home() / ".ollama" / "models")
        env_vars.append(
            EnvVarStatus(
                name="OLLAMA_MODELS",
                value=models_dir,
                status="aligned" if models_dir else "missing",
                target_path=models_dir or default_models,
                message="Points to custom model weights storage" if models_dir else f"Default storage (~/.ollama/models: {'exists' if Path(default_models).is_dir() else 'not created'})",
            )
        )

        host_val = runner.read_env("OLLAMA_HOST")
        env_vars.append(
            EnvVarStatus(
                name="OLLAMA_HOST",
                value=host_val,
                status="aligned" if host_val else "missing",
                target_path="127.0.0.1:11434",
                message=f"Listening on custom address: {host_val}" if host_val else "Default address (127.0.0.1:11434)",
            )
        )

        keep_alive = runner.read_env("OLLAMA_KEEP_ALIVE")
        env_vars.append(
            EnvVarStatus(
                name="OLLAMA_KEEP_ALIVE",
                value=keep_alive,
                status="aligned" if keep_alive else "missing",
                target_path=None,
                message=f"Model cache duration: {keep_alive}" if keep_alive else "Default (5 minutes)",
            )
        )

        # 3. CLI Telemetry Dumps
        o_exec = base_report.binary_path or "ollama"
        res_ver = runner.run_command([o_exec, "--version"], timeout=2.0)
        if res_ver.ok and res_ver.stdout:
            raw_dumps["ollama --version"] = res_ver.stdout.strip()

        res_list = runner.run_command([o_exec, "list"], timeout=3.0)
        if res_list.ok and res_list.stdout:
            raw_dumps["ollama list (installed models)"] = res_list.stdout.strip()

        res_ps = runner.run_command([o_exec, "ps"], timeout=2.0)
        if res_ps.ok and res_ps.stdout:
            raw_dumps["ollama ps (running models)"] = res_ps.stdout.strip()

        if not base_report.metadata.get("daemon_online"):
            remediations.append("ollama serve")
        if base_report.metadata.get("models_count", 0) == 0:
            remediations.append("ollama run llama3.2")

        trace.append("Completed Ollama deep telemetry probes")

        return DeepTelemetryReport(
            tool_id=self.id,
            timestamp=datetime.now().isoformat(),
            probe_latency_ms=0,
            instances=instances,
            env_vars=env_vars,
            telemetry={
                "daemon_online": base_report.metadata.get("daemon_online", False),
                "models_count": base_report.metadata.get("models_count", 0),
                "models": base_report.metadata.get("models", []),
                "home_path": base_report.home_path,
            },
            raw_dumps=raw_dumps,
            detailed_diagnostics=detailed_diag,
            remediation_commands=remediations,
            discovery_trace=trace,
        )

