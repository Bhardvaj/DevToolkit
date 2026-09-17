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
}


def scan_roots_for_tools(roots: List[Path], max_depth: int = 2) -> Dict[str, List[Path]]:
    """Scan root directories up to max_depth and classify directories by content signature."""
    results: Dict[str, List[Path]] = {key: [] for key in SIGNATURE_CHECKERS}

    for root in roots:
        root_path = root.expanduser().resolve()
        if not root_path.exists() or not root_path.is_dir():
            continue

        _scan_recursive(root_path, depth=0, max_depth=max_depth, results=results)

    return results


def _scan_recursive(current: Path, depth: int, max_depth: int, results: Dict[str, List[Path]]) -> None:
    for tool_id, checker in SIGNATURE_CHECKERS.items():
        if checker(current):
            if current not in results[tool_id]:
                results[tool_id].append(current)

    if depth >= max_depth:
        return

    try:
        for entry in current.iterdir():
            if entry.is_dir():
                if entry.name.lower() in IGNORE_DIR_NAMES or entry.name.startswith("."):
                    continue
                _scan_recursive(entry, depth + 1, max_depth, results)
    except (PermissionError, OSError):
        pass
