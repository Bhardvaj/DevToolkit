"""Flutter & Dart Cross-Platform Mobile SDK Inspector."""

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


class FlutterInspector(BaseInspector):
    id = "flutter"
    name = "Flutter"
    category = "mobile"
    description = "Flutter cross-platform UI framework and Dart SDK"

    def inspect(self, runner: SafeRunner) -> ToolReport:
        flutter_bin = runner.resolve_binary("flutter")
        if not flutter_bin:
            return ToolReport(
                id=self.id,
                name=self.name,
                category=self.category,
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
            installed=True,
            version=version,
            binary_path=str(flutter_bin),
            home_path=str(flutter_bin.parent.parent),
            status=status,
            companions=companions,
            diagnostics=diagnostics,
            metadata={"channel": channel},
        )
