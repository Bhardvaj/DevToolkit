"""Unified 4-Layer Discovery Pipeline.

Provides a generalized, portable discovery engine that coordinates:
1. Standard OS environment & PATH
2. Dynamic OS application inventory (Windows Registry / Uninstall)
3. Cross-tool ecosystem configs (IDE configs, runtime managers, standard locations)
4. User-configured search roots & content signature scanning via FastSearchEngine
"""

import glob
import os
import sys
import threading
from pathlib import Path
from typing import Callable, Dict, List, Optional

from devtoolkit.core.config import load_config
from devtoolkit.core.ecosystem import EcosystemResolvers
from devtoolkit.core.inventory import OSInventory
from devtoolkit.core.runner import SafeRunner
from devtoolkit.core.signatures import SIGNATURE_CHECKERS, TARGET_TOOL_BINARIES, scan_roots_for_tools


class DiscoveryPipeline:
    """Coordinates layered discovery across all 22 supported tools without hardcoding custom machine paths."""

    def __init__(self, runner: Optional[SafeRunner] = None):
        self.runner = runner or SafeRunner()
        self._user_config = load_config()
        self._user_scan_cache: Optional[Dict[str, List[Path]]] = None
        self._scan_lock = threading.Lock()

    def _get_user_scanned_tools(self) -> Dict[str, List[Path]]:
        """Query user search roots or warm search engine index for tool signatures."""
        if self._user_scan_cache is not None:
            return self._user_scan_cache

        with self._scan_lock:
            if self._user_scan_cache is None:
                config = self._user_config or load_config()
                roots_to_scan = [
                    Path(p).expanduser().resolve()
                    for p in config.search_paths
                    if Path(p).exists() and Path(p).is_dir()
                ]
                if not roots_to_scan:
                    try:
                        from devtoolkit.core.search import get_search_engine
                        engine = get_search_engine()
                        if engine.roots:
                            roots_to_scan = [r for r in engine.roots if r.exists() and r.is_dir()]
                    except Exception:
                        pass

                self._user_scan_cache = scan_roots_for_tools(roots_to_scan) if roots_to_scan else {}
            return self._user_scan_cache

    def clear_scan_cache(self) -> None:
        """Invalidate in-memory discovery scan cache."""
        with self._scan_lock:
            self._user_scan_cache = None

    # =========================================================================
    # Specialized 4-Layer Tool Resolvers
    # =========================================================================

    def discover_android_sdk(self) -> Optional[Path]:
        """Discover Android SDK using 4-layer resolution."""
        # Layer 1: Standard Environment Variables
        for var in ["ANDROID_HOME", "ANDROID_SDK_ROOT"]:
            val = self.runner.read_env(var)
            if val:
                p = Path(val).resolve()
                if p.exists():
                    return p

        # Layer 1: Default OS Locations
        local_app_data = self.runner.read_env("LOCALAPPDATA")
        if local_app_data:
            default_sdk = Path(local_app_data) / "Android" / "Sdk"
            if default_sdk.exists():
                return default_sdk.resolve()

        home_sdk = Path.home() / "Android" / "Sdk"
        if home_sdk.exists():
            return home_sdk.resolve()

        # Layer 3: Cross-Tool Ecosystem (Android Studio config & Flutter config)
        studio_sdk = EcosystemResolvers.resolve_android_sdk_from_studio()
        if studio_sdk and studio_sdk.exists():
            return studio_sdk

        flutter_ecosystem = EcosystemResolvers.resolve_from_flutter(self.runner)
        if flutter_ecosystem.get("android_sdk") and flutter_ecosystem["android_sdk"].exists():
            return flutter_ecosystem["android_sdk"]

        # Layer 4: User-Configured Search Paths via Content Signature
        scanned = self._get_user_scanned_tools().get("android", [])
        if scanned:
            return scanned[0]

        return None

    def discover_android_studio(self) -> Optional[Path]:
        """Discover Android Studio IDE using 4-layer resolution."""
        # Layer 2: Dynamic OS Application Inventory (Windows Registry / Uninstall)
        studio_locations = OSInventory.find_app_locations("Android Studio")
        if studio_locations:
            return studio_locations[0]

        # Layer 3: Cross-Tool Ecosystem (Flutter config)
        flutter_ecosystem = EcosystemResolvers.resolve_from_flutter(self.runner)
        if flutter_ecosystem.get("android_studio") and flutter_ecosystem["android_studio"].exists():
            return flutter_ecosystem["android_studio"]

        # Layer 3: Well-known locations
        for prog in [os.environ.get("ProgramFiles"), os.environ.get("ProgramFiles(x86)"), os.environ.get("LOCALAPPDATA")]:
            if prog:
                cand = Path(prog) / "Android" / "Android Studio"
                if cand.exists() and (cand / "bin").exists():
                    return cand.resolve()

        # Layer 4: User-Configured Search Paths via Content Signature
        scanned = self._get_user_scanned_tools().get("android_studio", [])
        if scanned:
            return scanned[0]

        return None

    def discover_java_home(self) -> Optional[Path]:
        """Discover Java / JDK installation directory using 4-layer resolution."""
        # Layer 1: JAVA_HOME Environment Variable
        java_home_val = self.runner.read_env("JAVA_HOME")
        if java_home_val:
            p = Path(java_home_val).resolve()
            if p.exists():
                return p

        # Layer 1: Windows Registry JavaSoft keys
        for key_path in [r"SOFTWARE\JavaSoft\JDK", r"SOFTWARE\JavaSoft\Java Development Kit"]:
            reg_home = self.runner.query_winreg(key_path, "JavaHome")
            if reg_home:
                p = Path(reg_home).resolve()
                if p.exists():
                    return p

        # Layer 2: Dynamic OS Application Inventory (JDK / Java Uninstall entries)
        for query in ["JDK", "Java SE Development Kit", "Eclipse Adoptium", "Amazon Corretto", "Zulu", "Temurin"]:
            jdk_locations = OSInventory.find_app_locations(query)
            if jdk_locations:
                return jdk_locations[0]

        # Layer 3: Cross-Tool Ecosystem (Gradle config & Flutter config)
        gradle_java = EcosystemResolvers.resolve_from_gradle()
        if gradle_java and gradle_java.exists():
            return gradle_java

        flutter_ecosystem = EcosystemResolvers.resolve_from_flutter(self.runner)
        if flutter_ecosystem.get("jdk_dir") and flutter_ecosystem["jdk_dir"].exists():
            return flutter_ecosystem["jdk_dir"]

        # Layer 3: Bundled JDK inside discovered Android Studio installation
        studio_dir = self.discover_android_studio()
        if studio_dir:
            for sub in ["jbr", "jre"]:
                cand = studio_dir / sub
                if cand.exists() and (cand / "bin").exists():
                    return cand.resolve()

        # Layer 4: User-Configured Search Paths via Content Signature
        scanned = self._get_user_scanned_tools().get("java", [])
        if scanned:
            return scanned[0]

        return None

    def discover_flutter_sdk(self) -> Optional[Path]:
        """Discover Flutter SDK root using 4-layer resolution."""
        # Layer 1: System PATH
        flutter_bin = self.runner.resolve_binary("flutter") or self.runner.resolve_binary("flutter.bat")
        if flutter_bin:
            return flutter_bin.parent.parent.resolve()

        # Layer 3: Common developer paths
        for root_prefix in [Path.home(), Path("C:/"), Path("D:/")]:
            for folder in ["flutter", "tools/flutter", "dev/flutter", "development/flutter"]:
                cand = root_prefix / folder
                if cand.exists() and (cand / "bin" / "flutter.bat").exists():
                    return cand.resolve()

        # Layer 4: User-Configured Search Paths via Content Signature
        scanned = self._get_user_scanned_tools().get("flutter", [])
        if scanned:
            return scanned[0]

        return None

    def discover_python(self) -> Optional[Path]:
        """Discover Python root directory."""
        # Layer 1: System PATH
        py_bin = self.runner.resolve_binary("python") or self.runner.resolve_binary("py")
        if py_bin:
            return (py_bin.parent if py_bin.parent.name != "Scripts" else py_bin.parent.parent).resolve()

        # Layer 1: Environment variables
        py_home = self.runner.read_env("PYTHONHOME")
        if py_home and Path(py_home).is_dir():
            return Path(py_home).resolve()

        # Layer 2: Windows Registry PythonCore InstallPath
        if sys.platform == "win32":
            for ver in ["3.14", "3.13", "3.12", "3.11", "3.10", "3.9"]:
                reg_p = self.runner.query_winreg(rf"SOFTWARE\Python\PythonCore\{ver}\InstallPath", "")
                if reg_p and Path(reg_p).is_dir():
                    return Path(reg_p).resolve()

        # Layer 3: Standard Windows Python directories
        local_app = os.environ.get("LOCALAPPDATA")
        if local_app:
            base = Path(local_app) / "Programs" / "Python"
            if base.is_dir():
                subdirs = sorted(base.glob("Python*"), reverse=True)
                if subdirs and subdirs[0].is_dir():
                    return subdirs[0].resolve()

        # Layer 4: FastSearchEngine Content Signature
        scanned = self._get_user_scanned_tools().get("python", [])
        if scanned:
            return scanned[0]

        return None

    def discover_node(self) -> Optional[Path]:
        """Discover Node.js root directory."""
        # Layer 1: System PATH
        node_bin = self.runner.resolve_binary("node")
        if node_bin:
            return (node_bin.parent if node_bin.parent.name != "bin" else node_bin.parent.parent).resolve()

        # Layer 2: Dynamic OS Inventory
        node_locs = OSInventory.find_app_locations("Node.js")
        if node_locs:
            return node_locs[0]

        # Layer 3: NVM / standard paths
        app_data = os.environ.get("APPDATA")
        if app_data:
            nvm_dir = Path(app_data) / "nvm"
            if nvm_dir.is_dir():
                vers = sorted(nvm_dir.glob("v*"), reverse=True)
                if vers and vers[0].is_dir():
                    return vers[0].resolve()

        prog = os.environ.get("ProgramFiles")
        if prog:
            cand = Path(prog) / "nodejs"
            if cand.is_dir():
                return cand.resolve()

        # Layer 4: Content Signature
        scanned = self._get_user_scanned_tools().get("node", [])
        if scanned:
            return scanned[0]

        return None

    def discover_rust(self) -> Optional[Path]:
        """Discover Rust toolchain root directory."""
        # Layer 1: System PATH
        rustc_bin = self.runner.resolve_binary("rustc")
        if rustc_bin:
            return (rustc_bin.parent.parent if rustc_bin.parent.name == "bin" else rustc_bin.parent).resolve()

        # Layer 3: Cargo home
        cargo_home = Path.home() / ".cargo"
        if (cargo_home / "bin" / ("rustc.exe" if sys.platform == "win32" else "rustc")).is_file():
            return cargo_home.resolve()

        # Layer 4: Content Signature
        scanned = self._get_user_scanned_tools().get("rust", [])
        if scanned:
            return scanned[0]

        return None

    def discover_golang(self) -> Optional[Path]:
        """Discover Go SDK root directory."""
        # Layer 1: GOROOT and PATH
        goroot = self.runner.read_env("GOROOT")
        if goroot and Path(goroot).is_dir():
            return Path(goroot).resolve()

        go_bin = self.runner.resolve_binary("go")
        if go_bin:
            return (go_bin.parent.parent if go_bin.parent.name == "bin" else go_bin.parent).resolve()

        # Layer 2: Dynamic OS Inventory
        go_locs = OSInventory.find_app_locations("Go Programming Language")
        if go_locs:
            return go_locs[0]

        # Layer 3: Standard locations
        for cand_str in ["C:/Go", os.path.join(os.environ.get("ProgramFiles", ""), "Go")]:
            cand = Path(cand_str)
            if cand.is_dir() and (cand / "bin").exists():
                return cand.resolve()

        # Layer 4: Content Signature
        scanned = self._get_user_scanned_tools().get("golang", [])
        if scanned:
            return scanned[0]

        return None

    def discover_dotnet(self) -> Optional[Path]:
        """Discover .NET SDK / runtime root directory."""
        # Layer 1: DOTNET_ROOT and PATH
        dotnet_root = self.runner.read_env("DOTNET_ROOT")
        if dotnet_root and Path(dotnet_root).is_dir():
            return Path(dotnet_root).resolve()

        dotnet_bin = self.runner.resolve_binary("dotnet")
        if dotnet_bin:
            return dotnet_bin.parent.resolve()

        # Layer 3: Standard locations
        prog = os.environ.get("ProgramFiles")
        if prog:
            cand = Path(prog) / "dotnet"
            if cand.is_dir() and (cand / "dotnet.exe").exists():
                return cand.resolve()

        # Layer 4: Content Signature
        scanned = self._get_user_scanned_tools().get("dotnet", [])
        if scanned:
            return scanned[0]

        return None

    def discover_c_compiler(self) -> Optional[Path]:
        """Discover C/C++ compiler toolchain root directory (MinGW, Clang, or MSVC)."""
        # Layer 1: PATH
        for c_bin in ["gcc", "clang", "cl"]:
            resolved = self.runner.resolve_binary(c_bin)
            if resolved:
                return (resolved.parent.parent if resolved.parent.name == "bin" else resolved.parent).resolve()

        # Layer 3: MSYS2 default installations
        for msys in ["C:/msys64/ucrt64", "C:/msys64/mingw64", "C:/msys64/clang64"]:
            cand = Path(msys)
            if cand.is_dir() and (cand / "bin" / ("gcc.exe" if sys.platform == "win32" else "gcc")).is_file():
                return cand.resolve()

        # Layer 3: LLVM default directory
        prog = os.environ.get("ProgramFiles")
        if prog:
            cand = Path(prog) / "LLVM"
            if cand.is_dir() and (cand / "bin").exists():
                return cand.resolve()

        # Layer 4: Content Signature
        scanned = self._get_user_scanned_tools().get("c_compiler", [])
        if scanned:
            return scanned[0]

        return None

    def discover_cmake(self) -> Optional[Path]:
        """Discover CMake root directory."""
        # Layer 1: PATH
        cmake_bin = self.runner.resolve_binary("cmake")
        if cmake_bin:
            return (cmake_bin.parent.parent if cmake_bin.parent.name == "bin" else cmake_bin.parent).resolve()

        # Layer 2: Dynamic OS Inventory
        cmake_locs = OSInventory.find_app_locations("CMake")
        if cmake_locs:
            return cmake_locs[0]

        # Layer 3: Standard Program Files
        prog = os.environ.get("ProgramFiles")
        if prog:
            cand = Path(prog) / "CMake"
            if cand.is_dir() and (cand / "bin").exists():
                return cand.resolve()

        # Layer 4: Content Signature
        scanned = self._get_user_scanned_tools().get("cmake", [])
        if scanned:
            return scanned[0]

        return None

    def discover_cuda(self) -> Optional[Path]:
        """Discover NVIDIA CUDA Toolkit root directory."""
        # Layer 1: CUDA_PATH and PATH
        cuda_path = self.runner.read_env("CUDA_PATH")
        if cuda_path and Path(cuda_path).is_dir():
            return Path(cuda_path).resolve()

        nvcc_bin = self.runner.resolve_binary("nvcc")
        if nvcc_bin:
            return (nvcc_bin.parent.parent if nvcc_bin.parent.name == "bin" else nvcc_bin.parent).resolve()

        # Layer 3: Standard NVIDIA Program Files
        prog = os.environ.get("ProgramFiles")
        if prog:
            base = Path(prog) / "NVIDIA GPU Computing Toolkit" / "CUDA"
            if base.is_dir():
                vers = sorted(base.glob("v*"), reverse=True)
                if vers and vers[0].is_dir():
                    return vers[0].resolve()

        # Layer 4: Content Signature
        scanned = self._get_user_scanned_tools().get("cuda", [])
        if scanned:
            return scanned[0]

        return None

    def discover_php(self) -> Optional[Path]:
        """Discover PHP runtime root directory."""
        # Layer 1: PHP_HOME and PATH
        php_home = self.runner.read_env("PHP_HOME")
        if php_home and Path(php_home).is_dir():
            return Path(php_home).resolve()

        php_bin = self.runner.resolve_binary("php")
        if php_bin:
            return (php_bin.parent if php_bin.parent.name != "bin" else php_bin.parent.parent).resolve()

        # Layer 3: Standard XAMPP / Laragon / standalone PHP paths
        for cand_str in ["C:/php", "C:/tools/php", "C:/xampp/php"]:
            cand = Path(cand_str)
            if cand.is_dir() and (cand / "php.exe").is_file():
                return cand.resolve()

        # Layer 4: Content Signature
        scanned = self._get_user_scanned_tools().get("php", [])
        if scanned:
            return scanned[0]

        return None

    def discover_git(self) -> Optional[Path]:
        """Discover Git installation root directory."""
        # Layer 1: PATH
        git_bin = self.runner.resolve_binary("git")
        if git_bin:
            parent = git_bin.parent
            return (parent.parent if parent.name in ["cmd", "bin"] else parent).resolve()

        # Layer 2: Dynamic OS Inventory / Registry
        reg_git = self.runner.query_winreg(r"SOFTWARE\GitForWindows", "InstallPath")
        if reg_git and Path(reg_git).is_dir():
            return Path(reg_git).resolve()

        git_locs = OSInventory.find_app_locations("Git")
        if git_locs:
            return git_locs[0]

        # Layer 3: Standard locations
        prog = os.environ.get("ProgramFiles")
        if prog:
            cand = Path(prog) / "Git"
            if cand.is_dir():
                return cand.resolve()

        # Layer 4: Content Signature
        scanned = self._get_user_scanned_tools().get("git", [])
        if scanned:
            return scanned[0]

        return None

    def discover_docker(self) -> Optional[Path]:
        """Discover Docker installation root directory."""
        # Layer 1: PATH
        docker_bin = self.runner.resolve_binary("docker")
        if docker_bin:
            parent = docker_bin.parent
            return (parent.parent if parent.name in ["bin", "resources"] else parent).resolve()

        # Layer 2: Dynamic OS Inventory
        doc_locs = OSInventory.find_app_locations("Docker Desktop")
        if doc_locs:
            return doc_locs[0]

        # Layer 3: Standard Program Files
        prog = os.environ.get("ProgramFiles")
        if prog:
            cand = Path(prog) / "Docker" / "Docker"
            if cand.is_dir():
                return cand.resolve()

        # Layer 4: Content Signature
        scanned = self._get_user_scanned_tools().get("docker", [])
        if scanned:
            return scanned[0]

        return None

    def discover_kubectl(self) -> Optional[Path]:
        """Discover Kubernetes CLI root directory."""
        # Layer 1: PATH
        k_bin = self.runner.resolve_binary("kubectl")
        if k_bin:
            return (k_bin.parent if k_bin.parent.name != "bin" else k_bin.parent.parent).resolve()

        # Layer 3: ~/.kube or standard tools
        for cand_str in ["C:/tools/kubectl", "C:/bin"]:
            cand = Path(cand_str)
            if cand.is_dir() and (cand / "kubectl.exe").is_file():
                return cand.resolve()

        # Layer 4: Content Signature
        scanned = self._get_user_scanned_tools().get("kubectl", [])
        if scanned:
            return scanned[0]

        return None

    def discover_terraform(self) -> Optional[Path]:
        """Discover Terraform / OpenTofu root directory."""
        # Layer 1: PATH
        tf_bin = self.runner.resolve_binary("terraform") or self.runner.resolve_binary("tofu")
        if tf_bin:
            return (tf_bin.parent if tf_bin.parent.name != "bin" else tf_bin.parent.parent).resolve()

        # Layer 3: Standard tools
        for cand_str in ["C:/terraform", "C:/tools/terraform", "C:/bin"]:
            cand = Path(cand_str)
            if cand.is_dir() and ((cand / "terraform.exe").is_file() or (cand / "tofu.exe").is_file()):
                return cand.resolve()

        # Layer 4: Content Signature
        scanned = self._get_user_scanned_tools().get("terraform", [])
        if scanned:
            return scanned[0]

        return None

    def discover_gh(self) -> Optional[Path]:
        """Discover GitHub CLI root directory."""
        # Layer 1: PATH
        gh_bin = self.runner.resolve_binary("gh")
        if gh_bin:
            return (gh_bin.parent.parent if gh_bin.parent.name == "bin" else gh_bin.parent).resolve()

        # Layer 2: Dynamic OS Inventory
        gh_locs = OSInventory.find_app_locations("GitHub CLI")
        if gh_locs:
            return gh_locs[0]

        # Layer 3: Standard Program Files
        prog = os.environ.get("ProgramFiles")
        if prog:
            cand = Path(prog) / "GitHub CLI"
            if cand.is_dir():
                return cand.resolve()

        # Layer 4: Content Signature
        scanned = self._get_user_scanned_tools().get("gh", [])
        if scanned:
            return scanned[0]

        return None

    def discover_ollama(self) -> Optional[Path]:
        """Discover Ollama root directory."""
        # Layer 1: PATH
        ollama_bin = self.runner.resolve_binary("ollama")
        if ollama_bin:
            return (ollama_bin.parent if ollama_bin.parent.name != "bin" else ollama_bin.parent.parent).resolve()

        # Layer 2: Dynamic OS Inventory
        ol_locs = OSInventory.find_app_locations("Ollama")
        if ol_locs:
            return ol_locs[0]

        # Layer 3: Local AppData
        local_app = os.environ.get("LOCALAPPDATA")
        if local_app:
            cand = Path(local_app) / "Programs" / "Ollama"
            if cand.is_dir():
                return cand.resolve()

        # Layer 4: Content Signature
        scanned = self._get_user_scanned_tools().get("ollama", [])
        if scanned:
            return scanned[0]

        return None

    def discover_sqlite(self) -> Optional[Path]:
        """Discover SQLite CLI root directory."""
        # Layer 1: PATH
        sqlite_bin = self.runner.resolve_binary("sqlite3")
        if sqlite_bin:
            return (sqlite_bin.parent if sqlite_bin.parent.name != "bin" else sqlite_bin.parent.parent).resolve()

        # Layer 3: Standard tools
        for cand_str in ["C:/sqlite", "C:/sqlite3", "C:/tools/sqlite"]:
            cand = Path(cand_str)
            if cand.is_dir() and (cand / "sqlite3.exe").is_file():
                return cand.resolve()

        # Layer 4: Content Signature
        scanned = self._get_user_scanned_tools().get("sqlite", [])
        if scanned:
            return scanned[0]

        return None

    def discover_bun(self) -> Optional[Path]:
        """Discover Bun runtime root directory."""
        # Layer 1: BUN_INSTALL and PATH
        bun_install = self.runner.read_env("BUN_INSTALL")
        if bun_install and Path(bun_install).is_dir():
            return Path(bun_install).resolve()

        bun_bin = self.runner.resolve_binary("bun")
        if bun_bin:
            return (bun_bin.parent.parent if bun_bin.parent.name == "bin" else bun_bin.parent).resolve()

        # Layer 3: ~/.bun
        bun_home = Path.home() / ".bun"
        if bun_home.is_dir():
            return bun_home.resolve()

        # Layer 4: Content Signature
        scanned = self._get_user_scanned_tools().get("bun", [])
        if scanned:
            return scanned[0]

        return None

    def discover_vscode(self) -> Optional[Path]:
        """Discover Visual Studio Code root directory."""
        # Layer 1: PATH
        for code_cmd in ["code", "code-insiders", "codium"]:
            code_bin = self.runner.resolve_binary(code_cmd)
            if code_bin:
                parent = code_bin.parent
                return (parent.parent if parent.name == "bin" else parent).resolve()

        # Layer 2: Dynamic OS Inventory
        for q in ["Visual Studio Code", "Visual Studio Code Insiders", "VSCodium"]:
            locs = OSInventory.find_app_locations(q)
            if locs:
                return locs[0]

        # Layer 3: Standard Locations
        local_app = os.environ.get("LOCALAPPDATA")
        if local_app:
            for sub in ["Microsoft VS Code", "Microsoft VS Code Insiders", "Programs/Microsoft VS Code", "Programs/VSCodium"]:
                cand = Path(local_app) / sub
                if cand.is_dir() and (cand / "resources").is_dir():
                    return cand.resolve()

        prog = os.environ.get("ProgramFiles")
        if prog:
            for sub in ["Microsoft VS Code", "Microsoft VS Code Insiders"]:
                cand = Path(prog) / sub
                if cand.is_dir() and (cand / "resources").is_dir():
                    return cand.resolve()

        # Layer 4: Content Signature
        scanned = self._get_user_scanned_tools().get("vscode", [])
        if scanned:
            return scanned[0]

        return None

    # =========================================================================
    # Universal Entry Points
    # =========================================================================

    def discover_tool(self, tool_id: str) -> Optional[Path]:
        """Universal 4-layer discovery entry point for any of the 22 developer tools."""
        dispatch_table: Dict[str, Callable[[], Optional[Path]]] = {
            "android": self.discover_android_sdk,
            "android_studio": self.discover_android_studio,
            "java": self.discover_java_home,
            "flutter": self.discover_flutter_sdk,
            "python": self.discover_python,
            "node": self.discover_node,
            "rust": self.discover_rust,
            "golang": self.discover_golang,
            "dotnet": self.discover_dotnet,
            "c_compiler": self.discover_c_compiler,
            "cmake": self.discover_cmake,
            "cuda": self.discover_cuda,
            "php": self.discover_php,
            "git": self.discover_git,
            "docker": self.discover_docker,
            "kubectl": self.discover_kubectl,
            "terraform": self.discover_terraform,
            "gh": self.discover_gh,
            "ollama": self.discover_ollama,
            "sqlite": self.discover_sqlite,
            "bun": self.discover_bun,
            "vscode": self.discover_vscode,
        }

        resolver = dispatch_table.get(tool_id)
        if resolver:
            res = resolver()
            if res and res.exists():
                return res

        # Generic fallback to Layer 4 scanned tools
        scanned = self._get_user_scanned_tools().get(tool_id, [])
        if scanned:
            return scanned[0]

        return None

    def discover_all_tool_instances(self, tool_id: str) -> List[Path]:
        """Discover all instances of a tool across all 4 layers (for multi-instance Inspector Drawer)."""
        instances: List[Path] = []
        seen_str = set()

        def _add(p: Optional[Path]) -> None:
            if not p:
                return
            try:
                resolved = p.resolve()
                key = str(resolved).lower() if sys.platform == "win32" else str(resolved)
                if key not in seen_str and resolved.exists():
                    seen_str.add(key)
                    instances.append(resolved)
            except Exception:
                pass

        # 1. Primary instance
        primary = self.discover_tool(tool_id)
        _add(primary)

        # 2. PATH instances via resolve_all_binaries
        # Map tool_id to target binary names
        bin_names = [k for k, v in TARGET_TOOL_BINARIES.items() if tool_id in v]
        for b_name in bin_names[:4]:  # limit to primary binary names
            for found_bin in self.runner.resolve_all_binaries(b_name, use_discovery=False):
                parent = found_bin.parent
                cand_root = parent.parent if parent.name in ["bin", "cmd", "Scripts", "platform-tools"] else parent
                _add(cand_root)

        # 3. Dynamic OS Inventory matches
        query_map = {
            "android_studio": ["Android Studio"],
            "java": ["JDK", "Java SE Development Kit", "Eclipse Adoptium", "Zulu", "Temurin"],
            "node": ["Node.js"],
            "python": ["Python"],
            "golang": ["Go Programming Language"],
            "cmake": ["CMake"],
            "git": ["Git"],
            "docker": ["Docker Desktop"],
            "gh": ["GitHub CLI"],
            "ollama": ["Ollama"],
            "vscode": ["Visual Studio Code", "Visual Studio Code Insiders", "VSCodium"],
        }
        for q in query_map.get(tool_id, []):
            for loc in OSInventory.find_app_locations(q):
                _add(loc)

        # 4. Layer 4 search engine scanned instances
        for sc in self._get_user_scanned_tools().get(tool_id, []):
            _add(sc)

        return instances
