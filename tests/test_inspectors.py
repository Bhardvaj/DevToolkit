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


def test_kubectl_inspector():
    from devtoolkit.modules.inspectors.kubectl import KubectlInspector
    runner = SafeRunner()
    inspector = KubectlInspector()
    report = inspector.inspect(runner)

    assert isinstance(report, ToolReport)
    assert report.id == "kubectl"
    assert "container" in report.categories
    assert "cloud" in report.categories


def test_terraform_inspector():
    from devtoolkit.modules.inspectors.terraform import TerraformInspector
    runner = SafeRunner()
    inspector = TerraformInspector()
    report = inspector.inspect(runner)

    assert isinstance(report, ToolReport)
    assert report.id == "terraform"
    assert "cloud" in report.categories
    assert "iac" in report.categories


def test_c_compiler_inspector():
    from devtoolkit.modules.inspectors.c_compiler import CCompilerInspector
    runner = SafeRunner()
    inspector = CCompilerInspector()
    report = inspector.inspect(runner)

    assert isinstance(report, ToolReport)
    assert report.id == "c_compiler"
    assert "build" in report.categories
    assert "compiler" in report.categories


def test_php_inspector():
    from devtoolkit.modules.inspectors.php import PHPInspector
    runner = SafeRunner()
    inspector = PHPInspector()
    report = inspector.inspect(runner)

    assert isinstance(report, ToolReport)
    assert report.id == "php"
    assert "runtime" in report.categories
    assert "web" in report.categories


def test_cuda_inspector():
    from devtoolkit.modules.inspectors.cuda import CudaInspector
    runner = SafeRunner()
    inspector = CudaInspector()
    report = inspector.inspect(runner)

    assert isinstance(report, ToolReport)
    assert report.id == "cuda"
    assert "ai" in report.categories
    assert "hardware" in report.categories


def test_sqlite_inspector():
    from devtoolkit.modules.inspectors.sqlite import SQLiteInspector
    runner = SafeRunner()
    inspector = SQLiteInspector()
    report = inspector.inspect(runner)

    assert isinstance(report, ToolReport)
    assert report.id == "sqlite"
    assert "database" in report.categories


