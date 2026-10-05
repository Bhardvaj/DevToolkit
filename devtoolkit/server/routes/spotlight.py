"""DevSpotlight client management and settings API routes."""

from __future__ import annotations

import csv
import io
import logging
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from clients.spotlight.settings import (
    BUILTIN_THEMES,
    get_effective_theme,
    get_spotlight_config_path,
    get_windows_system_theme,
    load_spotlight_settings,
    update_spotlight_settings,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/spotlight", tags=["spotlight"])


class SpotlightSettingsUpdateRequest(BaseModel):
    hotkey: Optional[str] = None
    monitor_mode: Optional[str] = None
    fixed_monitor_index: Optional[int] = None
    position_preset: Optional[str] = None
    accent_color: Optional[str] = None
    opacity: Optional[float] = None
    blur_radius: Optional[int] = None
    dismiss_on_blur: Optional[bool] = None
    theme_preset: Optional[str] = None
    animation_speed: Optional[str] = None
    show_details_panel: Optional[bool] = None
    corner_radius: Optional[int] = None
    double_tap_ctrl: Optional[bool] = None
    fallback_hotkey: Optional[str] = None
    restore_window_on_esc: Optional[bool] = None
    enabled_scopes: Optional[List[str]] = None
    custom_themes: Optional[List[Dict[str, Any]]] = None


class CustomThemeCreateRequest(BaseModel):
    name: str
    accent_color: str
    opacity: float = 0.90
    blur_radius: int = 20
    corner_radius: int = 8
    animation_speed: str = "normal"


def get_running_spotlight_pids() -> List[int]:
    """Inspect system processes to find running DevToolkitSpotlight instances without console flashing."""
    pids: List[int] = []
    if sys.platform == "win32":
        # 1. Preferred: High-performance in-process Win32 Toolhelp32 snapshot (0 subprocesses, 0 conhost popups)
        try:
            import ctypes
            from ctypes import wintypes

            TH32CS_SNAPPROCESS = 0x00000002

            class PROCESSENTRY32W(ctypes.Structure):
                _fields_ = [
                    ("dwSize", wintypes.DWORD),
                    ("cntUsage", wintypes.DWORD),
                    ("th32ProcessID", wintypes.DWORD),
                    ("th32DefaultHeapID", ctypes.c_size_t),
                    ("th32ModuleID", wintypes.DWORD),
                    ("cntThreads", wintypes.DWORD),
                    ("th32ParentProcessID", wintypes.DWORD),
                    ("pcPriClassBase", wintypes.LONG),
                    ("dwFlags", wintypes.DWORD),
                    ("szExeFile", wintypes.WCHAR * 260),
                ]

            kernel32 = ctypes.windll.kernel32
            h_snap = kernel32.CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0)
            if h_snap and h_snap != -1:
                try:
                    entry = PROCESSENTRY32W()
                    entry.dwSize = ctypes.sizeof(PROCESSENTRY32W)
                    if kernel32.Process32FirstW(h_snap, ctypes.byref(entry)):
                        while True:
                            exe_name = entry.szExeFile.lower()
                            if exe_name.startswith("devtoolkitspotlight"):
                                pids.append(entry.th32ProcessID)
                            if not kernel32.Process32NextW(h_snap, ctypes.byref(entry)):
                                break
                finally:
                    kernel32.CloseHandle(h_snap)
                return pids
        except Exception as e:
            logger.debug(f"Direct Win32 toolhelp snapshot failed, falling back to tasklist: {e}")

        # 2. Fallback: tasklist with CREATE_NO_WINDOW flag
        try:
            CREATE_NO_WINDOW = 0x08000000
            res = subprocess.run(
                ["tasklist", "/FI", "IMAGENAME eq DevToolkitSpotlight.exe", "/FO", "CSV", "/NH"],
                capture_output=True,
                text=True,
                timeout=3.0,
                creationflags=CREATE_NO_WINDOW,
            )
            for row in csv.reader(io.StringIO(res.stdout)):
                if row and len(row) > 1 and row[0].lower().startswith("devtoolkitspotlight"):
                    try:
                        pids.append(int(row[1].strip()))
                    except ValueError:
                        pass
        except Exception as e:
            logger.debug(f"Failed to check tasklist for spotlight: {e}")
    return pids


def get_spotlight_binary_path() -> Optional[Path]:
    """Locate DevToolkitSpotlight.exe or entry point script."""
    candidates = [
        Path("dist/DevToolkitSpotlight.exe").resolve(),
        Path(sys.executable).parent / "DevToolkitSpotlight.exe",
        Path("clients/spotlight/entry.py").resolve(),
    ]
    for c in candidates:
        if c.is_file():
            return c
    return None


def get_available_monitors() -> List[Dict[str, Any]]:
    """Enumerate display monitors on Windows."""
    monitors: List[Dict[str, Any]] = []
    if sys.platform != "win32":
        return [{"index": 0, "name": "Monitor 1 (Primary)", "is_primary": True, "resolution": "1920x1080"}]

    try:
        import ctypes
        from ctypes import wintypes

        user32 = ctypes.windll.user32

        class RECT(ctypes.Structure):
            _fields_ = [
                ("left", wintypes.LONG),
                ("top", wintypes.LONG),
                ("right", wintypes.LONG),
                ("bottom", wintypes.LONG),
            ]

        class MONITORINFOEXW(ctypes.Structure):
            _fields_ = [
                ("cbSize", wintypes.DWORD),
                ("rcMonitor", RECT),
                ("rcWork", RECT),
                ("dwFlags", wintypes.DWORD),
                ("szDevice", wintypes.WCHAR * 32),
            ]

        MONITORINFOF_PRIMARY = 1
        MONITORENUMPROC = ctypes.WINFUNCTYPE(
            wintypes.BOOL,
            wintypes.HMONITOR,
            wintypes.HDC,
            ctypes.POINTER(RECT),
            wintypes.LPARAM,
        )

        idx = 0

        def _callback(hmon, hdc, lprect, lparam):
            nonlocal idx
            mi = MONITORINFOEXW()
            mi.cbSize = ctypes.sizeof(MONITORINFOEXW)
            if user32.GetMonitorInfoW(hmon, ctypes.byref(mi)):
                w = mi.rcMonitor.right - mi.rcMonitor.left
                h = mi.rcMonitor.bottom - mi.rcMonitor.top
                is_primary = bool(mi.dwFlags & MONITORINFOF_PRIMARY)
                monitors.append({
                    "index": idx,
                    "name": f"Monitor {idx + 1}" + (" (Primary)" if is_primary else ""),
                    "device": mi.szDevice,
                    "is_primary": is_primary,
                    "resolution": f"{w}x{h}",
                    "width": w,
                    "height": h,
                })
                idx += 1
            return True

        user32.EnumDisplayMonitors(None, None, MONITORENUMPROC(_callback), 0)
    except Exception as e:
        logger.debug(f"Failed to enumerate monitors: {e}")

    if not monitors:
        monitors.append({"index": 0, "name": "Monitor 1 (Primary)", "is_primary": True, "resolution": "Default"})

    return monitors


@router.get("/status")
def get_spotlight_status() -> Dict[str, Any]:
    """Return runtime process status, configuration, and binary availability for DevSpotlight."""
    pids = get_running_spotlight_pids()
    is_running = len(pids) > 0
    bin_path = get_spotlight_binary_path()
    settings = load_spotlight_settings()
    cfg_path = get_spotlight_config_path()

    return {
        "running": is_running,
        "pids": pids,
        "primary_pid": pids[0] if pids else None,
        "executable_exists": bin_path is not None and bin_path.suffix == ".exe",
        "executable_path": str(bin_path) if bin_path else None,
        "config_path": str(cfg_path),
        "settings": settings.to_dict(),
        "version": "v0.6.0",
        "available_monitors": get_available_monitors(),
        "system_theme": get_windows_system_theme(),
        "builtin_themes": BUILTIN_THEMES,
        "effective_theme": get_effective_theme(settings),
    }


@router.post("/launch")
def post_spotlight_launch() -> Dict[str, Any]:
    """Launch the DevSpotlight standalone desktop client process."""
    pids = get_running_spotlight_pids()
    if pids:
        return {
            "status": "already_running",
            "message": f"DevSpotlight is already running with PID {pids[0]}.",
            "pid": pids[0],
        }

    bin_path = get_spotlight_binary_path()
    if not bin_path:
        raise HTTPException(
            status_code=404,
            detail="DevSpotlight executable or entry script not found in application path.",
        )

    try:
        creation_flags = 0
        if sys.platform == "win32":
            creation_flags = (
                getattr(subprocess, "DETACHED_PROCESS", 0x00000008)
                | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0x00000200)
                | getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)
            )

        if bin_path.suffix == ".exe":
            proc = subprocess.Popen(
                [str(bin_path)],
                creationflags=creation_flags,
                close_fds=True,
            )
        else:
            # Fallback to python runner
            py_exe = sys.executable
            proc = subprocess.Popen(
                [py_exe, "-m", "clients.spotlight.entry"],
                creationflags=creation_flags,
                close_fds=True,
            )

        return {
            "status": "ok",
            "message": "DevSpotlight launched successfully.",
            "pid": proc.pid,
        }
    except Exception as e:
        logger.error(f"Failed to launch DevSpotlight: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to launch DevSpotlight: {e}")


@router.post("/stop")
def post_spotlight_stop() -> Dict[str, Any]:
    """Gracefully terminate running DevSpotlight desktop client processes."""
    pids = get_running_spotlight_pids()
    if not pids:
        return {"status": "ok", "message": "DevSpotlight is not currently running."}

    if sys.platform == "win32":
        try:
            CREATE_NO_WINDOW = 0x08000000
            subprocess.run(
                ["taskkill", "/IM", "DevToolkitSpotlight.exe", "/F"],
                capture_output=True,
                timeout=5.0,
                creationflags=CREATE_NO_WINDOW,
            )
            return {"status": "ok", "message": f"Terminated {len(pids)} DevSpotlight process(es)."}
        except Exception as e:
            logger.error(f"Failed to terminate DevSpotlight: {e}")
            raise HTTPException(status_code=500, detail=f"Failed to stop DevSpotlight: {e}")

    return {"status": "ok", "message": "Stopped."}


@router.get("/settings")
def get_spotlight_settings() -> Dict[str, Any]:
    """Retrieve current DevSpotlight preferences."""
    settings = load_spotlight_settings()
    return settings.to_dict()


@router.post("/settings")
def post_spotlight_settings(req: SpotlightSettingsUpdateRequest) -> Dict[str, Any]:
    """Update DevSpotlight preferences."""
    dump_fn = getattr(req, "model_dump", getattr(req, "dict", None))
    data = dump_fn() if dump_fn else {}
    updates = {k: v for k, v in data.items() if v is not None}
    if not updates:
        return load_spotlight_settings().to_dict()

    new_settings = update_spotlight_settings(**updates)
    return new_settings.to_dict()


@router.post("/open-config")
def post_spotlight_open_config() -> Dict[str, Any]:
    """Open spotlight.json in the user's default text editor."""
    cfg_path = get_spotlight_config_path()
    if not cfg_path.is_file():
        # Ensure default file exists
        load_spotlight_settings()

    if sys.platform == "win32" and cfg_path.is_file():
        os.startfile(str(cfg_path))
        return {"status": "ok", "message": f"Opened {cfg_path.name}"}

    return {"status": "error", "message": "Config file not found."}


@router.post("/open-logs")
def post_spotlight_open_logs() -> Dict[str, Any]:
    """Open spotlight.log in the user's default text editor."""
    candidates = [
        Path("dist/spotlight.log").resolve(),
        Path("spotlight.log").resolve(),
    ]
    for p in candidates:
        if p.is_file() and sys.platform == "win32":
            os.startfile(str(p))
            return {"status": "ok", "message": f"Opened {p.name}"}

    return {"status": "warning", "message": "No spotlight log file found."}


@router.post("/themes")
def post_spotlight_theme(req: CustomThemeCreateRequest) -> Dict[str, Any]:
    """Create or update a custom theme preset and persist to spotlight.json."""
    settings = load_spotlight_settings()
    theme_id = f"custom_{int(time.time() * 1000)}"
    new_theme = {
        "id": theme_id,
        "name": req.name.strip() or "Custom Theme",
        "accent_color": req.accent_color,
        "opacity": req.opacity,
        "blur_radius": req.blur_radius,
        "corner_radius": req.corner_radius,
        "animation_speed": req.animation_speed,
        "is_builtin": False,
    }

    current_custom = [t for t in settings.custom_themes if t.get("name") != new_theme["name"]]
    current_custom.append(new_theme)

    updated = update_spotlight_settings(custom_themes=current_custom, theme_preset=theme_id)
    return {
        "status": "ok",
        "theme": new_theme,
        "settings": updated.to_dict(),
    }


@router.delete("/themes/{theme_id}")
def delete_spotlight_theme(theme_id: str) -> Dict[str, Any]:
    """Remove a custom theme preset from spotlight.json."""
    settings = load_spotlight_settings()
    current_custom = [t for t in settings.custom_themes if t.get("id") != theme_id]

    new_preset = settings.theme_preset
    if new_preset == theme_id:
        new_preset = "obsidian"

    updated = update_spotlight_settings(custom_themes=current_custom, theme_preset=new_preset)
    return {
        "status": "ok",
        "deleted_id": theme_id,
        "settings": updated.to_dict(),
    }

