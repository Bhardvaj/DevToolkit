"""PHP & Composer Inspector."""

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


class PHPInspector(BaseInspector):
    id = "php"
    name = "PHP & Composer"
    category = "runtime"
    categories = ["runtime", "web"]
    description = "PHP script interpreter and Composer package manager"

    def inspect(self, runner: SafeRunner) -> ToolReport:
        php_bin = runner.resolve_binary("php")
        if not php_bin:
            return ToolReport(
                id=self.id,
                name=self.name,
                category=self.category,
                categories=self.categories,
                installed=False,
                status=HealthStatus.NOT_FOUND,
            )

        # Version probe: `php -v`
        res = runner.run_command([str(php_bin), "-v"])
        version = None
        if res.ok and res.stdout.strip():
            # e.g. "PHP 8.3.14 (cli) (built: Dec  3 2024 16:30:22)"
            m = re.search(r"PHP\s+([\d\.]+)", res.stdout)
            version = m.group(1) if m else res.stdout.splitlines()[0].strip()

        companions: List[CompanionTool] = []

        # Companion: Composer
        composer_bin = runner.resolve_binary("composer") or runner.resolve_binary("composer.bat")
        comp_ver = None
        if composer_bin:
            comp_res = runner.run_command([str(composer_bin), "--version"])
            if comp_res.ok:
                m_comp = re.search(r"Composer\s+(?:version\s+)?([\d\.]+)", comp_res.stdout)
                comp_ver = m_comp.group(1) if m_comp else None
            companions.append(CompanionTool(name="composer", installed=True, version=comp_ver, binary_path=str(composer_bin)))
        else:
            companions.append(CompanionTool(name="composer", installed=False))

        diagnostics: List[DiagnosticIssue] = []
        if not composer_bin:
            diagnostics.append(
                DiagnosticIssue(
                    level=DiagnosticLevel.WARNING,
                    message="Composer dependency manager is not detected alongside PHP.",
                    suggested_fix="Install Composer from https://getcomposer.org or via winget: 'winget install Composer.Composer'.",
                )
            )

        status = HealthStatus.HEALTHY if composer_bin else HealthStatus.WARNING

        return ToolReport(
            id=self.id,
            name=self.name,
            category=self.category,
            categories=self.categories,
            installed=True,
            version=version,
            binary_path=str(php_bin),
            home_path=str(php_bin.parent),
            status=status,
            companions=companions,
            diagnostics=diagnostics,
            metadata={"composer_installed": composer_bin is not None},
        )
