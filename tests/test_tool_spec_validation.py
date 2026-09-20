"""Comprehensive Tool Specification & Flow Branch Validation Tests.

Validates all 22 developer tools against their documented specifications in agent/documentation.md:
- Taxonomy (id, name, category, categories, description)
- inspect() contracts, version extraction, companion probing, health logic
- deep_inspect() contracts, multi-instance discovery, env var alignment, telemetry dumps
- Controlled condition branches (NOT_FOUND fallbacks, missing companions, divergent env vars)
"""

from pathlib import Path
from unittest.mock import MagicMock, patch
import pytest

from devtoolkit.core.models import (
    CompanionTool,
    DeepTelemetryReport,
    DiagnosticIssue,
    DiagnosticLevel,
    DiscoveredInstance,
    EnvVarStatus,
    HealthStatus,
    ToolReport,
)
from devtoolkit.core.runner import CommandResult, SafeRunner

# Import all 22 inspector classes
from devtoolkit.modules.inspectors.android import AndroidInspector
from devtoolkit.modules.inspectors.android_studio import AndroidStudioInspector
from devtoolkit.modules.inspectors.bun import BunInspector
from devtoolkit.modules.inspectors.c_compiler import CCompilerInspector
from devtoolkit.modules.inspectors.cmake import CMakeInspector
from devtoolkit.modules.inspectors.cuda import CudaInspector
from devtoolkit.modules.inspectors.docker import DockerInspector
from devtoolkit.modules.inspectors.dotnet import DotNetInspector
from devtoolkit.modules.inspectors.flutter import FlutterInspector
from devtoolkit.modules.inspectors.gh import GitHubCLIInspector
from devtoolkit.modules.inspectors.git import GitInspector
from devtoolkit.modules.inspectors.golang import GoInspector
from devtoolkit.modules.inspectors.java import JavaInspector
from devtoolkit.modules.inspectors.kubectl import KubectlInspector
from devtoolkit.modules.inspectors.node import NodeInspector
from devtoolkit.modules.inspectors.ollama import OllamaInspector
from devtoolkit.modules.inspectors.php import PHPInspector
from devtoolkit.modules.inspectors.python import PythonInspector
from devtoolkit.modules.inspectors.rust import RustInspector
from devtoolkit.modules.inspectors.sqlite import SQLiteInspector
from devtoolkit.modules.inspectors.terraform import TerraformInspector
from devtoolkit.modules.inspectors.vscode import VSCodeInspector

ALL_INSPECTORS = [
    # Batch 1: Runtimes & Languages
    (PythonInspector, "python", "Python", "runtime", ["runtime", "scripting", "ai"]),
    (NodeInspector, "node", "Node.js", "runtime", ["runtime", "web"]),
    (JavaInspector, "java", "Java / JDK", "runtime", ["runtime", "mobile", "sdk"]),
    (GoInspector, "golang", "Go", "runtime", ["runtime", "backend"]),
    (RustInspector, "rust", "Rust / Cargo", "runtime", ["runtime", "compiler"]),
    (DotNetInspector, "dotnet", ".NET SDK", "runtime", ["runtime", "framework"]),
    (PHPInspector, "php", "PHP & Composer", "runtime", ["runtime", "web"]),
    (BunInspector, "bun", "Bun", "runtime", ["runtime", "web"]),
    # Batch 2: Compilers, Build Systems & Hardware
    (CCompilerInspector, "c_compiler", "C/C++ Compiler", "build", ["build", "compiler", "runtime"]),
    (CMakeInspector, "cmake", "CMake", "build", ["build", "tools"]),
    (CudaInspector, "cuda", "NVIDIA CUDA Toolkit", "ai", ["ai", "compiler", "hardware"]),
    # Batch 3: VCS, Cloud & Containers
    (GitInspector, "git", "Git", "vcs", ["vcs", "tool"]),
    (GitHubCLIInspector, "gh", "GitHub CLI", "vcs", ["vcs", "cli", "tools"]),
    (DockerInspector, "docker", "Docker", "container", ["container", "runtime"]),
    (KubectlInspector, "kubectl", "Kubernetes CLI", "container", ["container", "cloud", "devops"]),
    (TerraformInspector, "terraform", "Terraform", "cloud", ["cloud", "devops", "iac"]),
    # Batch 4: Mobile, IDEs & AI/Databases
    (AndroidInspector, "android", "Android SDK", "mobile", ["mobile", "sdk"]),
    (AndroidStudioInspector, "android_studio", "Android Studio", "ide", ["ide", "mobile"]),
    (FlutterInspector, "flutter", "Flutter", "mobile", ["mobile", "sdk", "runtime"]),
    (VSCodeInspector, "vscode", "Visual Studio Code", "ide", ["ide", "editor"]),
    (OllamaInspector, "ollama", "Ollama", "ai", ["ai", "tools"]),
    (SQLiteInspector, "sqlite", "SQLite", "database", ["database", "tools"]),
]


# ==============================================================================
# 1. TAXONOMY & CONTRACT TESTS ACROSS ALL 22 TOOLS
# ==============================================================================

@pytest.mark.parametrize("inspector_cls,tool_id,name,cat,cats", ALL_INSPECTORS)
def test_tool_taxonomy_matches_documentation(inspector_cls, tool_id, name, cat, cats):
    """Verify that every tool's ID, Name, Category, and Multi-categories match the spec."""
    inspector = inspector_cls()
    assert inspector.id == tool_id
    assert inspector.name == name
    assert inspector.category == cat
    assert inspector.categories == cats
    assert len(inspector.description) > 0


@pytest.mark.parametrize("inspector_cls,tool_id,name,cat,cats", ALL_INSPECTORS)
def test_tool_live_inspection_contracts(inspector_cls, tool_id, name, cat, cats):
    """Verify that inspect() produces a valid ToolReport conforming to the spec schema."""
    runner = SafeRunner()
    inspector = inspector_cls()
    report = inspector.inspect(runner)

    assert isinstance(report, ToolReport)
    assert report.id == tool_id
    assert report.name == name
    assert report.category == cat
    assert report.categories == cats
    assert isinstance(report.installed, bool)
    assert isinstance(report.status, HealthStatus)
    assert isinstance(report.companions, list)
    assert isinstance(report.diagnostics, list)

    for comp in report.companions:
        assert isinstance(comp, CompanionTool)
        assert isinstance(comp.installed, bool)
        assert isinstance(comp.name, str)

    for diag in report.diagnostics:
        assert isinstance(diag, DiagnosticIssue)
        assert isinstance(diag.level, DiagnosticLevel)
        assert isinstance(diag.message, str)


@pytest.mark.parametrize("inspector_cls,tool_id,name,cat,cats", ALL_INSPECTORS)
def test_tool_live_deep_inspection_contracts(inspector_cls, tool_id, name, cat, cats):
    """Verify that deep_inspect() produces a valid DeepTelemetryReport conforming to the spec schema."""
    runner = SafeRunner()
    inspector = inspector_cls()
    base_report = inspector.inspect(runner)
    deep_rep = inspector.deep_inspect(runner, base_report)

    assert isinstance(deep_rep, DeepTelemetryReport)
    assert deep_rep.tool_id == tool_id
    assert deep_rep.probe_latency_ms >= 0
    assert isinstance(deep_rep.instances, list)
    assert isinstance(deep_rep.env_vars, list)
    assert isinstance(deep_rep.raw_dumps, dict)
    assert isinstance(deep_rep.discovery_trace, list)
    assert len(deep_rep.discovery_trace) > 0

    # Ensure every discovered instance conforms to schema
    active_count = 0
    for inst in deep_rep.instances:
        assert isinstance(inst, DiscoveredInstance)
        assert isinstance(inst.path, str)
        assert isinstance(inst.source, str)
        assert isinstance(inst.is_active, bool)
        if inst.is_active:
            active_count += 1
    assert active_count <= 1  # Exactly 0 or 1 active instance

    # Ensure every env var conforms to schema
    valid_statuses = {"aligned", "divergent", "missing"}
    for ev in deep_rep.env_vars:
        assert isinstance(ev, EnvVarStatus)
        assert isinstance(ev.name, str)
        assert ev.status in valid_statuses


# ==============================================================================
# 2. CONTROLLED BRANCH TESTS: NOT FOUND FALLBACKS
# ==============================================================================

@pytest.mark.parametrize("inspector_cls,tool_id,name,cat,cats", ALL_INSPECTORS)
def test_tool_not_found_branch(inspector_cls, tool_id, name, cat, cats):
    """Verify that when no binary or directory is resolved, tool returns NOT_FOUND status."""
    mock_runner = MagicMock(spec=SafeRunner)
    mock_runner.resolve_binary.return_value = None
    mock_runner.find_binary.return_value = None
    mock_runner.resolve_all_binaries.return_value = []
    mock_runner.read_env.return_value = None

    # Mock discovery methods
    mock_discovery = MagicMock()
    mock_discovery.discover_java_home.return_value = None
    mock_discovery.discover_android_sdk.return_value = None
    mock_discovery.discover_android_studio.return_value = None
    mock_runner.discovery = mock_discovery

    # Mock failed command execution
    mock_runner.run_command.return_value = CommandResult(
        command=["test"], exit_code=1, stdout="", stderr="not found", execution_time_ms=5
    )

    inspector = inspector_cls()

    # Patch platform-specific filesystem checks to avoid detecting local machine files
    with patch("pathlib.Path.is_file", return_value=False), \
         patch("pathlib.Path.is_dir", return_value=False), \
         patch("shutil.which", return_value=None):
        report = inspector.inspect(mock_runner)
        assert report.installed is False
        assert report.status == HealthStatus.NOT_FOUND


# ==============================================================================
# 3. DOMAIN-SPECIFIC CONDITION & DIAGNOSTIC BRANCH TESTS
# ==============================================================================

def test_python_missing_pip_warning():
    """Verify Python triggers WARNING and ensurepip fix when pip is absent."""
    mock_runner = MagicMock(spec=SafeRunner)
    mock_runner.resolve_binary.side_effect = lambda name, **kwargs: Path(r"C:\Python312\python.exe") if name in ["python", "python3"] else None
    mock_runner.run_command.side_effect = lambda cmd, **kwargs: (
        CommandResult(command=cmd, exit_code=0, stdout="Python 3.12.3\n", stderr="", execution_time_ms=5)
        if "--version" in cmd else CommandResult(command=cmd, exit_code=1, stdout="", stderr="", execution_time_ms=5)
    )

    inspector = PythonInspector()
    report = inspector.inspect(mock_runner)

    assert report.installed is True
    assert report.status == HealthStatus.WARNING
    assert any("pip package manager is not installed" in d.message for d in report.diagnostics)
    assert any("python -m ensurepip --upgrade" in (d.suggested_fix or "") for d in report.diagnostics)


def test_node_missing_npm_warning():
    """Verify Node triggers WARNING and corepack fix when npm is absent."""
    mock_runner = MagicMock(spec=SafeRunner)
    mock_runner.resolve_binary.side_effect = lambda name, **kwargs: Path(r"C:\Program Files\nodejs\node.exe") if name == "node" else None
    mock_runner.run_command.side_effect = lambda cmd, **kwargs: (
        CommandResult(command=cmd, exit_code=0, stdout="v22.12.0\n", stderr="", execution_time_ms=5)
    )

    inspector = NodeInspector()
    report = inspector.inspect(mock_runner)

    assert report.installed is True
    assert report.status == HealthStatus.WARNING
    assert any("npm package manager is not detected" in d.message for d in report.diagnostics)
    assert any("corepack enable" in (d.suggested_fix or "") for d in report.diagnostics)


def test_git_missing_user_identity_warning():
    """Verify Git triggers WARNING when user.name or user.email is missing."""
    mock_runner = MagicMock(spec=SafeRunner)
    mock_runner.resolve_binary.side_effect = lambda name, **kwargs: Path(r"C:\Program Files\Git\cmd\git.exe") if name == "git" else None
    
    def mock_run(cmd, **kwargs):
        cmd_str = " ".join(str(c) for c in cmd)
        if "--version" in cmd_str:
            return CommandResult(command=cmd, exit_code=0, stdout="git version 2.47.1.windows.1\n", stderr="", execution_time_ms=5)
        elif "user.name" in cmd_str:
            return CommandResult(command=cmd, exit_code=0, stdout="\n", stderr="", execution_time_ms=5)
        elif "user.email" in cmd_str:
            return CommandResult(command=cmd, exit_code=0, stdout="\n", stderr="", execution_time_ms=5)
        return CommandResult(command=cmd, exit_code=1, stdout="", stderr="", execution_time_ms=5)

    mock_runner.run_command.side_effect = mock_run

    inspector = GitInspector()
    report = inspector.inspect(mock_runner)

    assert report.installed is True
    assert report.status == HealthStatus.WARNING
    assert any("Global Git user identity" in d.message for d in report.diagnostics)


def test_docker_daemon_stopped_warning():
    """Verify Docker triggers WARNING when docker CLI exists but daemon is stopped."""
    mock_runner = MagicMock(spec=SafeRunner)
    mock_runner.resolve_binary.side_effect = lambda name, **kwargs: Path(r"C:\Program Files\Docker\Docker\resources\bin\docker.exe") if name == "docker" else None
    
    def mock_run(cmd, **kwargs):
        cmd_str = " ".join(str(c) for c in cmd)
        if "--version" in cmd_str:
            return CommandResult(command=cmd, exit_code=0, stdout="Docker version 27.0.3, build 7d4bed8\n", stderr="", execution_time_ms=5)
        elif "compose version" in cmd_str:
            return CommandResult(command=cmd, exit_code=0, stdout="v2.28.1\n", stderr="", execution_time_ms=5)
        elif "info" in cmd_str:
            # Daemon stopped: fails or does not contain "Server:"
            return CommandResult(command=cmd, exit_code=1, stdout="", stderr="error during connect", execution_time_ms=5)
        return CommandResult(command=cmd, exit_code=1, stdout="", stderr="", execution_time_ms=5)

    mock_runner.run_command.side_effect = mock_run

    inspector = DockerInspector()
    report = inspector.inspect(mock_runner)

    assert report.installed is True
    assert report.status == HealthStatus.WARNING
    assert any("Docker daemon" in d.message for d in report.diagnostics)


def test_java_broken_java_home_error():
    """Verify Java triggers ERROR when JAVA_HOME points to a non-existent path."""
    mock_runner = MagicMock(spec=SafeRunner)
    mock_runner.read_env.side_effect = lambda var: r"C:\NonExistent\JDK" if var == "JAVA_HOME" else None
    mock_runner.resolve_binary.return_value = Path(r"C:\Program Files\Java\jdk-21\bin\java.exe")
    mock_runner.discovery.discover_java_home.return_value = Path(r"C:\Program Files\Java\jdk-21")
    mock_runner.run_command.return_value = CommandResult(
        command=["java", "-version"], exit_code=0, stdout="", stderr='openjdk version "21.0.2" 2024-01-16\n', execution_time_ms=5
    )

    inspector = JavaInspector()

    def fake_exists(path_obj):
        return "NonExistent" not in str(path_obj)

    with patch.object(Path, "exists", fake_exists), \
         patch("shutil.which", return_value=r"C:\Program Files\Java\jdk-21\bin\java.exe"):
        report = inspector.inspect(mock_runner)
        assert report.installed is True
        assert any(d.level == DiagnosticLevel.ERROR and "does not exist on disk" in d.message for d in report.diagnostics)


def test_c_compiler_missing_cpp_warning():
    """Verify C compiler triggers WARNING when gcc is present but g++/clang++ are missing."""
    mock_runner = MagicMock(spec=SafeRunner)
    mock_runner.resolve_binary.side_effect = lambda name, **kwargs: (
        Path(r"C:\msys64\ucrt64\bin\gcc.exe") if name == "gcc" else None
    )
    mock_runner.run_command.side_effect = lambda cmd, **kwargs: (
        CommandResult(command=cmd, exit_code=0, stdout="gcc (Rev2) 14.2.0\n", stderr="", execution_time_ms=5)
    )

    inspector = CCompilerInspector()
    report = inspector.inspect(mock_runner)

    assert report.installed is True
    assert report.status == HealthStatus.WARNING
    assert any("C++ compiler (g++ / clang++) is not found" in d.message for d in report.diagnostics)


def test_cmake_missing_ninja_info_diagnostic():
    """Verify CMake adds INFO diagnostic and winget fix when Ninja is missing."""
    mock_runner = MagicMock(spec=SafeRunner)
    mock_runner.resolve_binary.side_effect = lambda name, **kwargs: (
        Path(r"C:\Program Files\CMake\bin\cmake.exe") if name == "cmake" else None
    )
    mock_runner.run_command.side_effect = lambda cmd, **kwargs: (
        CommandResult(command=cmd, exit_code=0, stdout="cmake version 3.31.2\n", stderr="", execution_time_ms=5)
    )

    inspector = CMakeInspector()
    report = inspector.inspect(mock_runner)

    assert report.installed is True
    assert report.status == HealthStatus.HEALTHY
    assert any("Ninja build generator is not installed" in d.message for d in report.diagnostics)
    assert any("Ninja-build.Ninja" in (d.suggested_fix or "") for d in report.diagnostics)


def test_vscode_cli_missing_from_path_warning():
    """Verify VS Code triggers WARNING when app is installed but CLI is absent from PATH."""
    mock_runner = MagicMock(spec=SafeRunner)
    mock_runner.resolve_binary.return_value = None  # CLI not on PATH
    mock_runner.run_command.return_value = CommandResult(
        command=["code", "--version"], exit_code=0, stdout="1.96.2\n", stderr="", execution_time_ms=5
    )

    inspector = VSCodeInspector()

    def fake_is_file(path_obj):
        return "Code.exe" in str(path_obj)

    # Simulate finding Code.exe in standard LocalAppData
    with patch("os.environ.get", return_value=r"C:\Users\test\AppData\Local"), \
         patch.object(Path, "is_file", fake_is_file), \
         patch.object(Path, "is_dir", return_value=True):
        report = inspector.inspect(mock_runner)
        assert report.installed is True
        assert report.status == HealthStatus.WARNING
        assert any("'code' command is not in system PATH" in d.message for d in report.diagnostics)
