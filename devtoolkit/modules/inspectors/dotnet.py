""".NET SDK & Runtime Inspector."""

import os
import re
import sys
from pathlib import Path
from typing import List

from datetime import datetime, timezone
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


class DotNetInspector(BaseInspector):
    id = "dotnet"
    name = ".NET SDK"
    category = "runtime"
    categories = ["runtime", "framework"]
    description = ".NET SDK, CLR runtime, MSBuild and package tools"

    def inspect(self, runner: SafeRunner) -> ToolReport:
        dotnet_bin = runner.resolve_binary("dotnet", tool_id=self.id)
        if not dotnet_bin and sys.platform == "win32":
            default_path = Path(os.environ.get("ProgramFiles", "C:\\Program Files")) / "dotnet" / "dotnet.exe"
            if default_path.is_file():
                dotnet_bin = default_path

        if not dotnet_bin:
            return ToolReport(
                id=self.id,
                name=self.name,
                category=self.category,
                categories=self.categories,
                installed=False,
                status=HealthStatus.NOT_FOUND,
            )

        # Version probe: `dotnet --version`
        res = runner.run_command([str(dotnet_bin), "--version"])
        version = res.stdout.strip() if res.ok and res.stdout.strip() else None

        # Check installed SDKs
        sdks_res = runner.run_command([str(dotnet_bin), "--list-sdks"])
        sdk_lines = [line.strip() for line in sdks_res.stdout.splitlines() if line.strip()] if sdks_res.ok else []

        # Check installed runtimes
        runtimes_res = runner.run_command([str(dotnet_bin), "--list-runtimes"])
        runtime_lines = [line.strip() for line in runtimes_res.stdout.splitlines() if line.strip()] if runtimes_res.ok else []

        # Companions
        companions: List[CompanionTool] = []

        # MSBuild
        msbuild_bin = runner.resolve_binary("msbuild")
        if msbuild_bin:
            res_ms = runner.run_command([str(msbuild_bin), "-version"])
            m_ver = res_ms.stdout.strip().splitlines()[-1] if res_ms.ok and res_ms.stdout.strip() else None
            companions.append(CompanionTool(name="msbuild", installed=True, version=m_ver, binary_path=str(msbuild_bin)))
        else:
            companions.append(CompanionTool(name="msbuild", installed=False))

        # NuGet
        nuget_bin = runner.resolve_binary("nuget")
        if nuget_bin:
            res_nu = runner.run_command([str(nuget_bin)])
            # NuGet Version: 6.x...
            m = re.search(r"NuGet Version:\s*([\d\.]+)", res_nu.stdout) if res_nu.ok else None
            n_ver = m.group(1) if m else None
            companions.append(CompanionTool(name="nuget", installed=True, version=n_ver, binary_path=str(nuget_bin)))
        else:
            companions.append(CompanionTool(name="nuget", installed=False))

        diagnostics: List[DiagnosticIssue] = []

        # Diagnostic: No SDKs found
        if not sdk_lines:
            diagnostics.append(
                DiagnosticIssue(
                    level=DiagnosticLevel.WARNING,
                    message="No .NET SDKs installed (only the .NET runtime is available). Building projects requires an SDK.",
                    suggested_fix="winget install Microsoft.DotNet.SDK.8",
                )
            )

        # Diagnostic: Check DOTNET_ROOT
        dotnet_root = os.environ.get("DOTNET_ROOT")
        if dotnet_root:
            root_p = Path(dotnet_root)
            if not root_p.exists() or not root_p.is_dir():
                diagnostics.append(
                    DiagnosticIssue(
                        level=DiagnosticLevel.ERROR,
                        message=f"DOTNET_ROOT points to non-existent path: {dotnet_root}",
                        suggested_fix=f'setx DOTNET_ROOT "{dotnet_bin.parent}" /M',
                    )
                )

        status = HealthStatus.HEALTHY
        if any(d.level == DiagnosticLevel.ERROR for d in diagnostics):
            status = HealthStatus.ERROR
        elif any(d.level == DiagnosticLevel.WARNING for d in diagnostics):
            status = HealthStatus.WARNING

        home_dir = str(dotnet_bin.parent)

        return ToolReport(
            id=self.id,
            name=self.name,
            category=self.category,
            categories=self.categories,
            installed=True,
            version=version,
            binary_path=str(dotnet_bin),
            home_path=home_dir,
            status=status,
            companions=companions,
            diagnostics=diagnostics,
            metadata={
                "sdks_count": len(sdk_lines),
                "runtimes_count": len(runtime_lines),
                "sdk_list": sdk_lines[:5],
            },
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
        path_bins = runner.resolve_all_binaries("dotnet")
        trace.append(f"Found {len(path_bins)} 'dotnet' binary candidates in system PATH")
        for idx, pb in enumerate(path_bins):
            is_act = (idx == 0) and bool(base_rep.binary_path) and (str(pb).lower() == str(base_rep.binary_path).lower())
            ver = base_rep.version if is_act else None
            _add_inst(pb.parent, pb, ver, "PATH", is_act, "Active binary in system PATH" if is_act else "Alternate binary in PATH")

        # 2. Known 64-bit and 32-bit Program Files locations
        for cand in [
            Path(r"C:\Program Files\dotnet\dotnet.exe"),
            Path(r"C:\Program Files (x86)\dotnet\dotnet.exe"),
        ]:
            if cand.exists():
                is_act = bool(base_rep.binary_path) and (str(cand).lower() == str(base_rep.binary_path).lower())
                arch = "64-bit Architecture" if "x86" not in str(cand).lower() else "32-bit (x86) Architecture"
                _add_inst(cand.parent, cand, None, "Registry", is_act, f"Standard .NET root ({arch})")

        # 3. Registry uninstall inventory
        reg_apps = OSInventory.find_app_locations(".NET")
        for reg_p in reg_apps:
            reg_bin = reg_p / "dotnet.exe"
            b_target = reg_bin if reg_bin.exists() else None
            is_act = bool(base_rep.binary_path and b_target and str(b_target).lower() == str(base_rep.binary_path).lower())
            _add_inst(reg_p, b_target, None, "Registry", is_act, "Windows Registry App Entry")

        # 4. Discovery Pipeline (4-Layer & FastSearchEngine)
        for disc_root in runner.discovery.discover_all_tool_instances(self.id):
            cand_bin = disc_root / ("dotnet.exe" if sys.platform == "win32" else "dotnet")
            b_target = cand_bin if cand_bin.is_file() else None
            is_act = bool(base_rep.binary_path and b_target and str(b_target).lower() == str(base_rep.binary_path).lower())
            _add_inst(disc_root, b_target, None, "Discovery Pipeline", is_act, "Discovered via 4-Layer / FastSearchEngine signatures")

        # 4. Monitored Environment Variables Alignment
        env_vars: list[EnvVarStatus] = []
        active_home = base_rep.home_path

        # DOTNET_ROOT
        dotnet_root = runner.read_env("DOTNET_ROOT")
        if dotnet_root:
            dr_exists = Path(dotnet_root).exists()
            is_aligned = active_home and (str(Path(dotnet_root).resolve()).lower() == str(Path(active_home).resolve()).lower())
            env_vars.append(
                EnvVarStatus(
                    name="DOTNET_ROOT",
                    value=dotnet_root,
                    status="aligned" if is_aligned else ("divergent" if dr_exists else "missing"),
                    target_path=active_home or dotnet_root,
                    message="Aligned with active .NET host" if is_aligned else "Diverges from active .NET installation directory!",
                )
            )
        else:
            env_vars.append(
                EnvVarStatus(
                    name="DOTNET_ROOT",
                    value=None,
                    status="aligned",
                    message="Not set (using standard C:\\Program Files\\dotnet default location)",
                )
            )

        # DOTNET_MULTILEVEL_LOOKUP
        ml_lookup = runner.read_env("DOTNET_MULTILEVEL_LOOKUP")
        if ml_lookup:
            env_vars.append(
                EnvVarStatus(
                    name="DOTNET_MULTILEVEL_LOOKUP",
                    value=ml_lookup,
                    status="aligned",
                    message=f"Multi-level lookup explicitly configured to '{ml_lookup}'",
                )
            )

        # 5. Deep Domain Telemetry & Raw Dumps
        telemetry: dict[str, Any] = {
            "sdks_installed_count": base_rep.metadata.get("sdks_count", 0),
            "runtimes_installed_count": base_rep.metadata.get("runtimes_count", 0),
        }

        raw_dumps: dict[str, str] = {}
        if base_rep.binary_path:
            # dotnet --info (comprehensive dump)
            info_res = runner.run_command([base_rep.binary_path, "--info"], timeout=3.5)
            if info_res.ok and info_res.stdout:
                raw_dumps["dotnet --info"] = info_res.stdout

            # dotnet --list-sdks
            sdks_res = runner.run_command([base_rep.binary_path, "--list-sdks"], timeout=2.5)
            if sdks_res.ok and sdks_res.stdout:
                raw_dumps["dotnet --list-sdks"] = sdks_res.stdout
                telemetry["sdks"] = [l.strip() for l in sdks_res.stdout.splitlines() if l.strip()]

            # dotnet --list-runtimes
            runtimes_res = runner.run_command([base_rep.binary_path, "--list-runtimes"], timeout=2.5)
            if runtimes_res.ok and runtimes_res.stdout:
                raw_dumps["dotnet --list-runtimes"] = runtimes_res.stdout
                telemetry["runtimes"] = [l.strip() for l in runtimes_res.stdout.splitlines() if l.strip()]

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
