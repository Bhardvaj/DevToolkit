"""Android SDK & Mobile Development Inspector."""

import re
import shutil
import sys
from pathlib import Path
from typing import List, Optional

from devtoolkit.core.base import BaseInspector
from devtoolkit.core.models import (
    CompanionTool,
    DeepTelemetryReport,
    DiagnosticIssue,
    DiagnosticLevel,
    DiscoveredInstance,
    EnvVarStatus,
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

    def deep_inspect(self, runner: SafeRunner, base_report: Optional[ToolReport] = None) -> DeepTelemetryReport:
        if base_report is None:
            base_report = self.inspect(runner)
        from datetime import datetime
        raw_dumps = {}
        trace = ["Starting Android SDK deep inspection probe"]
        instances: List[DiscoveredInstance] = []
        env_vars: List[EnvVarStatus] = []
        detailed_diag: List[DiagnosticIssue] = list(base_report.diagnostics)
        remediations: List[str] = []

        # 1. Multi-Instance Discovery
        seen_paths = set()

        # Primary resolved adb
        if base_report.binary_path:
            p_adb = Path(base_report.binary_path)
            seen_paths.add(str(p_adb).lower())
            instances.append(
                DiscoveredInstance(
                    path=str(p_adb),
                    binary_path=str(p_adb),
                    version=base_report.version,
                    source="Active PATH / Resolved",
                    is_active=True,
                    details="Active adb binary used by Android build tools and terminal",
                )
            )

        # Probe all adb on PATH
        for bin_p in runner.resolve_all_binaries("adb"):
            if str(bin_p).lower() not in seen_paths:
                seen_paths.add(str(bin_p).lower())
                is_act = bool(base_report.binary_path and str(bin_p).lower() == str(base_report.binary_path).lower())
                ver = None
                res_v = runner.run_command([str(bin_p), "--version"])
                if res_v.ok and res_v.stdout:
                    m = re.search(r"Version\s+([0-9a-zA-Z.-]+)", res_v.stdout)
                    ver = m.group(1) if m else None
                instances.append(
                    DiscoveredInstance(
                        path=str(bin_p),
                        binary_path=str(bin_p),
                        version=ver,
                        source="PATH",
                        is_active=is_act,
                        details="System PATH adb binary",
                    )
                )

        # Check in resolved home path
        if base_report.home_path:
            sdk_adb = Path(base_report.home_path) / "platform-tools" / ("adb.exe" if sys.platform == "win32" else "adb")
            if sdk_adb.is_file() and str(sdk_adb).lower() not in seen_paths:
                seen_paths.add(str(sdk_adb).lower())
                instances.append(
                    DiscoveredInstance(
                        path=str(sdk_adb),
                        binary_path=str(sdk_adb),
                        version=base_report.version,
                        source="SDK Root",
                        is_active=False,
                        details="Bundled platform-tools adb inside discovered SDK root",
                    )
                )

        # Discovery Pipeline instances (Layer 2-4 Discovery)
        for disc_p in runner.discovery.discover_all_tool_instances(self.id):
            cand_bin = disc_p / "platform-tools" / ("adb.exe" if sys.platform == "win32" else "adb")
            b_target = cand_bin if cand_bin.is_file() else None
            k = str(b_target or disc_p).lower()
            if k not in seen_paths:
                seen_paths.add(k)
                instances.append(
                    DiscoveredInstance(
                        path=str(disc_p),
                        binary_path=str(b_target) if b_target else None,
                        version=base_report.version,
                        source="Discovery Pipeline",
                        is_active=bool(base_report.binary_path and b_target and str(b_target).lower() == str(base_report.binary_path).lower()),
                        details="Discovered Android SDK root (Layer 2-4)",
                    )
                )

        trace.append(f"Discovered {len(instances)} Android/adb instances")

        # 2. Environment Variables Alignment
        ah_val = runner.read_env("ANDROID_HOME")
        ah_target = base_report.home_path
        if ah_val:
            is_match = bool(ah_target and Path(ah_val).resolve() == Path(ah_target).resolve())
            env_vars.append(
                EnvVarStatus(
                    name="ANDROID_HOME",
                    value=ah_val,
                    status="aligned" if is_match else "divergent",
                    target_path=ah_target,
                    message="Matches resolved Android SDK installation" if is_match else f"Points to '{ah_val}' which differs from resolved SDK '{ah_target}'",
                )
            )
            if not is_match and ah_target:
                remediations.append(f'setx ANDROID_HOME "{ah_target}"')
        else:
            env_vars.append(
                EnvVarStatus(
                    name="ANDROID_HOME",
                    value=None,
                    status="missing",
                    target_path=ah_target,
                    message="Unset. Gradle, Flutter, and Android CLI tools rely on ANDROID_HOME.",
                )
            )
            if ah_target:
                remediations.append(f'setx ANDROID_HOME "{ah_target}"')

        # ANDROID_SDK_ROOT (Legacy fallback)
        asr_val = runner.read_env("ANDROID_SDK_ROOT")
        if asr_val:
            is_asr_match = bool(ah_target and Path(asr_val).resolve() == Path(ah_target).resolve())
            env_vars.append(
                EnvVarStatus(
                    name="ANDROID_SDK_ROOT",
                    value=asr_val,
                    status="aligned" if is_asr_match else "divergent",
                    target_path=ah_target,
                    message="Legacy variable matches SDK installation" if is_asr_match else f"Legacy variable points to '{asr_val}'",
                )
            )

        # ANDROID_AVD_HOME
        avd_val = runner.read_env("ANDROID_AVD_HOME")
        env_vars.append(
            EnvVarStatus(
                name="ANDROID_AVD_HOME",
                value=avd_val,
                status="aligned" if avd_val else "missing",
                target_path=str(Path.home() / ".android" / "avd"),
                message="Points to custom Android Virtual Device storage" if avd_val else "Not configured (defaults to ~/.android/avd)",
            )
        )

        # 3. CLI Telemetry Dumps
        adb_exec = base_report.binary_path or (str(instances[0].binary_path) if instances else None)
        if adb_exec:
            res_ver = runner.run_command([adb_exec, "version"])
            if res_ver.ok and res_ver.stdout:
                raw_dumps["adb version"] = res_ver.stdout.strip()

            res_dev = runner.run_command([adb_exec, "devices", "-l"], timeout_seconds=2)
            if res_dev.ok and res_dev.stdout:
                raw_dumps["adb devices -l"] = res_dev.stdout.strip()

        # Platforms & build-tools summary dumps
        if base_report.home_path:
            sdk_p = Path(base_report.home_path)
            plat_p = sdk_p / "platforms"
            if plat_p.is_dir():
                installed_plats = [p.name for p in plat_p.iterdir() if p.is_dir()]
                raw_dumps["SDK Platforms"] = "\n".join(installed_plats) if installed_plats else "(none installed)"

            bt_p = sdk_p / "build-tools"
            if bt_p.is_dir():
                installed_bts = [p.name for p in bt_p.iterdir() if p.is_dir()]
                raw_dumps["Build Tools"] = "\n".join(installed_bts) if installed_bts else "(none installed)"

        trace.append("Completed Android SDK deep telemetry probes")

        return DeepTelemetryReport(
            tool_id=self.id,
            timestamp=datetime.now().isoformat(),
            probe_latency_ms=0,
            instances=instances,
            env_vars=env_vars,
            telemetry={
                "platforms": base_report.metadata.get("platforms", []),
                "build_tools": base_report.metadata.get("build_tools", []),
                "home_path": base_report.home_path,
            },
            raw_dumps=raw_dumps,
            detailed_diagnostics=detailed_diag,
            remediation_commands=remediations,
            discovery_trace=trace,
        )

