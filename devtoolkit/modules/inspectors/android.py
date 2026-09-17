"""Android SDK & Mobile Development Inspector."""

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


class AndroidInspector(BaseInspector):
    id = "android"
    name = "Android SDK"
    category = "mobile"
    description = "Android SDK tools, adb (Android Debug Bridge), emulator, and ANDROID_HOME"

    def inspect(self, runner: SafeRunner) -> ToolReport:
        android_home = runner.read_env("ANDROID_HOME") or runner.read_env("ANDROID_SDK_ROOT")
        candidate_sdk_dirs = []

        if android_home:
            candidate_sdk_dirs.append(Path(android_home))

        # Windows default SDK location: %LOCALAPPDATA%\Android\Sdk
        local_app_data = runner.read_env("LOCALAPPDATA")
        if local_app_data:
            candidate_sdk_dirs.append(Path(local_app_data) / "Android" / "Sdk")

        # Linux/macOS defaults
        candidate_sdk_dirs.append(Path.home() / "Android" / "Sdk")
        candidate_sdk_dirs.append(Path.home() / "Library" / "Android" / "sdk")

        resolved_sdk_dir = None
        for cand in candidate_sdk_dirs:
            if cand.exists() and (cand / "platform-tools").exists():
                resolved_sdk_dir = cand.resolve()
                break

        extra_bin_dirs = []
        if resolved_sdk_dir:
            extra_bin_dirs.append(str(resolved_sdk_dir / "platform-tools"))
            extra_bin_dirs.append(str(resolved_sdk_dir / "emulator"))
            extra_bin_dirs.append(str(resolved_sdk_dir / "cmdline-tools" / "latest" / "bin"))

        adb_bin = runner.resolve_binary("adb", extra_paths=extra_bin_dirs)

        if not resolved_sdk_dir and not adb_bin:
            return ToolReport(
                id=self.id,
                name=self.name,
                category=self.category,
                installed=False,
                status=HealthStatus.NOT_FOUND,
            )

        version = None
        if adb_bin:
            res = runner.run_command([str(adb_bin), "--version"])
            if res.ok and res.stdout:
                m = re.search(r"Version\s+([0-9a-zA-Z.-]+)", res.stdout)
                version = m.group(1) if m else res.stdout.splitlines()[0]

        companions = []
        diagnostics = []

        # Check companion tools: emulator, fastboot
        for tool in ["emulator", "fastboot"]:
            t_bin = runner.resolve_binary(tool, extra_paths=extra_bin_dirs)
            companions.append(
                CompanionTool(
                    name=tool,
                    installed=t_bin is not None,
                    binary_path=str(t_bin) if t_bin else None,
                )
            )

        # Health Diagnostics
        if not android_home and resolved_sdk_dir:
            diagnostics.append(
                DiagnosticIssue(
                    level=DiagnosticLevel.WARNING,
                    message="Android SDK found on disk, but ANDROID_HOME environment variable is not defined.",
                    suggested_fix=f"Set ANDROID_HOME to '{resolved_sdk_dir}' in your system environment variables.",
                )
            )
            status = HealthStatus.WARNING
        elif android_home and not Path(android_home).exists():
            diagnostics.append(
                DiagnosticIssue(
                    level=DiagnosticLevel.ERROR,
                    message=f"ANDROID_HOME is configured as '{android_home}', but path does not exist on disk.",
                    suggested_fix="Correct the ANDROID_HOME path or reinstall the Android SDK.",
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
            binary_path=str(adb_bin) if adb_bin else None,
            home_path=str(resolved_sdk_dir) if resolved_sdk_dir else None,
            status=status,
            companions=companions,
            diagnostics=diagnostics,
            metadata={"ANDROID_HOME": android_home},
        )
