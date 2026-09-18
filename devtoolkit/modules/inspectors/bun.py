"""Bun JavaScript/TypeScript Runtime Inspector."""

import os
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


class BunInspector(BaseInspector):
    id = "bun"
    name = "Bun"
    category = "runtime"
    categories = ["runtime", "web"]
    description = "Bun all-in-one JavaScript runtime, bundler, and package manager"

    def inspect(self, runner: SafeRunner) -> ToolReport:
        bun_bin = runner.resolve_binary("bun")
        user_bun = None

        if not bun_bin:
            bun_install = os.environ.get("BUN_INSTALL")
            if bun_install:
                cand = Path(bun_install) / ("bin/bun.exe" if sys.platform == "win32" else "bin/bun")
                if cand.is_file():
                    user_bun = cand
            else:
                default_bun = Path.home() / ".bun" / ("bin/bun.exe" if sys.platform == "win32" else "bin/bun")
                if default_bun.is_file():
                    user_bun = default_bun

        active_bin = bun_bin or user_bun
        if not active_bin:
            return ToolReport(
                id=self.id,
                name=self.name,
                category=self.category,
                categories=self.categories,
                installed=False,
                status=HealthStatus.NOT_FOUND,
            )

        # Version probe: `bun --version`
        res = runner.run_command([str(active_bin), "--version"])
        version = res.stdout.strip() if res.ok and res.stdout.strip() else None

        # Companions: bunx
        companions: List[CompanionTool] = []
        bunx_bin = runner.resolve_binary("bunx")
        if not bunx_bin and active_bin.parent:
            cand_bunx = active_bin.parent / ("bunx.exe" if sys.platform == "win32" else "bunx")
            if cand_bunx.is_file():
                bunx_bin = cand_bunx

        if bunx_bin:
            companions.append(CompanionTool(name="bunx", installed=True, version=version, binary_path=str(bunx_bin)))
        else:
            companions.append(CompanionTool(name="bunx", installed=False))

        diagnostics: List[DiagnosticIssue] = []
        is_on_path = runner.resolve_binary("bun") is not None
        if not is_on_path and user_bun:
            diagnostics.append(
                DiagnosticIssue(
                    level=DiagnosticLevel.WARNING,
                    message="Bun is installed in your profile but its bin folder is not in PATH.",
                    suggested_fix=f'Add "{user_bun.parent}" to your PATH environment variable.',
                )
            )

        status = HealthStatus.HEALTHY if is_on_path else HealthStatus.WARNING

        return ToolReport(
            id=self.id,
            name=self.name,
            category=self.category,
            categories=self.categories,
            installed=True,
            version=version,
            binary_path=str(active_bin),
            home_path=str(active_bin.parent.parent if active_bin.parent.name == "bin" else active_bin.parent),
            status=status,
            companions=companions,
            diagnostics=diagnostics,
            metadata={"prefix": str(active_bin.parent)},
        )

    def deep_inspect(self, runner: SafeRunner, base_report: Optional[ToolReport] = None) -> DeepTelemetryReport:
        if base_report is None:
            base_report = self.inspect(runner)
        from datetime import datetime
        raw_dumps = {}
        trace = ["Starting Bun JavaScript runtime deep inspection probe"]
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
                    path=base_report.home_path or str(p_bin.parent),
                    binary_path=str(p_bin),
                    version=base_report.version,
                    source="Active / Resolved",
                    is_active=True,
                    details="Active Bun runtime binary",
                )
            )

        # Multi-instance discovery across PATH
        for b_bin in runner.resolve_all_binaries("bun"):
            if str(b_bin).lower() not in seen_bins:
                seen_bins.add(str(b_bin).lower())
                is_act = bool(base_report.binary_path and str(b_bin).lower() == str(base_report.binary_path).lower())
                ver_str = None
                res_v = runner.run_command([str(b_bin), "--version"], timeout=2.0)
                if res_v.ok and res_v.stdout.strip():
                    ver_str = res_v.stdout.strip()
                instances.append(
                    DiscoveredInstance(
                        path=str(b_bin.parent.parent if b_bin.parent.name == "bin" else b_bin.parent),
                        binary_path=str(b_bin),
                        version=ver_str,
                        source="PATH",
                        is_active=is_act,
                        details="Bun executable in system PATH",
                    )
                )

        # Check default user profile directory
        default_user_bun = Path.home() / ".bun" / "bin" / ("bun.exe" if sys.platform == "win32" else "bun")
        if default_user_bun.is_file() and str(default_user_bun).lower() not in seen_bins:
            seen_bins.add(str(default_user_bun).lower())
            instances.append(
                DiscoveredInstance(
                    path=str(default_user_bun.parent.parent),
                    binary_path=str(default_user_bun),
                    version=base_report.version,
                    source="User Profile (~/.bun)",
                    is_active=False,
                    details="Bun user home installation directory",
                )
            )

        trace.append(f"Discovered {len(instances)} Bun runtime instances")

        # 2. Environment Variables Alignment
        bun_install = runner.read_env("BUN_INSTALL")
        default_bun_dir = str(Path.home() / ".bun")
        env_vars.append(
            EnvVarStatus(
                name="BUN_INSTALL",
                value=bun_install,
                status="aligned" if bun_install else "missing",
                target_path=bun_install or default_bun_dir,
                message="Points to custom Bun installation folder" if bun_install else f"Default (~/.bun: {'exists' if Path(default_bun_dir).is_dir() else 'not found'})",
            )
        )

        # 3. CLI Telemetry Dumps
        b_exec = base_report.binary_path or "bun"
        res_ver = runner.run_command([b_exec, "--version"], timeout=2.0)
        if res_ver.ok and res_ver.stdout:
            raw_dumps["bun --version"] = res_ver.stdout.strip()

        res_pm = runner.run_command([b_exec, "pm", "ls", "-g"], timeout=3.0)
        if res_pm.ok and res_pm.stdout:
            raw_dumps["bun pm ls -g (global packages)"] = res_pm.stdout.strip()

        # Check bunx companion
        bunx_bin = runner.resolve_binary("bunx")
        if bunx_bin:
            res_bx = runner.run_command([str(bunx_bin), "--version"], timeout=2.0)
            if res_bx.ok and res_bx.stdout:
                raw_dumps["bunx --version"] = res_bx.stdout.strip()

        # Remediations
        if base_report.binary_path and runner.resolve_binary("bun") is None:
            p_dir = Path(base_report.binary_path).parent
            remediations.append(f'setx PATH "%PATH%;{p_dir}"')

        trace.append("Completed Bun runtime deep telemetry probes")

        return DeepTelemetryReport(
            tool_id=self.id,
            timestamp=datetime.now().isoformat(),
            probe_latency_ms=0,
            instances=instances,
            env_vars=env_vars,
            telemetry={
                "prefix": base_report.metadata.get("prefix"),
                "home_path": base_report.home_path,
            },
            raw_dumps=raw_dumps,
            detailed_diagnostics=detailed_diag,
            remediation_commands=remediations,
            discovery_trace=trace,
        )

