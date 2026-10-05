"""Dedicated native Windows system tray icon for DevToolkit Spotlight."""

from __future__ import annotations

import logging
import os
import sys
import threading
import time
from pathlib import Path
from typing import Callable, Optional

logger = logging.getLogger(__name__)

# Menu item command IDs
ID_OPEN_SPOTLIGHT = 2001
ID_SETTINGS = 2002
ID_OPEN_DASHBOARD = 2003
ID_EXIT_SPOTLIGHT = 2004

# Win32 Constants
NIM_ADD = 0x00000000
NIM_MODIFY = 0x00000001
NIM_DELETE = 0x00000002

NIF_MESSAGE = 0x00000001
NIF_ICON = 0x00000002
NIF_TIP = 0x00000004

WM_NULL = 0x0000
WM_DESTROY = 0x0002
WM_CLOSE = 0x0010
WM_USER = 0x0400
WM_TRAYICON = WM_USER + 30
WM_LBUTTONUP = 0x0202
WM_RBUTTONUP = 0x0205

MF_STRING = 0x00000000
MF_SEPARATOR = 0x00000800
TPM_RETURNCMD = 0x0100
TPM_NONOTIFY = 0x0080
TPM_RIGHTBUTTON = 0x0002


class SpotlightTray:
    """Dedicated system tray icon for DevToolkit Spotlight."""

    def __init__(
        self,
        on_open_spotlight: Optional[Callable[[], None]] = None,
        on_open_settings: Optional[Callable[[], None]] = None,
        on_exit: Optional[Callable[[], None]] = None,
    ) -> None:
        self.on_open_spotlight = on_open_spotlight
        self.on_open_settings = on_open_settings
        self.on_exit = on_exit

        self._hwnd: Optional[int] = None
        self._thread: Optional[threading.Thread] = None
        self._is_running = False
        self._class_name = f"SpotlightTray_{id(self)}_{int(time.time())}"

    def start(self) -> bool:
        if sys.platform != "win32":
            return False
        if self._is_running:
            return True

        self._is_running = True
        self._thread = threading.Thread(target=self._run_loop, name="SpotlightTrayThread", daemon=True)
        self._thread.start()
        return True

    def _get_icon_handle(self, hinst=None):
        import ctypes
        from ctypes import wintypes
        user32 = ctypes.windll.user32
        kernel32 = ctypes.windll.kernel32

        kernel32.GetModuleHandleW.argtypes = [wintypes.LPCWSTR]
        kernel32.GetModuleHandleW.restype = wintypes.HINSTANCE

        user32.LoadImageW.argtypes = [
            wintypes.HINSTANCE,
            wintypes.LPCWSTR,
            wintypes.UINT,
            ctypes.c_int,
            ctypes.c_int,
            wintypes.UINT,
        ]
        user32.LoadImageW.restype = wintypes.HANDLE

        user32.LoadIconW.argtypes = [wintypes.HINSTANCE, wintypes.LPCWSTR]
        user32.LoadIconW.restype = wintypes.HICON

        if hinst is None:
            hinst = kernel32.GetModuleHandleW(None)

        cx = user32.GetSystemMetrics(49)  # SM_CXSMICON
        cy = user32.GetSystemMetrics(50)  # SM_CYSMICON

        # 1. Check candidate paths for devspotlight.ico
        candidates = []
        if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
            candidates.append(Path(sys._MEIPASS) / "assets" / "devspotlight.ico")
            candidates.append(Path(sys._MEIPASS) / "devspotlight.ico")

        candidates.append(Path(__file__).resolve().parent.parent.parent / "assets" / "devspotlight.ico")
        candidates.append(Path(sys.executable).resolve().parent / "assets" / "devspotlight.ico")
        candidates.append(Path(sys.executable).resolve().parent / "devspotlight.ico")
        candidates.append(Path("assets/devspotlight.ico").resolve())
        candidates.append(Path(__file__).resolve().parent / "devspotlight.ico")

        for p in candidates:
            if p.is_file():
                h = user32.LoadImageW(None, str(p), 1, cx, cy, 0x00000010)
                if h:
                    return h
                h = user32.LoadImageW(None, str(p), 1, 0, 0, 0x00000010 | 0x00000040)
                if h:
                    return h

        # 2. In compiled .exe (PyInstaller), load embedded icon resource (ID 1)
        if getattr(sys, "frozen", False) and hinst:
            h = user32.LoadImageW(hinst, ctypes.cast(1, wintypes.LPCWSTR), 1, cx, cy, 0)
            if h:
                return h
            h = user32.LoadIconW(hinst, ctypes.cast(1, wintypes.LPCWSTR))
            if h:
                return h

        return user32.LoadIconW(None, ctypes.cast(32512, wintypes.LPCWSTR))

    def _run_loop(self) -> None:
        import ctypes
        from ctypes import wintypes

        user32 = ctypes.windll.user32
        kernel32 = ctypes.windll.kernel32
        shell32 = ctypes.windll.shell32

        LRESULT = ctypes.c_ssize_t
        user32.DefWindowProcW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
        user32.DefWindowProcW.restype = LRESULT
        WNDPROC = ctypes.WINFUNCTYPE(LRESULT, wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM)

        class WNDCLASSEX(ctypes.Structure):
            _fields_ = [
                ("cbSize", wintypes.UINT),
                ("style", wintypes.UINT),
                ("lpfnWndProc", WNDPROC),
                ("cbClsExtra", wintypes.INT),
                ("cbWndExtra", wintypes.INT),
                ("hInstance", wintypes.HANDLE),
                ("hIcon", wintypes.HICON),
                ("hCursor", wintypes.HANDLE),
                ("hbrBackground", wintypes.HBRUSH),
                ("lpszMenuName", wintypes.LPCWSTR),
                ("lpszClassName", wintypes.LPCWSTR),
                ("hIconSm", wintypes.HICON),
            ]

        class NOTIFYICONDATAW(ctypes.Structure):
            _fields_ = [
                ("cbSize", wintypes.DWORD),
                ("hWnd", wintypes.HWND),
                ("uID", wintypes.UINT),
                ("uFlags", wintypes.UINT),
                ("uCallbackMessage", wintypes.UINT),
                ("hIcon", wintypes.HICON),
                ("szTip", wintypes.WCHAR * 128),
                ("dwState", wintypes.DWORD),
                ("dwStateMask", wintypes.DWORD),
                ("szInfo", wintypes.WCHAR * 256),
                ("uTimeoutOrVersion", wintypes.UINT),
                ("szInfoTitle", wintypes.WCHAR * 64),
                ("dwInfoFlags", wintypes.DWORD),
            ]

        def _window_proc(hwnd, msg, wparam, lparam):
            if msg == WM_TRAYICON:
                if lparam == WM_LBUTTONUP:
                    if self.on_open_spotlight:
                        self.on_open_spotlight()
                    return 0
                elif lparam == WM_RBUTTONUP:
                    self._show_context_menu(hwnd)
                    return 0
            elif msg == WM_DESTROY:
                user32.PostQuitMessage(0)
                return 0
            return user32.DefWindowProcW(hwnd, msg, wparam, lparam)

        wproc = WNDPROC(_window_proc)
        hinst = kernel32.GetModuleHandleW(None)

        wc = WNDCLASSEX(
            cbSize=ctypes.sizeof(WNDCLASSEX),
            style=0,
            lpfnWndProc=wproc,
            cbClsExtra=0,
            cbWndExtra=0,
            hInstance=hinst,
            hIcon=None,
            hCursor=None,
            hbrBackground=None,
            lpszMenuName=None,
            lpszClassName=self._class_name,
            hIconSm=None,
        )
        user32.RegisterClassExW(ctypes.byref(wc))

        hwnd = user32.CreateWindowExW(
            0, self._class_name, "SpotlightTrayHiddenWindow", 0, 0, 0, 0, 0, None, None, hinst, None
        )
        self._hwnd = hwnd

        # Register tray icon
        hicon = self._get_icon_handle(hinst)
        nid = NOTIFYICONDATAW()
        nid.cbSize = ctypes.sizeof(NOTIFYICONDATAW)
        nid.hWnd = hwnd
        nid.uID = 1
        nid.uFlags = NIF_MESSAGE | NIF_ICON | NIF_TIP
        nid.uCallbackMessage = WM_TRAYICON
        nid.hIcon = hicon
        nid.szTip = "DevToolkit Spotlight ⚡ (Alt+Space)"

        shell32.Shell_NotifyIconW(NIM_ADD, ctypes.byref(nid))

        msg = wintypes.MSG()
        try:
            while self._is_running:
                res = user32.GetMessageW(ctypes.byref(msg), None, 0, 0)
                if res <= 0:
                    break
                user32.TranslateMessage(ctypes.byref(msg))
                user32.DispatchMessageW(ctypes.byref(msg))
        finally:
            shell32.Shell_NotifyIconW(NIM_DELETE, ctypes.byref(nid))
            user32.DestroyWindow(hwnd)
            user32.UnregisterClassW(self._class_name, hinst)
            self._is_running = False

    def _show_context_menu(self, hwnd: int) -> None:
        import ctypes
        from ctypes import wintypes
        import webbrowser

        user32 = ctypes.windll.user32
        hmenu = user32.CreatePopupMenu()
        try:
            user32.AppendMenuW(hmenu, MF_STRING, ID_OPEN_SPOTLIGHT, "Open Spotlight (Alt+Space)")
            user32.AppendMenuW(hmenu, MF_STRING, ID_SETTINGS, "Settings...")
            user32.AppendMenuW(hmenu, MF_STRING, ID_OPEN_DASHBOARD, "Open DevToolkit Dashboard")
            user32.AppendMenuW(hmenu, MF_SEPARATOR, 0, None)
            user32.AppendMenuW(hmenu, MF_STRING, ID_EXIT_SPOTLIGHT, "Exit Spotlight")

            pt = wintypes.POINT()
            user32.GetCursorPos(ctypes.byref(pt))
            user32.SetForegroundWindow(hwnd)

            cmd = user32.TrackPopupMenuEx(
                hmenu, TPM_RETURNCMD | TPM_NONOTIFY | TPM_RIGHTBUTTON, pt.x, pt.y, hwnd, None
            )
            user32.PostMessageW(hwnd, WM_NULL, 0, 0)

            if cmd == ID_OPEN_SPOTLIGHT and self.on_open_spotlight:
                self.on_open_spotlight()
            elif cmd == ID_SETTINGS and self.on_open_settings:
                self.on_open_settings()
            elif cmd == ID_OPEN_DASHBOARD:
                webbrowser.open("http://127.0.0.1:4321")
            elif cmd == ID_EXIT_SPOTLIGHT and self.on_exit:
                self.on_exit()
        finally:
            user32.DestroyMenu(hmenu)

    def stop(self) -> None:
        self._is_running = False
        if sys.platform == "win32" and self._hwnd:
            try:
                import ctypes
                user32 = ctypes.windll.user32
                user32.PostMessageW(self._hwnd, WM_CLOSE, 0, 0)
            except Exception:
                pass

