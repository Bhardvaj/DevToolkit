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
    assert isinstance(report.categories, list)
    assert "runtime" in report.categories


def test_git_inspector():
    runner = SafeRunner()
    inspector = GitInspector()
    report = inspector.inspect(runner)

    assert isinstance(report, ToolReport)
    assert report.id == "git"
    assert report.installed is True
    assert report.version is not None
    assert "vcs" in report.categories


def test_node_inspector():
    runner = SafeRunner()
    inspector = NodeInspector()
    report = inspector.inspect(runner)

    assert isinstance(report, ToolReport)
    assert report.id == "node"
    assert "runtime" in report.categories
    if report.installed:
        assert report.binary_path is not None


def test_multiple_categories():
    from devtoolkit.modules.inspectors.android_studio import AndroidStudioInspector
    from devtoolkit.modules.inspectors.android import AndroidInspector
    from devtoolkit.modules.inspectors.java import JavaInspector

    studio = AndroidStudioInspector()
    assert "ide" in studio.categories
    assert "mobile" in studio.categories

    sdk = AndroidInspector()
    assert "mobile" in sdk.categories
    assert "sdk" in sdk.categories

    java = JavaInspector()
    assert "runtime" in java.categories
    assert "mobile" in java.categories


def test_vscode_inspector():
    from devtoolkit.modules.inspectors.vscode import VSCodeInspector
    runner = SafeRunner()
    inspector = VSCodeInspector()
    report = inspector.inspect(runner)

    assert isinstance(report, ToolReport)
    assert report.id == "vscode"
    assert "ide" in report.categories
    assert "editor" in report.categories


def test_dotnet_inspector():
    from devtoolkit.modules.inspectors.dotnet import DotNetInspector
    runner = SafeRunner()
    inspector = DotNetInspector()
    report = inspector.inspect(runner)

    assert isinstance(report, ToolReport)
    assert report.id == "dotnet"
    assert "runtime" in report.categories
    assert "framework" in report.categories


def test_bun_inspector():
    from devtoolkit.modules.inspectors.bun import BunInspector
    runner = SafeRunner()
    inspector = BunInspector()
    report = inspector.inspect(runner)

    assert isinstance(report, ToolReport)
    assert report.id == "bun"
    assert "runtime" in report.categories


def test_gh_inspector():
    from devtoolkit.modules.inspectors.gh import GitHubCLIInspector
    runner = SafeRunner()
    inspector = GitHubCLIInspector()
    report = inspector.inspect(runner)

    assert isinstance(report, ToolReport)
    assert report.id == "gh"
    assert "vcs" in report.categories
    assert "cli" in report.categories


def test_cmake_inspector():
    from devtoolkit.modules.inspectors.cmake import CMakeInspector
    runner = SafeRunner()
    inspector = CMakeInspector()
    report = inspector.inspect(runner)

    assert isinstance(report, ToolReport)
    assert report.id == "cmake"
    assert "build" in report.categories


def test_ollama_inspector():
    from devtoolkit.modules.inspectors.ollama import OllamaInspector
    runner = SafeRunner()
    inspector = OllamaInspector()
    report = inspector.inspect(runner)

    assert isinstance(report, ToolReport)
    assert report.id == "ollama"
    assert "ai" in report.categories

