"""Default query mode: Fast Search + Desktop Application Launcher with Acronym Matching."""

from __future__ import annotations

import logging
import os
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

from clients.spotlight.icons import get_app_icon_data_url, warm_icons_background
from clients.spotlight.matcher import extract_acronym, score_match

logger = logging.getLogger(__name__)

# Lightweight offline fallback cache
_offline_apps_cache: Optional[List[Dict[str, Any]]] = None


def get_offline_start_menu_apps() -> List[Dict[str, Any]]:
    """Scan Start Menu and Desktop shortcuts for offline app launching."""
    global _offline_apps_cache
    if _offline_apps_cache is not None:
        return _offline_apps_cache

    apps: List[Dict[str, Any]] = []
    if sys.platform != "win32":
        return apps

    user_sm = Path(os.environ.get("APPDATA", "")) / "Microsoft" / "Windows" / "Start Menu" / "Programs"
    common_sm = Path(os.environ.get("PROGRAMDATA", "")) / "Microsoft" / "Windows" / "Start Menu" / "Programs"
    desktop = Path(os.environ.get("USERPROFILE", "")) / "Desktop"

    dirs = [user_sm, common_sm, desktop]
    seen: set[str] = set()

    for d in dirs:
        if not d.is_dir():
            continue
        try:
            for p in d.rglob("*.lnk"):
                clean_name = p.stem.strip()
                if not clean_name:
                    continue
                name_low = clean_name.lower()
                if any(ign in name_low for ign in ("uninstall", "readme", "help", "documentation", "license")):
                    continue
                if name_low in seen:
                    continue
                seen.add(name_low)

                acr = extract_acronym(clean_name)
                apps.append(
                    {
                        "name": clean_name,
                        "path": str(p.resolve()),
                        "folder": str(p.parent),
                        "entry_type": "app",
                        "ext": "APP",
                        "acronym": acr,
                    }
                )
        except Exception:
            pass

    _offline_apps_cache = apps
    warm_icons_background([a["path"] for a in apps[:40]])
    return apps


def _search_offline_apps(q: str, limit: int = 15) -> List[Dict[str, Any]]:
    """Scan and score cached Start Menu / Desktop applications against query."""
    offline_apps = get_offline_start_menu_apps()
    scored_apps: List[tuple[int, Dict[str, Any]]] = []

    for app in offline_apps:
        score = score_match(q, app["name"], app.get("acronym"))
        if score > 0:
            scored_apps.append((score, app))

    scored_apps.sort(key=lambda x: x[0], reverse=True)

    results: List[Dict[str, Any]] = []
    for score, app in scored_apps[:limit]:
        p = app["path"]
        folder = str(Path(p).parent) if p else ""
        item_dict = {
            "id": f"app_{p}",
            "title": app["name"],
            "subtitle": folder or "Application",
            "path": p,
            "entry_type": "app",
            "badge": "APP",
            "action": "launch_app",
        }
        icon_url = get_app_icon_data_url(p)
        if icon_url:
            item_dict["icon"] = icon_url
        results.append(item_dict)

    return results


def query_default(
    query: str,
    client: Optional[Any] = None,
    allow_apps: bool = True,
    allow_files: bool = True,
) -> List[Dict[str, Any]]:
    """Execute unified search across files, folders, and applications."""
    q = query.strip()
    if not q or (not allow_apps and not allow_files):
        return []

    # 1. Daemon Online Path: Full Everything-class Fast Search + App Index
    if client and client.is_alive():
        try:
            res = client.get(f"/api/search?q={q}&limit=20")
            items = res.get("results", [])
            formatted: List[Dict[str, Any]] = []
            for item in items:
                entry_type = item.get("entry_type", "file")
                if entry_type == "app" and not allow_apps:
                    continue
                if entry_type != "app" and not allow_files:
                    continue

                is_dir = item.get("is_dir", False)
                name = item.get("name")
                p = item.get("path")
                ext = item.get("ext", "")

                icon_url = None
                if entry_type == "app" or (p and p.lower().endswith((".exe", ".lnk"))):
                    icon_url = get_app_icon_data_url(p)

                size_fmt = item.get("size_formatted", "")
                if entry_type == "app":
                    badge = "APP"
                    sub = item.get("folder") or (str(Path(p).parent) if p else "Application")
                    act = "launch_app"
                elif is_dir:
                    badge = "DIR"
                    sub = str(Path(p).parent) if p else p
                    act = "open_folder"
                else:
                    badge = ext.lstrip(".").upper() if ext else "FILE"
                    parent_str = str(Path(p).parent) if p else ""
                    sub = f"{parent_str} • {size_fmt}" if (parent_str and size_fmt) else (parent_str or size_fmt)
                    act = "open_file"

                item_dict = {
                    "id": f"{entry_type}_{p}",
                    "title": name,
                    "subtitle": sub,
                    "path": p,
                    "entry_type": entry_type,
                    "is_dir": is_dir,
                    "badge": badge,
                    "action": act,
                }
                if size_fmt:
                    item_dict["size_formatted"] = size_fmt
                if icon_url:
                    item_dict["icon"] = icon_url
                formatted.append(item_dict)

            # If FastSearch is in idle mode (0 results) or daemon returned no apps,
            # fall back / blend with offline Start Menu application scanner
            if allow_apps:
                has_apps = any(it.get("entry_type") == "app" for it in formatted)
                if not has_apps:
                    offline_apps = _search_offline_apps(q, limit=10 if formatted else 15)
                    existing_paths = {it.get("path") for it in formatted if it.get("path")}
                    apps_to_add = [a for a in offline_apps if a.get("path") not in existing_paths]
                    formatted = apps_to_add + formatted

            return formatted
        except Exception as e:
            logger.debug(f"Daemon search request failed: {e}")

    # 2. Daemon Offline Fallback: Local Start Menu App Search
    if not allow_apps:
        return []
    return _search_offline_apps(q, limit=15)


def launch_target_path(path: str, run_as_admin: bool = False) -> bool:
    """Launch application or file, optionally elevated as administrator."""
    if not path or not Path(path).exists():
        return False

    if sys.platform == "win32":
        import ctypes
        shell32 = ctypes.windll.shell32
        verb = "runas" if run_as_admin else "open"
        SW_SHOWNORMAL = 1
        res = shell32.ShellExecuteW(None, verb, str(Path(path).resolve()), None, None, SW_SHOWNORMAL)
        return int(res) > 32
    else:
        try:
            subprocess.Popen(["xdg-open", path], close_fds=True)
            return True
        except Exception:
            return False


def reveal_in_explorer(path: str) -> bool:
    """Reveal file or directory in Windows File Explorer."""
    if not path or not Path(path).exists():
        return False

    p = str(Path(path).resolve())
    if sys.platform == "win32":
        try:
            if Path(p).is_dir():
                os.startfile(p)
            else:
                subprocess.Popen(["explorer.exe", f"/select,{p}"], close_fds=True)
            return True
        except Exception as e:
            logger.error(f"Failed to reveal in Explorer: {e}")
            return False
    return False

