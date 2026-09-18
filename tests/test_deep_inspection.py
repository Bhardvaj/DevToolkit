"""Tests for Phase 7 Deep Tool Inspection, Multi-Instance Precedence, and Environment Alignment."""

import pytest
from fastapi import HTTPException

from devtoolkit.core.models import (
    DeepTelemetryReport,
    DiscoveredInstance,
    EnvVarStatus,
    HealthStatus,
    ToolReport,
)
from devtoolkit.core.registry import PluginRegistry
from devtoolkit.server.app import get_tool_deep


def test_deep_inspection_models():
    """Verify serialization and validation of deep telemetry models."""
    inst = DiscoveredInstance(
        path="C:\\Tools\\Python",
        binary_path="C:\\Tools\\Python\\python.exe",
        version="3.12.0",
        source="PATH",
        is_active=True,
        details="Active binary in system PATH",
    )
    assert inst.is_active is True
    assert inst.source == "PATH"

    env_var = EnvVarStatus(
        name="JAVA_HOME",
        value="C:\\Program Files\\Java\\jdk-21",
        status="aligned",
        target_path="C:\\Program Files\\Java\\jdk-21",
        message="Aligned with active java binary",
    )
    assert env_var.status == "aligned"

    report = DeepTelemetryReport(
        tool_id="python",
        timestamp="2026-09-18T12:00:00Z",
        probe_latency_ms=42,
        instances=[inst],
        env_vars=[env_var],
        telemetry={"virtual_env": False},
        raw_dumps={"python -VV": "Python 3.12.0"},
        discovery_trace=["Inspection started", "Found 1 instance"],
    )
    assert report.tool_id == "python"
    assert report.probe_latency_ms == 42
    assert len(report.instances) == 1
    assert len(report.env_vars) == 1

    # Backwards compatibility of ToolReport
    tool_rep = ToolReport(
        id="python",
        name="Python",
        category="runtime",
        installed=True,
        status=HealthStatus.HEALTHY,
        deep_report=report,
    )
    assert tool_rep.deep_report is not None
    assert tool_rep.deep_report.tool_id == "python"


def test_registry_deep_inspection_batch1():
    """Verify registry can run deep inspection on Batch 1 tools."""
    registry = PluginRegistry()
    batch1_tools = ["python", "node", "git", "docker", "java", "golang", "rust", "dotnet"]

    for tool_id in batch1_tools:
        inspector = registry.get_inspector(tool_id)
        assert inspector is not None, f"Inspector for {tool_id} should be registered"

        deep_rep = registry.run_deep_inspection(tool_id)
        assert deep_rep is not None
        assert deep_rep.tool_id == tool_id
        assert deep_rep.probe_latency_ms >= 0
        assert isinstance(deep_rep.instances, list)
        assert isinstance(deep_rep.env_vars, list)
        assert isinstance(deep_rep.discovery_trace, list)
        assert len(deep_rep.discovery_trace) > 0


def test_get_tool_deep_endpoint_valid():
    """Verify get_tool_deep endpoint returns valid telemetry."""
    rep = get_tool_deep("python")
    assert rep.tool_id == "python"
    assert rep.probe_latency_ms >= 0


def test_registry_deep_inspection_batch2():
    """Verify registry can run deep inspection on Batch 2 tools."""
    registry = PluginRegistry()
    batch2_tools = [
        "android",
        "android_studio",
        "flutter",
        "vscode",
        "bun",
        "gh",
        "cmake",
        "ollama",
        "kubectl",
        "terraform",
        "c_compiler",
        "php",
        "cuda",
        "sqlite",
    ]

    for tool_id in batch2_tools:
        inspector = registry.get_inspector(tool_id)
        assert inspector is not None, f"Inspector for {tool_id} should be registered"

        deep_rep = registry.run_deep_inspection(tool_id)
        assert deep_rep is not None, f"Deep report for {tool_id} should not be None"
        assert deep_rep.tool_id == tool_id
        assert deep_rep.probe_latency_ms >= 0
        assert isinstance(deep_rep.instances, list)
        assert isinstance(deep_rep.env_vars, list)
        assert isinstance(deep_rep.discovery_trace, list)
        assert len(deep_rep.discovery_trace) > 0


def test_all_22_inspectors_have_deep_inspection():
    """Verify all 22 registered inspectors in DevToolkit have custom deep inspection implementations."""
    registry = PluginRegistry()
    inspectors = registry.list_inspectors()
    assert len(inspectors) == 22, f"Expected 22 inspectors, found {len(inspectors)}"

    for insp in inspectors:
        # Verify the inspector has a callable deep_inspect method
        assert hasattr(insp, "deep_inspect"), f"{insp.id} must have deep_inspect method"
        assert callable(insp.deep_inspect)


def test_get_tool_deep_endpoint_404():
    """Verify get_tool_deep raises HTTPException 404 for unknown tool."""
    with pytest.raises(HTTPException) as exc_info:
        get_tool_deep("nonexistent_tool_xyz")
    assert exc_info.value.status_code == 404

