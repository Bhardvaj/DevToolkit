import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

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


class GitInspector(BaseInspector):
    id = "git"
    name = "Git"
    category = "vcs"
    categories = ["vcs", "tool"]
    description = "Git distributed version control system and GitHub CLI"

    def inspect(self, runner: SafeRunner) -> ToolReport:
        git_bin = runner.resolve_binary("git")
        if not git_bin:
            return ToolReport(
                id=self.id,
                name=self.name,
                category=self.category,
                categories=self.categories,
                installed=False,
                status=HealthStatus.NOT_FOUND,
            )

        # Output format: "git version 2.54.0.windows.1"
        res = runner.run_command([str(git_bin), "--version"])
        version = None
        if res.ok and res.stdout:
            m = re.search(r"git version\s+([0-9a-zA-Z.-]+)", res.stdout)
            version = m.group(1) if m else res.stdout

        companions = []
        diagnostics = []

        # Check GitHub CLI (gh)
        gh_bin = runner.resolve_binary("gh")
        if gh_bin:
            gh_res = runner.run_command([str(gh_bin), "--version"])
            gh_ver = None
            if gh_res.ok and gh_res.stdout:
                m = re.search(r"gh version\s+([0-9.]+)", gh_res.stdout)
                gh_ver = m.group(1) if m else None
            companions.append(
                CompanionTool(
                    name="gh",
                    installed=True,
                    version=gh_ver,
                    binary_path=str(gh_bin),
                )
            )
        else:
            companions.append(CompanionTool(name="gh", installed=False))

        # Check global git user config
        user_name_res = runner.run_command([str(git_bin), "config", "--global", "user.name"])
        user_email_res = runner.run_command([str(git_bin), "config", "--global", "user.email"])

        user_name = user_name_res.stdout.strip() if user_name_res.ok else ""
        user_email = user_email_res.stdout.strip() if user_email_res.ok else ""

        if not user_name or not user_email:
            diagnostics.append(
                DiagnosticIssue(
                    level=DiagnosticLevel.WARNING,
                    message="Global Git user identity (user.name / user.email) is not fully configured.",
                    suggested_fix='git config --global user.name "Developer" && git config --global user.email "dev@example.com"',
                )
            )

        status = HealthStatus.HEALTHY if (user_name and user_email) else HealthStatus.WARNING

        return ToolReport(
            id=self.id,
            name=self.name,
            category=self.category,
            categories=self.categories,
            installed=True,
            version=version,
            binary_path=str(git_bin),
            home_path=str(git_bin.parent),
            status=status,
            companions=companions,
            diagnostics=diagnostics,
            metadata={"user.name": user_name, "user.email": user_email},
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
        path_bins = runner.resolve_all_binaries("git")
        trace.append(f"Found {len(path_bins)} 'git' binary candidates in system PATH")
        for idx, pb in enumerate(path_bins):
            is_act = (idx == 0) and bool(base_rep.binary_path) and (str(pb).lower() == str(base_rep.binary_path).lower())
            ver = base_rep.version if is_act else None
            if not ver:
                ver_res = runner.run_command([str(pb), "--version"], timeout=2.0)
                if ver_res.ok and ver_res.stdout:
                    m = re.search(r"git version\s+([0-9a-zA-Z.-]+)", ver_res.stdout)
                    ver = m.group(1) if m else ver_res.stdout.strip()
            det = "Active binary in system PATH" if is_act else "Alternate binary in PATH"
            _add_inst(pb.parent, pb, ver, "PATH", is_act, det)

        # 2. Registry uninstaller entries
        reg_apps = OSInventory.find_app_locations("Git")
        trace.append(f"Found {len(reg_apps)} Git installations in Windows Registry")
        for reg_p in reg_apps:
            reg_bin = reg_p / "cmd" / "git.exe"
            b_target = reg_bin if reg_bin.exists() else None
            is_act = bool(base_rep.binary_path and b_target and str(b_target).lower() == str(base_rep.binary_path).lower())
            _add_inst(reg_p, b_target, None, "Registry", is_act, "Discovered via Windows Registry uninstall inventory")

        # 3. GitHub Desktop embedded Git check
        try:
            gh_desktop_root = Path.home() / "AppData" / "Local" / "GitHubDesktop"
            if gh_desktop_root.exists():
                for cand in gh_desktop_root.glob("app-*/resources/app/git/cmd/git.exe"):
                    if cand.is_file():
                        _add_inst(cand.parent.parent.parent, cand, None, "IDE_Config", False, "Embedded Git inside GitHub Desktop")
        except Exception:
            pass

        # 4. Monitored Environment Variables Alignment
        env_vars: list[EnvVarStatus] = []

        # GIT_SSH
        git_ssh = runner.read_env("GIT_SSH") or runner.read_env("GIT_SSH_COMMAND")
        if git_ssh:
            ssh_exists = Path(git_ssh.split()[0]).exists()
            env_vars.append(
                EnvVarStatus(
                    name="GIT_SSH",
                    value=git_ssh,
                    status="aligned" if ssh_exists else "divergent",
                    target_path=git_ssh,
                    message="Custom SSH client exists" if ssh_exists else "Custom SSH client binary not found!",
                )
            )
        else:
            env_vars.append(
                EnvVarStatus(
                    name="GIT_SSH",
                    value=None,
                    status="aligned",
                    message="Using default bundled OpenSSH",
                )
            )

        # GIT_CONFIG_GLOBAL
        git_cfg_global = runner.read_env("GIT_CONFIG_GLOBAL")
        if git_cfg_global:
            cfg_exists = Path(git_cfg_global).exists()
            env_vars.append(
                EnvVarStatus(
                    name="GIT_CONFIG_GLOBAL",
                    value=git_cfg_global,
                    status="aligned" if cfg_exists else "divergent",
                    target_path=git_cfg_global,
                    message="Custom global config exists" if cfg_exists else "Configured global config file does not exist!",
                )
            )
        else:
            std_cfg = Path.home() / ".gitconfig"
            env_vars.append(
                EnvVarStatus(
                    name="GIT_CONFIG_GLOBAL",
                    value=str(std_cfg) if std_cfg.exists() else None,
                    status="aligned",
                    message=f"Standard config located at ~/{std_cfg.name}" if std_cfg.exists() else "No global ~/.gitconfig created yet",
                )
            )

        # 5. Deep Domain Telemetry & Raw Dumps
        telemetry: dict[str, Any] = {
            "user_name": base_rep.metadata.get("user.name") or "Not configured",
            "user_email": base_rep.metadata.get("user.email") or "Not configured",
        }

        raw_dumps: dict[str, str] = {}
        if base_rep.binary_path:
            # git config -l --show-origin
            cfg_res = runner.run_command([base_rep.binary_path, "config", "-l", "--show-origin"], timeout=3.0)
            if cfg_res.ok and cfg_res.stdout:
                raw_dumps["git config -l --show-origin"] = cfg_res.stdout

            # git version --build-options
            b_res = runner.run_command([base_rep.binary_path, "version", "--build-options"], timeout=2.5)
            if b_res.ok and b_res.stdout:
                raw_dumps["git version --build-options"] = b_res.stdout
                telemetry["build_options"] = b_res.stdout.splitlines()

            # default branch
            def_branch_res = runner.run_command([base_rep.binary_path, "config", "--global", "init.defaultBranch"], timeout=2.0)
            telemetry["default_branch"] = def_branch_res.stdout.strip() if def_branch_res.ok and def_branch_res.stdout else "master (default)"

            # credential helper
            cred_res = runner.run_command([base_rep.binary_path, "config", "--global", "credential.helper"], timeout=2.0)
            telemetry["credential_helper"] = cred_res.stdout.strip() if cred_res.ok and cred_res.stdout else "manager (default)"

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
