"""Git & GitHub CLI Version Control Inspector."""

import re
from pathlib import Path
from devtoolkit.core.base import BaseInspector
from devtoolkit.core.models import (
    CompanionTool,
    DiagnosticIssue,
    DiagnosticLevel,
    HealthStatus,
    ToolReport,
)
from devtoolkit.core.runner import SafeRunner


class GitInspector(BaseInspector):
    id = "git"
    name = "Git"
    category = "vcs"
    description = "Git distributed version control system and GitHub CLI"

    def inspect(self, runner: SafeRunner) -> ToolReport:
        git_bin = runner.resolve_binary("git")
        if not git_bin:
            return ToolReport(
                id=self.id,
                name=self.name,
                category=self.category,
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
                    suggested_fix="Run 'git config --global user.name \"Your Name\"' and 'git config --global user.email \"email@example.com\"'.",
                )
            )

        status = HealthStatus.HEALTHY if (user_name and user_email) else HealthStatus.WARNING

        return ToolReport(
            id=self.id,
            name=self.name,
            category=self.category,
            installed=True,
            version=version,
            binary_path=str(git_bin),
            home_path=str(git_bin.parent),
            status=status,
            companions=companions,
            diagnostics=diagnostics,
            metadata={"user.name": user_name, "user.email": user_email},
        )

