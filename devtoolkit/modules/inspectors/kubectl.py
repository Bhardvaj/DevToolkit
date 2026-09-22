"""Kubernetes CLI Inspector."""

import os
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


class KubectlInspector(BaseInspector):
    id = "kubectl"
    name = "Kubernetes CLI"
    category = "container"
    categories = ["container", "cloud", "devops"]
    description = "Kubernetes cluster management CLI and container orchestration tools"

    def inspect(self, runner: SafeRunner) -> ToolReport:
        kubectl_bin = runner.resolve_binary("kubectl", tool_id=self.id)
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

    def deep_inspect(self, runner: SafeRunner, base_report: Optional[ToolReport] = None) -> DeepTelemetryReport:
        if base_report is None:
            base_report = self.inspect(runner)
        from datetime import datetime
        raw_dumps = {}
        trace = ["Starting Kubernetes CLI deep inspection probe"]
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
                    details="Active kubectl binary used for cluster orchestration",
                )
            )

        # Multi-instance discovery across PATH
        for k_bin in runner.resolve_all_binaries("kubectl"):
            if str(k_bin).lower() not in seen_bins:
                seen_bins.add(str(k_bin).lower())
                is_act = bool(base_report.binary_path and str(k_bin).lower() == str(base_report.binary_path).lower())
                ver_str = None
                res_v = runner.run_command([str(k_bin), "version", "--client"], timeout=2.0)
                if res_v.ok and res_v.stdout:
                    m = re.search(r"(?:Client Version:\s*|GitVersion:\s*\"?v?)([\d\.]+)", res_v.stdout)
                    ver_str = m.group(1) if m else None
                instances.append(
                    DiscoveredInstance(
                        path=str(k_bin.parent),
                        binary_path=str(k_bin),
                        version=ver_str,
                        source="Alternate PATH",
                        is_active=is_act,
                        details="Alternate kubectl CLI on system PATH",
                    )
                )

        # Check Docker Desktop bundled kubectl
        if sys.platform == "win32":
            dock_k = Path("C:/Program Files/Docker/Docker/resources/bin/kubectl.exe")
            if dock_k.is_file() and str(dock_k).lower() not in seen_bins:
                seen_bins.add(str(dock_k).lower())
                instances.append(
                    DiscoveredInstance(
                        path=str(dock_k.parent),
                        binary_path=str(dock_k),
                        version=None,
                        source="Docker Desktop Bundled",
                        is_active=False,
                        details="Bundled Kubernetes CLI inside Docker Desktop resources",
                    )
                )

        # Discovery Pipeline instances (Layer 2-4 Discovery)
        for disc_p in runner.discovery.discover_all_tool_instances(self.id):
            cand_bin = disc_p / ("kubectl.exe" if sys.platform == "win32" else "kubectl")
            if not cand_bin.is_file():
                cand_bin = disc_p / "bin" / ("kubectl.exe" if sys.platform == "win32" else "kubectl")
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
                        details="Discovered kubectl binary (Layer 2-4)",
                    )
                )

        trace.append(f"Discovered {len(instances)} kubectl instances")

        # 2. Environment Variables Alignment
        kubeconfig_val = runner.read_env("KUBECONFIG")
        default_cfg = Path.home() / ".kube" / "config"
        target_cfg = kubeconfig_val if kubeconfig_val else str(default_cfg)
        env_vars.append(
            EnvVarStatus(
                name="KUBECONFIG",
                value=kubeconfig_val,
                status="aligned" if kubeconfig_val else "missing",
                target_path=target_cfg,
                message="Points to explicit cluster configuration file" if kubeconfig_val else f"Default path (~/.kube/config: {'exists' if default_cfg.is_file() else 'missing'})",
            )
        )

        # 3. CLI Telemetry Dumps
        k_exec = base_report.binary_path or "kubectl"
        res_ver = runner.run_command([k_exec, "version", "--client", "--output=yaml"], timeout=2.5)
        if not res_ver.ok or not res_ver.stdout:
            res_ver = runner.run_command([k_exec, "version", "--client"], timeout=2.5)
        if res_ver.ok and res_ver.stdout:
            raw_dumps["kubectl version --client"] = res_ver.stdout.strip()

        res_ctx = runner.run_command([k_exec, "config", "view", "--minify"], timeout=2.5)
        if res_ctx.ok and res_ctx.stdout:
            raw_dumps["kubectl config view --minify"] = res_ctx.stdout.strip()

        res_contexts = runner.run_command([k_exec, "config", "get-contexts"], timeout=2.5)
        if res_contexts.ok and res_contexts.stdout:
            raw_dumps["kubectl config get-contexts"] = res_contexts.stdout.strip()

        if not base_report.metadata.get("context"):
            remediations.append("Connect to a Kubernetes cluster using your provider CLI (e.g. 'aws eks update-kubeconfig' or 'gcloud container clusters get-credentials').")

        trace.append("Completed Kubernetes CLI deep telemetry probes")

        return DeepTelemetryReport(
            tool_id=self.id,
            timestamp=datetime.now().isoformat(),
            probe_latency_ms=0,
            instances=instances,
            env_vars=env_vars,
            telemetry={
                "kubeconfig": base_report.metadata.get("kubeconfig"),
                "context": base_report.metadata.get("context"),
            },
            raw_dumps=raw_dumps,
            detailed_diagnostics=detailed_diag,
            remediation_commands=remediations,
            discovery_trace=trace,
        )

