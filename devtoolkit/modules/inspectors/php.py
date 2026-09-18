"""PHP & Composer Inspector."""

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


class PHPInspector(BaseInspector):
    id = "php"
    name = "PHP & Composer"
    category = "runtime"
    categories = ["runtime", "web"]
    description = "PHP script interpreter and Composer package manager"

    def inspect(self, runner: SafeRunner) -> ToolReport:
        php_bin = runner.resolve_binary("php")
        if not php_bin:
            return ToolReport(
                id=self.id,
                name=self.name,
                category=self.category,
                categories=self.categories,
                installed=False,
                status=HealthStatus.NOT_FOUND,
            )

        # Version probe: `php -v`
        res = runner.run_command([str(php_bin), "-v"])
        version = None
        if res.ok and res.stdout.strip():
            # e.g. "PHP 8.3.14 (cli) (built: Dec  3 2024 16:30:22)"
            m = re.search(r"PHP\s+([\d\.]+)", res.stdout)
            version = m.group(1) if m else res.stdout.splitlines()[0].strip()

        companions: List[CompanionTool] = []

        # Companion: Composer
        composer_bin = runner.resolve_binary("composer") or runner.resolve_binary("composer.bat")
        comp_ver = None
        if composer_bin:
            comp_res = runner.run_command([str(composer_bin), "--version"])
            if comp_res.ok:
                m_comp = re.search(r"Composer\s+(?:version\s+)?([\d\.]+)", comp_res.stdout)
                comp_ver = m_comp.group(1) if m_comp else None
            companions.append(CompanionTool(name="composer", installed=True, version=comp_ver, binary_path=str(composer_bin)))
        else:
            companions.append(CompanionTool(name="composer", installed=False))

        diagnostics: List[DiagnosticIssue] = []
        if not composer_bin:
            diagnostics.append(
                DiagnosticIssue(
                    level=DiagnosticLevel.WARNING,
                    message="Composer dependency manager is not detected alongside PHP.",
                    suggested_fix="Install Composer from https://getcomposer.org or via winget: 'winget install Composer.Composer'.",
                )
            )

        status = HealthStatus.HEALTHY if composer_bin else HealthStatus.WARNING

        return ToolReport(
            id=self.id,
            name=self.name,
            category=self.category,
            categories=self.categories,
            installed=True,
            version=version,
            binary_path=str(php_bin),
            home_path=str(php_bin.parent),
            status=status,
            companions=companions,
            diagnostics=diagnostics,
            metadata={"composer_installed": composer_bin is not None},
        )

    def deep_inspect(self, runner: SafeRunner, base_report: Optional[ToolReport] = None) -> DeepTelemetryReport:
        if base_report is None:
            base_report = self.inspect(runner)
        from datetime import datetime
        raw_dumps = {}
        trace = ["Starting PHP & Composer deep inspection probe"]
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
                    details="Active PHP interpreter on system PATH",
                )
            )

        # Multi-instance discovery across PATH
        for bin_p in runner.resolve_all_binaries("php"):
            if str(bin_p).lower() not in seen_bins:
                seen_bins.add(str(bin_p).lower())
                is_act = bool(base_report.binary_path and str(bin_p).lower() == str(base_report.binary_path).lower())
                ver_str = None
                res_v = runner.run_command([str(bin_p), "-v"], timeout=2.0)
                if res_v.ok and res_v.stdout:
                    m = re.search(r"PHP\s+([\d\.]+)", res_v.stdout)
                    ver_str = m.group(1) if m else None
                instances.append(
                    DiscoveredInstance(
                        path=str(bin_p.parent),
                        binary_path=str(bin_p),
                        version=ver_str,
                        source="Alternate PATH",
                        is_active=is_act,
                        details="Alternate PHP executable in PATH",
                    )
                )

        # Check XAMPP and Laragon on Windows
        if sys.platform == "win32":
            xampp_php = Path("C:/xampp/php/php.exe")
            if xampp_php.is_file() and str(xampp_php).lower() not in seen_bins:
                seen_bins.add(str(xampp_php).lower())
                instances.append(
                    DiscoveredInstance(
                        path=str(xampp_php.parent),
                        binary_path=str(xampp_php),
                        version=None,
                        source="XAMPP Stack",
                        is_active=False,
                        details="Bundled PHP runtime inside XAMPP",
                    )
                )

        trace.append(f"Discovered {len(instances)} PHP instances")

        # 2. Environment Variables Alignment
        phprc = runner.read_env("PHPRC")
        env_vars.append(
            EnvVarStatus(
                name="PHPRC",
                value=phprc,
                status="aligned" if phprc else "missing",
                target_path=phprc,
                message="Points to custom php.ini configuration path" if phprc else "Unset (PHP searches directory of active executable)",
            )
        )

        comp_home = runner.read_env("COMPOSER_HOME")
        default_comp = str(Path.home() / "AppData" / "Roaming" / "Composer" if sys.platform == "win32" else Path.home() / ".composer")
        env_vars.append(
            EnvVarStatus(
                name="COMPOSER_HOME",
                value=comp_home,
                status="aligned" if comp_home else "missing",
                target_path=comp_home or default_comp,
                message="Custom Composer global directory" if comp_home else "Default composer global storage",
            )
        )

        # 3. CLI Telemetry Dumps
        p_exec = base_report.binary_path or "php"
        res_ver = runner.run_command([p_exec, "-v"], timeout=2.0)
        if res_ver.ok and res_ver.stdout:
            raw_dumps["php -v"] = res_ver.stdout.strip()

        res_ini = runner.run_command([p_exec, "--ini"], timeout=2.0)
        if res_ini.ok and res_ini.stdout:
            raw_dumps["php --ini (configuration files)"] = res_ini.stdout.strip()

        res_mod = runner.run_command([p_exec, "-m"], timeout=2.0)
        if res_mod.ok and res_mod.stdout:
            raw_dumps["php -m (loaded modules)"] = res_mod.stdout.strip()

        comp_bin = runner.resolve_binary("composer") or runner.resolve_binary("composer.bat")
        if comp_bin:
            res_comp = runner.run_command([str(comp_bin), "--version"], timeout=2.5)
            if res_comp.ok and res_comp.stdout:
                raw_dumps["composer --version"] = res_comp.stdout.strip()
        else:
            remediations.append("winget install Composer.Composer")

        trace.append("Completed PHP deep telemetry probes")

        return DeepTelemetryReport(
            tool_id=self.id,
            timestamp=datetime.now().isoformat(),
            probe_latency_ms=0,
            instances=instances,
            env_vars=env_vars,
            telemetry={
                "composer_installed": base_report.metadata.get("composer_installed", False),
                "home_path": base_report.home_path,
            },
            raw_dumps=raw_dumps,
            detailed_diagnostics=detailed_diag,
            remediation_commands=remediations,
            discovery_trace=trace,
        )

