"""Java / JDK Runtime & Development Kit Inspector."""

import re
import shutil
import sys
from pathlib import Path
from typing import List, Optional

from datetime import datetime, timezone
from devtoolkit.core.base import BaseInspector
from devtoolkit.core.inventory import OSInventory
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


class JavaInspector(BaseInspector):
    id = "java"
    name = "Java / JDK"
    category = "runtime"
    categories = ["runtime", "mobile", "sdk"]
    description = "Java Virtual Machine (JVM), Java Compiler (javac), and JAVA_HOME environment"

    def inspect(self, runner: SafeRunner) -> ToolReport:
        java_home_env = runner.read_env("JAVA_HOME")
        discovered_home = runner.discovery.discover_java_home()

        extra_bin_dirs = []
        if discovered_home:
            extra_bin_dirs.append(str(discovered_home / "bin"))

        system_java = shutil.which("java")
        resolved_java = runner.resolve_binary("java", extra_paths=extra_bin_dirs)

        if not resolved_java and not discovered_home:
            return ToolReport(
                id=self.id,
                name=self.name,
                category=self.category,
                categories=self.categories,
                installed=False,
                status=HealthStatus.NOT_FOUND,
            )

        res = runner.run_command([str(resolved_java), "-version"])
        output = f"{res.stdout}\n{res.stderr}".strip()
        version = None
        m = re.search(r'(?:openjdk|java)?\s*version\s*["\']?([0-9._]+)["\']?', output, re.IGNORECASE)
        if m:
            version = m.group(1)
        elif output:
            version = output.splitlines()[0]

        companions = []
        diagnostics = []

        # Check javac (Java Development Kit compiler)
        system_javac = shutil.which("javac")
        javac_bin = runner.resolve_binary("javac", extra_paths=extra_bin_dirs)
        if javac_bin:
            javac_res = runner.run_command([str(javac_bin), "-version"])
            j_out = f"{javac_res.stdout}\n{javac_res.stderr}".strip()
            j_m = re.search(r"javac\s+([0-9._]+)", j_out)
            companions.append(
                CompanionTool(
                    name="javac (JDK)",
                    installed=True,
                    version=j_m.group(1) if j_m else None,
                    binary_path=str(javac_bin),
                )
            )
        else:
            companions.append(CompanionTool(name="javac (JDK)", installed=False))
            diagnostics.append(
                DiagnosticIssue(
                    level=DiagnosticLevel.INFO,
                    message="javac compiler not found. You have a JRE installed, but not a full JDK.",
                    suggested_fix='winget install EclipseAdoptium.Temurin.21.JDK',
                )
            )

        # Health Diagnostics
        is_healthy = True

        if not java_home_env:
            is_healthy = False
            origin = "Android Studio JBR" if (discovered_home and "android_studio" in str(discovered_home).lower()) else "installed runtime"
            target_fix = f'setx JAVA_HOME "{discovered_home}" /M' if discovered_home else 'setx JAVA_HOME "C:\\Program Files\\Eclipse Adoptium\\jdk-21" /M'
            diagnostics.append(
                DiagnosticIssue(
                    level=DiagnosticLevel.WARNING,
                    message=f"JAVA_HOME is not defined in system environment (detected Java in {origin} at '{discovered_home}').",
                    suggested_fix=target_fix,
                )
            )
        elif not Path(java_home_env).exists():
            is_healthy = False
            diagnostics.append(
                DiagnosticIssue(
                    level=DiagnosticLevel.ERROR,
                    message=f"JAVA_HOME is set to '{java_home_env}', but this path does not exist on disk.",
                    suggested_fix=f'setx JAVA_HOME "{discovered_home}" /M' if discovered_home else 'setx JAVA_HOME "C:\\Program Files\\Eclipse Adoptium\\jdk-21" /M',
                )
            )

        if resolved_java and not system_java:
            is_healthy = False
            diagnostics.append(
                DiagnosticIssue(
                    level=DiagnosticLevel.WARNING,
                    message=f"Java executable was found at '{resolved_java}', but is not in system PATH.",
                    suggested_fix=f'setx PATH "%PATH%;{resolved_java.parent}"',
                )
            )

        status = HealthStatus.HEALTHY if is_healthy else HealthStatus.WARNING

        return ToolReport(
            id=self.id,
            name=self.name,
            category=self.category,
            categories=self.categories,
            installed=True,
            version=version,
            binary_path=str(resolved_java) if resolved_java else None,
            home_path=str(discovered_home) if discovered_home else (str(resolved_java.parent.parent) if resolved_java else None),
            status=status,
            companions=companions,
            diagnostics=diagnostics,
            metadata={"JAVA_HOME": java_home_env},
        )

    def deep_inspect(self, runner: SafeRunner, base_report: Optional[ToolReport] = None) -> DeepTelemetryReport:
        base_rep = base_report if base_report is not None else self.inspect(runner)
        trace: list[str] = [f"Base inspection complete. installed={base_rep.installed}"]
        instances: list[DiscoveredInstance] = []
        seen_paths: set[str] = set()

        def _add_inst(p: Path, bin_p: Path | None, ver: str | None, src: str, active: bool, details: str | None = None):
            key = str(bin_p or p).lower() if sys.platform == "win32" else str(bin_p or p)
            if key not in seen_paths:
                seen_paths.add(key)
                instances.append(
                    DiscoveredInstance(
                        path=str(p),
                        binary_path=str(bin_p) if bin_p else None,
                        version=ver,
                        source=src,
                        is_active=active,
                        details=details,
                    )
                )

        # 1. System PATH binaries
        path_bins = runner.resolve_all_binaries("java")
        trace.append(f"Found {len(path_bins)} 'java' binary candidates in system PATH")
        for idx, pb in enumerate(path_bins):
            is_act = (idx == 0) and bool(base_rep.binary_path) and (str(pb).lower() == str(base_rep.binary_path).lower())
            ver = base_rep.version if is_act else None
            _add_inst(pb.parent.parent, pb, ver, "PATH", is_act, "Active binary in system PATH" if is_act else "Alternate binary in PATH")

        # 2. JAVA_HOME instance
        java_home_val = runner.read_env("JAVA_HOME")
        if java_home_val and Path(java_home_val).exists():
            jh_path = Path(java_home_val)
            jh_bin = jh_path / "bin" / ("java.exe" if sys.platform == "win32" else "java")
            b_target = jh_bin if jh_bin.exists() else None
            is_act = bool(base_rep.binary_path and b_target and str(b_target).lower() == str(base_rep.binary_path).lower())
            _add_inst(jh_path, b_target, None, "Environment", is_act, "JAVA_HOME Installation Root")

        # 3. Dynamic Registry JDK query
        for q in ["JDK", "Eclipse Adoptium", "Amazon Corretto", "Zulu", "Java SE Development Kit"]:
            reg_roots = OSInventory.find_app_locations(q)
            for rp in reg_roots:
                r_bin = rp / "bin" / ("java.exe" if sys.platform == "win32" else "java")
                b_target = r_bin if r_bin.exists() else None
                is_act = bool(base_rep.binary_path and b_target and str(b_target).lower() == str(base_rep.binary_path).lower())
                _add_inst(rp, b_target, None, "Registry", is_act, f"Registry installed JDK ({q})")

        # 4. Bundled Android Studio JBR
        studio_dir = runner.discovery.discover_android_studio()
        if studio_dir:
            for sub in ["jbr", "jre"]:
                cand = studio_dir / sub
                cand_bin = cand / "bin" / ("java.exe" if sys.platform == "win32" else "java")
                if cand_bin.exists():
                    is_act = bool(base_rep.binary_path and str(cand_bin).lower() == str(base_rep.binary_path).lower())
                    _add_inst(cand, cand_bin, None, "IDE_Config", is_act, "Embedded JetBrains Runtime inside Android Studio")

        # 5. Discovery Pipeline (4-Layer & FastSearchEngine)
        for sp in runner.discovery.discover_all_tool_instances(self.id):
            sp_bin = sp / "bin" / ("java.exe" if sys.platform == "win32" else "java")
            b_target = sp_bin if sp_bin.exists() else None
            is_act = bool(base_rep.binary_path and b_target and str(b_target).lower() == str(base_rep.binary_path).lower())
            _add_inst(sp, b_target, None, "Discovery Pipeline", is_act, "Discovered JDK root (Layer 2-4)")

        # 6. Monitored Environment Variables Alignment
        env_vars: list[EnvVarStatus] = []
        active_bin = base_rep.binary_path

        if java_home_val:
            jh_exists = Path(java_home_val).exists()
            if not jh_exists:
                env_vars.append(
                    EnvVarStatus(
                        name="JAVA_HOME",
                        value=java_home_val,
                        status="missing",
                        target_path=java_home_val,
                        message="Configured directory does not exist on disk!",
                    )
                )
            else:
                jh_bin = Path(java_home_val) / "bin" / ("java.exe" if sys.platform == "win32" else "java")
                is_aligned = active_bin and jh_bin.exists() and (str(jh_bin.resolve()).lower() == str(Path(active_bin).resolve()).lower())
                env_vars.append(
                    EnvVarStatus(
                        name="JAVA_HOME",
                        value=java_home_val,
                        status="aligned" if is_aligned else "divergent",
                        target_path=str(Path(active_bin).parent.parent) if active_bin else java_home_val,
                        message="Aligned with active java executable" if is_aligned else f"Diverges! Points to a different JDK than active binary in PATH",
                    )
                )
        else:
            env_vars.append(
                EnvVarStatus(
                    name="JAVA_HOME",
                    value=None,
                    status="divergent" if base_rep.installed else "missing",
                    target_path=base_rep.home_path,
                    message="JAVA_HOME is not configured in system environment!",
                )
            )

        # 7. Deep Domain Telemetry & Raw Dumps
        telemetry: dict[str, Any] = {
            "has_jdk": any(c.installed for c in base_rep.companions if "javac" in c.name),
        }

        raw_dumps: dict[str, str] = {}
        if base_rep.binary_path:
            # java -version
            j_res = runner.run_command([base_rep.binary_path, "-version"], timeout=2.5)
            j_out = f"{j_res.stdout}\n{j_res.stderr}".strip()
            raw_dumps["java -version"] = j_out

            # Infer vendor
            if "temurin" in j_out.lower():
                telemetry["jvm_vendor"] = "Eclipse Adoptium (Temurin)"
            elif "corretto" in j_out.lower():
                telemetry["jvm_vendor"] = "Amazon Corretto"
            elif "zulu" in j_out.lower():
                telemetry["jvm_vendor"] = "Azul Zulu"
            elif "microsoft" in j_out.lower():
                telemetry["jvm_vendor"] = "Microsoft OpenJDK"
            elif "oracle" in j_out.lower():
                telemetry["jvm_vendor"] = "Oracle HotSpot"
            else:
                telemetry["jvm_vendor"] = "OpenJDK Community"

            # Check bytecode target from release file
            if base_rep.home_path:
                rel_file = Path(base_rep.home_path) / "release"
                if rel_file.is_file():
                    try:
                        content = rel_file.read_text(encoding="utf-8", errors="ignore")
                        raw_dumps["release file"] = content
                        for line in content.splitlines():
                            if line.startswith("JAVA_VERSION="):
                                telemetry["release_java_version"] = line.split("=")[-1].strip('"')
                            elif line.startswith("OS_ARCH="):
                                telemetry["bytecode_arch"] = line.split("=")[-1].strip('"')
                    except Exception:
                        pass

            # java -XshowSettings:properties -version
            prop_res = runner.run_command([base_rep.binary_path, "-XshowSettings:properties", "-version"], timeout=3.0)
            prop_out = f"{prop_res.stdout}\n{prop_res.stderr}".strip()
            if prop_out:
                raw_dumps["java -XshowSettings:properties"] = prop_out

        return DeepTelemetryReport(
            tool_id=self.id,
            timestamp=datetime.now(timezone.utc).isoformat(),
            probe_latency_ms=0,
            instances=instances,
            env_vars=env_vars,
            telemetry=telemetry,
            raw_dumps=raw_dumps,
            discovery_trace=trace,
        )
