"""Tests for PluginRegistry dynamic discovery and filtering."""

from devtoolkit.core.registry import PluginRegistry


def test_plugin_registry_discovery():
    registry = PluginRegistry()
    inspectors = registry.list_inspectors()
    assert len(inspectors) >= 8

    tool_ids = {i.id for i in inspectors}
    assert "node" in tool_ids
    assert "python" in tool_ids
    assert "git" in tool_ids
    assert "docker" in tool_ids
    assert "golang" in tool_ids
    assert "rust" in tool_ids
    assert "java" in tool_ids
    assert "android" in tool_ids
    assert "flutter" in tool_ids


def test_plugin_registry_audit_filtering():
    registry = PluginRegistry()
    summary = registry.run_audit(categories=["vcs"])
    assert summary.total_tools == 1
    assert summary.reports[0].id == "git"

    summary_tools = registry.run_audit(tool_ids=["node", "python"])
    assert summary_tools.total_tools == 2
    tool_ids = {r.id for r in summary_tools.reports}
    assert tool_ids == {"node", "python"}
