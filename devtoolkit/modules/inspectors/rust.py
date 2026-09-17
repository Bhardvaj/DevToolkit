"""Rust & Cargo Systems Programming Inspector."""

import re
from pathlib import Path
from devtoolkit.core.base import BaseInspector
from devtoolkit.core.models import (
    CompanionTool,
    DiagnosticIssue,
    DiagnosticLevel,
    HealthStatus,
    ToolReport,
)
from devtoolkit.core.runner import SafeRunner


class RustInspector(BaseInspector):
    id = "rust"
    name = "Rust / Cargo"
    category = "runtime"
    categories = ["runtime", "compiler"]
    description = "Rust compiler (rustc), Cargo package manager, and rustup toolchains"

    def inspect(self, runner: SafeRunner) -> ToolReport:
        rustc_bin = runner.resolve_binary("rustc")
        if not rustc_bin:
            return ToolReport(
                id=self.id,
                name=self.name,
                category=self.category,
                categories=self.categories,
                installed=False,
                status=HealthStatus.NOT_FOUND,
            )

        # Output format: "rustc 1.79.0 (129f3b996 2024-06-10)"
        res = runner.run_command([str(rustc_bin), "--version"])
        version = None
        if res.ok and res.stdout:
            m = re.search(r"rustc\s+([0-9.]+)", res.stdout)
            version = m.group(1) if m else res.stdout

        companions = []
        diagnostics = []

        # Check Cargo and rustup
        for tool_name in ["cargo", "rustup"]:
            t_bin = runner.resolve_binary(tool_name)
            if t_bin:
                t_res = runner.run_command([str(t_bin), "--version"])
                t_ver = None
                if t_res.ok and t_res.stdout:
                    m = re.search(r"[0-9.]+", t_res.stdout)
                    t_ver = m.group(0) if m else None
                companions.append(
                    CompanionTool(
                        name=tool_name,
                        installed=True,
                        version=t_ver,
                        binary_path=str(t_bin),
                    )
                )
            else:
                companions.append(CompanionTool(name=tool_name, installed=False))

        cargo_found = any(c.installed for c in companions if c.name == "cargo")
        if not cargo_found:
            diagnostics.append(
                DiagnosticIssue(
                    level=DiagnosticLevel.WARNING,
                    message="Cargo package manager is not found alongside rustc.",
                    suggested_fix="Install Cargo via rustup or distribution package manager.",
                )
            )

        status = HealthStatus.HEALTHY if cargo_found else HealthStatus.WARNING

        return ToolReport(
            id=self.id,
            name=self.name,
            category=self.category,
            categories=self.categories,
            installed=True,
            version=version,
            binary_path=str(rustc_bin),
            home_path=str(rustc_bin.parent),
            status=status,
            companions=companions,
            diagnostics=diagnostics,
        )
