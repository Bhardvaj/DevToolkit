"""Go (Golang) Runtime & Environment Inspector."""

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


class GoInspector(BaseInspector):
    id = "golang"
    name = "Go"
    category = "runtime"
    description = "Go compiler runtime, GOPATH, and GOROOT environment"

    def inspect(self, runner: SafeRunner) -> ToolReport:
        go_bin = runner.resolve_binary("go")
        if not go_bin:
            return ToolReport(
                id=self.id,
                name=self.name,
                category=self.category,
                installed=False,
                status=HealthStatus.NOT_FOUND,
            )

        # Output format: "go version go1.22.4 windows/amd64"
        res = runner.run_command([str(go_bin), "version"])
        version = None
        if res.ok and res.stdout:
            m = re.search(r"go version go([0-9.]+)", res.stdout)
            version = m.group(1) if m else res.stdout

        companions = []
        diagnostics = []

        # Check Go env for GOPATH and GOROOT
        gopath_res = runner.run_command([str(go_bin), "env", "GOPATH"])
        goroot_res = runner.run_command([str(go_bin), "env", "GOROOT"])

        gopath = gopath_res.stdout.strip() if gopath_res.ok else runner.read_env("GOPATH")
        goroot = goroot_res.stdout.strip() if goroot_res.ok else runner.read_env("GOROOT")

        status = HealthStatus.HEALTHY

        return ToolReport(
            id=self.id,
            name=self.name,
            category=self.category,
            installed=True,
            version=version,
            binary_path=str(go_bin),
            home_path=goroot or str(go_bin.parent.parent),
            status=status,
            companions=companions,
            diagnostics=diagnostics,
            metadata={"GOPATH": gopath, "GOROOT": goroot},
        )

