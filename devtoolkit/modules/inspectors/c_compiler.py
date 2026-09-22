"""C/C++ Compiler & Native Build Toolchain Inspector."""

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


class CCompilerInspector(BaseInspector):
    id = "c_compiler"
    name = "C/C++ Compiler"
    category = "build"
    categories = ["build", "compiler", "runtime"]
    description = "Native C/C++ toolchain (GCC, Clang, MinGW) for native extensions and compilation"

    def inspect(self, runner: SafeRunner) -> ToolReport:
        gcc_bin = runner.resolve_binary("gcc", tool_id=self.id)
        clang_bin = runner.resolve_binary("clang", tool_id=self.id)
        cl_bin = runner.resolve_binary("cl", tool_id=self.id)

        primary_bin = gcc_bin or clang_bin or cl_bin
        if not primary_bin:
            return ToolReport(
                id=self.id,
                name=self.name,
                category=self.category,
                categories=self.categories,
                installed=False,
                status=HealthStatus.NOT_FOUND,
                diagnostics=[
                    DiagnosticIssue(
                        level=DiagnosticLevel.INFO,
                        message="No C/C++ compiler (GCC or Clang) found in PATH. Building native Python C extensions or Node addons may fail.",
                        suggested_fix="Install MinGW-w64 (via 'winget install MSYS2.MSYS2' or 'choco install mingw') or Visual Studio C++ Build Tools.",
                    )
                ],
            )

        # Version probe: `<compiler> --version`
        res = runner.run_command([str(primary_bin), "--version"])
        version = None
        if res.ok and res.stdout.strip():
            # e.g. "gcc (Rev2, Built by MSYS2 project) 14.2.0" or "clang version 19.1.0"
            m = re.search(r"(?:gcc|clang version)\s+.*?([\d\.]+)", res.stdout, re.IGNORECASE)
            version = m.group(1) if m else res.stdout.splitlines()[0].strip()

        companions: List[CompanionTool] = []

        # Companion: g++
        gpp_bin = runner.resolve_binary("g++")
        companions.append(CompanionTool(name="g++", installed=gpp_bin is not None, binary_path=str(gpp_bin) if gpp_bin else None))

        # Companion: clang++
        clangpp_bin = runner.resolve_binary("clang++")
        companions.append(CompanionTool(name="clang++", installed=clangpp_bin is not None, binary_path=str(clangpp_bin) if clangpp_bin else None))

        # Companion: make / mingw32-make
        make_bin = runner.resolve_binary("make") or runner.resolve_binary("mingw32-make")
        companions.append(CompanionTool(name="make", installed=make_bin is not None, binary_path=str(make_bin) if make_bin else None))

        # Companion: gdb / lldb
        gdb_bin = runner.resolve_binary("gdb") or runner.resolve_binary("lldb")
        companions.append(CompanionTool(name="debugger", installed=gdb_bin is not None, binary_path=str(gdb_bin) if gdb_bin else None))

        diagnostics: List[DiagnosticIssue] = []
        if not gpp_bin and not clangpp_bin:
            diagnostics.append(
                DiagnosticIssue(
                    level=DiagnosticLevel.WARNING,
                    message="C compiler is present, but C++ compiler (g++ / clang++) is not found.",
                    suggested_fix="Ensure your C++ development packages (g++ / clang++) are installed and added to PATH.",
                )
            )

        status = HealthStatus.HEALTHY if (gpp_bin or clangpp_bin) else HealthStatus.WARNING

        return ToolReport(
            id=self.id,
            name=self.name,
            category=self.category,
            categories=self.categories,
            installed=True,
            version=version,
            binary_path=str(primary_bin),
            home_path=str(primary_bin.parent.parent if primary_bin.parent.name == "bin" else primary_bin.parent),
            status=status,
            companions=companions,
            diagnostics=diagnostics,
            metadata={"compiler_flavor": "gcc" if primary_bin == gcc_bin else "clang"},
        )

    def deep_inspect(self, runner: SafeRunner, base_report: Optional[ToolReport] = None) -> DeepTelemetryReport:
        if base_report is None:
            base_report = self.inspect(runner)
        from datetime import datetime
        raw_dumps = {}
        trace = ["Starting C/C++ compiler toolchain deep inspection probe"]
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
                    details=f"Active C compiler ({p_bin.name})",
                )
            )

        # Multi-instance discovery across PATH for compiler toolchains
        compiler_names = ["gcc", "clang", "cl", "g++", "clang++"]
        for c_name in compiler_names:
            for bin_p in runner.resolve_all_binaries(c_name):
                if str(bin_p).lower() not in seen_bins:
                    seen_bins.add(str(bin_p).lower())
                    is_act = bool(base_report.binary_path and str(bin_p).lower() == str(base_report.binary_path).lower())
                    ver_str = None
                    res_v = runner.run_command([str(bin_p), "--version"], timeout=2.0)
                    if res_v.ok and res_v.stdout:
                        m = re.search(r"(?:gcc|clang version|MSVC)\s+.*?([\d\.]+)", res_v.stdout, re.IGNORECASE)
                        ver_str = m.group(1) if m else None
                    instances.append(
                        DiscoveredInstance(
                            path=str(bin_p.parent),
                            binary_path=str(bin_p),
                            version=ver_str,
                            source="PATH",
                            is_active=is_act,
                            details=f"Discovered compiler toolchain binary ({c_name})",
                        )
                    )

        # Check MSYS2 default directory
        if sys.platform == "win32":
            msys_cand = Path("C:/msys64/ucrt64/bin/gcc.exe")
            if msys_cand.is_file() and str(msys_cand).lower() not in seen_bins:
                seen_bins.add(str(msys_cand).lower())
                instances.append(
                    DiscoveredInstance(
                        path=str(msys_cand.parent),
                        binary_path=str(msys_cand),
                        version=None,
                        source="MSYS2 UCRT64",
                        is_active=False,
                        details="MSYS2 modern C/C++ compiler toolchain",
                    )
                )

        # Discovery Pipeline instances (Layer 2-4 Discovery)
        for disc_p in runner.discovery.discover_all_tool_instances(self.id):
            cand_bin = None
            for b_name in ["gcc.exe", "clang.exe", "cl.exe", "gcc", "clang"]:
                for sub in [disc_p / "bin" / b_name, disc_p / b_name]:
                    if sub.is_file():
                        cand_bin = sub
                        break
                if cand_bin:
                    break
            k = str(cand_bin or disc_p).lower()
            if k not in seen_bins:
                seen_bins.add(k)
                instances.append(
                    DiscoveredInstance(
                        path=str(disc_p),
                        binary_path=str(cand_bin) if cand_bin else None,
                        version=None,
                        source="Discovery Pipeline",
                        is_active=bool(base_report.binary_path and cand_bin and str(cand_bin).lower() == str(base_report.binary_path).lower()),
                        details="Discovered C/C++ compiler toolchain (Layer 2-4)",
                    )
                )

        trace.append(f"Discovered {len(instances)} C/C++ compiler instances")

        # 2. Environment Variables Alignment
        cc_val = runner.read_env("CC")
        env_vars.append(
            EnvVarStatus(
                name="CC",
                value=cc_val,
                status="aligned" if cc_val else "missing",
                target_path=base_report.binary_path,
                message=f"Configured C compiler: {cc_val}" if cc_val else "Unset (tools discover compiler from PATH)",
            )
        )

        cxx_val = runner.read_env("CXX")
        env_vars.append(
            EnvVarStatus(
                name="CXX",
                value=cxx_val,
                status="aligned" if cxx_val else "missing",
                target_path=None,
                message=f"Configured C++ compiler: {cxx_val}" if cxx_val else "Unset (tools discover compiler from PATH)",
            )
        )

        # 3. CLI Telemetry Dumps
        primary_exec = base_report.binary_path or "gcc"
        res_ver = runner.run_command([primary_exec, "--version"], timeout=2.0)
        if res_ver.ok and res_ver.stdout:
            raw_dumps[f"{Path(primary_exec).name} --version"] = res_ver.stdout.strip()

        res_mach = runner.run_command([primary_exec, "-dumpmachine"], timeout=2.0)
        if res_mach.ok and res_mach.stdout:
            raw_dumps["Target Machine (-dumpmachine)"] = res_mach.stdout.strip()

        res_v = runner.run_command([primary_exec, "-v"], timeout=2.0)
        out_v = f"{res_v.stdout}\n{res_v.stderr}".strip()
        if out_v:
            raw_dumps["Compiler Specs (-v)"] = out_v

        trace.append("Completed C/C++ compiler toolchain deep telemetry probes")

        return DeepTelemetryReport(
            tool_id=self.id,
            timestamp=datetime.now().isoformat(),
            probe_latency_ms=0,
            instances=instances,
            env_vars=env_vars,
            telemetry={
                "compiler_flavor": base_report.metadata.get("compiler_flavor"),
                "home_path": base_report.home_path,
            },
            raw_dumps=raw_dumps,
            detailed_diagnostics=detailed_diag,
            remediation_commands=remediations,
            discovery_trace=trace,
        )

