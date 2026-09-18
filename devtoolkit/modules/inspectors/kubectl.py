"""Kubernetes CLI Inspector."""

import os
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


class KubectlInspector(BaseInspector):
    id = "kubectl"
    name = "Kubernetes CLI"
    category = "container"
    categories = ["container", "cloud", "devops"]
    description = "Kubernetes cluster management CLI and container orchestration tools"

    def inspect(self, runner: SafeRunner) -> ToolReport:
        kubectl_bin = runner.resolve_binary("kubectl")
        if not kubectl_bin:
            return ToolReport(
                id=self.id,
                name=self.name,
                category=self.category,
                categories=self.categories,
                installed=False,
                status=HealthStatus.NOT_FOUND,
            )

        # Version probe: `kubectl version --client`
        res = runner.run_command([str(kubectl_bin), "version", "--client"])
        version = None
        if res.ok and res.stdout.strip():
            m = re.search(r"(?:Client Version:\s*|GitVersion:\s*\"?v?)([\d\.]+)", res.stdout)
            version = m.group(1) if m else res.stdout.splitlines()[0].strip()

        # Check Kubeconfig and current context
        kubeconfig_path = os.environ.get("KUBECONFIG")
        default_config = Path.home() / ".kube" / "config"
        config_file = None

        if kubeconfig_path and Path(kubeconfig_path).is_file():
            config_file = Path(kubeconfig_path)
        elif default_config.is_file():
            config_file = default_config

        current_context = None
        if config_file:
            try:
                content = config_file.read_text(encoding="utf-8", errors="ignore")
                m_ctx = re.search(r"current-context:\s*([^\r\n]+)", content)
                if m_ctx:
                    current_context = m_ctx.group(1).strip()
            except Exception:
                pass

        companions: List[CompanionTool] = []

        # Companion: Helm
        helm_bin = runner.resolve_binary("helm")
        if helm_bin:
            h_res = runner.run_command([str(helm_bin), "version", "--short"])
            h_ver = h_res.stdout.strip().lstrip("v") if h_res.ok else None
            companions.append(CompanionTool(name="helm", installed=True, version=h_ver, binary_path=str(helm_bin)))
        else:
            companions.append(CompanionTool(name="helm", installed=False))

        # Companion: Minikube
        minikube_bin = runner.resolve_binary("minikube")
        if minikube_bin:
            m_res = runner.run_command([str(minikube_bin), "version", "--short"])
            m_ver = m_res.stdout.strip().lstrip("v") if m_res.ok else None
            companions.append(CompanionTool(name="minikube", installed=True, version=m_ver, binary_path=str(minikube_bin)))
        else:
            companions.append(CompanionTool(name="minikube", installed=False))

        # Companion: Kubeconfig status
        companions.append(
            CompanionTool(
                name="context",
                installed=config_file is not None,
                version=current_context or ("Configured" if config_file else "Missing"),
            )
        )

        diagnostics: List[DiagnosticIssue] = []
        if not config_file:
            diagnostics.append(
                DiagnosticIssue(
                    level=DiagnosticLevel.INFO,
                    message="No active kubeconfig found at ~/.kube/config or via KUBECONFIG.",
                    suggested_fix="Connect to a cluster using your cloud provider CLI (e.g. 'aws eks update-kubeconfig' or 'gcloud container clusters get-credentials').",
                )
            )

        return ToolReport(
            id=self.id,
            name=self.name,
            category=self.category,
            categories=self.categories,
            installed=True,
            version=version,
            binary_path=str(kubectl_bin),
            home_path=str(kubectl_bin.parent),
            status=HealthStatus.HEALTHY,
            companions=companions,
            diagnostics=diagnostics,
            metadata={"kubeconfig": str(config_file) if config_file else None, "context": current_context},
        )
