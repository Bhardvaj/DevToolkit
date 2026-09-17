""".NET SDK & Runtime Inspector."""

import os
import re
import sys
from pathlib import Path
from typing import List

from devtoolkit.core.base import BaseInspector
from devtoolkit.core.models import (
    CompanionTool,
    DiagnosticIssue,
    DiagnosticLevel,
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
        dotnet_bin = runner.resolve_binary("dotnet")
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
                    suggested_fix="Install the latest .NET SDK from https://dotnet.microsoft.com/download",
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
                        suggested_fix="Correct or remove the DOTNET_ROOT environment variable.",
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
