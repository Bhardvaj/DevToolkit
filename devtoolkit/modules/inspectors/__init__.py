"""Pluggable environment inspector modules."""

from devtoolkit.modules.inspectors.android import AndroidInspector
from devtoolkit.modules.inspectors.android_studio import AndroidStudioInspector
from devtoolkit.modules.inspectors.docker import DockerInspector
from devtoolkit.modules.inspectors.flutter import FlutterInspector
from devtoolkit.modules.inspectors.git import GitInspector
from devtoolkit.modules.inspectors.golang import GoInspector
from devtoolkit.modules.inspectors.java import JavaInspector
from devtoolkit.modules.inspectors.node import NodeInspector
from devtoolkit.modules.inspectors.python import PythonInspector
from devtoolkit.modules.inspectors.rust import RustInspector

# Alias for backwards compatibility
GolangInspector = GoInspector

BUILTIN_INSPECTORS = [
    AndroidInspector,
    AndroidStudioInspector,
    DockerInspector,
    FlutterInspector,
    GitInspector,
    GoInspector,
    JavaInspector,
    NodeInspector,
    PythonInspector,
    RustInspector,
]
