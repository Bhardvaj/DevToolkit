"""PluginRegistry: Dynamic discovery, registration, and concurrent execution of inspectors."""

import importlib
import inspect
import pkgutil
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from typing import Dict, List, Optional, Type

from devtoolkit.core.base import BaseInspector, BaseUtility
from devtoolkit.core.models import AuditSummary, HealthStatus, ToolReport
from devtoolkit.core.runner import SafeRunner
import devtoolkit.modules.inspectors as inspectors_pkg


class PluginRegistry:
    """Manages discovery and lifecycle of inspectors and utilities."""

    def __init__(self, runner: Optional[SafeRunner] = None):
        self.runner = runner or SafeRunner()
        self._inspectors: Dict[str, BaseInspector] = {}
        self._utilities: Dict[str, BaseUtility] = {}
        self.discover_inspectors()

    def register_inspector(self, inspector: BaseInspector) -> None:
        self._inspectors[inspector.id] = inspector

    def register_utility(self, utility: BaseUtility) -> None:
        self._utilities[utility.id] = utility

    def get_inspector(self, tool_id: str) -> Optional[BaseInspector]:
        return self._inspectors.get(tool_id)

    def list_inspectors(self) -> List[BaseInspector]:
        return list(self._inspectors.values())

    def discover_inspectors(self) -> None:
        """Dynamically find and load all BaseInspector subclasses in devtoolkit.modules.inspectors."""
        package = inspectors_pkg
        for _, module_name, _ in pkgutil.iter_modules(package.__path__):
            full_module_name = f"{package.__name__}.{module_name}"
            try:
                module = importlib.import_module(full_module_name)
                for _, obj in inspect.getmembers(module, inspect.isclass):
                    if (
                        issubclass(obj, BaseInspector)
                        and obj is not BaseInspector
                        and getattr(obj, "id", "base") != "base"
                    ):
                        instance = obj()
                        self.register_inspector(instance)
            except Exception as e:
                # Silently catch module import failures or log in verbose mode
                continue

    def run_audit(
        self,
        categories: Optional[List[str]] = None,
        tool_ids: Optional[List[str]] = None,
        max_workers: int = 8,
    ) -> AuditSummary:
        """Run safe environment inspection across registered inspectors concurrently."""
        target_inspectors = list(self._inspectors.values())

        if categories:
            norm_cats = {c.lower() for c in categories}
            target_inspectors = [i for i in target_inspectors if i.category.lower() in norm_cats]

        if tool_ids:
            norm_ids = {t.lower() for t in tool_ids}
            target_inspectors = [i for i in target_inspectors if i.id.lower() in norm_ids]

        reports: List[ToolReport] = []

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_inspector = {
                executor.submit(inspector.inspect, self.runner): inspector
                for inspector in target_inspectors
            }
            for future in as_completed(future_to_inspector):
                inspector = future_to_inspector[future]
                try:
                    report = future.result()
                    reports.append(report)
                except Exception as e:
                    reports.append(
                        ToolReport(
                            id=inspector.id,
                            name=inspector.name,
                            category=inspector.category,
                            installed=False,
                            status=HealthStatus.ERROR,
                            metadata={"error": str(e)},
                        )
                    )

        # Sort reports alphabetically by category and name
        reports.sort(key=lambda r: (r.category, r.name))

        # Calculate metrics
        installed_count = sum(1 for r in reports if r.installed)
        healthy_count = sum(1 for r in reports if r.status == HealthStatus.HEALTHY)
        warning_count = sum(1 for r in reports if r.status == HealthStatus.WARNING)
        error_count = sum(1 for r in reports if r.status == HealthStatus.ERROR)
        not_found_count = sum(1 for r in reports if r.status == HealthStatus.NOT_FOUND)

        return AuditSummary(
            timestamp=datetime.now(timezone.utc).isoformat(),
            system=self.runner.get_system_info(),
            total_tools=len(reports),
            installed_count=installed_count,
            healthy_count=healthy_count,
            warning_count=warning_count,
            error_count=error_count,
            not_found_count=not_found_count,
            reports=reports,
        )

