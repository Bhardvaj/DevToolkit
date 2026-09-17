"""Pluggable environment inspector modules."""

from devtoolkit.modules.inspectors.android import AndroidInspector
from devtoolkit.modules.inspectors.android_studio import AndroidStudioInspector
from devtoolkit.modules.inspectors.bun import BunInspector
from devtoolkit.modules.inspectors.cmake import CMakeInspector
from devtoolkit.modules.inspectors.docker import DockerInspector
from devtoolkit.modules.inspectors.dotnet import DotNetInspector
from devtoolkit.modules.inspectors.flutter import FlutterInspector
from devtoolkit.modules.inspectors.gh import GitHubCLIInspector
from devtoolkit.modules.inspectors.git import GitInspector
from devtoolkit.modules.inspectors.golang import GoInspector
from devtoolkit.modules.inspectors.java import JavaInspector
from devtoolkit.modules.inspectors.node import NodeInspector
from devtoolkit.modules.inspectors.ollama import OllamaInspector
from devtoolkit.modules.inspectors.python import PythonInspector
from devtoolkit.modules.inspectors.rust import RustInspector
from devtoolkit.modules.inspectors.vscode import VSCodeInspector

# Alias for backwards compatibility
GolangInspector = GoInspector

BUILTIN_INSPECTORS = [
    AndroidInspector,
    AndroidStudioInspector,
    BunInspector,
    CMakeInspector,
    DockerInspector,
    DotNetInspector,
    FlutterInspector,
    GitHubCLIInspector,
    GitInspector,
    GoInspector,
    JavaInspector,
    NodeInspector,
    OllamaInspector,
    PythonInspector,
    RustInspector,
    VSCodeInspector,
]
