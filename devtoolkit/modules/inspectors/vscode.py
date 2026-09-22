"""Visual Studio Code Inspector."""

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


class VSCodeInspector(BaseInspector):
    id = "vscode"
    name = "Visual Studio Code"
    category = "ide"
    categories = ["ide", "editor"]
    description = "Visual Studio Code code editor and CLI integration"

    def inspect(self, runner: SafeRunner) -> ToolReport:
        code_bin = runner.resolve_binary("code", tool_id=self.id) or runner.resolve_binary("code.cmd", tool_id=self.id)
        app_exe = None
        code_dir = None

        # If not directly resolved on PATH, check standard installation paths
        if not code_bin:
            candidates: List[Path] = []
            if sys.platform == "win32":
                local_app = os.environ.get("LOCALAPPDATA")
                prog_files = os.environ.get("ProgramFiles")
                prog_files_x86 = os.environ.get("ProgramFiles(x86)")
                if local_app:
                    candidates.append(Path(local_app) / "Programs" / "Microsoft VS Code")
                if prog_files:
                    candidates.append(Path(prog_files) / "Microsoft VS Code")
                if prog_files_x86:
                    candidates.append(Path(prog_files_x86) / "Microsoft VS Code")
            elif sys.platform == "darwin":
                candidates.append(Path("/Applications/Visual Studio Code.app/Contents/Resources/app"))
            else:
                candidates.append(Path("/usr/share/code"))

            for cand in candidates:
                if (cand / "Code.exe").is_file():
                    app_exe = cand / "Code.exe"
                    code_dir = cand
                    cmd = cand / "bin" / "code.cmd"
                    if cmd.is_file():
                        code_bin = cmd
                    break
                elif (cand / "bin" / "code").is_file():
                    app_exe = cand / "bin" / "code"
                    code_dir = cand
                    code_bin = app_exe
                    break

        if not code_bin and not app_exe:
            return ToolReport(
                id=self.id,
                name=self.name,
                category=self.category,
                categories=self.categories,
                installed=False,
                status=HealthStatus.NOT_FOUND,
            )

        # Probe version using code CLI or reading product.json
        version = None
        probe_bin = code_bin or app_exe
        if probe_bin:
            res = runner.run_command([str(probe_bin), "--version"])
            if res.ok and res.stdout.strip():
                version = res.stdout.strip().splitlines()[0].strip()

        if not version and code_dir:
            prod_json = code_dir / "resources" / "app" / "product.json"
            if prod_json.is_file():
                try:
                    import json
                    data = json.loads(prod_json.read_text(encoding="utf-8", errors="ignore"))
                    version = data.get("version")
                except Exception:
                    pass

        # Companions: Check VS Code Insiders
        companions: List[CompanionTool] = []
        insiders_bin = runner.resolve_binary("code-insiders") or runner.resolve_binary("code-insiders.cmd")
        if insiders_bin:
            res_ins = runner.run_command([str(insiders_bin), "--version"])
            ins_ver = res_ins.stdout.strip().splitlines()[0] if res_ins.ok and res_ins.stdout.strip() else None
            companions.append(CompanionTool(name="code-insiders", installed=True, version=ins_ver, binary_path=str(insiders_bin)))
        else:
            companions.append(CompanionTool(name="code-insiders", installed=False))

        diagnostics: List[DiagnosticIssue] = []
        # Check if code CLI is missing from PATH
        is_on_path = runner.resolve_binary("code") is not None or runner.resolve_binary("code.cmd") is not None
        if not is_on_path and code_dir:
            bin_path = code_dir / "bin"
            diagnostics.append(
                DiagnosticIssue(
                    level=DiagnosticLevel.WARNING,
                    message="VS Code desktop application is installed, but 'code' command is not in system PATH.",
                    suggested_fix=f'Add "{bin_path}" to your PATH environment variable.',
                )
            )

        status = HealthStatus.HEALTHY if is_on_path else HealthStatus.WARNING

        home_dir = str(code_dir) if code_dir else (str(code_bin.parent.parent) if code_bin and code_bin.parent.name == "bin" else str(code_bin.parent if code_bin else ""))
        final_bin = str(code_bin) if code_bin else (str(app_exe) if app_exe else None)

        return ToolReport(
            id=self.id,
            name=self.name,
            category=self.category,
            categories=self.categories,
            installed=True,
            version=version,
            binary_path=final_bin,
            home_path=home_dir,
            status=status,
            companions=companions,
            diagnostics=diagnostics,
            metadata={"cli_in_path": is_on_path},
        )

    def deep_inspect(self, runner: SafeRunner, base_report: Optional[ToolReport] = None) -> DeepTelemetryReport:
        if base_report is None:
            base_report = self.inspect(runner)
        from datetime import datetime
        raw_dumps = {}
        trace = ["Starting Visual Studio Code deep inspection probe"]
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
                    path=base_report.home_path or str(p_bin.parent),
                    binary_path=str(p_bin),
                    version=base_report.version,
                    source="Active PATH / App",
                    is_active=True,
                    details="Active VS Code executable or CLI launcher",
                )
            )

        # Multi-instance discovery across PATH
        for bin_name in ["code", "code.cmd", "code-insiders", "code-insiders.cmd"]:
            for c_bin in runner.resolve_all_binaries(bin_name):
                if str(c_bin).lower() not in seen_bins:
                    seen_bins.add(str(c_bin).lower())
                    is_act = bool(base_report.binary_path and str(c_bin).lower() == str(base_report.binary_path).lower())
                    ver_str = None
                    res_v = runner.run_command([str(c_bin), "--version"], timeout=2.0)
                    if res_v.ok and res_v.stdout.strip():
                        ver_str = res_v.stdout.strip().splitlines()[0].strip()
                    instances.append(
                        DiscoveredInstance(
                            path=str(c_bin.parent),
                            binary_path=str(c_bin),
                            version=ver_str,
                            source="PATH",
                            is_active=is_act,
                            details=f"Discovered CLI launcher in PATH ({bin_name})",
                        )
                    )

        # Check standard desktop installation locations
        if sys.platform == "win32":
            local_app = os.environ.get("LOCALAPPDATA")
            prog_files = os.environ.get("ProgramFiles", "C:\\Program Files")
            prog_files_x86 = os.environ.get("ProgramFiles(x86)", "C:\\Program Files (x86)")

            win_candidates = [
                (Path(local_app) / "Programs" / "Microsoft VS Code" / "Code.exe") if local_app else None,
                Path(prog_files) / "Microsoft VS Code" / "Code.exe",
                Path(prog_files_x86) / "Microsoft VS Code" / "Code.exe",
                (Path(local_app) / "Programs" / "Microsoft VS Code Insiders" / "Code - Insiders.exe") if local_app else None,
            ]
            for cand in win_candidates:
                if cand and cand.is_file() and str(cand).lower() not in seen_bins:
                    seen_bins.add(str(cand).lower())
                    instances.append(
                        DiscoveredInstance(
                            path=str(cand.parent),
                            binary_path=str(cand),
                            version=base_report.version,
                            source="Desktop Installation",
                            is_active=False,
                            details="Installed desktop application executable",
                        )
                    )

        # Discovery Pipeline instances (Layer 2-4 Discovery)
        for disc_p in runner.discovery.discover_all_tool_instances(self.id):
            cand_bin = None
            for b_name in ["Code.exe", "code.cmd", "Code - Insiders.exe", "code-insiders.cmd", "VSCodium.exe", "codium.cmd", "code"]:
                for sub in [disc_p / b_name, disc_p / "bin" / b_name]:
                    if sub.is_file():
                        cand_bin = sub
                        break
                if cand_bin:
                    break
            k = str(cand_bin or disc_p).lower()
            if k not in seen_bins:
                seen_bins.add(k)
                instances.append(
                    DiscoveredInstance(
                        path=str(disc_p),
                        binary_path=str(cand_bin) if cand_bin else None,
                        version=None,
                        source="Discovery Pipeline",
                        is_active=bool(base_report.binary_path and cand_bin and str(cand_bin).lower() == str(base_report.binary_path).lower()),
                        details="Discovered VS Code installation (Layer 2-4)",
                    )
                )

        trace.append(f"Discovered {len(instances)} VS Code installations")

        # 2. Environment Variables Alignment
        portable = runner.read_env("VSCODE_PORTABLE")
        env_vars.append(
            EnvVarStatus(
                name="VSCODE_PORTABLE",
                value=portable,
                status="aligned" if portable else "missing",
                target_path=None,
                message="Points to portable data directory" if portable else "Unset (standard user profile directory used)",
            )
        )

        git_askpass = runner.read_env("VSCODE_GIT_ASKPASS_NODE")
        env_vars.append(
            EnvVarStatus(
                name="VSCODE_GIT_ASKPASS_NODE",
                value=git_askpass,
                status="aligned" if git_askpass else "missing",
                target_path=None,
                message="Internal VS Code Git credential helper integration active" if git_askpass else "Unset (outside active VS Code terminal)",
            )
        )

        # 3. CLI Telemetry Dumps
        c_exec = None
        # Prefer a CLI launcher (.cmd or code without .exe GUI window)
        for inst in instances:
            if inst.binary_path and ("code.cmd" in inst.binary_path.lower() or inst.binary_path.lower().endswith("bin\\code")):
                c_exec = inst.binary_path
                break
        if not c_exec:
            c_exec = base_report.binary_path

        if c_exec:
            res_ver = runner.run_command([c_exec, "--version"], timeout=2.5)
            if res_ver.ok and res_ver.stdout:
                raw_dumps["code --version"] = res_ver.stdout.strip()

            res_ext = runner.run_command([c_exec, "--list-extensions", "--show-versions"], timeout=3.5)
            if res_ext.ok and res_ext.stdout:
                ext_lines = res_ext.stdout.strip().splitlines()
                raw_dumps[f"Installed Extensions ({len(ext_lines)})"] = "\n".join(ext_lines[:50])
                if len(ext_lines) > 50:
                    raw_dumps[f"Installed Extensions ({len(ext_lines)})"] += f"\n... and {len(ext_lines) - 50} more"

            res_status = runner.run_command([c_exec, "--status"], timeout=2.5)
            if res_status.ok and res_status.stdout:
                raw_dumps["code --status"] = res_status.stdout.strip()

        # Remediations
        if not base_report.metadata.get("cli_in_path"):
            for inst in instances:
                if inst.binary_path and "code.exe" in inst.binary_path.lower():
                    bin_dir = Path(inst.binary_path).parent / "bin"
                    remediations.append(f'Add "{bin_dir}" to your system PATH variable.')
                    break

        trace.append("Completed VS Code deep telemetry probes")

        return DeepTelemetryReport(
            tool_id=self.id,
            timestamp=datetime.now().isoformat(),
            probe_latency_ms=0,
            instances=instances,
            env_vars=env_vars,
            telemetry={
                "cli_in_path": base_report.metadata.get("cli_in_path", False),
                "home_path": base_report.home_path,
            },
            raw_dumps=raw_dumps,
            detailed_diagnostics=detailed_diag,
            remediation_commands=remediations,
            discovery_trace=trace,
        )

