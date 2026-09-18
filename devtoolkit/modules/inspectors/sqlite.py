"""SQLite Database Inspector."""

import re
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


class SQLiteInspector(BaseInspector):
    id = "sqlite"
    name = "SQLite"
    category = "database"
    categories = ["database", "tools"]
    description = "Self-contained serverless SQL database engine command-line utility"

    def inspect(self, runner: SafeRunner) -> ToolReport:
        sqlite_bin = runner.resolve_binary("sqlite3")
        if not sqlite_bin:
            return ToolReport(
                id=self.id,
                name=self.name,
                category=self.category,
                categories=self.categories,
                installed=False,
                status=HealthStatus.NOT_FOUND,
            )

        # Version probe: `sqlite3 --version`
        res = runner.run_command([str(sqlite_bin), "--version"])
        version = None
        if res.ok and res.stdout.strip():
            # e.g. "3.45.1 2024-01-30 16:01:20 ..."
            parts = res.stdout.strip().split()
            if parts:
                version = parts[0].strip()

        return ToolReport(
            id=self.id,
            name=self.name,
            category=self.category,
            categories=self.categories,
            installed=True,
            version=version,
            binary_path=str(sqlite_bin),
            home_path=str(sqlite_bin.parent),
            status=HealthStatus.HEALTHY,
            companions=[],
            diagnostics=[],
            metadata={},
        )

    def deep_inspect(self, runner: SafeRunner, base_report: Optional[ToolReport] = None) -> DeepTelemetryReport:
        if base_report is None:
            base_report = self.inspect(runner)
        from datetime import datetime
        raw_dumps = {}
        trace = ["Starting SQLite database CLI deep inspection probe"]
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
                    source="Active PATH",
                    is_active=True,
                    details="Active SQLite CLI shell on system PATH",
                )
            )

        # Multi-instance discovery across PATH
        for s_bin in runner.resolve_all_binaries("sqlite3"):
            if str(s_bin).lower() not in seen_bins:
                seen_bins.add(str(s_bin).lower())
                is_act = bool(base_report.binary_path and str(s_bin).lower() == str(base_report.binary_path).lower())
                ver_str = None
                res_v = runner.run_command([str(s_bin), "--version"], timeout=2.0)
                if res_v.ok and res_v.stdout.strip():
                    parts = res_v.stdout.strip().split()
                    ver_str = parts[0].strip() if parts else None
                instances.append(
                    DiscoveredInstance(
                        path=str(s_bin.parent),
                        binary_path=str(s_bin),
                        version=ver_str,
                        source="Alternate PATH",
                        is_active=is_act,
                        details="Alternate sqlite3 binary on system PATH",
                    )
                )

        trace.append(f"Discovered {len(instances)} sqlite3 instances")

        # 2. Environment Variables Alignment
        tmpdir_val = runner.read_env("SQLITE_TMPDIR")
        env_vars.append(
            EnvVarStatus(
                name="SQLITE_TMPDIR",
                value=tmpdir_val,
                status="aligned" if tmpdir_val else "missing",
                target_path=tmpdir_val,
                message="Points to custom SQLite temporary table storage" if tmpdir_val else "Unset (SQLite uses system temporary directory)",
            )
        )

        # 3. CLI Telemetry Dumps
        s_exec = base_report.binary_path or "sqlite3"
        res_ver = runner.run_command([s_exec, "--version"], timeout=2.0)
        if res_ver.ok and res_ver.stdout:
            raw_dumps["sqlite3 --version"] = res_ver.stdout.strip()

        # Compile options probe
        res_opts = runner.run_command([s_exec, ":memory:", "PRAGMA compile_options;"], timeout=2.5)
        if res_opts.ok and res_opts.stdout.strip():
            raw_dumps["PRAGMA compile_options"] = res_opts.stdout.strip()

        trace.append("Completed SQLite deep telemetry probes")

        return DeepTelemetryReport(
            tool_id=self.id,
            timestamp=datetime.now().isoformat(),
            probe_latency_ms=0,
            instances=instances,
            env_vars=env_vars,
            telemetry={
                "home_path": base_report.home_path,
            },
            raw_dumps=raw_dumps,
            detailed_diagnostics=detailed_diag,
            remediation_commands=remediations,
            discovery_trace=trace,
        )

