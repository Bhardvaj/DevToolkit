"""Tests for PluginRegistry dynamic discovery and filtering."""

from devtoolkit.core.registry import PluginRegistry


def test_plugin_registry_discovery():
    registry = PluginRegistry()
    inspectors = registry.list_inspectors()
    assert len(inspectors) >= 22

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
    assert "vscode" in tool_ids
    assert "dotnet" in tool_ids
    assert "bun" in tool_ids
    assert "gh" in tool_ids
    assert "cmake" in tool_ids
    assert "ollama" in tool_ids
    assert "kubectl" in tool_ids
    assert "terraform" in tool_ids
    assert "c_compiler" in tool_ids
    assert "php" in tool_ids
    assert "cuda" in tool_ids
    assert "sqlite" in tool_ids


def test_plugin_registry_audit_filtering():
    registry = PluginRegistry()
    summary = registry.run_audit(categories=["vcs"])
    assert summary.total_tools == 2
    assert {r.id for r in summary.reports} == {"git", "gh"}

    summary_db = registry.run_audit(categories=["database"])
    assert summary_db.total_tools == 1
    assert summary_db.reports[0].id == "sqlite"

    summary_tools = registry.run_audit(tool_ids=["node", "python"])
    assert summary_tools.total_tools == 2
    tool_ids = {r.id for r in summary_tools.reports}
    assert tool_ids == {"node", "python"}
