"""Android SDK & Mobile Development Inspector."""

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


class AndroidInspector(BaseInspector):
    id = "android"
    name = "Android SDK"
    category = "mobile"
    description = "Android SDK tools, adb, build-tools, emulator, and ANDROID_HOME environment"

    def _discover_sdk_path(self, runner: SafeRunner) -> Optional[Path]:
        """Discover Android SDK directory across env vars, Flutter config, and standard dev drives."""
        candidate_paths: List[Path] = []

        # 1. Environment variables
        for env_var in ["ANDROID_HOME", "ANDROID_SDK_ROOT"]:
            val = runner.read_env(env_var)
            if val:
                candidate_paths.append(Path(val))

        # 2. Check Flutter configuration if available
        flutter_bin = runner.resolve_binary("flutter") or runner.resolve_binary("flutter.bat")
        if not flutter_bin and sys.platform == "win32":
            for drive in ["D", "C", "E"]:
                candidate_flutter = Path(f"{drive}:/Dev/flutter/bin/flutter.bat")
                if candidate_flutter.exists():
                    flutter_bin = candidate_flutter
                    break

        if flutter_bin:
            res = runner.run_command([str(flutter_bin), "config", "--machine"], timeout=3.0)
            if res.ok and res.stdout:
                try:
                    f_cfg = json.loads(res.stdout)
                    sdk_dir = f_cfg.get("android-sdk")
                    if sdk_dir:
                        candidate_paths.append(Path(sdk_dir))
                except Exception:
                    pass

        # 3. Known paths across Windows drives & common dev locations
        drives = ["D", "C", "E"] if sys.platform == "win32" else [""]
        for d in drives:
            prefix = f"{d}:" if d else ""
            candidate_paths.extend([
                Path(f"{prefix}/Dev/android_sdk"),
                Path(f"{prefix}/Dev/Android/Sdk"),
                Path(f"{prefix}/Android/Sdk"),
                Path(f"{prefix}/Android/android_sdk"),
                Path(f"{prefix}/android_sdk"),
            ])

        # 4. Standard OS user locations
        local_app_data = runner.read_env("LOCALAPPDATA")
        if local_app_data:
            candidate_paths.append(Path(local_app_data) / "Android" / "Sdk")

        candidate_paths.append(Path.home() / "Android" / "Sdk")
        candidate_paths.append(Path.home() / "Library" / "Android" / "sdk")

        for cand in candidate_paths:
            try:
                expanded = cand.expanduser().resolve()
                if expanded.exists() and (
                    (expanded / "platform-tools").exists()
                    or (expanded / "build-tools").exists()
                    or (expanded / "platforms").exists()
                ):
                    return expanded
            except Exception:
                continue

        return None

    def inspect(self, runner: SafeRunner) -> ToolReport:
        resolved_sdk = self._discover_sdk_path(runner)
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
        build_tools_installed = []
        platforms_installed = []
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
