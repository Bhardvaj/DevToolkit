"""GitHub CLI Inspector."""

import re
from pathlib import Path
from typing import List

from devtoolkit.core.base import BaseInspector
from devtoolkit.core.models import (
    CompanionTool,
    DiagnosticIssue,
    DiagnosticLevel,
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
        gh_bin = runner.resolve_binary("gh")
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
