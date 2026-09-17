"""Tests for tool inspectors."""

from devtoolkit.core.models import ToolReport
from devtoolkit.core.runner import SafeRunner
from devtoolkit.modules.inspectors.android import AndroidInspector
from devtoolkit.modules.inspectors.android_studio import AndroidStudioInspector
from devtoolkit.modules.inspectors.git import GitInspector
from devtoolkit.modules.inspectors.java import JavaInspector
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
    assert report.installed is True
    assert report.version is not None


def test_android_inspector():
    runner = SafeRunner()
    inspector = AndroidInspector()
    report = inspector.inspect(runner)

    assert isinstance(report, ToolReport)
    assert report.id == "android"
    assert report.installed is True
    assert report.home_path is not None


def test_android_studio_inspector():
    runner = SafeRunner()
    inspector = AndroidStudioInspector()
    report = inspector.inspect(runner)

    assert isinstance(report, ToolReport)
    assert report.id == "android_studio"
    assert report.installed is True


def test_java_inspector():
    runner = SafeRunner()
    inspector = JavaInspector()
    report = inspector.inspect(runner)

    assert isinstance(report, ToolReport)
    assert report.id == "java"
    assert report.installed is True
