"""CMake & Native Build System Inspector."""

import re
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
