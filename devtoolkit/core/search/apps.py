"""Windows Desktop Application indexer and discovery service.

Discovers, parses, and indexes applications from Start Menu, Desktop shortcuts,
and Windows Registry App Paths into first-class 'app' search entries.
"""

from __future__ import annotations

import logging
import os
import re
import sys
from pathlib import Path
from typing import List, Set

from devtoolkit.core.search.matcher import extract_acronym
from devtoolkit.core.search.models import SearchResult

logger = logging.getLogger(__name__)

# Ignore common administrative, uninstaller, and documentation links
IGNORE_PATTERNS = {
    "uninstall",
    "remove",
    "readme",
    "help",
    "documentation",
    "license",
    "release notes",
    "website",
    "manual",
}


def get_start_menu_directories() -> List[Path]:
    """Return user and common Start Menu and Desktop directory paths."""
    dirs: List[Path] = []
    if sys.platform != "win32":
        return dirs

    # 1. User Start Menu
    appdata = os.environ.get("APPDATA")
    if appdata:
        p = Path(appdata) / "Microsoft" / "Windows" / "Start Menu" / "Programs"
        if p.is_dir():
            dirs.append(p)

    # 2. Common/All Users Start Menu
    programdata = os.environ.get("PROGRAMDATA")
    if programdata:
        p = Path(programdata) / "Microsoft" / "Windows" / "Start Menu" / "Programs"
        if p.is_dir():
            dirs.append(p)

    # 3. User Desktop
    userprofile = os.environ.get("USERPROFILE")
    if userprofile:
        p = Path(userprofile) / "Desktop"
        if p.is_dir():
            dirs.append(p)

    # 4. Public Desktop
    pub_desktop = Path("C:/Users/Public/Desktop")
    if pub_desktop.is_dir():
        dirs.append(pub_desktop)

    return dirs


def _clean_app_name(raw_name: str) -> str:
    """Clean shortcut or executable filename into a human-friendly application title."""
    clean = raw_name
    for ext in (".lnk", ".url", ".appref-ms", ".exe"):
        if clean.lower().endswith(ext):
            clean = clean[: -len(ext)]
            break
    clean = re.sub(r"\s+", " ", clean).strip()
    return clean


def _should_ignore_app(name: str) -> bool:
    """Filter out uninstallers, manuals, and documentation links."""
    name_lower = name.lower()
    return any(p in name_lower for p in IGNORE_PATTERNS)


def discover_registry_app_paths() -> List[SearchResult]:
    """Discover applications registered under Windows Registry 'App Paths'."""
    results: List[SearchResult] = []
    if sys.platform != "win32":
        return results

    try:
        import winreg
    except ImportError:
        return results

    registry_keys = [
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths"),
        (winreg.HKEY_CURRENT_USER, r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths"),
    ]

    seen_paths: Set[str] = set()

    for hkey, subkey_path in registry_keys:
        try:
            with winreg.OpenKey(hkey, subkey_path) as root_key:
                num_subkeys = winreg.QueryInfoKey(root_key)[0]
                for i in range(num_subkeys):
                    try:
                        app_name = winreg.EnumKey(root_key, i)
                        with winreg.OpenKey(root_key, app_name) as app_key:
                            exe_path_raw = winreg.QueryValue(app_key, "")
                            if not exe_path_raw or not isinstance(exe_path_raw, str):
                                continue

                            # Strip quotes
                            exe_path = exe_path_raw.strip('"')
                            p = Path(exe_path)
                            if not p.is_file():
                                continue

                            norm_path = str(p.resolve()).lower()
                            if norm_path in seen_paths:
                                continue
                            seen_paths.add(norm_path)

                            display_name = _clean_app_name(app_name)
                            if _should_ignore_app(display_name):
                                continue

                            acronym = extract_acronym(display_name)
                            try:
                                stat = p.stat()
                                size = stat.st_size
                                mtime = stat.st_mtime
                            except Exception:
                                size = 0
                                mtime = 0.0

                            results.append(
                                SearchResult(
                                    path=str(p.resolve()),
                                    name=display_name,
                                    is_dir=False,
                                    size=size,
                                    mtime=mtime,
                                    entry_type="app",
                                    acronym=acronym,
                                )
                            )
                    except Exception:
                        continue
        except Exception:
            continue

    return results


def discover_shortcut_applications() -> List[SearchResult]:
    """Scan Start Menu and Desktop directories for .lnk and .appref-ms shortcuts."""
    results: List[SearchResult] = []
    if sys.platform != "win32":
        return results

    dirs = get_start_menu_directories()
    seen_names: Set[str] = set()
    seen_paths: Set[str] = set()

    for d in dirs:
        if not d.exists():
            continue
        try:
            for p in d.rglob("*"):
                if not p.is_file():
                    continue
                ext = p.suffix.lower()
                if ext not in (".lnk", ".url", ".appref-ms"):
                    continue

                display_name = _clean_app_name(p.name)
                if not display_name or _should_ignore_app(display_name):
                    continue

                norm_name = display_name.lower()
                norm_path = str(p.resolve()).lower()

                if norm_name in seen_names or norm_path in seen_paths:
                    continue

                seen_names.add(norm_name)
                seen_paths.add(norm_path)

                acronym = extract_acronym(display_name)
                try:
                    stat = p.stat()
                    size = stat.st_size
                    mtime = stat.st_mtime
                except Exception:
                    size = 0
                    mtime = 0.0

                results.append(
                    SearchResult(
                        path=str(p.resolve()),
                        name=display_name,
                        is_dir=False,
                        size=size,
                        mtime=mtime,
                        entry_type="app",
                        acronym=acronym,
                    )
                )
        except Exception as e:
            logger.debug(f"Failed scanning app shortcut directory {d}: {e}")

    return results


def index_all_applications() -> List[SearchResult]:
    """Discover and deduplicate all installed desktop applications from all sources."""
    shortcuts = discover_shortcut_applications()
    registry_apps = discover_registry_app_paths()

    # Prioritize shortcuts as they have cleaner user-facing display names
    combined: List[SearchResult] = []
    seen_keys: Set[str] = set()

    for app in shortcuts + registry_apps:
        key = app.name.lower()
        if key not in seen_keys:
            seen_keys.add(key)
            combined.append(app)

    return combined

