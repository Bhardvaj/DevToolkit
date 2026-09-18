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
        # 1. Register builtin inspectors (guaranteed bundled and available in PyInstaller frozen executables)
        builtin = getattr(inspectors_pkg, "BUILTIN_INSPECTORS", [])
        for cls in builtin:
            try:
                self.register_inspector(cls())
            except Exception:
                continue

        # 2. Also dynamically scan package directory for any custom/external inspector modules
        package = inspectors_pkg
        try:
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
                            if obj.id not in self._inspectors:
                                instance = obj()
                                self.register_inspector(instance)
                except Exception:
                    continue
        except Exception:
            pass

    def run_audit(
        self,
        categories: Optional[List[str]] = None,
        tool_ids: Optional[List[str]] = None,
        max_workers: Optional[int] = None,
    ) -> AuditSummary:
        """Run safe environment inspection across registered inspectors concurrently."""
        target_inspectors = list(self._inspectors.values())

        if categories:
            norm_cats = {c.lower() for c in categories}
            target_inspectors = [
                i
                for i in target_inspectors
                if any(c.lower() in norm_cats for c in getattr(i, "categories", [i.category]))
                or i.category.lower() in norm_cats
            ]

        if tool_ids:
            norm_ids = {t.lower() for t in tool_ids}
            target_inspectors = [i for i in target_inspectors if i.id.lower() in norm_ids]

        reports: List[ToolReport] = []
        worker_count = max_workers if max_workers is not None else min(32, max(len(target_inspectors), 1))

        with ThreadPoolExecutor(max_workers=worker_count) as executor:
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
                            categories=getattr(inspector, "categories", [inspector.category]),
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

    def stream_audit(
        self,
        categories: Optional[List[str]] = None,
        tool_ids: Optional[List[str]] = None,
        max_workers: Optional[int] = None,
    ):
        """Yield audit results progressively as each tool inspection completes."""
        target_inspectors = list(self._inspectors.values())

        if categories:
            norm_cats = {c.lower() for c in categories}
            target_inspectors = [
                i
                for i in target_inspectors
                if any(c.lower() in norm_cats for c in getattr(i, "categories", [i.category]))
                or i.category.lower() in norm_cats
            ]

        if tool_ids:
            norm_ids = {t.lower() for t in tool_ids}
            target_inspectors = [i for i in target_inspectors if i.id.lower() in norm_ids]

        worker_count = max_workers if max_workers is not None else min(32, max(len(target_inspectors), 1))
        sys_info = self.runner.get_system_info()

        yield {
            "type": "init",
            "total_tools": len(target_inspectors),
            "system": sys_info.model_dump(mode="json"),
        }

        reports: List[ToolReport] = []
        with ThreadPoolExecutor(max_workers=worker_count) as executor:
            future_to_inspector = {
                executor.submit(inspector.inspect, self.runner): inspector
                for inspector in target_inspectors
            }
            for future in as_completed(future_to_inspector):
                inspector = future_to_inspector[future]
                try:
                    report = future.result()
                except Exception as e:
                    report = ToolReport(
                        id=inspector.id,
                        name=inspector.name,
                        category=inspector.category,
                        categories=getattr(inspector, "categories", [inspector.category]),
                        installed=False,
                        status=HealthStatus.ERROR,
                        metadata={"error": str(e)},
                    )
                reports.append(report)
                yield {
                    "type": "tool",
                    "report": report.model_dump(mode="json"),
                }

        # Calculate final metrics
        installed_count = sum(1 for r in reports if r.installed)
        healthy_count = sum(1 for r in reports if r.status == HealthStatus.HEALTHY)
        warning_count = sum(1 for r in reports if r.status == HealthStatus.WARNING)
        error_count = sum(1 for r in reports if r.status == HealthStatus.ERROR)
        not_found_count = sum(1 for r in reports if r.status == HealthStatus.NOT_FOUND)

        yield {
            "type": "done",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "total_tools": len(reports),
            "installed_count": installed_count,
            "healthy_count": healthy_count,
            "warning_count": warning_count,
            "error_count": error_count,
            "not_found_count": not_found_count,
            "system": sys_info.model_dump(mode="json"),
        }

