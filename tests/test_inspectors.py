"""Tests for tool inspectors."""

from devtoolkit.core.models import ToolReport
from devtoolkit.core.runner import SafeRunner
from devtoolkit.modules.inspectors.git import GitInspector
from devtoolkit.modules.inspectors.node import NodeInspector
from devtoolkit.modules.inspectors.python import PythonInspector


def test_python_inspector():
    runner = SafeRunner()
    inspector = PythonInspector()
    report = inspector.inspect(runner)

    assert isinstance(report, ToolReport)
    assert report.id == "python"
    assert report.installed is True
    assert report.version is not None
    assert report.binary_path is not None


def test_git_inspector():
    runner = SafeRunner()
    inspector = GitInspector()
    report = inspector.inspect(runner)

    assert isinstance(report, ToolReport)
    assert report.id == "git"
    assert report.installed is True
    assert report.version is not None


def test_node_inspector():
    runner = SafeRunner()
    inspector = NodeInspector()
    report = inspector.inspect(runner)

    assert isinstance(report, ToolReport)
    assert report.id == "node"
    if report.installed:
        assert report.binary_path is not None
