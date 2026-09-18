"""SQLite Database Inspector."""

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


class SQLiteInspector(BaseInspector):
    id = "sqlite"
    name = "SQLite"
    category = "database"
    categories = ["database", "tools"]
    description = "Self-contained serverless SQL database engine command-line utility"

    def inspect(self, runner: SafeRunner) -> ToolReport:
        sqlite_bin = runner.resolve_binary("sqlite3")
        if not sqlite_bin:
            return ToolReport(
                id=self.id,
                name=self.name,
                category=self.category,
                categories=self.categories,
                installed=False,
                status=HealthStatus.NOT_FOUND,
            )

        # Version probe: `sqlite3 --version`
        res = runner.run_command([str(sqlite_bin), "--version"])
        version = None
        if res.ok and res.stdout.strip():
            # e.g. "3.45.1 2024-01-30 16:01:20 ..."
            parts = res.stdout.strip().split()
            if parts:
                version = parts[0].strip()

        return ToolReport(
            id=self.id,
            name=self.name,
            category=self.category,
            categories=self.categories,
            installed=True,
            version=version,
            binary_path=str(sqlite_bin),
            home_path=str(sqlite_bin.parent),
            status=HealthStatus.HEALTHY,
            companions=[],
            diagnostics=[],
            metadata={},
        )
