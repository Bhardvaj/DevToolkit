"""Android Studio IDE & Environment Inspector."""

import json
import os
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


class AndroidStudioInspector(BaseInspector):
    id = "android_studio"
    name = "Android Studio"
    category = "ide"
    description = "Android Studio IDE, JetBrains Runtime (JBR), and mobile tooling"

    def _discover_studio_dir(self, runner: SafeRunner) -> Optional[Path]:
        candidate_paths: List[Path] = []

        # 1. Flutter config
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
                    studio_dir = f_cfg.get("android-studio-dir")
                    if studio_dir:
                        candidate_paths.append(Path(studio_dir))
                except Exception:
                    pass

        # 2. Known dev locations across drives
        drives = ["D", "C", "E"] if sys.platform == "win32" else [""]
        for d in drives:
            prefix = f"{d}:" if d else ""
            candidate_paths.extend([
                Path(f"{prefix}/Dev/android_studio"),
                Path(f"{prefix}/Dev/AndroidStudio"),
                Path(f"{prefix}/Program Files/Android/Android Studio"),
                Path(f"{prefix}/Android/android_studio"),
            ])

        # 3. Local app data and macOS / Linux locations
        local_app_data = runner.read_env("LOCALAPPDATA")
        if local_app_data:
            candidate_paths.append(Path(local_app_data) / "Programs" / "Android Studio")

        candidate_paths.append(Path("/Applications/Android Studio.app/Contents"))
        candidate_paths.append(Path("/opt/android-studio"))
        candidate_paths.append(Path.home() / "android-studio")

        for cand in candidate_paths:
            try:
                expanded = cand.expanduser().resolve()
                if expanded.exists() and (
                    (expanded / "bin" / "studio64.exe").exists()
                    or (expanded / "bin" / "studio.sh").exists()
                    or (expanded / "MacOS" / "studio").exists()
                    or (expanded / "product-info.json").exists()
                ):
                    return expanded
            except Exception:
                continue

        return None

    def inspect(self, runner: SafeRunner) -> ToolReport:
        studio_dir = self._discover_studio_dir(runner)
        if not studio_dir:
            return ToolReport(
                id=self.id,
                name=self.name,
                category=self.category,
                installed=False,
                status=HealthStatus.NOT_FOUND,
            )

        # Detect version from product-info.json or build.txt
        version = None
        build_number = None
        prod_info_file = studio_dir / "product-info.json"
        if prod_info_file.exists():
            try:
                data = json.loads(prod_info_file.read_text(encoding="utf-8"))
                version = data.get("dataDirectoryName") or data.get("version")
                build_number = data.get("buildNumber")
            except Exception:
                pass

        if not version:
            build_txt = studio_dir / "build.txt"
            if build_txt.exists():
                version = build_txt.read_text(encoding="utf-8").strip()

        # Find launcher binary
        launcher_bin = None
        for cand in [
            studio_dir / "bin" / "studio64.exe",
            studio_dir / "bin" / "studio.exe",
            studio_dir / "bin" / "studio.sh",
            studio_dir / "MacOS" / "studio",
        ]:
            if cand.exists():
                launcher_bin = cand
                break

        companions = []
        diagnostics = []

        # Companion: JBR (JetBrains Runtime)
        jbr_bin = None
        for jbr_cand in [
            studio_dir / "jbr" / "bin" / ("java.exe" if sys.platform == "win32" else "java"),
            studio_dir / "jre" / "bin" / ("java.exe" if sys.platform == "win32" else "java"),
        ]:
            if jbr_cand.exists():
                jbr_bin = jbr_cand
                break

        if jbr_bin:
            j_res = runner.run_command([str(jbr_bin), "-version"])
            out = f"{j_res.stdout}\n{j_res.stderr}"
            j_ver = None
            if "version" in out.lower():
                for line in out.splitlines():
                    if "version" in line.lower():
                        j_ver = line.strip()
                        break
            companions.append(
                CompanionTool(
                    name="jbr (OpenJDK)",
                    installed=True,
                    version=j_ver,
                    binary_path=str(jbr_bin),
                )
            )
        else:
            companions.append(CompanionTool(name="jbr (OpenJDK)", installed=False))

        return ToolReport(
            id=self.id,
            name=self.name,
            category=self.category,
            installed=True,
            version=version,
            binary_path=str(launcher_bin) if launcher_bin else None,
            home_path=str(studio_dir),
            status=HealthStatus.HEALTHY,
            companions=companions,
            diagnostics=diagnostics,
            metadata={"build_number": build_number},
        )
