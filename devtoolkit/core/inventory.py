"""OS Application Inventory: Dynamic registry and installed software discovery."""

import re
import sys
from pathlib import Path
from typing import List, Optional
from pydantic import BaseModel


class InstalledApp(BaseModel):
    name: str
    version: Optional[str] = None
    install_location: Optional[str] = None
    publisher: Optional[str] = None
    source: str = "registry"


class OSInventory:
    """Discovers installed software via official OS inventory mechanisms (Registry on Windows)."""

    _cached_apps: Optional[List[InstalledApp]] = None

    @classmethod
    def clear_cache(cls) -> None:
        """Clear cached inventory."""
        cls._cached_apps = None

    @classmethod
    def get_installed_apps(cls, use_cache: bool = True) -> List[InstalledApp]:
        if sys.platform != "win32":
            return []

        if cls._cached_apps is not None and use_cache:
            return cls._cached_apps

        apps: List[InstalledApp] = []
        try:
            import winreg

            roots = [
                (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"),
                (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall"),
                (winreg.HKEY_CURRENT_USER, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"),
            ]

            for root_key, subkey_path in roots:
                try:
                    with winreg.OpenKey(root_key, subkey_path, 0, winreg.KEY_READ | winreg.KEY_WOW64_64KEY) as key:
                        subkeys_count, _, _ = winreg.QueryInfoKey(key)
                        for i in range(subkeys_count):
                            try:
                                subkey_name = winreg.EnumKey(key, i)
                                with winreg.OpenKey(key, subkey_name) as app_key:
                                    name = cls._read_reg_str(app_key, "DisplayName")
                                    if not name:
                                        continue

                                    ver = cls._read_reg_str(app_key, "DisplayVersion")
                                    pub = cls._read_reg_str(app_key, "Publisher")
                                    loc = cls._read_reg_str(app_key, "InstallLocation")
                                    icon = cls._read_reg_str(app_key, "DisplayIcon")
                                    uninst = cls._read_reg_str(app_key, "UninstallString")

                                    # Infer install location if not explicitly provided
                                    if not loc or not Path(loc).exists():
                                        inferred = cls._infer_location(icon, uninst)
                                        if inferred:
                                            loc = str(inferred)

                                    apps.append(
                                        InstalledApp(
                                            name=name,
                                            version=ver,
                                            install_location=loc,
                                            publisher=pub,
                                        )
                                    )
                            except OSError:
                                continue
                except OSError:
                    continue

        except Exception:
            pass

        cls._cached_apps = apps
        return apps

    @classmethod
    def find_apps_by_name(cls, query: str) -> List[InstalledApp]:
        """Find installed applications matching a case-insensitive search term."""
        norm_query = query.lower()
        return [app for app in cls.get_installed_apps() if norm_query in app.name.lower()]

    @classmethod
    def find_app_locations(cls, query: str) -> List[Path]:
        """Return valid on-disk directories for matching applications."""
        locations: List[Path] = []
        for app in cls.find_apps_by_name(query):
            if app.install_location:
                p = Path(app.install_location).resolve()
                if p.exists() and p.is_dir() and p not in locations:
                    locations.append(p)
        return locations

    @staticmethod
    def _read_reg_str(key, val_name: str) -> Optional[str]:
        try:
            import winreg

            val, _ = winreg.QueryValueEx(key, val_name)
            if val:
                return str(val).strip().strip('"')
        except OSError:
            pass
        return None

    @staticmethod
    def _infer_location(icon: Optional[str], uninst: Optional[str]) -> Optional[Path]:
        for candidate_path_str in [icon, uninst]:
            if not candidate_path_str:
                continue
            # Remove arguments or quotes, e.g. "C:\Path\uninstall.exe" /S
            m = re.search(r'^["]?([^",]+\.exe)["]?', candidate_path_str, re.IGNORECASE)
            raw = m.group(1) if m else candidate_path_str.split()[0]
            try:
                p = Path(raw.strip('"')).resolve()
                if p.exists():
                    parent = p.parent
                    # If inside a bin folder, take parent of bin
                    if parent.name.lower() == "bin":
                        return parent.parent
                    return parent
            except Exception:
                continue
        return None
