"""Python Runtime & Package Manager Inspector."""

import re
import sys
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


class PythonInspector(BaseInspector):
    id = "python"
    name = "Python"
    category = "runtime"
    description = "Python interpreter, pip, uv, poetry, and virtualenv tooling"

    def inspect(self, runner: SafeRunner) -> ToolReport:
        py_bin = runner.resolve_binary("python") or runner.resolve_binary("python3")
        if not py_bin:
            return ToolReport(
                id=self.id,
                name=self.name,
                category=self.category,
                installed=False,
                status=HealthStatus.NOT_FOUND,
            )

        res = runner.run_command([str(py_bin), "--version"])
        # Format: "Python 3.14.5"
        version = None
        if res.ok and res.stdout:
            parts = res.stdout.split()
            if len(parts) >= 2:
                version = parts[1]

        companions = []
        diagnostics = []

        # Check companions: pip, uv, poetry, conda, pipenv
        for comp_name in ["pip", "uv", "poetry", "conda", "pipenv"]:
            comp_bin = runner.resolve_binary(comp_name)
            if comp_bin:
                comp_ver_res = runner.run_command([str(comp_bin), "--version"])
                comp_ver = None
                if comp_ver_res.ok and comp_ver_res.stdout:
                    # Match version number in output like "pip 24.0 from ..." or "uv 0.1.0"
                    m = re.search(r"(\d+\.\d+(\.\d+)?)", comp_ver_res.stdout)
                    comp_ver = m.group(1) if m else comp_ver_res.stdout.split()[0]
                companions.append(
                    CompanionTool(
                        name=comp_name,
                        installed=True,
                        version=comp_ver,
                        binary_path=str(comp_bin),
                    )
                )
            else:
                companions.append(CompanionTool(name=comp_name, installed=False))

        pip_found = any(c.installed for c in companions if c.name == "pip")
        if not pip_found:
            diagnostics.append(
                DiagnosticIssue(
                    level=DiagnosticLevel.WARNING,
                    message="pip package manager is not installed in the global environment.",
                    suggested_fix="Run 'python -m ensurepip --upgrade' to provision pip.",
                )
            )

        status = HealthStatus.HEALTHY if pip_found else HealthStatus.WARNING

        return ToolReport(
            id=self.id,
            name=self.name,
            category=self.category,
            installed=True,
            version=version,
            binary_path=str(py_bin),
            home_path=str(py_bin.parent),
            status=status,
            companions=companions,
            diagnostics=diagnostics,
            metadata={"base_prefix": sys.base_prefix, "prefix": sys.prefix},
        )
