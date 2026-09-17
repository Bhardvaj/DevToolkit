"""Android SDK & Mobile Development Inspector."""

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


class AndroidInspector(BaseInspector):
    id = "android"
    name = "Android SDK"
    category = "mobile"
    categories = ["mobile", "sdk"]
    description = "Android SDK tools, adb, build-tools, emulator, and ANDROID_HOME environment"

    def inspect(self, runner: SafeRunner) -> ToolReport:
        # Layered resolution (Env -> OS -> Ecosystem -> Signatures)
        resolved_sdk = runner.discovery.discover_android_sdk()
        android_home = runner.read_env("ANDROID_HOME") or runner.read_env("ANDROID_SDK_ROOT")

        extra_bin_dirs = []
        if resolved_sdk:
            extra_bin_dirs.append(str(resolved_sdk / "platform-tools"))
            extra_bin_dirs.append(str(resolved_sdk / "emulator"))
            extra_bin_dirs.append(str(resolved_sdk / "cmdline-tools" / "latest" / "bin"))

        # Check adb on system PATH vs in SDK directory
        system_adb = shutil.which("adb")
        resolved_adb = runner.resolve_binary("adb", extra_paths=extra_bin_dirs)

        if not resolved_sdk and not resolved_adb:
            return ToolReport(
                id=self.id,
                name=self.name,
                category=self.category,
                categories=self.categories,
                installed=False,
                status=HealthStatus.NOT_FOUND,
            )

        # Probe adb version
        version = None
        if resolved_adb:
            res = runner.run_command([str(resolved_adb), "--version"])
            if res.ok and res.stdout:
                m = re.search(r"Version\s+([0-9a-zA-Z.-]+)", res.stdout)
                version = m.group(1) if m else res.stdout.splitlines()[0]

        companions = []
        diagnostics = []

        # Companion: adb
        companions.append(
            CompanionTool(
                name="adb",
                installed=resolved_adb is not None,
                version=version,
                binary_path=str(resolved_adb) if resolved_adb else None,
            )
        )

        # Companion: emulator
        emulator_bin = runner.resolve_binary("emulator", extra_paths=extra_bin_dirs)
        companions.append(
            CompanionTool(
                name="emulator",
                installed=emulator_bin is not None,
                binary_path=str(emulator_bin) if emulator_bin else None,
            )
        )

        # Discover build-tools and platforms
        build_tools_installed: List[str] = []
        platforms_installed: List[str] = []
        if resolved_sdk:
            bt_dir = resolved_sdk / "build-tools"
            if bt_dir.exists():
                build_tools_installed = sorted([p.name for p in bt_dir.iterdir() if p.is_dir()])
            plat_dir = resolved_sdk / "platforms"
            if plat_dir.exists():
                platforms_installed = sorted([p.name for p in plat_dir.iterdir() if p.is_dir()])

        # Companion: build-tools
        companions.append(
            CompanionTool(
                name="build-tools",
                installed=len(build_tools_installed) > 0,
                version=", ".join(build_tools_installed[-3:]) if build_tools_installed else None,
                binary_path=str(resolved_sdk / "build-tools") if resolved_sdk else None,
            )
        )

        # Health Diagnostics
        is_healthy = True

        if not android_home and resolved_sdk:
            is_healthy = False
            diagnostics.append(
                DiagnosticIssue(
                    level=DiagnosticLevel.WARNING,
                    message=f"Android SDK detected at '{resolved_sdk}', but ANDROID_HOME environment variable is unset.",
                    suggested_fix=f"Set system environment variable ANDROID_HOME to '{resolved_sdk}'.",
                )
            )

        if resolved_adb and not system_adb:
            is_healthy = False
            diagnostics.append(
                DiagnosticIssue(
                    level=DiagnosticLevel.WARNING,
                    message=f"adb binary was found at '{resolved_adb}', but is not in system PATH.",
                    suggested_fix=f"Add '{resolved_adb.parent}' to your system PATH variable.",
                )
            )

        status = HealthStatus.HEALTHY if is_healthy else HealthStatus.WARNING

        return ToolReport(
            id=self.id,
            name=self.name,
            category=self.category,
            categories=self.categories,
            installed=True,
            version=version or (build_tools_installed[-1] if build_tools_installed else None),
            binary_path=str(resolved_adb) if resolved_adb else None,
            home_path=str(resolved_sdk) if resolved_sdk else None,
            status=status,
            companions=companions,
            diagnostics=diagnostics,
            metadata={
                "ANDROID_HOME": android_home,
                "build_tools": build_tools_installed,
                "platforms": platforms_installed,
            },
        )
