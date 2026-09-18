"""Pluggable environment inspector modules."""

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

# Alias for backwards compatibility
GolangInspector = GoInspector

BUILTIN_INSPECTORS = [
    AndroidInspector,
    AndroidStudioInspector,
    BunInspector,
    CCompilerInspector,
    CMakeInspector,
    CudaInspector,
    DockerInspector,
    DotNetInspector,
    FlutterInspector,
    GitHubCLIInspector,
    GitInspector,
    GoInspector,
    JavaInspector,
    KubectlInspector,
    NodeInspector,
    OllamaInspector,
    PHPInspector,
    PythonInspector,
    RustInspector,
    SQLiteInspector,
    TerraformInspector,
    VSCodeInspector,
]
