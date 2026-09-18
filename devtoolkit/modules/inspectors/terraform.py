"""Terraform Infrastructure as Code Inspector."""

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


class TerraformInspector(BaseInspector):
    id = "terraform"
    name = "Terraform"
    category = "cloud"
    categories = ["cloud", "devops", "iac"]
    description = "HashiCorp Terraform infrastructure as code CLI and OpenTofu compatibility"

    def inspect(self, runner: SafeRunner) -> ToolReport:
        tf_bin = runner.resolve_binary("terraform")
        tofu_bin = runner.resolve_binary("tofu")

        active_bin = tf_bin or tofu_bin
        if not active_bin:
            return ToolReport(
                id=self.id,
                name=self.name,
                category=self.category,
                categories=self.categories,
                installed=False,
                status=HealthStatus.NOT_FOUND,
            )

        # Version probe: `terraform version`
        res = runner.run_command([str(active_bin), "version"])
        version = None
        if res.ok and res.stdout.strip():
            # e.g. "Terraform v1.10.4" or "OpenTofu v1.9.0"
            m = re.search(r"(?:Terraform|OpenTofu)\s+v?([\d\.]+)", res.stdout)
            version = m.group(1) if m else res.stdout.splitlines()[0].strip()

        companions: List[CompanionTool] = []

        # Companion: OpenTofu
        if tofu_bin:
            tofu_res = runner.run_command([str(tofu_bin), "version"])
            tofu_ver = re.search(r"v?([\d\.]+)", tofu_res.stdout).group(1) if (tofu_res.ok and re.search(r"v?([\d\.]+)", tofu_res.stdout)) else None
            companions.append(CompanionTool(name="opentofu", installed=True, version=tofu_ver, binary_path=str(tofu_bin)))
        else:
            companions.append(CompanionTool(name="opentofu", installed=False))

        return ToolReport(
            id=self.id,
            name=self.name,
            category=self.category,
            categories=self.categories,
            installed=True,
            version=version,
            binary_path=str(active_bin),
            home_path=str(active_bin.parent),
            status=HealthStatus.HEALTHY,
            companions=companions,
            diagnostics=[],
            metadata={"is_opentofu": active_bin == tofu_bin},
        )

    def deep_inspect(self, runner: SafeRunner, base_report: Optional[ToolReport] = None) -> DeepTelemetryReport:
        if base_report is None:
            base_report = self.inspect(runner)
        from datetime import datetime
        raw_dumps = {}
        trace = ["Starting Terraform deep inspection probe"]
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
                    details="Active binary invoked via command line",
                )
            )

        # Multi-instance discovery across PATH (both terraform and tofu)
        for bin_name in ["terraform", "tofu"]:
            for t_bin in runner.resolve_all_binaries(bin_name):
                if str(t_bin).lower() not in seen_bins:
                    seen_bins.add(str(t_bin).lower())
                    is_act = bool(base_report.binary_path and str(t_bin).lower() == str(base_report.binary_path).lower())
                    ver_str = None
                    res_v = runner.run_command([str(t_bin), "version"], timeout=2.0)
                    if res_v.ok and res_v.stdout:
                        m = re.search(r"(?:Terraform|OpenTofu)\s+v?([\d\.]+)", res_v.stdout)
                        ver_str = m.group(1) if m else None
                    instances.append(
                        DiscoveredInstance(
                            path=str(t_bin.parent),
                            binary_path=str(t_bin),
                            version=ver_str,
                            source=f"PATH ({bin_name})",
                            is_active=is_act,
                            details=f"Discovered {bin_name} executable in PATH",
                        )
                    )

        trace.append(f"Discovered {len(instances)} Terraform / OpenTofu instances")

        # 2. Environment Variables Alignment
        cache_dir = runner.read_env("TF_PLUGIN_CACHE_DIR")
        env_vars.append(
            EnvVarStatus(
                name="TF_PLUGIN_CACHE_DIR",
                value=cache_dir,
                status="aligned" if cache_dir else "missing",
                target_path=cache_dir,
                message="Points to shared plugin cache directory" if cache_dir else "Unset (providers re-download per workspace unless cached)",
            )
        )
        if not cache_dir:
            remediations.append('setx TF_PLUGIN_CACHE_DIR "%USERPROFILE%\\.terraform.d\\plugin-cache"')

        tf_cfg = runner.read_env("TF_CLI_CONFIG_FILE")
        env_vars.append(
            EnvVarStatus(
                name="TF_CLI_CONFIG_FILE",
                value=tf_cfg,
                status="aligned" if tf_cfg else "missing",
                target_path=tf_cfg,
                message="Custom CLI configuration file path" if tf_cfg else "Default config (~/.terraformrc or %APPDATA%/terraform.rc)",
            )
        )

        tf_log = runner.read_env("TF_LOG")
        env_vars.append(
            EnvVarStatus(
                name="TF_LOG",
                value=tf_log,
                status="aligned" if tf_log else "missing",
                target_path=None,
                message=f"Logging level: {tf_log}" if tf_log else "Unset (logging disabled by default)",
            )
        )

        # 3. CLI Telemetry Dumps
        t_exec = base_report.binary_path or "terraform"
        res_ver = runner.run_command([t_exec, "version", "-json"], timeout=2.5)
        if not res_ver.ok or not res_ver.stdout:
            res_ver = runner.run_command([t_exec, "version"], timeout=2.5)
        if res_ver.ok and res_ver.stdout:
            raw_dumps[f"{Path(t_exec).stem} version"] = res_ver.stdout.strip()

        trace.append("Completed Terraform deep telemetry probes")

        return DeepTelemetryReport(
            tool_id=self.id,
            timestamp=datetime.now().isoformat(),
            probe_latency_ms=0,
            instances=instances,
            env_vars=env_vars,
            telemetry={
                "is_opentofu": base_report.metadata.get("is_opentofu", False),
                "home_path": base_report.home_path,
            },
            raw_dumps=raw_dumps,
            detailed_diagnostics=detailed_diag,
            remediation_commands=remediations,
            discovery_trace=trace,
        )

