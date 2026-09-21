"""Content Signature Matchers.

Identifies SDKs and development tools by their structural contents and binary signatures,
completely independent of directory names or drive letters.
"""

import sys
from pathlib import Path
from typing import Dict, List, Set

IGNORE_DIR_NAMES: Set[str] = {
    ".git",
    ".svn",
    ".hg",
    "node_modules",
    ".venv",
    "venv",
    "env",
    "__pycache__",
    "temp",
    "tmp",
    "$recycle.bin",
    "system volume information",
}


def is_android_sdk(path: Path) -> bool:
    """Check if directory is an Android SDK by structural signature."""
    try:
        adb_name = "adb.exe" if sys.platform == "win32" else "adb"
        has_adb = (path / "platform-tools" / adb_name).is_file()
        has_tools = (path / "build-tools").is_dir() or (path / "platforms").is_dir()
        return has_adb and has_tools
    except Exception:
        return False


def is_jdk(path: Path) -> bool:
    """Check if directory is a Java Development Kit by structural signature."""
    try:
        javac_name = "javac.exe" if sys.platform == "win32" else "javac"
        java_name = "java.exe" if sys.platform == "win32" else "java"
        has_javac = (path / "bin" / javac_name).is_file()
        has_java = (path / "bin" / java_name).is_file()
        if has_javac and has_java:
            return True

        release_file = path / "release"
        if release_file.is_file() and has_java:
            content = release_file.read_text(encoding="utf-8", errors="ignore")
            if "JAVA_VERSION" in content:
                return True
    except Exception:
        pass
    return False


def is_android_studio(path: Path) -> bool:
    """Check if directory is Android Studio IDE by structural signature."""
    try:
        prod_info = path / "product-info.json"
        if prod_info.is_file():
            content = prod_info.read_text(encoding="utf-8", errors="ignore")
            if '"productCode": "AI"' in content or "Android Studio" in content:
                return True

        bin_dir = path / "bin"
        if (bin_dir / "studio64.exe").is_file() or (bin_dir / "studio.sh").is_file():
            return True
    except Exception:
        pass
    return False


def is_flutter_sdk(path: Path) -> bool:
    """Check if directory is a Flutter SDK by structural signature."""
    try:
        flutter_bin = "flutter.bat" if sys.platform == "win32" else "flutter"
        has_bin = (path / "bin" / flutter_bin).is_file()
        has_pkg = (path / "packages" / "flutter").is_dir()
        return has_bin and has_pkg
    except Exception:
        return False


def is_rust_sdk(path: Path) -> bool:
    """Check if directory is a Rust toolchain by structural signature."""
    try:
        rustc_name = "rustc.exe" if sys.platform == "win32" else "rustc"
        cargo_name = "cargo.exe" if sys.platform == "win32" else "cargo"
        return (path / "bin" / rustc_name).is_file() and (path / "bin" / cargo_name).is_file()
    except Exception:
        return False


def is_go_sdk(path: Path) -> bool:
    """Check if directory is a Go SDK by structural signature."""
    try:
        go_name = "go.exe" if sys.platform == "win32" else "go"
        has_bin = (path / "bin" / go_name).is_file()
        has_pkg = (path / "pkg" / "tool").is_dir() or (path / "src" / "runtime").is_dir()
        return has_bin and has_pkg
    except Exception:
        return False


def is_dotnet_sdk(path: Path) -> bool:
    """Check if directory is a .NET SDK / Runtime installation."""
    try:
        dotnet_name = "dotnet.exe" if sys.platform == "win32" else "dotnet"
        has_bin = (path / dotnet_name).is_file()
        has_sub = (path / "sdk").is_dir() or (path / "shared").is_dir()
        return has_bin and has_sub
    except Exception:
        return False


def is_vscode(path: Path) -> bool:
    """Check if directory is a Visual Studio Code installation."""
    try:
        code_name = "Code.exe" if sys.platform == "win32" else "code"
        has_bin = (path / code_name).is_file() or (path / "bin" / "code.cmd").is_file()
        has_res = (path / "resources" / "app").is_dir()
        return has_bin and has_res
    except Exception:
        return False


def is_cmake(path: Path) -> bool:
    """Check if directory is a CMake installation."""
    try:
        cmake_name = "cmake.exe" if sys.platform == "win32" else "cmake"
        has_bin = (path / "bin" / cmake_name).is_file()
        has_share = (path / "share").is_dir()
        return has_bin and has_share
    except Exception:
        return False


def is_cuda_toolkit(path: Path) -> bool:
    """Check if directory is an NVIDIA CUDA Toolkit installation."""
    try:
        nvcc_name = "nvcc.exe" if sys.platform == "win32" else "nvcc"
        has_bin = (path / "bin" / nvcc_name).is_file()
        has_inc = (path / "include").is_dir()
        return has_bin and has_inc
    except Exception:
        return False


def is_php_sdk(path: Path) -> bool:
    """Check if directory is a PHP runtime installation."""
    try:
        php_name = "php.exe" if sys.platform == "win32" else "php"
        has_bin = (path / php_name).is_file()
        has_ext = (path / "ext").is_dir() or (path / "php.ini").is_file() or (path / "lib").is_dir()
        return has_bin and has_ext
    except Exception:
        return False


def is_mingw(path: Path) -> bool:
    """Check if directory is a MinGW / GCC C/C++ compiler installation."""
    try:
        gcc_name = "gcc.exe" if sys.platform == "win32" else "gcc"
        has_bin = (path / "bin" / gcc_name).is_file()
        has_inc = (path / "include").is_dir() or (path / "lib").is_dir()
        return has_bin and has_inc
    except Exception:
        return False


def is_python_sdk(path: Path) -> bool:
    """Check if directory is a Python runtime installation or virtualenv."""
    try:
        py_name = "python.exe" if sys.platform == "win32" else "python"
        has_py = (path / py_name).is_file() or (path / "Scripts" / py_name).is_file() or (path / "bin" / py_name).is_file()
        has_lib = (path / "Lib").is_dir() or (path / "lib").is_dir() or (path / "pyvenv.cfg").is_file()
        return has_py and has_lib
    except Exception:
        return False


def is_node_sdk(path: Path) -> bool:
    """Check if directory is a Node.js runtime installation."""
    try:
        node_name = "node.exe" if sys.platform == "win32" else "node"
        has_node = (path / node_name).is_file() or (path / "bin" / node_name).is_file()
        has_npm = (path / "node_modules" / "npm").is_dir() or (path / "npm.cmd").is_file() or (path / "bin" / "npm").is_file()
        return has_node and (has_npm or (path / "package.json").is_file())
    except Exception:
        return False


def is_git_install(path: Path) -> bool:
    """Check if directory is a Git installation."""
    try:
        git_name = "git.exe" if sys.platform == "win32" else "git"
        has_cmd = (path / "cmd" / git_name).is_file() or (path / "bin" / git_name).is_file() or (path / git_name).is_file()
        has_sub = (path / "usr").is_dir() or (path / "mingw64").is_dir() or (path / "etc").is_dir()
        return has_cmd and has_sub
    except Exception:
        return False


def is_docker_install(path: Path) -> bool:
    """Check if directory is Docker Desktop / CLI installation."""
    try:
        docker_name = "docker.exe" if sys.platform == "win32" else "docker"
        return (path / docker_name).is_file() or (path / "resources" / "bin" / docker_name).is_file()
    except Exception:
        return False


def is_kubectl_install(path: Path) -> bool:
    """Check if directory contains Kubernetes CLI."""
    try:
        k_name = "kubectl.exe" if sys.platform == "win32" else "kubectl"
        return (path / k_name).is_file() or (path / "bin" / k_name).is_file()
    except Exception:
        return False


def is_terraform_install(path: Path) -> bool:
    """Check if directory contains Terraform or OpenTofu."""
    try:
        tf_name = "terraform.exe" if sys.platform == "win32" else "terraform"
        tofu_name = "tofu.exe" if sys.platform == "win32" else "tofu"
        return (path / tf_name).is_file() or (path / tofu_name).is_file() or (path / "bin" / tf_name).is_file()
    except Exception:
        return False


def is_gh_install(path: Path) -> bool:
    """Check if directory contains GitHub CLI."""
    try:
        gh_name = "gh.exe" if sys.platform == "win32" else "gh"
        return (path / "bin" / gh_name).is_file() or (path / gh_name).is_file()
    except Exception:
        return False


def is_ollama_install(path: Path) -> bool:
    """Check if directory contains Ollama runtime."""
    try:
        ollama_name = "ollama.exe" if sys.platform == "win32" else "ollama"
        return (path / ollama_name).is_file() or (path / "lib" / "ollama").is_dir()
    except Exception:
        return False


def is_sqlite_install(path: Path) -> bool:
    """Check if directory contains SQLite CLI."""
    try:
        sqlite_name = "sqlite3.exe" if sys.platform == "win32" else "sqlite3"
        return (path / sqlite_name).is_file() or (path / "bin" / sqlite_name).is_file()
    except Exception:
        return False


def is_bun_install(path: Path) -> bool:
    """Check if directory contains Bun runtime."""
    try:
        bun_name = "bun.exe" if sys.platform == "win32" else "bun"
        return (path / "bin" / bun_name).is_file() or (path / bun_name).is_file()
    except Exception:
        return False


SIGNATURE_CHECKERS = {
    "android": is_android_sdk,
    "java": is_jdk,
    "android_studio": is_android_studio,
    "flutter": is_flutter_sdk,
    "rust": is_rust_sdk,
    "golang": is_go_sdk,
    "dotnet": is_dotnet_sdk,
    "vscode": is_vscode,
    "cmake": is_cmake,
    "cuda": is_cuda_toolkit,
    "php": is_php_sdk,
    "c_compiler": is_mingw,
    "python": is_python_sdk,
    "node": is_node_sdk,
    "git": is_git_install,
    "docker": is_docker_install,
    "kubectl": is_kubectl_install,
    "terraform": is_terraform_install,
    "gh": is_gh_install,
    "ollama": is_ollama_install,
    "sqlite": is_sqlite_install,
    "bun": is_bun_install,
}

TARGET_TOOL_BINARIES: Dict[str, List[str]] = {
    "adb.exe": ["android"],
    "adb": ["android"],
    "javac.exe": ["java"],
    "javac": ["java"],
    "java.exe": ["java"],
    "java": ["java"],
    "studio64.exe": ["android_studio"],
    "studio.sh": ["android_studio"],
    "flutter.bat": ["flutter"],
    "flutter": ["flutter"],
    "rustc.exe": ["rust"],
    "rustc": ["rust"],
    "cargo.exe": ["rust"],
    "cargo": ["rust"],
    "go.exe": ["golang"],
    "go": ["golang"],
    "dotnet.exe": ["dotnet"],
    "dotnet": ["dotnet"],
    "code.exe": ["vscode"],
    "code.cmd": ["vscode"],
    "code": ["vscode"],
    "cmake.exe": ["cmake"],
    "cmake": ["cmake"],
    "nvcc.exe": ["cuda"],
    "nvcc": ["cuda"],
    "php.exe": ["php"],
    "php": ["php"],
    "gcc.exe": ["c_compiler"],
    "gcc": ["c_compiler"],
    "clang.exe": ["c_compiler"],
    "clang": ["c_compiler"],
    "cl.exe": ["c_compiler"],
    "python.exe": ["python"],
    "python": ["python"],
    "node.exe": ["node"],
    "node": ["node"],
    "git.exe": ["git"],
    "git": ["git"],
    "docker.exe": ["docker"],
    "docker": ["docker"],
    "kubectl.exe": ["kubectl"],
    "kubectl": ["kubectl"],
    "terraform.exe": ["terraform"],
    "terraform": ["terraform"],
    "tofu.exe": ["terraform"],
    "tofu": ["terraform"],
    "gh.exe": ["gh"],
    "gh": ["gh"],
    "ollama.exe": ["ollama"],
    "ollama": ["ollama"],
    "sqlite3.exe": ["sqlite"],
    "sqlite3": ["sqlite"],
    "bun.exe": ["bun"],
    "bun": ["bun"],
}


def scan_roots_for_tools(roots: List[Path], max_depth: int = 6) -> Dict[str, List[Path]]:
    """Scan root directories using FastSearchEngine and classify directories by content signature."""
    from devtoolkit.core.search import FastSearchEngine

    results: Dict[str, List[Path]] = {key: [] for key in SIGNATURE_CHECKERS}
    valid_roots = [r.expanduser().resolve() for r in roots if r.exists() and r.is_dir()]
    if not valid_roots:
        return results

    # Tool binaries typically reside in subdirectories (bin/, platform-tools/) 1-2 levels below the SDK root
    crawler_depth = max_depth + 2
    engine = FastSearchEngine(max_depth=crawler_depth)
    engine.index_roots(valid_roots)

    matches = engine.find_exact_names(TARGET_TOOL_BINARIES.keys())

    for bin_name, search_results in matches.items():
        tool_ids = TARGET_TOOL_BINARIES.get(bin_name.lower(), [])
        for sr in search_results:
            file_path = sr.path_obj
            parent = file_path.parent
            grandparent = parent.parent
            candidates = [parent, grandparent]
            if len(grandparent.parts) > 1:
                candidates.append(grandparent.parent)

            for tool_id in tool_ids:
                checker = SIGNATURE_CHECKERS.get(tool_id)
                if not checker:
                    continue
                for cand in candidates:
                    try:
                        if cand not in results[tool_id] and checker(cand):
                            results[tool_id].append(cand)
                    except Exception:
                        pass

    return results
