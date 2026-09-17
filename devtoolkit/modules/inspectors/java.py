"""Java / JDK Runtime & Development Kit Inspector."""

import json
import os
import re
import shutil
import sys
from pathlib import Path
from typing import List, Optional

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

    def _discover_java_home(self, runner: SafeRunner) -> Optional[Path]:
        """Find Java installation directory across env, Flutter config, registry, and IDE runtimes."""
        candidate_homes: List[Path] = []

        # 1. JAVA_HOME environment variable
        java_home_env = runner.read_env("JAVA_HOME")
        if java_home_env:
            candidate_homes.append(Path(java_home_env))

        # 2. Check Flutter configuration for jdk-dir
        flutter_bin = runner.resolve_binary("flutter") or runner.resolve_binary("flutter.bat")
        if not flutter_bin and sys.platform == "win32":
            for drive in ["D", "C", "E"]:
                f_path = Path(f"{drive}:/Dev/flutter/bin/flutter.bat")
                if f_path.exists():
                    flutter_bin = f_path
                    break

        if flutter_bin:
            res = runner.run_command([str(flutter_bin), "config", "--machine"], timeout=3.0)
            if res.ok and res.stdout:
                try:
                    f_cfg = json.loads(res.stdout)
                    jdk_dir = f_cfg.get("jdk-dir")
                    if jdk_dir:
                        candidate_homes.append(Path(jdk_dir))
                except Exception:
                    pass

        # 3. Android Studio bundled JBR/JRE across drives
        drives = ["D", "C", "E"] if sys.platform == "win32" else [""]
        for d in drives:
            prefix = f"{d}:" if d else ""
            candidate_homes.extend([
                Path(f"{prefix}/Dev/android_studio/jbr"),
                Path(f"{prefix}/Dev/android_studio/jre"),
                Path(f"{prefix}/Program Files/Android/Android Studio/jbr"),
                Path(f"{prefix}/Program Files/Android/Android Studio/jre"),
            ])

        # 4. Windows Registry lookups
        reg_home = runner.query_winreg(r"SOFTWARE\JavaSoft\JDK", "JavaHome")
        if reg_home:
            candidate_homes.append(Path(reg_home))
        reg_jre = runner.query_winreg(r"SOFTWARE\JavaSoft\Java Runtime Environment", "JavaHome")
        if reg_jre:
            candidate_homes.append(Path(reg_jre))

        # 5. Standard system JDK directories
        for d in drives:
            prefix = f"{d}:" if d else ""
            for base_folder in [Path(f"{prefix}/Program Files/Eclipse Adoptium"), Path(f"{prefix}/Program Files/Java")]:
                if base_folder.exists():
                    for sub in base_folder.iterdir():
                        if sub.is_dir():
                            candidate_homes.append(sub)

        for cand in candidate_homes:
            try:
                expanded = cand.expanduser().resolve()
                java_exe = expanded / "bin" / ("java.exe" if sys.platform == "win32" else "java")
                if expanded.exists() and java_exe.exists():
                    return expanded
            except Exception:
                continue

        return None

    def inspect(self, runner: SafeRunner) -> ToolReport:
        java_home_env = runner.read_env("JAVA_HOME")
        discovered_home = self._discover_java_home(runner)

        extra_bin_dirs = []
        if discovered_home:
            extra_bin_dirs.append(str(discovered_home / "bin"))

        system_java = shutil.which("java")
        resolved_java = runner.resolve_binary("java", extra_paths=extra_bin_dirs)

        if not resolved_java and not discovered_home:
            return ToolReport(
                id=self.id,
                name=self.name,
                category=self.category,
                installed=False,
                status=HealthStatus.NOT_FOUND,
            )

        # JVM prints version information to stderr or stdout depending on vendor
        res = runner.run_command([str(resolved_java), "-version"])
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
        system_javac = shutil.which("javac")
        javac_bin = runner.resolve_binary("javac", extra_paths=extra_bin_dirs)
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

        # Health Diagnostics
        is_healthy = True

        if not java_home_env:
            is_healthy = False
            origin = "Android Studio JBR" if "android_studio" in str(discovered_home).lower() else "disk"
            diagnostics.append(
                DiagnosticIssue(
                    level=DiagnosticLevel.WARNING,
                    message=f"JAVA_HOME is not defined in system environment (detected Java in {origin} at '{discovered_home}').",
                    suggested_fix=f"Set system environment variable JAVA_HOME to '{discovered_home}' and add '%JAVA_HOME%\\bin' to PATH.",
                )
            )
        elif not Path(java_home_env).exists():
            is_healthy = False
            diagnostics.append(
                DiagnosticIssue(
                    level=DiagnosticLevel.ERROR,
                    message=f"JAVA_HOME is set to '{java_home_env}', but this path does not exist on disk.",
                    suggested_fix="Update JAVA_HOME to point to a valid JDK directory.",
                )
            )

        if resolved_java and not system_java:
            is_healthy = False
            diagnostics.append(
                DiagnosticIssue(
                    level=DiagnosticLevel.WARNING,
                    message=f"Java executable was found at '{resolved_java}', but is not in system PATH.",
                    suggested_fix=f"Add '{resolved_java.parent}' to system PATH.",
                )
            )

        status = HealthStatus.HEALTHY if is_healthy else HealthStatus.WARNING

        return ToolReport(
            id=self.id,
            name=self.name,
            category=self.category,
            installed=True,
            version=version,
            binary_path=str(resolved_java) if resolved_java else None,
            home_path=str(discovered_home) if discovered_home else None,
            status=status,
            companions=companions,
            diagnostics=diagnostics,
            metadata={"JAVA_HOME": java_home_env, "source": "Android Studio JBR" if "android_studio" in str(discovered_home).lower() else "System"},
        )
