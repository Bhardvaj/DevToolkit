"""Flutter & Dart Cross-Platform Mobile SDK Inspector."""

import re
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


class FlutterInspector(BaseInspector):
    id = "flutter"
    name = "Flutter"
    category = "mobile"
    description = "Flutter cross-platform UI framework and Dart SDK"

    def _discover_flutter_bin(self, runner: SafeRunner) -> Optional[Path]:
        # 1. System PATH
        system_flutter = runner.resolve_binary("flutter") or runner.resolve_binary("flutter.bat")
        if system_flutter:
            return system_flutter

        # 2. Check candidate paths across drives
        drives = ["D", "C", "E"] if sys.platform == "win32" else [""]
        for d in drives:
            prefix = f"{d}:" if d else ""
            for cand in [
                Path(f"{prefix}/Dev/flutter/bin/flutter.bat"),
                Path(f"{prefix}/Dev/flutter/bin/flutter"),
                Path(f"{prefix}/flutter/bin/flutter.bat"),
                Path(f"{prefix}/flutter/bin/flutter"),
                Path(f"{prefix}/src/flutter/bin/flutter.bat"),
            ]:
                if cand.exists():
                    return cand

        return None

    def inspect(self, runner: SafeRunner) -> ToolReport:
        flutter_bin = self._discover_flutter_bin(runner)
        if not flutter_bin:
            return ToolReport(
                id=self.id,
                name=self.name,
                category=self.category,
                installed=False,
                status=HealthStatus.NOT_FOUND,
            )

        # Probe version with adequate timeout for Dart VM initialization
        res = runner.run_command([str(flutter_bin), "--version"], timeout=8.0)
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
        dart_extra = [str(flutter_bin.parent / "cache" / "dart-sdk" / "bin")]
        dart_bin = runner.resolve_binary("dart", extra_paths=dart_extra) or runner.resolve_binary("dart.bat", extra_paths=dart_extra)
        if dart_bin:
            dart_res = runner.run_command([str(dart_bin), "--version"], timeout=5.0)
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

        return ToolReport(
            id=self.id,
            name=self.name,
            category=self.category,
            installed=True,
            version=version,
            binary_path=str(flutter_bin),
            home_path=str(flutter_bin.parent.parent),
            status=HealthStatus.HEALTHY,
            companions=companions,
            diagnostics=diagnostics,
            metadata={"channel": channel},
        )
