"""Content Signature Matchers.

Identifies SDKs and development tools by their structural contents and binary signatures,
completely independent of directory names or drive letters.
"""

import sys
from pathlib import Path
from typing import Dict, List, Optional, Set

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
        has_tools = (
            (path / "build-tools").is_dir()
            or (path / "platforms").is_dir()
            or (path / "cmdline-tools").is_dir()
            or (path / "licenses").is_dir()
        )
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

        if has_java and ((path / "include").is_dir() or (path / "lib").is_dir() or (path / "jmods").is_dir()):
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
        if (
            (bin_dir / "studio64.exe").is_file()
            or (bin_dir / "studio.exe").is_file()
            or (bin_dir / "studio.sh").is_file()
        ):
            return True
    except Exception:
        pass
    return False


def is_flutter_sdk(path: Path) -> bool:
    """Check if directory is a Flutter SDK by structural signature."""
    try:
        flutter_bin = "flutter.bat" if sys.platform == "win32" else "flutter"
        has_bin = (path / "bin" / flutter_bin).is_file()
        has_pkg = (path / "packages" / "flutter").is_dir() or (path / "bin" / "cache").is_dir()
        return has_bin and has_pkg
    except Exception:
        return False


def is_rust_sdk(path: Path) -> bool:
    """Check if directory is a Rust toolchain by structural signature."""
    try:
        rustc_name = "rustc.exe" if sys.platform == "win32" else "rustc"
        cargo_name = "cargo.exe" if sys.platform == "win32" else "cargo"
        has_rustc = (path / "bin" / rustc_name).is_file() or (path / rustc_name).is_file()
        has_cargo = (path / "bin" / cargo_name).is_file() or (path / cargo_name).is_file()
        has_lib = (path / "lib" / "rustlib").is_dir() or (path / "etc").is_dir()
        return (has_rustc and has_cargo) or (has_rustc and has_lib)
    except Exception:
        return False


def is_go_sdk(path: Path) -> bool:
    """Check if directory is a Go SDK by structural signature."""
    try:
        go_name = "go.exe" if sys.platform == "win32" else "go"
        has_bin = (path / "bin" / go_name).is_file()
        has_pkg = (
            (path / "pkg" / "tool").is_dir()
            or (path / "src" / "runtime").is_dir()
            or (path / "pkg").is_dir()
        )
        return has_bin and has_pkg
    except Exception:
        return False


def is_dotnet_sdk(path: Path) -> bool:
    """Check if directory is a .NET SDK / Runtime installation."""
    try:
        dotnet_name = "dotnet.exe" if sys.platform == "win32" else "dotnet"
        has_bin = (path / dotnet_name).is_file()
        has_sub = (path / "sdk").is_dir() or (path / "shared").is_dir() or (path / "host").is_dir()
        return has_bin and has_sub
    except Exception:
        return False


def is_vscode(path: Path) -> bool:
    """Check if directory is a Visual Studio Code / VSCodium installation."""
    try:
        code_bins = [
            "Code.exe",
            "code.exe",
            "Code - Insiders.exe",
            "code-insiders.exe",
            "VSCodium.exe",
            "codium.exe",
            "code",
        ]
        has_bin = any((path / b).is_file() or (path / "bin" / b).is_file() for b in code_bins)
        has_cmd = (path / "bin" / "code.cmd").is_file() or (path / "bin" / "code-insiders.cmd").is_file() or (path / "bin" / "codium.cmd").is_file()
        has_res = (path / "resources" / "app").is_dir() or (path / "resources").is_dir() or (path / "locales").is_dir()
        return (has_bin or has_cmd) and has_res
    except Exception:
        return False


def is_cmake(path: Path) -> bool:
    """Check if directory is a CMake installation."""
    try:
        cmake_name = "cmake.exe" if sys.platform == "win32" else "cmake"
        has_bin = (path / "bin" / cmake_name).is_file() or (path / cmake_name).is_file()
        has_share = (
            (path / "share").is_dir()
            or (path / "doc").is_dir()
            or (path / "bin" / "ctest.exe").is_file()
            or (path / "bin" / "ctest").is_file()
        )
        return has_bin and has_share
    except Exception:
        return False


def is_cuda_toolkit(path: Path) -> bool:
    """Check if directory is an NVIDIA CUDA Toolkit installation."""
    try:
        nvcc_name = "nvcc.exe" if sys.platform == "win32" else "nvcc"
        has_bin = (path / "bin" / nvcc_name).is_file() or (path / nvcc_name).is_file()
        has_inc = (
            (path / "include").is_dir()
            or (path / "lib").is_dir()
            or (path / "nvvm").is_dir()
            or (path / "version.txt").is_file()
            or (path / "version.json").is_file()
        )
        return has_bin and has_inc
    except Exception:
        return False


def is_php_sdk(path: Path) -> bool:
    """Check if directory is a PHP runtime installation."""
    try:
        php_name = "php.exe" if sys.platform == "win32" else "php"
        has_bin = (path / php_name).is_file() or (path / "bin" / php_name).is_file()
        has_ext = (
            (path / "ext").is_dir()
            or (path / "php.ini").is_file()
            or (path / "php.ini-development").is_file()
            or (path / "lib").is_dir()
            or (path / "composer.bat").is_file()
            or (path / "composer.phar").is_file()
        )
        return has_bin and has_ext
    except Exception:
        return False


def is_c_compiler(path: Path) -> bool:
    """Check if directory is a C/C++ compiler toolchain (MinGW, Clang/LLVM, or MSVC)."""
    try:
        # MinGW / GCC
        gcc_names = ["gcc.exe", "gcc", "g++.exe", "g++"]
        has_gcc = any((path / "bin" / g).is_file() or (path / g).is_file() for g in gcc_names)
        has_mingw_support = (
            (path / "include").is_dir()
            or (path / "lib").is_dir()
            or (path / "libexec").is_dir()
            or (path / "mingw64").is_dir()
        )
        if has_gcc and has_mingw_support:
            return True

        # Clang / LLVM
        clang_names = ["clang.exe", "clang", "clang++.exe", "clang++"]
        has_clang = any((path / "bin" / c).is_file() or (path / c).is_file() for c in clang_names)
        if has_clang and ((path / "include").is_dir() or (path / "lib").is_dir()):
            return True

        # MSVC (Visual Studio / Build Tools VC directory)
        cl_name = "cl.exe" if sys.platform == "win32" else "cl"
        if (
            (path / cl_name).is_file()
            or (path / "bin" / cl_name).is_file()
            or (path / "vcvarsall.bat").is_file()
            or (path / "VC" / "Auxiliary" / "Build" / "vcvarsall.bat").is_file()
        ):
            return True

        # Check MSVC subfolder Hostx64/x64
        if any(path.glob("bin/Host*/*/cl.exe")):
            return True
    except Exception:
        return False
    return False


# Alias for backward compatibility
is_mingw = is_c_compiler


def is_python_sdk(path: Path) -> bool:
    """Check if directory is a Python runtime installation or virtualenv."""
    try:
        py_names = ["python.exe", "python", "python3.exe", "python3"]
        has_py = any(
            (path / p).is_file()
            or (path / "Scripts" / p).is_file()
            or (path / "bin" / p).is_file()
            for p in py_names
        )
        has_lib = (
            (path / "Lib").is_dir()
            or (path / "lib").is_dir()
            or (path / "pyvenv.cfg").is_file()
            or (path / "include").is_dir()
            or (path / "DLLs").is_dir()
        )
        return has_py and has_lib
    except Exception:
        return False


def is_node_sdk(path: Path) -> bool:
    """Check if directory is a Node.js runtime installation."""
    try:
        node_name = "node.exe" if sys.platform == "win32" else "node"
        has_node = (path / node_name).is_file() or (path / "bin" / node_name).is_file()
        has_npm = (
            (path / "node_modules" / "npm").is_dir()
            or (path / "npm.cmd").is_file()
            or (path / "bin" / "npm").is_file()
            or (path / "npm").is_file()
            or (path / "package.json").is_file()
        )
        return has_node and has_npm
    except Exception:
        return False


def is_git_install(path: Path) -> bool:
    """Check if directory is a Git installation."""
    try:
        git_name = "git.exe" if sys.platform == "win32" else "git"
        has_cmd = (
            (path / "cmd" / git_name).is_file()
            or (path / "bin" / git_name).is_file()
            or (path / git_name).is_file()
        )
        has_sub = (
            (path / "usr").is_dir()
            or (path / "mingw64").is_dir()
            or (path / "etc").is_dir()
            or (path / "cmd").is_dir()
            or (path / "share" / "git-core").is_dir()
        )
        return has_cmd and has_sub
    except Exception:
        return False


def is_docker_install(path: Path) -> bool:
    """Check if directory is Docker Desktop / CLI installation."""
    try:
        docker_name = "docker.exe" if sys.platform == "win32" else "docker"
        return (
            (path / docker_name).is_file()
            or (path / "resources" / "bin" / docker_name).is_file()
            or (path / "bin" / docker_name).is_file()
            or (path / "Docker Desktop.exe").is_file()
            or (path / "Docker for Windows").is_dir()
        )
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
        return (
            (path / tf_name).is_file()
            or (path / tofu_name).is_file()
            or (path / "bin" / tf_name).is_file()
            or (path / "bin" / tofu_name).is_file()
        )
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
        return (
            (path / ollama_name).is_file()
            or (path / "bin" / ollama_name).is_file()
            or (path / "ollama app.exe").is_file()
            or (path / "lib" / "ollama").is_dir()
        )
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
    "c_compiler": is_c_compiler,
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
    # 1. Android
    "adb.exe": ["android"],
    "adb": ["android"],
    "emulator.exe": ["android"],
    "emulator": ["android"],
    "sdkmanager.bat": ["android"],
    "sdkmanager": ["android"],
    "avdmanager.bat": ["android"],
    "avdmanager": ["android"],
    "fastboot.exe": ["android"],
    "fastboot": ["android"],

    # 2. Java / JDK
    "javac.exe": ["java"],
    "javac": ["java"],
    "java.exe": ["java"],
    "java": ["java"],
    "javap.exe": ["java"],
    "javap": ["java"],
    "jar.exe": ["java"],
    "jar": ["java"],
    "jshell.exe": ["java"],
    "jshell": ["java"],

    # 3. Android Studio
    "studio64.exe": ["android_studio"],
    "studio.exe": ["android_studio"],
    "studio.sh": ["android_studio"],

    # 4. Flutter
    "flutter.bat": ["flutter"],
    "flutter": ["flutter"],
    "dart.bat": ["flutter"],
    "dart.exe": ["flutter"],
    "dart": ["flutter"],

    # 5. Rust
    "rustc.exe": ["rust"],
    "rustc": ["rust"],
    "cargo.exe": ["rust"],
    "cargo": ["rust"],
    "rustup.exe": ["rust"],
    "rustup": ["rust"],

    # 6. Go
    "go.exe": ["golang"],
    "go": ["golang"],
    "gofmt.exe": ["golang"],
    "gofmt": ["golang"],

    # 7. .NET
    "dotnet.exe": ["dotnet"],
    "dotnet": ["dotnet"],

    # 8. Visual Studio Code
    "code.exe": ["vscode"],
    "code.cmd": ["vscode"],
    "code": ["vscode"],
    "code - insiders.exe": ["vscode"],
    "code-insiders.exe": ["vscode"],
    "code-insiders.cmd": ["vscode"],
    "codium.exe": ["vscode"],
    "codium.cmd": ["vscode"],
    "codium": ["vscode"],

    # 9. CMake
    "cmake.exe": ["cmake"],
    "cmake": ["cmake"],
    "ctest.exe": ["cmake"],
    "ctest": ["cmake"],
    "cpack.exe": ["cmake"],
    "cpack": ["cmake"],
    "cmake-gui.exe": ["cmake"],

    # 10. CUDA
    "nvcc.exe": ["cuda"],
    "nvcc": ["cuda"],

    # 11. PHP
    "php.exe": ["php"],
    "php": ["php"],
    "composer.bat": ["php"],
    "composer": ["php"],

    # 12. C/C++ Compiler
    "gcc.exe": ["c_compiler"],
    "gcc": ["c_compiler"],
    "g++.exe": ["c_compiler"],
    "g++": ["c_compiler"],
    "clang.exe": ["c_compiler"],
    "clang": ["c_compiler"],
    "clang++.exe": ["c_compiler"],
    "clang++": ["c_compiler"],
    "cl.exe": ["c_compiler"],
    "mingw32-make.exe": ["c_compiler"],

    # 13. Python
    "python.exe": ["python"],
    "python": ["python"],
    "python3.exe": ["python"],
    "python3": ["python"],
    "py.exe": ["python"],
    "pypy.exe": ["python"],
    "pypy3.exe": ["python"],

    # 14. Node.js
    "node.exe": ["node"],
    "node": ["node"],
    "npm.cmd": ["node"],
    "npm": ["node"],
    "npx.cmd": ["node"],
    "npx": ["node"],
    "corepack.cmd": ["node"],
    "corepack": ["node"],

    # 15. Git
    "git.exe": ["git"],
    "git": ["git"],
    "git-bash.exe": ["git"],
    "git-cmd.exe": ["git"],

    # 16. Docker
    "docker.exe": ["docker"],
    "docker": ["docker"],
    "dockerd.exe": ["docker"],
    "dockerd": ["docker"],
    "docker-compose.exe": ["docker"],
    "docker-compose": ["docker"],
    "docker desktop.exe": ["docker"],

    # 17. Kubectl
    "kubectl.exe": ["kubectl"],
    "kubectl": ["kubectl"],

    # 18. Terraform / OpenTofu
    "terraform.exe": ["terraform"],
    "terraform": ["terraform"],
    "tofu.exe": ["terraform"],
    "tofu": ["terraform"],

    # 19. GitHub CLI
    "gh.exe": ["gh"],
    "gh": ["gh"],

    # 20. Ollama
    "ollama.exe": ["ollama"],
    "ollama": ["ollama"],
    "ollama app.exe": ["ollama"],

    # 21. SQLite
    "sqlite3.exe": ["sqlite"],
    "sqlite3": ["sqlite"],

    # 22. Bun
    "bun.exe": ["bun"],
    "bun": ["bun"],
    "bunx.exe": ["bun"],
    "bunx": ["bun"],
}


def scan_roots_for_tools(roots: List[Path], max_depth: Optional[int] = None) -> Dict[str, List[Path]]:
    """Scan root directories using FastSearchEngine and classify directories by content signature."""
    from devtoolkit.core.search import get_search_engine

    results: Dict[str, List[Path]] = {key: [] for key in SIGNATURE_CHECKERS}
    valid_roots = [r.expanduser().resolve() for r in roots if r.exists() and r.is_dir()]
    if not valid_roots:
        return results

    engine = get_search_engine()
    # If engine is actively indexing in background, wait for it to complete
    if engine.is_indexing:
        engine.wait_until_indexed(timeout=10.0)

    # Check if engine is already warm and indexing all valid_roots
    all_covered = not engine.is_indexing and engine.total_entries > 0 and bool(engine.roots) and all(
        any(str(vr).lower() == str(er).lower() for er in engine.roots)
        for vr in valid_roots
    )
    if not all_covered:
        engine.index_roots(valid_roots)

    matches = engine.find_exact_names(TARGET_TOOL_BINARIES.keys())

    for bin_name, search_results in matches.items():
        tool_ids = TARGET_TOOL_BINARIES.get(bin_name.lower(), [])
        for sr in search_results:
            file_path = sr.path_obj
            # Ensure file_path actually resides under one of the requested roots
            try:
                fp_resolved = file_path.resolve()
                if not any(fp_resolved == vr or vr in fp_resolved.parents for vr in valid_roots):
                    continue
            except Exception:
                continue

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
                        cand_resolved = cand.resolve()
                        if cand_resolved not in results[tool_id] and checker(cand_resolved):
                            results[tool_id].append(cand_resolved)
                    except Exception:
                        pass

    return results
