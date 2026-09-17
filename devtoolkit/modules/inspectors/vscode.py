"""Visual Studio Code Inspector."""

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


class VSCodeInspector(BaseInspector):
    id = "vscode"
    name = "Visual Studio Code"
    category = "ide"
    categories = ["ide", "editor"]
    description = "Visual Studio Code code editor and CLI integration"

    def inspect(self, runner: SafeRunner) -> ToolReport:
        code_bin = runner.resolve_binary("code") or runner.resolve_binary("code.cmd")
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
