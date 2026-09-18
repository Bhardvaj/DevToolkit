"""Terraform Infrastructure as Code Inspector."""

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


class TerraformInspector(BaseInspector):
    id = "terraform"
    name = "Terraform"
    category = "cloud"
    categories = ["cloud", "devops", "iac"]
    description = "HashiCorp Terraform infrastructure as code CLI and OpenTofu compatibility"

    def inspect(self, runner: SafeRunner) -> ToolReport:
        tf_bin = runner.resolve_binary("terraform")
        tofu_bin = runner.resolve_binary("tofu")

        active_bin = tf_bin or tofu_bin
        if not active_bin:
            return ToolReport(
                id=self.id,
                name=self.name,
                category=self.category,
                categories=self.categories,
                installed=False,
                status=HealthStatus.NOT_FOUND,
            )

        # Version probe: `terraform version`
        res = runner.run_command([str(active_bin), "version"])
        version = None
        if res.ok and res.stdout.strip():
            # e.g. "Terraform v1.10.4" or "OpenTofu v1.9.0"
            m = re.search(r"(?:Terraform|OpenTofu)\s+v?([\d\.]+)", res.stdout)
            version = m.group(1) if m else res.stdout.splitlines()[0].strip()

        companions: List[CompanionTool] = []

        # Companion: OpenTofu
        if tofu_bin:
            tofu_res = runner.run_command([str(tofu_bin), "version"])
            tofu_ver = re.search(r"v?([\d\.]+)", tofu_res.stdout).group(1) if (tofu_res.ok and re.search(r"v?([\d\.]+)", tofu_res.stdout)) else None
            companions.append(CompanionTool(name="opentofu", installed=True, version=tofu_ver, binary_path=str(tofu_bin)))
        else:
            companions.append(CompanionTool(name="opentofu", installed=False))

        return ToolReport(
            id=self.id,
            name=self.name,
            category=self.category,
            categories=self.categories,
            installed=True,
            version=version,
            binary_path=str(active_bin),
            home_path=str(active_bin.parent),
            status=HealthStatus.HEALTHY,
            companions=companions,
            diagnostics=[],
            metadata={"is_opentofu": active_bin == tofu_bin},
        )
