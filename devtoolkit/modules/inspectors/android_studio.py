"""Android Studio IDE & Environment Inspector."""

import json
import os
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

    def deep_inspect(self, runner: SafeRunner, base_report: Optional[ToolReport] = None) -> DeepTelemetryReport:
        if base_report is None:
            base_report = self.inspect(runner)
        from datetime import datetime
        raw_dumps = {}
        trace = ["Starting Android Studio deep inspection probe"]
        instances: List[DiscoveredInstance] = []
        env_vars: List[EnvVarStatus] = []
        detailed_diag: List[DiagnosticIssue] = list(base_report.diagnostics)
        remediations: List[str] = []

        seen_roots = set()

        # Primary resolved instance
        if base_report.home_path:
            p_root = Path(base_report.home_path)
            seen_roots.add(str(p_root).lower())
            instances.append(
                DiscoveredInstance(
                    path=str(p_root),
                    binary_path=base_report.binary_path,
                    version=base_report.version,
                    source="Active Discovery",
                    is_active=True,
                    details=f"Primary Studio root ({base_report.metadata.get('build_number') or 'installed'})",
                )
            )

        # Check standard alternative locations
        alt_candidates = []
        if sys.platform == "win32":
            prog_files = os.environ.get("ProgramFiles", "C:\\Program Files")
            local_app = os.environ.get("LOCALAPPDATA")
            alt_candidates.append(Path(prog_files) / "Android" / "Android Studio")
            alt_candidates.append(Path(prog_files) / "Android" / "Android Studio Preview")
            if local_app:
                alt_candidates.append(Path(local_app) / "Programs" / "Android Studio")
                # JetBrains Toolbox installs
                tb_path = Path(local_app) / "JetBrains" / "Toolbox" / "apps" / "AndroidStudio" / "ch-0"
                if tb_path.is_dir():
                    for ch in tb_path.iterdir():
                        if ch.is_dir():
                            alt_candidates.append(ch)

        for cand_root in alt_candidates:
            if cand_root.is_dir() and str(cand_root).lower() not in seen_roots:
                # verify it has product-info.json or bin/studio64.exe
                launcher = cand_root / "bin" / ("studio64.exe" if sys.platform == "win32" else "studio.sh")
                if launcher.is_file() or (cand_root / "product-info.json").is_file():
                    seen_roots.add(str(cand_root).lower())
                    v_alt = None
                    p_info = cand_root / "product-info.json"
                    if p_info.is_file():
                        try:
                            d = json.loads(p_info.read_text(encoding="utf-8", errors="ignore"))
                            v_alt = d.get("dataDirectoryName") or d.get("version")
                        except Exception:
                            pass
                    instances.append(
                        DiscoveredInstance(
                            path=str(cand_root),
                            binary_path=str(launcher) if launcher.is_file() else None,
                            version=v_alt,
                            source="Filesystem Candidate",
                            is_active=False,
                            details="Alternate Android Studio installation directory",
                        )
                    )

        trace.append(f"Discovered {len(instances)} Android Studio installations")

        # 2. Environment Variables Alignment
        studio_jdk = runner.read_env("STUDIO_JDK")
        env_vars.append(
            EnvVarStatus(
                name="STUDIO_JDK",
                value=studio_jdk,
                status="aligned" if studio_jdk else "missing",
                target_path=str(Path(base_report.home_path) / "jbr") if base_report.home_path else None,
                message="Points to custom JVM runtime for Studio" if studio_jdk else "Unset (Studio uses bundled JBR runtime)",
            )
        )

        studio_vm = runner.read_env("STUDIO_VM_OPTIONS")
        env_vars.append(
            EnvVarStatus(
                name="STUDIO_VM_OPTIONS",
                value=studio_vm,
                status="aligned" if studio_vm else "missing",
                target_path=None,
                message="Points to custom VM options file" if studio_vm else "Unset (Studio uses default heap & GC options)",
            )
        )

        # 3. CLI / File Telemetry Dumps
        if base_report.home_path:
            p_root = Path(base_report.home_path)
            prod_info = p_root / "product-info.json"
            if prod_info.is_file():
                try:
                    raw_dumps["product-info.json"] = prod_info.read_text(encoding="utf-8", errors="ignore")
                except Exception as e:
                    raw_dumps["product-info.json"] = f"Error reading file: {e}"

            # Check for bundled JBR
            jbr_java = p_root / "jbr" / "bin" / ("java.exe" if sys.platform == "win32" else "java")
            if jbr_java.is_file():
                res_jbr = runner.run_command([str(jbr_java), "-version"])
                raw_dumps["Bundled JBR (-version)"] = f"{res_jbr.stdout}\n{res_jbr.stderr}".strip()

        # Studio XML config check
        appdata = os.environ.get("APPDATA")
        if appdata:
            g_dir = Path(appdata) / "Google"
            if g_dir.is_dir():
                for s_dir in g_dir.glob("AndroidStudio*"):
                    sdk_xml = s_dir / "options" / "android.sdk.path.xml"
                    if sdk_xml.is_file():
                        try:
                            raw_dumps[f"{s_dir.name} - android.sdk.path.xml"] = sdk_xml.read_text(encoding="utf-8", errors="ignore")
                        except Exception:
                            pass

        trace.append("Completed Android Studio deep telemetry probes")

        return DeepTelemetryReport(
            tool_id=self.id,
            timestamp=datetime.now().isoformat(),
            probe_latency_ms=0,
            instances=instances,
            env_vars=env_vars,
            telemetry={
                "build_number": base_report.metadata.get("build_number"),
                "home_path": base_report.home_path,
            },
            raw_dumps=raw_dumps,
            detailed_diagnostics=detailed_diag,
            remediation_commands=remediations,
            discovery_trace=trace,
        )

