"""Flutter & Dart Cross-Platform Mobile SDK Inspector."""

import re
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


class FlutterInspector(BaseInspector):
    id = "flutter"
    name = "Flutter"
    category = "mobile"
    categories = ["mobile", "sdk", "runtime"]
    description = "Flutter cross-platform UI framework and Dart SDK"

    def inspect(self, runner: SafeRunner) -> ToolReport:
        flutter_bin = runner.resolve_binary("flutter", tool_id=self.id)
        if not flutter_bin:
            return ToolReport(
                id=self.id,
                name=self.name,
                category=self.category,
                categories=self.categories,
                installed=False,
                status=HealthStatus.NOT_FOUND,
            )

        # Output format: "Flutter 3.22.2 • channel stable • https://github.com/flutter/flutter.git"
        res = runner.run_command([str(flutter_bin), "--version"], timeout=4.0)
        version = None
        channel = None
        if res.ok and res.stdout:
            m = re.search(r"Flutter\s+([0-9.]+)", res.stdout)
            version = m.group(1) if m else None
            m_chan = re.search(r"channel\s+([a-zA-Z]+)", res.stdout)
            channel = m_chan.group(1) if m_chan else None

        companions = []
        diagnostics = []

        # Check Dart SDK
        dart_bin = runner.resolve_binary("dart", extra_paths=[str(flutter_bin.parent / "cache" / "dart-sdk" / "bin")])
        if dart_bin:
            dart_res = runner.run_command([str(dart_bin), "--version"])
            d_ver = None
            out = f"{dart_res.stdout}\n{dart_res.stderr}"
            m_dart = re.search(r"Dart SDK version:\s*([0-9.]+)", out)
            d_ver = m_dart.group(1) if m_dart else None
            companions.append(
                CompanionTool(
                    name="dart",
                    installed=True,
                    version=d_ver,
                    binary_path=str(dart_bin),
                )
            )
        else:
            companions.append(CompanionTool(name="dart", installed=False))

        status = HealthStatus.HEALTHY

        return ToolReport(
            id=self.id,
            name=self.name,
            category=self.category,
            categories=self.categories,
            installed=True,
            version=version,
            binary_path=str(flutter_bin),
            home_path=str(flutter_bin.parent.parent),
            status=status,
            companions=companions,
            diagnostics=diagnostics,
            metadata={"channel": channel},
        )

    def deep_inspect(self, runner: SafeRunner, base_report: Optional[ToolReport] = None) -> DeepTelemetryReport:
        if base_report is None:
            base_report = self.inspect(runner)
        from datetime import datetime
        raw_dumps = {}
        trace = ["Starting Flutter SDK deep inspection probe"]
        instances: List[DiscoveredInstance] = []
        env_vars: List[EnvVarStatus] = []
        detailed_diag: List[DiagnosticIssue] = list(base_report.diagnostics)
        remediations: List[str] = []

        seen_bins = set()

        # Primary resolved binary
        if base_report.binary_path:
            p_bin = Path(base_report.binary_path)
            seen_bins.add(str(p_bin).lower())
            instances.append(
                DiscoveredInstance(
                    path=str(p_bin.parent.parent),
                    binary_path=str(p_bin),
                    version=base_report.version,
                    source="Active PATH",
                    is_active=True,
                    details=f"Active Flutter SDK (channel: {base_report.metadata.get('channel') or 'stable'})",
                )
            )

        # Multi-instance discovery across PATH
        for f_bin in runner.resolve_all_binaries("flutter"):
            if str(f_bin).lower() not in seen_bins:
                seen_bins.add(str(f_bin).lower())
                is_act = bool(base_report.binary_path and str(f_bin).lower() == str(base_report.binary_path).lower())
                ver_str = None
                res_v = runner.run_command([str(f_bin), "--version"], timeout=2.5)
                if res_v.ok and res_v.stdout:
                    m = re.search(r"Flutter\s+([0-9.]+)", res_v.stdout)
                    ver_str = m.group(1) if m else None
                instances.append(
                    DiscoveredInstance(
                        path=str(f_bin.parent.parent),
                        binary_path=str(f_bin),
                        version=ver_str,
                        source="Alternate PATH",
                        is_active=is_act,
                        details="Alternate Flutter installation in PATH",
                    )
                )

        # Discovery Pipeline instances (Layer 2-4 Discovery)
        for disc_p in runner.discovery.discover_all_tool_instances(self.id):
            cand_bin = disc_p / "bin" / ("flutter.bat" if sys.platform == "win32" else "flutter")
            b_target = cand_bin if cand_bin.is_file() else None
            k = str(b_target or disc_p).lower()
            if k not in seen_bins:
                seen_bins.add(k)
                instances.append(
                    DiscoveredInstance(
                        path=str(disc_p),
                        binary_path=str(b_target) if b_target else None,
                        version=None,
                        source="Discovery Pipeline",
                        is_active=bool(base_report.binary_path and b_target and str(b_target).lower() == str(base_report.binary_path).lower()),
                        details="Discovered Flutter SDK (Layer 2-4)",
                    )
                )

        trace.append(f"Discovered {len(instances)} Flutter SDK installations")

        # 2. Environment Variables Alignment
        fl_root = runner.read_env("FLUTTER_ROOT")
        target_root = base_report.home_path
        if fl_root:
            is_match = bool(target_root and Path(fl_root).resolve() == Path(target_root).resolve())
            env_vars.append(
                EnvVarStatus(
                    name="FLUTTER_ROOT",
                    value=fl_root,
                    status="aligned" if is_match else "divergent",
                    target_path=target_root,
                    message="Matches resolved Flutter SDK root" if is_match else f"Points to '{fl_root}' which differs from active root '{target_root}'",
                )
            )
            if not is_match and target_root:
                remediations.append(f'setx FLUTTER_ROOT "{target_root}"')
        else:
            env_vars.append(
                EnvVarStatus(
                    name="FLUTTER_ROOT",
                    value=None,
                    status="missing",
                    target_path=target_root,
                    message="Unset (Flutter derives its root directory dynamically from binary location)",
                )
            )

        pub_cache = runner.read_env("PUB_CACHE")
        env_vars.append(
            EnvVarStatus(
                name="PUB_CACHE",
                value=pub_cache,
                status="aligned" if pub_cache else "missing",
                target_path=str(Path.home() / ".pub-cache"),
                message="Points to custom Dart package cache directory" if pub_cache else "Default cache (~/.pub-cache or %LOCALAPPDATA%/Pub/Cache)",
            )
        )

        # 3. CLI Telemetry Dumps
        f_exec = base_report.binary_path or "flutter"
        res_ver = runner.run_command([f_exec, "--version"], timeout=3.5)
        if res_ver.ok and res_ver.stdout:
            raw_dumps["flutter --version"] = res_ver.stdout.strip()

        res_cfg = runner.run_command([f_exec, "config", "--machine"], timeout=3.0)
        if res_cfg.ok and res_cfg.stdout:
            raw_dumps["flutter config --machine"] = res_cfg.stdout.strip()

        # Probe Dart companion
        if base_report.home_path:
            dart_p = Path(base_report.home_path) / "bin" / "cache" / "dart-sdk" / "bin" / ("dart.exe" if sys.platform == "win32" else "dart")
            if dart_p.is_file():
                d_res = runner.run_command([str(dart_p), "--version"])
                raw_dumps["Bundled Dart SDK"] = f"{d_res.stdout}\n{d_res.stderr}".strip()

        # Run fast doctor check
        res_doc = runner.run_command([f_exec, "doctor", "-v"], timeout=1.5)
        if res_doc.ok and res_doc.stdout:
            raw_dumps["flutter doctor -v"] = res_doc.stdout.strip()

        trace.append("Completed Flutter SDK deep telemetry probes")

        return DeepTelemetryReport(
            tool_id=self.id,
            timestamp=datetime.now().isoformat(),
            probe_latency_ms=0,
            instances=instances,
            env_vars=env_vars,
            telemetry={
                "channel": base_report.metadata.get("channel"),
                "home_path": base_report.home_path,
            },
            raw_dumps=raw_dumps,
            detailed_diagnostics=detailed_diag,
            remediation_commands=remediations,
            discovery_trace=trace,
        )

