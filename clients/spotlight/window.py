"""PyWebView resident window controller with Win32 25% golden ratio positioning and hotkey toggle."""

from __future__ import annotations

import logging
import os
import subprocess
import sys
import threading
import time
import webbrowser
from pathlib import Path
from typing import Any, Dict, List, Optional

from clients.spotlight.dispatcher import dispatch_query
from clients.spotlight.modes.actions import execute_action
from clients.spotlight.modes.default import launch_target_path, reveal_in_explorer
from clients.spotlight.modes.ports import kill_target_port
from clients.spotlight.modes.project import open_in_terminal
from clients.spotlight.modes.tools import get_deep_telemetry
from clients.spotlight.modes.window_walker import close_window_by_hwnd, switch_to_window
from clients.spotlight.settings import load_spotlight_settings, update_spotlight_settings
from devtoolkit.client.api import DevToolkitClient

logger = logging.getLogger(__name__)

SPOTLIGHT_TITLE = "DevToolkit Spotlight"
WINDOW_WIDTH = 840
DEFAULT_BAR_HEIGHT = 58
DEFAULT_EMPTY_HEIGHT = 92
MAX_WINDOW_HEIGHT = 640
HEADER_HEIGHT = 58


class SpotlightJSAPI:
    """JavaScript-to-Python bridge API exposed in PyWebView."""

    def __init__(self, window_manager: "SpotlightWindowManager", client: DevToolkitClient) -> None:
        self._wm = window_manager
        self._client = client

    def get_empty_state(self, params: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """Return items for empty search query (no daemon status row)."""
        return []

    def get_daemon_status(self, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Check if background daemon is online."""
        is_online = self._client.is_alive() if self._client else False
        return {
            "online": is_online,
            "port": getattr(self._client, "port", 4321),
            "status": "online" if is_online else "offline",
        }

    def resize_window(self, params: Dict[str, Any]) -> None:
        """Dynamically resize window height based on result count."""
        height = params.get("height", DEFAULT_BAR_HEIGHT)
        self._wm.set_height(int(height))

    def set_settings_open(self, params: Dict[str, Any]) -> None:
        """Inform window manager if settings modal is open to avoid auto-dismiss."""
        self._wm.set_settings_open(bool(params.get("open", False)))

    def launch_daemon_process(self) -> bool:
        """Launch the DevToolkit daemon as an independent external process without bundling daemon code."""
        port = getattr(self._client, "port", 4321)
        try:
            base_dir = Path(sys.executable).parent if getattr(sys, "frozen", False) else Path.cwd()
            candidates = [
                base_dir / "DevToolkit.exe",
                base_dir / "devtoolkit.exe",
                base_dir.parent / "DevToolkit.exe",
                base_dir / "dist" / "DevToolkit.exe",
                Path("dist/DevToolkit.exe").resolve(),
                Path("DevToolkit.exe").resolve(),
            ]
            for c in candidates:
                if c.is_file():
                    flags = 0
                    if sys.platform == "win32":
                        flags = subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP
                    subprocess.Popen([str(c), "--daemon", "--port", str(port)], creationflags=flags, close_fds=True)
                    return True

            if not getattr(sys, "frozen", False):
                flags = 0
                if sys.platform == "win32":
                    flags = subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP
                cmd = [sys.executable, "-m", "devtoolkit.entry", "--daemon", "--port", str(port)]
                subprocess.Popen(cmd, creationflags=flags, close_fds=True)
                return True
        except Exception as e:
            logger.error(f"Failed to launch DevToolkit daemon: {e}")
        return False

    def search(self, params: Dict[str, Any]) -> List[Dict[str, Any]]:
        query = params.get("query", "")
        settings = load_spotlight_settings()
        return dispatch_query(query, client=self._client, enabled_scopes=settings.enabled_scopes)

    def execute_item(self, params: Dict[str, Any]) -> Dict[str, Any]:
        item = params.get("item", {})
        verb = params.get("verb", "open")
        act = item.get("action", "")
        p = item.get("path", "")

        # 1. Start Daemon action
        if act == "start_daemon":
            self.launch_daemon_process()
            return {"status": "ok"}

        # 2. Window Walker actions
        if act == "switch_window":
            hwnd = item.get("hwnd", 0)
            if verb == "kill":
                close_window_by_hwnd(hwnd)
            else:
                switch_to_window(hwnd)
                self._wm.hide()
            return {"status": "ok"}

        # 3. Port actions
        if act in ("kill_port", "drilldown_port", "open_browser") or verb == "kill":
            port = item.get("port")
            if verb == "kill" or act == "kill_port":
                return kill_target_port(port, client=self._client)
            if act == "open_browser":
                webbrowser.open(f"http://localhost:{port}")
                self._wm.hide()
                return {"status": "ok"}

        # 4. Project action
        if act == "open_terminal":
            if verb == "reveal":
                reveal_in_explorer(p)
            else:
                open_in_terminal(p)
            self._wm.hide()
            return {"status": "ok"}

        # 5. App & File launch actions
        if act in ("launch_app", "open_file", "open_folder"):
            if verb == "reveal":
                reveal_in_explorer(p)
            elif verb == "runas":
                launch_target_path(p, run_as_admin=True)
                self._wm.hide()
            else:
                launch_target_path(p, run_as_admin=False)
                self._wm.hide()
            return {"status": "ok"}

        # 6. Built-in system actions
        if act.startswith("open_") or act.startswith("trigger_") or act.startswith("quit_") or act == "start_daemon":
            if act == "quit_spotlight":
                self._wm.quit()
                return {"status": "ok"}
            if act == "start_daemon":
                launched = self.launch_daemon_process()
                return {"status": "ok" if launched else "error"}
            res = execute_action(act, client=self._client)
            if act not in ("open_settings", "open_logs", "open_config"):
                self._wm.hide()
            return res

        # 7. Copy value / path action (calculator, UUID, epoch, files)
        if act == "copy" or verb == "copy":
            val = str(item.get("path") or item.get("value") or "")
            if sys.platform == "win32" and val:
                try:
                    import ctypes
                    user32 = ctypes.windll.user32
                    kernel32 = ctypes.windll.kernel32
                    GMEM_MOVEABLE = 0x0002
                    CF_UNICODETEXT = 13

                    user32.OpenClipboard(0)
                    user32.EmptyClipboard()
                    data = val.encode("utf-16le") + b"\x00\x00"
                    hglobal = kernel32.GlobalAlloc(GMEM_MOVEABLE, len(data))
                    ptr = kernel32.GlobalLock(hglobal)
                    ctypes.memmove(ptr, data, len(data))
                    kernel32.GlobalUnlock(hglobal)
                    user32.SetClipboardData(CF_UNICODETEXT, hglobal)
                    user32.CloseClipboard()
                except Exception as e:
                    logger.debug(f"Clipboard copy error: {e}")
            if verb != "copy":
                self._wm.hide()
            return {"status": "ok", "copied": val}

        return {"status": "ok"}

    def get_tool_deep(self, params: Dict[str, Any]) -> Dict[str, Any]:
        tool_id = params.get("tool_id", "")
        return get_deep_telemetry(tool_id, client=self._client)

    def get_item_metadata(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Fetch filesystem stats and metadata for selected item in the details panel."""
        raw_path = params.get("path", "")
        if not raw_path:
            return {"exists": False}

        try:
            p = Path(raw_path).resolve()
            if not p.exists():
                return {"exists": False, "full_path": raw_path}

            stat = p.stat()
            is_dir = p.is_dir()
            size_bytes = stat.st_size if not is_dir else None

            size_str = ""
            if size_bytes is not None:
                if size_bytes < 1024:
                    size_str = f"{size_bytes} B"
                elif size_bytes < 1024 * 1024:
                    size_str = f"{size_bytes / 1024:.2f} KB"
                elif size_bytes < 1024 * 1024 * 1024:
                    size_str = f"{size_bytes / (1024 * 1024):.2f} MB"
                else:
                    size_str = f"{size_bytes / (1024 * 1024 * 1024):.2f} GB"

            from datetime import datetime
            ctime_str = datetime.fromtimestamp(stat.st_ctime).strftime("%Y-%m-%d %H:%M")
            mtime_str = datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M")

            ext = p.suffix.lower().lstrip(".")
            type_desc = "Folder" if is_dir else (f"{ext.upper()} File" if ext else "File")

            return {
                "exists": True,
                "full_path": str(p),
                "is_dir": is_dir,
                "file_size": size_str,
                "file_size_bytes": size_bytes,
                "created_time": ctime_str,
                "modified_time": mtime_str,
                "file_type": type_desc,
                "extension": ext,
                "parent_dir": str(p.parent),
                "basename": p.name,
            }
        except Exception as e:
            logger.debug(f"Failed to fetch item metadata for {raw_path}: {e}")
            return {"exists": False, "full_path": raw_path, "error": str(e)}

    def hide_window(self, params: Optional[Dict[str, Any]] = None) -> None:
        self._wm.hide()

    def get_settings(self, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        s = load_spotlight_settings()
        res = s.to_dict()
        try:
            from clients.spotlight.settings import get_effective_theme, get_windows_system_theme
            res["system_theme"] = get_windows_system_theme()
            res["effective_theme"] = get_effective_theme(s)
        except Exception as e:
            logger.debug(f"Failed enriching spotlight settings: {e}")
        return res

    def update_settings(self, params: Dict[str, Any]) -> Dict[str, Any]:
        res = update_spotlight_settings(**params).to_dict()
        try:
            self._wm.apply_win32_window_styles()
            if any(k in params for k in ("position_preset", "monitor_mode", "fixed_monitor_index")):
                self._wm.reposition()
        except Exception:
            pass
        return res


class SpotlightWindowManager:
    """Manages the PyWebView window lifecycle, positioning, dynamic height, and Win32 focus blur."""

    def __init__(self, client: DevToolkitClient) -> None:
        self.client = client
        self.window = None
        self._hwnd: Optional[int] = None
        self._is_visible = False
        self._closing_for_real = False
        self._current_height = DEFAULT_EMPTY_HEIGHT
        self._settings_open = False
        self._just_shown_time = 0.0
        self._focus_watcher_started = False
        self._prev_active_hwnd: Optional[int] = None
        self._api = SpotlightJSAPI(self, client)

    def set_settings_open(self, is_open: bool) -> None:
        self._settings_open = is_open

    def get_dpi_scale(self) -> float:
        """Get the DPI scaling factor for the current window or system."""
        if sys.platform == "win32" and self._hwnd:
            try:
                import ctypes
                from ctypes import wintypes
                user32 = ctypes.windll.user32
                if hasattr(user32, "GetDpiForWindow"):
                    user32.GetDpiForWindow.argtypes = [wintypes.HWND]
                    user32.GetDpiForWindow.restype = wintypes.UINT
                    dpi = user32.GetDpiForWindow(self._hwnd)
                    if dpi > 0:
                        return dpi / 96.0
            except Exception as e:
                logger.debug(f"Error getting window DPI: {e}")
        return 1.0

    def set_height(self, new_height: int) -> None:
        """Dynamically resize window height based on active results."""
        new_height = max(DEFAULT_BAR_HEIGHT, min(new_height, MAX_WINDOW_HEIGHT))
        if new_height == self._current_height:
            return
        self._current_height = new_height
        if sys.platform == "win32" and self._hwnd:
            try:
                import ctypes
                from ctypes import wintypes
                user32 = ctypes.windll.user32

                user32.SetWindowPos.argtypes = [
                    wintypes.HWND, wintypes.HWND,
                    ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int,
                    wintypes.UINT
                ]
                user32.SetWindowPos.restype = wintypes.BOOL

                # Read current physical window rect to guarantee width never narrows
                rc = wintypes.RECT()
                user32.GetWindowRect.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.RECT)]
                user32.GetWindowRect.restype = wintypes.BOOL
                user32.GetWindowRect(self._hwnd, ctypes.byref(rc))

                current_phys_width = rc.right - rc.left
                scale = self.get_dpi_scale()
                expected_phys_width = int(WINDOW_WIDTH * scale)
                target_width = max(current_phys_width, expected_phys_width)
                target_height = int(new_height * scale)

                SWP_NOMOVE = 0x0002
                SWP_NOZORDER = 0x0004
                SWP_NOACTIVATE = 0x0010
                SWP_FRAMECHANGED = 0x0020
                user32.SetWindowPos(
                    self._hwnd, None, 0, 0, target_width, target_height,
                    SWP_NOMOVE | SWP_NOZORDER | SWP_NOACTIVATE | SWP_FRAMECHANGED
                )
            except Exception as e:
                logger.debug(f"Failed to set window height: {e}")

    def get_target_monitor_rect(self) -> tuple[int, int, int, int]:
        """Compute (left, top, width, height) of target monitor working area."""
        if sys.platform != "win32":
            return (0, 0, 1920, 1080)

        import ctypes
        from ctypes import wintypes

        user32 = ctypes.windll.user32
        settings = load_spotlight_settings()
        mode = settings.monitor_mode

        MONITOR_DEFAULTTONEAREST = 2

        class RECT(ctypes.Structure):
            _fields_ = [
                ("left", wintypes.LONG),
                ("top", wintypes.LONG),
                ("right", wintypes.LONG),
                ("bottom", wintypes.LONG),
            ]

        class MONITORINFO(ctypes.Structure):
            _fields_ = [
                ("cbSize", wintypes.DWORD),
                ("rcMonitor", RECT),
                ("rcWork", RECT),
                ("dwFlags", wintypes.DWORD),
            ]

        hmon = None
        if mode == "cursor":
            pt = wintypes.POINT()
            user32.GetCursorPos(ctypes.byref(pt))
            hmon = user32.MonitorFromPoint(pt, MONITOR_DEFAULTTONEAREST)
        elif mode == "focused":
            fg = user32.GetForegroundWindow()
            if fg:
                hmon = user32.MonitorFromWindow(fg, MONITOR_DEFAULTTONEAREST)
        elif mode.startswith("monitor_"):
            try:
                target_idx = int(mode.split("_")[-1])
                h_list = []
                MONITORENUMPROC = ctypes.WINFUNCTYPE(
                    wintypes.BOOL,
                    wintypes.HMONITOR,
                    wintypes.HDC,
                    ctypes.POINTER(RECT),
                    wintypes.LPARAM,
                )

                def _enum_cb(h, hdc, lprc, lp):
                    h_list.append(h)
                    return True

                user32.EnumDisplayMonitors(None, None, MONITORENUMPROC(_enum_cb), 0)
                if 0 <= target_idx < len(h_list):
                    hmon = h_list[target_idx]
            except Exception as e:
                logger.debug(f"Failed selecting monitor index: {e}")

        if not hmon:
            pt = wintypes.POINT(0, 0)
            hmon = user32.MonitorFromPoint(pt, MONITOR_DEFAULTTONEAREST)

        mi = MONITORINFO()
        mi.cbSize = ctypes.sizeof(MONITORINFO)
        user32.GetMonitorInfoW(hmon, ctypes.byref(mi))

        rc = mi.rcWork
        return (rc.left, rc.top, rc.right - rc.left, rc.bottom - rc.top)

    def calculate_window_position(self) -> tuple[int, int]:
        """Calculate screen placement based on configured position preset."""
        left, top, width, height = self.get_target_monitor_rect()
        scale = self.get_dpi_scale()
        phys_width = int(WINDOW_WIDTH * scale)
        phys_height = int(self._current_height * scale)

        from clients.spotlight.settings import load_spotlight_settings
        settings = load_spotlight_settings()
        preset = getattr(settings, "position_preset", "center") or "center"

        # Y Anchor: 22% (standard optical center) or 5% (top)
        if preset in ("center_top", "left_top", "right_top"):
            pos_top = top + int(height * 0.05)
        else:
            # Default 22% screen height anchor
            pos_top = top + int(height * 0.22)

        # X Anchor: Centered, Left (5%), or Right (95% - phys_width)
        if preset in ("left_center", "left_top"):
            pos_left = left + int(width * 0.05)
        elif preset in ("right_center", "right_top"):
            pos_left = left + width - phys_width - int(width * 0.05)
        else:
            # Center horizontally
            pos_left = left + (width - phys_width) // 2

        # Clamp safely within working area
        pos_left = max(left, min(pos_left, left + max(0, width - phys_width)))
        pos_top = max(top, min(pos_top, top + max(0, height - phys_height)))
        return pos_left, pos_top

    def reposition(self) -> None:
        """Reposition the window dynamically to match updated position preset / monitor."""
        if sys.platform != "win32" or not self._hwnd or not self._is_visible:
            return
        try:
            import ctypes
            from ctypes import wintypes
            user32 = ctypes.windll.user32
            pos_left, pos_top = self.calculate_window_position()
            scale = self.get_dpi_scale()
            phys_width = int(WINDOW_WIDTH * scale)
            phys_height = int(self._current_height * scale)
            SWP_NOZORDER = 0x0004
            SWP_NOACTIVATE = 0x0010
            SWP_FRAMECHANGED = 0x0020
            user32.SetWindowPos(
                self._hwnd, None, pos_left, pos_top, phys_width, phys_height,
                SWP_NOZORDER | SWP_NOACTIVATE | SWP_FRAMECHANGED
            )
        except Exception as e:
            logger.debug(f"Failed to reposition window: {e}")

    def apply_win32_window_styles(self) -> None:
        """Apply WS_EX_TOOLWINDOW, HWND_TOPMOST, and DWM Acrylic backdrop."""
        if sys.platform != "win32" or not self._hwnd:
            return
        try:
            import ctypes
            from ctypes import wintypes
            user32 = ctypes.windll.user32
            dwmapi = ctypes.windll.dwmapi

            GWL_STYLE = -16
            GWL_EXSTYLE = -20
            WS_BORDER = 0x00800000
            WS_THICKFRAME = 0x00040000
            WS_DLGFRAME = 0x00400000
            WS_CAPTION = 0x00C00000
            WS_EX_TOOLWINDOW = 0x00000080
            WS_EX_WINDOWEDGE = 0x00000100
            WS_EX_CLIENTEDGE = 0x00000200
            WS_EX_STATICEDGE = 0x00020000
            HWND_TOPMOST = -1
            SWP_NOMOVE = 0x0002
            SWP_NOSIZE = 0x0001
            SWP_NOACTIVATE = 0x0010
            SWP_FRAMECHANGED = 0x0020

            user32.SetWindowLongW.argtypes = [wintypes.HWND, ctypes.c_int, wintypes.LONG]
            user32.SetWindowLongW.restype = wintypes.LONG
            user32.SetWindowPos.argtypes = [
                wintypes.HWND, wintypes.HWND,
                ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int,
                wintypes.UINT
            ]
            user32.SetWindowPos.restype = wintypes.BOOL

            WS_EX_TRANSPARENT = 0x00000020
            WS_EX_LAYERED = 0x00080000

            # Strip classic window borders and sunken/raised edges
            current_style = user32.GetWindowLongW(self._hwnd, GWL_STYLE)
            user32.SetWindowLongW(self._hwnd, GWL_STYLE, current_style & ~(WS_BORDER | WS_THICKFRAME | WS_DLGFRAME | WS_CAPTION))

            current_ex = user32.GetWindowLongW(self._hwnd, GWL_EXSTYLE)
            user32.SetWindowLongW(
                self._hwnd,
                GWL_EXSTYLE,
                (current_ex | WS_EX_TOOLWINDOW) & ~(WS_EX_WINDOWEDGE | WS_EX_CLIENTEDGE | WS_EX_STATICEDGE | WS_EX_TRANSPARENT | WS_EX_LAYERED),
            )

            # 0. Set WinForms Form BackColor = Color.Black without TransparencyKey so WebView2 receives all mouse clicks and scroll events
            if hasattr(self.window, "native") and self.window.native:
                try:
                    import clr
                    clr.AddReference("System.Drawing")
                    from System.Drawing import Color
                    from System import Action
                    def _set_transparent_bg():
                        try:
                            if self.window and self.window.native:
                                self.window.native.BackColor = Color.Black
                                if hasattr(self.window.native, "TransparencyKey"):
                                    self.window.native.TransparencyKey = Color.Empty
                        except Exception:
                            pass
                    self.window.native.Invoke(Action(_set_transparent_bg))
                except Exception as e:
                    logger.debug(f"Failed setting form BackColor: {e}")

            # 1. Enable DWM Immersive Dark Mode matching system
            from clients.spotlight.settings import get_windows_system_theme
            sys_theme = get_windows_system_theme()
            is_dark = sys_theme.get("dark_mode", True)
            DWMWA_USE_IMMERSIVE_DARK_MODE = 20
            dark = ctypes.c_int(1 if is_dark else 0)
            dwmapi.DwmSetWindowAttribute(
                self._hwnd, DWMWA_USE_IMMERSIVE_DARK_MODE, ctypes.byref(dark), ctypes.sizeof(dark)
            )

            # 2. Suppress Windows 11 default 1px gray frame border: DWMWA_BORDER_COLOR = 34, DWMWA_COLOR_NONE = 0xFFFFFFFE
            DWMWA_BORDER_COLOR = 34
            DWMWA_COLOR_NONE = 0xFFFFFFFE
            noborder = ctypes.c_uint(DWMWA_COLOR_NONE)
            dwmapi.DwmSetWindowAttribute(
                self._hwnd, DWMWA_BORDER_COLOR, ctypes.byref(noborder), ctypes.sizeof(noborder)
            )

            # 3. Extend frame into client area across entire window
            class MARGINS(ctypes.Structure):
                _fields_ = [
                    ("cxLeftWidth", ctypes.c_int),
                    ("cxRightWidth", ctypes.c_int),
                    ("cyTopHeight", ctypes.c_int),
                    ("cyBottomHeight", ctypes.c_int),
                ]
            margins = MARGINS(-1, -1, -1, -1)
            dwmapi.DwmExtendFrameIntoClientArea(self._hwnd, ctypes.byref(margins))

            # 4. System Backdrop: DWMSBT_TRANSIENTWINDOW (Acrylic) = 3
            DWMWA_SYSTEMBACKDROP_TYPE = 38
            DWMSBT_TRANSIENTWINDOW = 3
            backdrop = ctypes.c_int(DWMSBT_TRANSIENTWINDOW)
            dwmapi.DwmSetWindowAttribute(
                self._hwnd, DWMWA_SYSTEMBACKDROP_TYPE, ctypes.byref(backdrop), ctypes.sizeof(backdrop)
            )

            # 4b. Windows Acrylic Blur Accent Policy fallback (AccentFlags = 0 to prevent border drawing)
            try:
                class ACCENT_POLICY(ctypes.Structure):
                    _fields_ = [
                        ("AccentState", ctypes.c_int),
                        ("AccentFlags", ctypes.c_int),
                        ("GradientColor", ctypes.c_uint),
                        ("AnimationId", ctypes.c_int),
                    ]

                class WINCOMPATTRDATA(ctypes.Structure):
                    _fields_ = [
                        ("Attribute", ctypes.c_int),
                        ("Data", ctypes.c_void_p),
                        ("SizeOfData", ctypes.c_size_t),
                    ]

                accent = ACCENT_POLICY()
                accent.AccentState = 4  # ACCENT_ENABLE_ACRYLICBLURBEHIND
                accent.AccentFlags = 0  # 0 = No native borders
                accent.GradientColor = 0x01141721 if is_dark else 0x01F5F5F5
                accent.AnimationId = 0

                data = WINCOMPATTRDATA()
                data.Attribute = 19  # WCA_ACCENT_POLICY
                data.Data = ctypes.cast(ctypes.pointer(accent), ctypes.c_void_p)
                data.SizeOfData = ctypes.sizeof(accent)

                user32.SetWindowCompositionAttribute.argtypes = [wintypes.HWND, ctypes.c_void_p]
                user32.SetWindowCompositionAttribute.restype = wintypes.BOOL
                user32.SetWindowCompositionAttribute(self._hwnd, ctypes.byref(data))
            except Exception:
                pass

            # 5. Window corner rounding: DWMWCP_ROUND = 2
            DWMWA_WINDOW_CORNER_PREFERENCE = 33
            DWMWCP_ROUND = 2
            corner = ctypes.c_int(DWMWCP_ROUND)
            dwmapi.DwmSetWindowAttribute(
                self._hwnd, DWMWA_WINDOW_CORNER_PREFERENCE, ctypes.byref(corner), ctypes.sizeof(corner)
            )

            # 6. Send WM_NCACTIVATE so DWM renders live acrylic blur even for tool windows
            WM_NCACTIVATE = 0x0086
            user32.SendMessageW(self._hwnd, WM_NCACTIVATE, 1, 0)

            # 7. Recalculate frame & force DWM composition update immediately
            user32.SetWindowPos(
                self._hwnd, wintypes.HWND(HWND_TOPMOST), 0, 0, 0, 0,
                SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE | SWP_FRAMECHANGED
            )

            # 8. Set native window icon from devspotlight.ico
            try:
                icon_candidates = [
                    Path(__file__).resolve().parent.parent.parent / "assets" / "devspotlight.ico",
                    Path(sys.executable).resolve().parent / "assets" / "devspotlight.ico",
                    Path(sys.executable).resolve().parent / "devspotlight.ico",
                    Path("assets/devspotlight.ico").resolve(),
                ]
                if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
                    icon_candidates.insert(0, Path(sys._MEIPASS) / "assets" / "devspotlight.ico")
                for ic_path in icon_candidates:
                    if ic_path.is_file():
                        h_icon = user32.LoadImageW(None, str(ic_path), 1, 0, 0, 0x00000010 | 0x00000040)
                        if h_icon:
                            WM_SETICON = 0x0080
                            user32.SendMessageW(self._hwnd, WM_SETICON, 0, h_icon)
                            user32.SendMessageW(self._hwnd, WM_SETICON, 1, h_icon)
                            break
            except Exception as e:
                logger.debug(f"Failed applying window icon: {e}")
        except Exception as e:
            logger.debug(f"Failed applying Win32 styles / DWM acrylic: {e}")

    def _start_focus_watcher(self) -> None:
        """Background thread monitoring foreground window to auto-dismiss on blur."""
        if self._focus_watcher_started or sys.platform != "win32":
            return
        self._focus_watcher_started = True

        def _focus_loop():
            import ctypes
            from ctypes import wintypes

            user32 = ctypes.windll.user32
            GA_ROOT = 2

            user32.GetForegroundWindow.restype = wintypes.HWND
            user32.GetAncestor.argtypes = [wintypes.HWND, wintypes.UINT]
            user32.GetAncestor.restype = wintypes.HWND
            user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
            user32.GetWindowThreadProcessId.restype = wintypes.DWORD

            my_pid = os.getpid()

            while not self._closing_for_real:
                time.sleep(0.06)
                if not self._is_visible or not self._hwnd:
                    continue

                # Grace period after showing so activation finishes
                if (time.time() - self._just_shown_time) < 0.35:
                    continue

                settings = load_spotlight_settings()
                if not settings.dismiss_on_blur:
                    continue
                if self._settings_open:
                    continue

                fg = user32.GetForegroundWindow()
                if not fg:
                    continue

                if fg == self._hwnd:
                    continue

                root = user32.GetAncestor(fg, GA_ROOT)
                if root == self._hwnd:
                    continue

                fg_pid = wintypes.DWORD()
                user32.GetWindowThreadProcessId(fg, ctypes.byref(fg_pid))
                if fg_pid.value != my_pid:
                    self.hide()
                elif root != self._hwnd and fg != self._hwnd:
                    self.hide()

        t = threading.Thread(target=_focus_loop, daemon=True, name="SpotlightFocusWatcher")
        t.start()

    def show(self, reset: bool = True) -> None:
        """Instant summon: reposition to target monitor and present window in <10ms."""
        self._just_shown_time = time.time()
        pos_left, pos_top = self.calculate_window_position()
        if sys.platform == "win32" and self._hwnd:
            import ctypes
            from ctypes import wintypes
            user32 = ctypes.windll.user32
            kernel32 = ctypes.windll.kernel32

            # Release Alt & Space keys to prevent Windows entering menu accelerator mode
            user32.keybd_event(0x12, 0, 2, 0)  # VK_MENU (Alt) up
            user32.keybd_event(0x20, 0, 2, 0)  # VK_SPACE up

            user32.SetWindowPos.argtypes = [
                wintypes.HWND, wintypes.HWND,
                ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int,
                wintypes.UINT
            ]
            user32.SetWindowPos.restype = wintypes.BOOL

            scale = self.get_dpi_scale()
            phys_width = int(WINDOW_WIDTH * scale)
            phys_height = int(self._current_height * scale)

            SWP_SHOWWINDOW = 0x0040
            SWP_FRAMECHANGED = 0x0020
            HWND_TOPMOST = -1
            SW_RESTORE = 9
            SW_SHOW = 5

            user32.SetWindowPos(
                self._hwnd, wintypes.HWND(HWND_TOPMOST), pos_left, pos_top, phys_width, phys_height, SWP_SHOWWINDOW | SWP_FRAMECHANGED
            )

            # Robust foreground window activation using AttachThreadInput
            fg_hwnd = user32.GetForegroundWindow()
            if fg_hwnd and fg_hwnd != self._hwnd:
                self._prev_active_hwnd = fg_hwnd
            cur_thread = kernel32.GetCurrentThreadId()
            fg_thread = user32.GetWindowThreadProcessId(fg_hwnd, None) if fg_hwnd else 0
            target_thread = user32.GetWindowThreadProcessId(self._hwnd, None) if self._hwnd else 0

            if fg_thread and fg_thread != cur_thread:
                user32.AttachThreadInput(cur_thread, fg_thread, True)
            if target_thread and target_thread != cur_thread:
                user32.AttachThreadInput(cur_thread, target_thread, True)

            user32.ShowWindow(self._hwnd, SW_RESTORE)
            user32.ShowWindow(self._hwnd, SW_SHOW)
            user32.BringWindowToTop(self._hwnd)
            user32.SetForegroundWindow(self._hwnd)

            if target_thread and target_thread != cur_thread:
                user32.AttachThreadInput(cur_thread, target_thread, False)
            if fg_thread and fg_thread != cur_thread:
                user32.AttachThreadInput(cur_thread, fg_thread, False)

            # Refresh DWM active rendering
            WM_NCACTIVATE = 0x0086
            user32.SendMessageW(self._hwnd, WM_NCACTIVATE, 1, 0)

            # Dispatch native activation and keyboard focus on WinForms GUI thread
            if hasattr(self.window, "native") and self.window.native:
                try:
                    from System import Action
                    def _do_native_focus():
                        try:
                            if self.window and self.window.native:
                                form = self.window.native
                                form.Show()
                                form.Activate()
                                form.BringToFront()
                                if hasattr(form, "webview") and form.webview:
                                    form.webview.Select()
                                    form.webview.Focus()
                                    try:
                                        user32.SetFocus(form.webview.Handle.ToInt32())
                                    except Exception:
                                        pass
                                elif hasattr(form, "browser") and hasattr(form.browser, "webview") and form.browser.webview:
                                    form.browser.webview.Select()
                                    form.browser.webview.Focus()
                                    try:
                                        user32.SetFocus(form.browser.webview.Handle.ToInt32())
                                    except Exception:
                                        pass
                        except Exception:
                            pass
                    self.window.native.BeginInvoke(Action(_do_native_focus))
                except Exception:
                    pass

            self._is_visible = True

            if self.window:
                try:
                    self.window.evaluate_js("if(window.reloadSpotlightSettings){ window.reloadSpotlightSettings(); }")
                    if reset:
                        self.window.evaluate_js("if(window.resetSpotlight){ window.resetSpotlight(); }")
                    else:
                        self.window.evaluate_js(
                            "if(window.focusInput){ window.focusInput(); setTimeout(window.focusInput, 50); setTimeout(window.focusInput, 150); }"
                        )
                except Exception:
                    pass
        else:
            if self.window:
                self.window.show()
                self._is_visible = True
                try:
                    self.window.evaluate_js("if(window.reloadSpotlightSettings){ window.reloadSpotlightSettings(); }")
                    if reset:
                        self.window.evaluate_js("if(window.resetSpotlight){ window.resetSpotlight(); }")
                except Exception:
                    pass

    def hide(self) -> None:
        """Instant hide."""
        if sys.platform == "win32" and self._hwnd:
            import ctypes
            user32 = ctypes.windll.user32
            SW_HIDE = 0
            user32.ShowWindow(self._hwnd, SW_HIDE)
            self._is_visible = False

            # Restore previous window if enabled
            try:
                settings = load_spotlight_settings()
                if settings.restore_window_on_esc and getattr(self, "_prev_active_hwnd", None):
                    prev = self._prev_active_hwnd
                    if prev and user32.IsWindow(prev) and prev != self._hwnd:
                        user32.BringWindowToTop(prev)
                        user32.SetForegroundWindow(prev)
                    self._prev_active_hwnd = None
            except Exception as e:
                logger.debug(f"Failed restoring foreground window: {e}")

            if self.window:
                try:
                    self.window.evaluate_js("if(window.resetSpotlight){ window.resetSpotlight(); }")
                except Exception:
                    pass
        else:
            if self.window:
                self.window.hide()
                self._is_visible = False
                try:
                    self.window.evaluate_js("if(window.resetSpotlight){ window.resetSpotlight(); }")
                except Exception:
                    pass

    def toggle(self) -> None:
        """Toggle between visible and hidden."""
        if self._is_visible:
            self.hide()
        else:
            self.show()

    def get_ui_html_path(self) -> Path:
        """Resolve the path to spotlight.html supporting both development and PyInstaller frozen runtime."""
        if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
            meipass_p = Path(sys._MEIPASS) / "clients" / "spotlight" / "ui" / "spotlight.html"
            if meipass_p.is_file():
                return meipass_p

        dev_p = Path(__file__).parent / "ui" / "spotlight.html"
        return dev_p

    def create_window(self) -> Any:
        """Create PyWebView window configured for Spotlight."""
        import webview

        ui_path = self.get_ui_html_path()
        html_content = ui_path.read_text(encoding="utf-8") if ui_path.is_file() else "<h1>DevToolkit Spotlight</h1>"
        pos_left, pos_top = self.calculate_window_position()

        self.window = webview.create_window(
            title=SPOTLIGHT_TITLE,
            html=html_content,
            width=WINDOW_WIDTH,
            height=self._current_height,
            x=pos_left,
            y=pos_top,
            frameless=True,
            easy_drag=False,
            on_top=True,
            transparent=True,
            js_api=self._api,
            text_select=True,
        )

        def on_loaded():
            time.sleep(0.05)
            if sys.platform == "win32":
                try:
                    if hasattr(self.window, "native") and self.window.native:
                        self._hwnd = int(self.window.native.Handle.ToInt32())
                except Exception:
                    pass
                if not self._hwnd:
                    import ctypes
                    from ctypes import wintypes

                    user32 = ctypes.windll.user32
                    user32.FindWindowW.argtypes = [wintypes.LPCWSTR, wintypes.LPCWSTR]
                    user32.FindWindowW.restype = wintypes.HWND
                    hwnd = user32.FindWindowW(None, SPOTLIGHT_TITLE)
                    if hwnd:
                        self._hwnd = int(hwnd)
                if self._hwnd:
                    self.apply_win32_window_styles()
                    self._start_focus_watcher()
                    self.show()

        def on_closing():
            if self._closing_for_real:
                return True
            self.hide()
            return False

        self.window.events.loaded += on_loaded
        self.window.events.closing += on_closing
        return self.window

    def start(self) -> None:
        """Start PyWebView window loop."""
        import webview

        if not self.window:
            self.create_window()
        webview.start()

    def open_settings_dialog(self) -> None:
        """Open settings dialog inside the active window."""
        self._settings_open = True
        self.show(reset=False)
        self.set_height(460)
        if self.window:
            try:
                self.window.evaluate_js("openSettings();")
            except Exception:
                pass

    def quit(self) -> None:
        """Destroy window and terminate process."""
        self._closing_for_real = True
        if self.window:
            try:
                self.window.destroy()
            except Exception:
                pass

