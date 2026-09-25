"""Cross-Tool Ecosystem Metadata Resolvers.

Extracts SDK and runtime pointers from standardized configuration files
maintained by major developer tools (Android Studio, Flutter, Gradle).
"""

import json
import os
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import List, Optional

from devtoolkit.core.runner import SafeRunner


class EcosystemResolvers:
    """Interrogates cross-tool ecosystem configs to find SDK and runtime locations."""

    _cached_flutter: Optional[dict] = None
    _cached_options_dirs: Optional[List[Path]] = None
    _cached_studio_sdk: Optional[Path] = None
    _cached_gradle_java: Optional[Path] = None

    @classmethod
    def clear_cache(cls) -> None:
        """Clear all cached ecosystem resolution results."""
        cls._cached_flutter = None
        cls._cached_options_dirs = None
        cls._cached_studio_sdk = None
        cls._cached_gradle_java = None

    @classmethod
    def get_android_studio_options_dirs(cls, use_cache: bool = True) -> List[Path]:
        """Find Google/Android Studio configuration directories across platforms."""
        if cls._cached_options_dirs is not None and use_cache:
            return cls._cached_options_dirs

        options_dirs: List[Path] = []
        candidates: List[Path] = []

        if sys.platform == "win32":
            appdata = os.environ.get("APPDATA")
            if appdata:
                candidates.append(Path(appdata) / "Google")
        elif sys.platform == "darwin":
            candidates.append(Path.home() / "Library" / "Application Support" / "Google")
        else:
            candidates.append(Path.home() / ".config" / "Google")

        for c in candidates:
            if c.exists() and c.is_dir():
                for sub in c.iterdir():
                    if sub.is_dir() and "AndroidStudio" in sub.name:
                        opt = sub / "options"
                        if opt.exists() and opt.is_dir():
                            options_dirs.append(opt)

        cls._cached_options_dirs = options_dirs
        return options_dirs

    @classmethod
    def resolve_android_sdk_from_studio(cls, use_cache: bool = True) -> Optional[Path]:
        """Read Android SDK path from Android Studio's android.sdk.path.xml or jdk.table.xml."""
        if cls._cached_studio_sdk is not None and use_cache:
            return cls._cached_studio_sdk

        for opt_dir in cls.get_android_studio_options_dirs():
            # 1. Check android.sdk.path.xml
            sdk_xml = opt_dir / "android.sdk.path.xml"
            if sdk_xml.exists():
                try:
                    tree = ET.parse(sdk_xml)
                    root = tree.getroot()
                    for opt in root.iter("option"):
                        if opt.attrib.get("name") == "androidSdkAbsolutePath":
                            val = opt.attrib.get("value")
                            if val:
                                p = Path(val).resolve()
                                if p.exists():
                                    cls._cached_studio_sdk = p
                                    return p
                except Exception:
                    pass

            # 2. Check jdk.table.xml fallback
            jdk_xml = opt_dir / "jdk.table.xml"
            if jdk_xml.exists():
                try:
                    tree = ET.parse(jdk_xml)
                    root = tree.getroot()
                    for jdk in root.iter("jdk"):
                        type_tag = jdk.find("type")
                        if type_tag is not None and type_tag.attrib.get("value") == "Android SDK":
                            home_tag = jdk.find("homePath")
                            if home_tag is not None:
                                val = home_tag.attrib.get("value")
                                if val:
                                    p = Path(val).resolve()
                                    if p.exists():
                                        cls._cached_studio_sdk = p
                                        return p
                except Exception:
                    pass

        return None

    @classmethod
    def resolve_from_flutter(cls, runner: SafeRunner, use_cache: bool = True) -> dict:
        """Query Flutter's machine configuration for configured SDK and JDK directories."""
        if cls._cached_flutter is not None and use_cache:
            return cls._cached_flutter

        flutter_bin = runner.resolve_binary("flutter") or runner.resolve_binary("flutter.bat")
        if not flutter_bin:
            cls._cached_flutter = {}
            return {}

        res = runner.run_command([str(flutter_bin), "config", "--machine"], timeout=4.0)
        if res.ok and res.stdout:
            try:
                data = json.loads(res.stdout)
                result = {}
                if data.get("android-sdk"):
                    p = Path(data["android-sdk"]).resolve()
                    if p.exists():
                        result["android_sdk"] = p
                if data.get("android-studio-dir"):
                    p = Path(data["android-studio-dir"]).resolve()
                    if p.exists():
                        result["android_studio"] = p
                if data.get("jdk-dir"):
                    p = Path(data["jdk-dir"]).resolve()
                    if p.exists():
                        result["jdk_dir"] = p
                cls._cached_flutter = result
                return result
            except Exception:
                pass

        cls._cached_flutter = {}
        return {}

    @classmethod
    def resolve_from_gradle(cls, use_cache: bool = True) -> Optional[Path]:
        """Read Java home from ~/.gradle/gradle.properties."""
        if cls._cached_gradle_java is not None and use_cache:
            return cls._cached_gradle_java

        gradle_props = Path.home() / ".gradle" / "gradle.properties"
        if not gradle_props.exists():
            return None

        try:
            for line in gradle_props.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if line.startswith("org.gradle.java.home="):
                    val = line.split("=", 1)[1].strip()
                    p = Path(val).resolve()
                    if p.exists():
                        cls._cached_gradle_java = p
                        return p
        except Exception:
            pass

        return None
