"""Base class abstractions for DevToolkit Inspectors and future Utility modules."""

from abc import ABC, abstractmethod
from typing import Optional

from devtoolkit.core.models import HealthStatus, ToolReport
from devtoolkit.core.runner import SafeRunner


class BaseInspector(ABC):
    """Abstract base class for all tool, runtime, and SDK detectors."""

    id: str = "base"
    name: str = "Base Inspector"
    category: str = "general"
    description: str = ""

    @abstractmethod
    def inspect(self, runner: SafeRunner) -> ToolReport:
        """Run safe discovery probes and return a structured ToolReport."""
        raise NotImplementedError


class BaseUtility(ABC):
    """Abstract base class for extensible utilities (cache cleaners, port killers, env editors)."""

    id: str = "utility"
    name: str = "Base Utility"
    description: str = ""

    @abstractmethod
    def execute(self, runner: SafeRunner, **kwargs) -> dict:
        """Execute the utility action with parameters."""
        raise NotImplementedError

