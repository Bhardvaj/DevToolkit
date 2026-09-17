"""Ollama Local AI Runtime Inspector."""

import os
import re
import sys
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


class OllamaInspector(BaseInspector):
    id = "ollama"
    name = "Ollama"
    category = "ai"
    categories = ["ai", "tools"]
    description = "Local LLM inference server, model runner, and CLI"

    def inspect(self, runner: SafeRunner) -> ToolReport:
        ollama_bin = runner.resolve_binary("ollama")
        user_bin = None

        if not ollama_bin and sys.platform == "win32":
            local_app = os.environ.get("LOCALAPPDATA")
            if local_app:
                cand = Path(local_app) / "Programs" / "Ollama" / "ollama.exe"
                if cand.is_file():
                    user_bin = cand

        active_bin = ollama_bin or user_bin
        if not active_bin:
            return ToolReport(
                id=self.id,
                name=self.name,
                category=self.category,
                categories=self.categories,
                installed=False,
                status=HealthStatus.NOT_FOUND,
            )

        # Version probe: `ollama --version`
        res = runner.run_command([str(active_bin), "--version"])
        version = None
        if res.ok and res.stdout.strip():
            # "ollama version is 0.5.7"
            m = re.search(r"version is\s+([\d\.]+)", res.stdout)
            version = m.group(1) if m else res.stdout.splitlines()[0].strip()

        # Probe daemon and model listing: `ollama list`
        list_res = runner.run_command([str(active_bin), "list"], timeout_seconds=3)
        daemon_online = list_res.ok
        model_names = []
        if list_res.ok and list_res.stdout.strip():
            # Output lines like: NAME ID SIZE MODIFIED
            lines = [line.strip() for line in list_res.stdout.splitlines() if line.strip()]
            if len(lines) > 1:
                for line in lines[1:]:
                    parts = line.split()
                    if parts:
                        model_names.append(parts[0])

        companions: List[CompanionTool] = []
        companions.append(
            CompanionTool(
                name="daemon",
                installed=daemon_online,
                version="Online (:11434)" if daemon_online else "Offline",
            )
        )
        companions.append(
            CompanionTool(
                name="models",
                installed=len(model_names) > 0,
                version=f"{len(model_names)} installed" if daemon_online else None,
            )
        )

        diagnostics: List[DiagnosticIssue] = []

        is_on_path = runner.resolve_binary("ollama") is not None
        if not is_on_path and user_bin:
            diagnostics.append(
                DiagnosticIssue(
                    level=DiagnosticLevel.WARNING,
                    message="Ollama is installed in local app data, but not added to your system PATH.",
                    suggested_fix=f'Add "{user_bin.parent}" to your PATH environment variable.',
                )
            )

        if not daemon_online:
            diagnostics.append(
                DiagnosticIssue(
                    level=DiagnosticLevel.INFO,
                    message="Ollama inference server is currently not running.",
                    suggested_fix="Launch Ollama from the Start Menu or run 'ollama serve' in background.",
                )
            )

        ollama_models_dir = os.environ.get("OLLAMA_MODELS")
        metadata = {
            "daemon_online": daemon_online,
            "models_count": len(model_names),
            "models": model_names[:5],
            "models_dir": ollama_models_dir or str(Path.home() / ".ollama" / "models"),
        }

        status = HealthStatus.HEALTHY if is_on_path else HealthStatus.WARNING

        return ToolReport(
            id=self.id,
            name=self.name,
            category=self.category,
            categories=self.categories,
            installed=True,
            version=version,
            binary_path=str(active_bin),
            home_path=str(active_bin.parent),
            status=status,
            companions=companions,
            diagnostics=diagnostics,
            metadata=metadata,
        )
