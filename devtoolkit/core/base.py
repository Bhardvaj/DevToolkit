"""Base class abstractions for DevToolkit Inspectors and future Utility modules."""

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Optional

from datetime import datetime, timezone
from devtoolkit.core.models import DeepTelemetryReport, DiscoveredInstance, EnvVarStatus, HealthStatus, ToolReport
from devtoolkit.core.runner import SafeRunner


class BaseInspector(ABC):
    """Abstract base class for all tool, runtime, and SDK detectors."""

    id: str = "base"
    name: str = "Base Inspector"
    category: str = "general"
    categories: list[str] = ["general"]
    description: str = ""

    @abstractmethod
    def inspect(self, runner: SafeRunner) -> ToolReport:
        """Run safe discovery probes and return a structured ToolReport."""
        raise NotImplementedError

    def deep_inspect(self, runner: SafeRunner) -> DeepTelemetryReport:
        """Run safe deep domain inspection probes. Subclasses can override for rich telemetry."""
        base_rep = self.inspect(runner)
        instances: list[DiscoveredInstance] = []
        trace: list[str] = [f"Base inspection completed with status={base_rep.status.value}"]

        bin_name = self.id
        all_bins = runner.resolve_all_binaries(bin_name)
        trace.append(f"Discovered {len(all_bins)} binary candidate(s) for '{bin_name}'")

        for idx, b in enumerate(all_bins):
            is_active = (idx == 0)
            instances.append(
                DiscoveredInstance(
                    path=str(b.parent),
                    binary_path=str(b),
                    version=base_rep.version if is_active else None,
                    source="PATH",
                    is_active=is_active,
                    details="Active binary in system PATH" if is_active else "Alternate binary in PATH",
                )
            )

        if not instances and base_rep.binary_path:
            instances.append(
                DiscoveredInstance(
                    path=base_rep.home_path or str(Path(base_rep.binary_path).parent),
                    binary_path=base_rep.binary_path,
                    version=base_rep.version,
                    source="PATH",
                    is_active=True,
                    details="Primary resolved binary",
                )
            )

        return DeepTelemetryReport(
            tool_id=self.id,
            timestamp=datetime.now(timezone.utc).isoformat(),
            probe_latency_ms=0,
            instances=instances,
            env_vars=[],
            telemetry={"installed": base_rep.installed, "version": base_rep.version, "status": base_rep.status.value},
            raw_dumps={},
            discovery_trace=trace,
        )


class BaseUtility(ABC):
    """Abstract base class for extensible utilities (cache cleaners, port killers, env editors)."""

    id: str = "utility"
    name: str = "Base Utility"
    description: str = ""

    @abstractmethod
    def execute(self, runner: SafeRunner, **kwargs) -> dict:
        """Execute the utility action with parameters."""
        raise NotImplementedError
