"""Bun JavaScript/TypeScript Runtime Inspector."""

import os
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


class BunInspector(BaseInspector):
    id = "bun"
    name = "Bun"
    category = "runtime"
    categories = ["runtime", "web"]
    description = "Bun all-in-one JavaScript runtime, bundler, and package manager"

    def inspect(self, runner: SafeRunner) -> ToolReport:
        bun_bin = runner.resolve_binary("bun")
        user_bun = None

        if not bun_bin:
            bun_install = os.environ.get("BUN_INSTALL")
            if bun_install:
                cand = Path(bun_install) / ("bin/bun.exe" if sys.platform == "win32" else "bin/bun")
                if cand.is_file():
                    user_bun = cand
            else:
                default_bun = Path.home() / ".bun" / ("bin/bun.exe" if sys.platform == "win32" else "bin/bun")
                if default_bun.is_file():
                    user_bun = default_bun

        active_bin = bun_bin or user_bun
        if not active_bin:
            return ToolReport(
                id=self.id,
                name=self.name,
                category=self.category,
                categories=self.categories,
                installed=False,
                status=HealthStatus.NOT_FOUND,
            )

        # Version probe: `bun --version`
        res = runner.run_command([str(active_bin), "--version"])
        version = res.stdout.strip() if res.ok and res.stdout.strip() else None

        # Companions: bunx
        companions: List[CompanionTool] = []
        bunx_bin = runner.resolve_binary("bunx")
        if not bunx_bin and active_bin.parent:
            cand_bunx = active_bin.parent / ("bunx.exe" if sys.platform == "win32" else "bunx")
            if cand_bunx.is_file():
                bunx_bin = cand_bunx

        if bunx_bin:
            companions.append(CompanionTool(name="bunx", installed=True, version=version, binary_path=str(bunx_bin)))
        else:
            companions.append(CompanionTool(name="bunx", installed=False))

        diagnostics: List[DiagnosticIssue] = []
        is_on_path = runner.resolve_binary("bun") is not None
        if not is_on_path and user_bun:
            diagnostics.append(
                DiagnosticIssue(
                    level=DiagnosticLevel.WARNING,
                    message="Bun is installed in your profile but its bin folder is not in PATH.",
                    suggested_fix=f'Add "{user_bun.parent}" to your PATH environment variable.',
                )
            )

        status = HealthStatus.HEALTHY if is_on_path else HealthStatus.WARNING

        return ToolReport(
            id=self.id,
            name=self.name,
            category=self.category,
            categories=self.categories,
            installed=True,
            version=version,
            binary_path=str(active_bin),
            home_path=str(active_bin.parent.parent if active_bin.parent.name == "bin" else active_bin.parent),
            status=status,
            companions=companions,
            diagnostics=diagnostics,
            metadata={"prefix": str(active_bin.parent)},
        )
