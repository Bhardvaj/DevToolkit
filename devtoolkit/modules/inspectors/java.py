"""Java / JDK Runtime & Development Kit Inspector."""

import os
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


class JavaInspector(BaseInspector):
    id = "java"
    name = "Java / JDK"
    category = "runtime"
    description = "Java Virtual Machine (JVM), Java Compiler (javac), and JAVA_HOME environment"

    def inspect(self, runner: SafeRunner) -> ToolReport:
        java_home = runner.read_env("JAVA_HOME")
        extra_paths = []
        if java_home:
            extra_paths.append(str(Path(java_home) / "bin"))

        # Windows registry fallback for JavaSoft
        reg_home = runner.query_winreg(r"SOFTWARE\JavaSoft\JDK", "JavaHome")
        if reg_home:
            extra_paths.append(str(Path(reg_home) / "bin"))

        java_bin = runner.resolve_binary("java", extra_paths=extra_paths)
        if not java_bin:
            return ToolReport(
                id=self.id,
                name=self.name,
                category=self.category,
                installed=False,
                status=HealthStatus.NOT_FOUND,
            )

        # JVM prints version information to stderr or stdout depending on vendor
        res = runner.run_command([str(java_bin), "-version"])
        output = f"{res.stdout}\n{res.stderr}".strip()
        version = None
        m = re.search(r'(?:openjdk|java)?\s*version\s*["\']?([0-9._]+)["\']?', output, re.IGNORECASE)
        if m:
            version = m.group(1)
        elif output:
            version = output.splitlines()[0]

        companions = []
        diagnostics = []

        # Check javac (Java Development Kit compiler)
        javac_bin = runner.resolve_binary("javac", extra_paths=extra_paths)
        if javac_bin:
            javac_res = runner.run_command([str(javac_bin), "-version"])
            j_out = f"{javac_res.stdout}\n{javac_res.stderr}".strip()
            j_m = re.search(r"javac\s+([0-9._]+)", j_out)
            companions.append(
                CompanionTool(
                    name="javac (JDK)",
                    installed=True,
                    version=j_m.group(1) if j_m else None,
                    binary_path=str(javac_bin),
                )
            )
        else:
            companions.append(CompanionTool(name="javac (JDK)", installed=False))
            diagnostics.append(
                DiagnosticIssue(
                    level=DiagnosticLevel.INFO,
                    message="javac compiler not found. You have a JRE installed, but not a full JDK.",
                    suggested_fix="Install a full Java Development Kit (e.g., Eclipse Temurin, Amazon Corretto).",
                )
            )

        # Check JAVA_HOME configuration
        if not java_home:
            diagnostics.append(
                DiagnosticIssue(
                    level=DiagnosticLevel.WARNING,
                    message="JAVA_HOME environment variable is not defined.",
                    suggested_fix=f"Set JAVA_HOME to '{java_bin.parent.parent}' in your system environment variables.",
                )
            )
            status = HealthStatus.WARNING
        elif not Path(java_home).exists():
            diagnostics.append(
                DiagnosticIssue(
                    level=DiagnosticLevel.ERROR,
                    message=f"JAVA_HOME is set to '{java_home}', but this path does not exist on disk.",
                    suggested_fix="Update JAVA_HOME to point to a valid JDK directory.",
                )
            )
            status = HealthStatus.ERROR
        else:
            status = HealthStatus.HEALTHY

        return ToolReport(
            id=self.id,
            name=self.name,
            category=self.category,
            installed=True,
            version=version,
            binary_path=str(java_bin),
            home_path=java_home or str(java_bin.parent.parent),
            status=status,
            companions=companions,
            diagnostics=diagnostics,
            metadata={"JAVA_HOME": java_home},
        )
