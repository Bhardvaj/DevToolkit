"""Node.js & JavaScript Runtime Inspector."""

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


class NodeInspector(BaseInspector):
    id = "node"
    name = "Node.js"
    category = "runtime"
    categories = ["runtime", "web"]
    description = "Node.js runtime, npm, and modern JavaScript package managers"

    def inspect(self, runner: SafeRunner) -> ToolReport:
        node_bin = runner.resolve_binary("node")
        if not node_bin:
            return ToolReport(
                id=self.id,
                name=self.name,
                category=self.category,
                categories=self.categories,
                installed=False,
                status=HealthStatus.NOT_FOUND,
            )

        # Probe version: `node -v` -> "v24.20.0"
        res = runner.run_command([str(node_bin), "-v"])
        version = res.stdout.lstrip("v").strip() if res.ok else None

        companions = []
        diagnostics = []

        # Check companions: npm, pnpm, yarn, corepack
        for companion_name in ["npm", "pnpm", "yarn", "corepack"]:
            comp_bin = runner.resolve_binary(companion_name)
            if comp_bin:
                comp_ver_res = runner.run_command([str(comp_bin), "--version"])
                comp_ver = comp_ver_res.stdout.strip() if comp_ver_res.ok else None
                companions.append(
                    CompanionTool(
                        name=companion_name,
                        installed=True,
                        version=comp_ver,
                        binary_path=str(comp_bin),
                    )
                )
            else:
                companions.append(CompanionTool(name=companion_name, installed=False))

        npm_found = any(c.installed for c in companions if c.name == "npm")
        if not npm_found:
            diagnostics.append(
                DiagnosticIssue(
                    level=DiagnosticLevel.WARNING,
                    message="npm package manager is not detected alongside Node.js.",
                    suggested_fix="Reinstall Node.js or run 'corepack enable'.",
                )
            )

        status = HealthStatus.HEALTHY if npm_found else HealthStatus.WARNING

        return ToolReport(
            id=self.id,
            name=self.name,
            category=self.category,
            categories=self.categories,
            installed=True,
            version=version,
            binary_path=str(node_bin),
            home_path=str(node_bin.parent),
            status=status,
            companions=companions,
            diagnostics=diagnostics,
            metadata={"prefix": str(node_bin.parent)},
        )
