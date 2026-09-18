"""CMake & Native Build System Inspector."""

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


class CMakeInspector(BaseInspector):
    id = "cmake"
    name = "CMake"
    category = "build"
    categories = ["build", "tools"]
    description = "Cross-platform build system generator, test runner, and native toolchains"

    def inspect(self, runner: SafeRunner) -> ToolReport:
        cmake_bin = runner.resolve_binary("cmake")
        if not cmake_bin:
            return ToolReport(
                id=self.id,
                name=self.name,
                category=self.category,
                categories=self.categories,
                installed=False,
                status=HealthStatus.NOT_FOUND,
            )

        # Probe version: `cmake --version`
        res = runner.run_command([str(cmake_bin), "--version"])
        version = None
        if res.ok and res.stdout.strip():
            # e.g. "cmake version 3.31.2"
            m = re.search(r"cmake version\s+([\d\.]+)", res.stdout)
            version = m.group(1) if m else res.stdout.splitlines()[0].strip()

        companions: List[CompanionTool] = []

        # Companion: Ninja
        ninja_bin = runner.resolve_binary("ninja")
        if ninja_bin:
            n_res = runner.run_command([str(ninja_bin), "--version"])
            n_ver = n_res.stdout.strip() if n_res.ok else None
            companions.append(CompanionTool(name="ninja", installed=True, version=n_ver, binary_path=str(ninja_bin)))
        else:
            companions.append(CompanionTool(name="ninja", installed=False))

        # Companion: CTest
        ctest_bin = runner.resolve_binary("ctest")
        companions.append(
            CompanionTool(
                name="ctest",
                installed=ctest_bin is not None,
                binary_path=str(ctest_bin) if ctest_bin else None,
            )
        )

        # Companion: CPack
        cpack_bin = runner.resolve_binary("cpack")
        companions.append(
            CompanionTool(
                name="cpack",
                installed=cpack_bin is not None,
                binary_path=str(cpack_bin) if cpack_bin else None,
            )
        )

        diagnostics: List[DiagnosticIssue] = []
        if not ninja_bin:
            diagnostics.append(
                DiagnosticIssue(
                    level=DiagnosticLevel.INFO,
                    message="Ninja build generator is not installed. Ninja significantly accelerates C/C++ builds.",
                    suggested_fix="Install Ninja via winget: 'winget install Ninja-build.Ninja'",
                )
            )

        return ToolReport(
            id=self.id,
            name=self.name,
            category=self.category,
            categories=self.categories,
            installed=True,
            version=version,
            binary_path=str(cmake_bin),
            home_path=str(cmake_bin.parent.parent if cmake_bin.parent.name == "bin" else cmake_bin.parent),
            status=HealthStatus.HEALTHY,
            companions=companions,
            diagnostics=diagnostics,
            metadata={"ninja_installed": ninja_bin is not None},
        )

    def deep_inspect(self, runner: SafeRunner, base_report: Optional[ToolReport] = None) -> DeepTelemetryReport:
        if base_report is None:
            base_report = self.inspect(runner)
        from datetime import datetime
        raw_dumps = {}
        trace = ["Starting CMake deep inspection probe"]
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
                    path=str(p_bin.parent.parent if p_bin.parent.name == "bin" else p_bin.parent),
                    binary_path=str(p_bin),
                    version=base_report.version,
                    source="Active PATH",
                    is_active=True,
                    details="Active CMake generator on system PATH",
                )
            )

        # Multi-instance discovery across PATH
        for c_bin in runner.resolve_all_binaries("cmake"):
            if str(c_bin).lower() not in seen_bins:
                seen_bins.add(str(c_bin).lower())
                is_act = bool(base_report.binary_path and str(c_bin).lower() == str(base_report.binary_path).lower())
                ver_str = None
                res_v = runner.run_command([str(c_bin), "--version"], timeout=2.0)
                if res_v.ok and res_v.stdout:
                    m = re.search(r"cmake version\s+([\d\.]+)", res_v.stdout)
                    ver_str = m.group(1) if m else None
                instances.append(
                    DiscoveredInstance(
                        path=str(c_bin.parent.parent if c_bin.parent.name == "bin" else c_bin.parent),
                        binary_path=str(c_bin),
                        version=ver_str,
                        source="Alternate PATH",
                        is_active=is_act,
                        details="Alternate CMake executable in PATH",
                    )
                )

        # Check Visual Studio bundled CMake
        if sys.platform == "win32":
            vs_roots = [
                Path("C:/Program Files/Microsoft Visual Studio"),
                Path("C:/Program Files (x86)/Microsoft Visual Studio"),
            ]
            for vs_root in vs_roots:
                if vs_root.is_dir():
                    for cm in vs_root.glob("*/Community/Common7/IDE/CommonExtensions/Microsoft/CMake/CMake/bin/cmake.exe"):
                        if cm.is_file() and str(cm).lower() not in seen_bins:
                            seen_bins.add(str(cm).lower())
                            instances.append(
                                DiscoveredInstance(
                                    path=str(cm.parent.parent),
                                    binary_path=str(cm),
                                    version=None,
                                    source="Visual Studio Bundled",
                                    is_active=False,
                                    details="Bundled CMake inside Visual Studio IDE",
                                )
                            )

        trace.append(f"Discovered {len(instances)} CMake installations")

        # 2. Environment Variables Alignment
        gen_val = runner.read_env("CMAKE_GENERATOR")
        env_vars.append(
            EnvVarStatus(
                name="CMAKE_GENERATOR",
                value=gen_val,
                status="aligned" if gen_val else "missing",
                target_path="Ninja",
                message=f"Default generator configured: {gen_val}" if gen_val else "Unset (CMake uses system compiler default generator)",
            )
        )

        jobs_val = runner.read_env("CMAKE_BUILD_PARALLEL_LEVEL")
        env_vars.append(
            EnvVarStatus(
                name="CMAKE_BUILD_PARALLEL_LEVEL",
                value=jobs_val,
                status="aligned" if jobs_val else "missing",
                target_path=None,
                message=f"Parallel jobs limit: {jobs_val}" if jobs_val else "Unset (uses all logical CPU cores)",
            )
        )

        # 3. CLI Telemetry Dumps
        cm_exec = base_report.binary_path or "cmake"
        res_ver = runner.run_command([cm_exec, "--version"], timeout=2.0)
        if res_ver.ok and res_ver.stdout:
            raw_dumps["cmake --version"] = res_ver.stdout.strip()

        # Extract available generators from cmake --help
        res_help = runner.run_command([cm_exec, "--help"], timeout=2.5)
        if res_help.ok and res_help.stdout:
            lines = res_help.stdout.splitlines()
            gen_start = False
            gen_lines = []
            for line in lines:
                if "Generators" in line:
                    gen_start = True
                if gen_start:
                    gen_lines.append(line)
            if gen_lines:
                raw_dumps["Available CMake Generators"] = "\n".join(gen_lines[:35])

        # Companion tools
        ninja_b = runner.resolve_binary("ninja")
        if ninja_b:
            res_n = runner.run_command([str(ninja_b), "--version"], timeout=2.0)
            if res_n.ok and res_n.stdout:
                raw_dumps["ninja --version"] = res_n.stdout.strip()
        else:
            remediations.append("winget install Ninja-build.Ninja")

        ctest_b = runner.resolve_binary("ctest")
        if ctest_b:
            res_ct = runner.run_command([str(ctest_b), "--version"], timeout=2.0)
            if res_ct.ok and res_ct.stdout:
                raw_dumps["ctest --version"] = res_ct.stdout.strip()

        trace.append("Completed CMake deep telemetry probes")

        return DeepTelemetryReport(
            tool_id=self.id,
            timestamp=datetime.now().isoformat(),
            probe_latency_ms=0,
            instances=instances,
            env_vars=env_vars,
            telemetry={
                "ninja_installed": base_report.metadata.get("ninja_installed", False),
                "home_path": base_report.home_path,
            },
            raw_dumps=raw_dumps,
            detailed_diagnostics=detailed_diag,
            remediation_commands=remediations,
            discovery_trace=trace,
        )

