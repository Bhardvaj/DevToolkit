"""GitHub CLI Inspector."""

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


class GitHubCLIInspector(BaseInspector):
    id = "gh"
    name = "GitHub CLI"
    category = "vcs"
    categories = ["vcs", "cli", "tools"]
    description = "Official GitHub command line tool, extensions, and authentication"

    def inspect(self, runner: SafeRunner) -> ToolReport:
        gh_bin = runner.resolve_binary("gh", tool_id=self.id)
        if not gh_bin:
            return ToolReport(
                id=self.id,
                name=self.name,
                category=self.category,
                categories=self.categories,
                installed=False,
                status=HealthStatus.NOT_FOUND,
            )

        # Version probe: `gh --version`
        res = runner.run_command([str(gh_bin), "--version"])
        version = None
        if res.ok and res.stdout.strip():
            # e.g. "gh version 2.65.0 (2025-01-08)"
            m = re.search(r"gh version\s+([\d\.]+)", res.stdout)
            version = m.group(1) if m else res.stdout.splitlines()[0].strip()

        # Check authentication status: `gh auth status`
        auth_res = runner.run_command([str(gh_bin), "auth", "status"])
        is_authenticated = auth_res.ok
        account_name = None

        # gh outputs auth info to stderr or stdout
        auth_text = (auth_res.stdout + " " + auth_res.stderr).strip()
        acc_match = re.search(r"account\s+([A-Za-z0-9_\-]+)", auth_text, re.IGNORECASE)
        if acc_match:
            account_name = acc_match.group(1)

        companions: List[CompanionTool] = []

        # Companion: Git
        git_bin = runner.resolve_binary("git")
        companions.append(
            CompanionTool(
                name="git",
                installed=git_bin is not None,
                binary_path=str(git_bin) if git_bin else None,
            )
        )

        # Companion: GitHub Auth Session
        companions.append(
            CompanionTool(
                name="auth",
                installed=is_authenticated,
                version=f"@{account_name}" if account_name else ("Active" if is_authenticated else "Unauthenticated"),
            )
        )

        diagnostics: List[DiagnosticIssue] = []
        if not is_authenticated:
            diagnostics.append(
                DiagnosticIssue(
                    level=DiagnosticLevel.INFO,
                    message="GitHub CLI is not logged in. Connect your GitHub account to enable repo and PR management.",
                    suggested_fix="gh auth login",
                )
            )

        return ToolReport(
            id=self.id,
            name=self.name,
            category=self.category,
            categories=self.categories,
            installed=True,
            version=version,
            binary_path=str(gh_bin),
            home_path=str(gh_bin.parent),
            status=HealthStatus.HEALTHY,
            companions=companions,
            diagnostics=diagnostics,
            metadata={"authenticated": is_authenticated, "account": account_name},
        )

    def deep_inspect(self, runner: SafeRunner, base_report: Optional[ToolReport] = None) -> DeepTelemetryReport:
        if base_report is None:
            base_report = self.inspect(runner)
        from datetime import datetime
        raw_dumps = {}
        trace = ["Starting GitHub CLI deep inspection probe"]
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
                    path=str(p_bin.parent),
                    binary_path=str(p_bin),
                    version=base_report.version,
                    source="Active PATH",
                    is_active=True,
                    details=f"Active GitHub CLI ({base_report.metadata.get('account') or 'logged out'})",
                )
            )

        # Multi-instance discovery across PATH
        for g_bin in runner.resolve_all_binaries("gh"):
            if str(g_bin).lower() not in seen_bins:
                seen_bins.add(str(g_bin).lower())
                is_act = bool(base_report.binary_path and str(g_bin).lower() == str(base_report.binary_path).lower())
                ver_str = None
                res_v = runner.run_command([str(g_bin), "--version"], timeout=2.0)
                if res_v.ok and res_v.stdout:
                    m = re.search(r"gh version\s+([\d\.]+)", res_v.stdout)
                    ver_str = m.group(1) if m else None
                instances.append(
                    DiscoveredInstance(
                        path=str(g_bin.parent),
                        binary_path=str(g_bin),
                        version=ver_str,
                        source="Alternate PATH",
                        is_active=is_act,
                        details="Alternate gh CLI executable in PATH",
                    )
                )

        # Discovery Pipeline instances (Layer 2-4 Discovery)
        for disc_p in runner.discovery.discover_all_tool_instances(self.id):
            cand_bin = disc_p / "bin" / ("gh.exe" if sys.platform == "win32" else "gh")
            if not cand_bin.is_file():
                cand_bin = disc_p / ("gh.exe" if sys.platform == "win32" else "gh")
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
                        details="Discovered GitHub CLI (Layer 2-4)",
                    )
                )

        trace.append(f"Discovered {len(instances)} gh CLI instances")

        # 2. Environment Variables Alignment
        gh_tok = runner.read_env("GH_TOKEN") or runner.read_env("GITHUB_TOKEN")
        env_vars.append(
            EnvVarStatus(
                name="GH_TOKEN",
                value="[REDACTED]" if gh_tok else None,
                status="aligned" if gh_tok else "missing",
                target_path=None,
                message="Active auth token configured via environment" if gh_tok else "Unset (authentication uses system credential helper)",
            )
        )

        gh_cfg = runner.read_env("GH_CONFIG_DIR")
        env_vars.append(
            EnvVarStatus(
                name="GH_CONFIG_DIR",
                value=gh_cfg,
                status="aligned" if gh_cfg else "missing",
                target_path=gh_cfg,
                message="Custom configuration directory" if gh_cfg else "Default (%APPDATA%/GitHub CLI or ~/.config/gh)",
            )
        )

        gh_host = runner.read_env("GH_HOST")
        env_vars.append(
            EnvVarStatus(
                name="GH_HOST",
                value=gh_host,
                status="aligned" if gh_host else "missing",
                target_path=None,
                message=f"Configured enterprise host: {gh_host}" if gh_host else "Default (github.com)",
            )
        )

        # 3. CLI Telemetry Dumps
        gh_exec = base_report.binary_path or "gh"
        res_ver = runner.run_command([gh_exec, "--version"], timeout=2.5)
        if res_ver.ok and res_ver.stdout:
            raw_dumps["gh --version"] = res_ver.stdout.strip()

        res_auth = runner.run_command([gh_exec, "auth", "status"], timeout=3.0)
        out_auth = f"{res_auth.stdout}\n{res_auth.stderr}".strip()
        if out_auth:
            raw_dumps["gh auth status"] = out_auth

        res_ext = runner.run_command([gh_exec, "extension", "list"], timeout=2.5)
        if res_ext.ok and res_ext.stdout:
            raw_dumps["gh extension list"] = res_ext.stdout.strip()

        res_cfg_list = runner.run_command([gh_exec, "config", "list"], timeout=2.0)
        if res_cfg_list.ok and res_cfg_list.stdout:
            raw_dumps["gh config list"] = res_cfg_list.stdout.strip()

        if not base_report.metadata.get("authenticated"):
            remediations.append("gh auth login")
        remediations.append("gh auth setup-git")

        trace.append("Completed GitHub CLI deep telemetry probes")

        return DeepTelemetryReport(
            tool_id=self.id,
            timestamp=datetime.now().isoformat(),
            probe_latency_ms=0,
            instances=instances,
            env_vars=env_vars,
            telemetry={
                "authenticated": base_report.metadata.get("authenticated", False),
                "account": base_report.metadata.get("account"),
                "home_path": base_report.home_path,
            },
            raw_dumps=raw_dumps,
            detailed_diagnostics=detailed_diag,
            remediation_commands=remediations,
            discovery_trace=trace,
        )

