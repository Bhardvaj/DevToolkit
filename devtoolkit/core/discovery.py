"""Unified 4-Layer Discovery Pipeline.

Provides a generalized, portable discovery engine that coordinates:
1. Standard OS environment & PATH
2. Dynamic OS application inventory (Windows Registry / Uninstall)
3. Cross-tool ecosystem configs (Android Studio, Flutter, Gradle)
4. User-configured search roots & content signature scanning
"""

from pathlib import Path
from typing import Dict, List, Optional

from devtoolkit.core.config import load_config
from devtoolkit.core.ecosystem import EcosystemResolvers
from devtoolkit.core.inventory import OSInventory
from devtoolkit.core.runner import SafeRunner
from devtoolkit.core.signatures import scan_roots_for_tools


class DiscoveryPipeline:
    """Coordinates layered discovery without hardcoding custom machine paths."""

    def __init__(self, runner: Optional[SafeRunner] = None):
        self.runner = runner or SafeRunner()
        self._user_config = load_config()
        self._user_scan_cache: Optional[Dict[str, List[Path]]] = None

    def _get_user_scanned_tools(self) -> Dict[str, List[Path]]:
        if self._user_scan_cache is None:
            user_roots = [Path(p) for p in self._user_config.search_paths]
            self._user_scan_cache = scan_roots_for_tools(user_roots, max_depth=2)
        return self._user_scan_cache

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
        for query in ["JDK", "Java SE Development Kit", "Eclipse Adoptium", "Amazon Corretto", "Zulu"]:
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

        # Layer 4: User-Configured Search Paths via Content Signature
        scanned = self._get_user_scanned_tools().get("flutter", [])
        if scanned:
            return scanned[0]

        return None
