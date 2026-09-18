"""C/C++ Compiler & Native Build Toolchain Inspector."""

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


class CCompilerInspector(BaseInspector):
    id = "c_compiler"
    name = "C/C++ Compiler"
    category = "build"
    categories = ["build", "compiler", "runtime"]
    description = "Native C/C++ toolchain (GCC, Clang, MinGW) for native extensions and compilation"

    def inspect(self, runner: SafeRunner) -> ToolReport:
        gcc_bin = runner.resolve_binary("gcc")
        clang_bin = runner.resolve_binary("clang")

        primary_bin = gcc_bin or clang_bin
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
