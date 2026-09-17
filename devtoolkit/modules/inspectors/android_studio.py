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
    categories = ["ide", "mobile"]
    description = "Android Studio IDE, JetBrains Runtime (JBR), and mobile tooling"

    def inspect(self, runner: SafeRunner) -> ToolReport:
        studio_dir = runner.discovery.discover_android_studio()
        if not studio_dir:
            return ToolReport(
                id=self.id,
                name=self.name,
                category=self.category,
                categories=self.categories,
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
            categories=self.categories,
            installed=True,
            version=version,
            binary_path=str(launcher_bin) if launcher_bin else None,
            home_path=str(studio_dir),
            status=HealthStatus.HEALTHY,
            companions=companions,
            diagnostics=diagnostics,
            metadata={"build_number": build_number},
        )
