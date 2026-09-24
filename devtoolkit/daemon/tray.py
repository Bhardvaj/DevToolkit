"""Native Windows System Tray service and cross-platform desktop integration for DevToolkit."""

from __future__ import annotations

import logging
import os
from pathlib import Path
import subprocess
import sys
import threading
import time
import webbrowser
from typing import Callable, Optional

logger = logging.getLogger(__name__)

WINDOW_TITLE = "DevToolkit ⚡ Workstation Environment Inspector"
NATIVE_WINDOW_TITLE = "DevToolkit ⚡ Native Workstation Inspector"

# Win32 Menu Item Command IDs
ID_OPEN_WINDOW = 1001
ID_OPEN_BROWSER = 1002
ID_RESCAN = 1003
ID_REINDEX = 1004
ID_STATUS = 1005
ID_EXIT = 1006
ID_OPEN_NATIVE = 1007

# Win32 Constants
NIM_ADD = 0x00000000
NIM_MODIFY = 0x00000001
NIM_DELETE = 0x00000002

NIF_MESSAGE = 0x00000001
NIF_ICON = 0x00000002
NIF_TIP = 0x00000004
NIF_INFO = 0x00000010

NIIF_NONE = 0x00000000
NIIF_INFO = 0x00000001
NIIF_WARNING = 0x00000002
NIIF_ERROR = 0x00000003

WM_NULL = 0x0000
WM_DESTROY = 0x0002
WM_CLOSE = 0x0010
WM_USER = 0x0400
WM_TRAYICON = WM_USER + 20
WM_LBUTTONUP = 0x0202
WM_LBUTTONDBLCLK = 0x0203
WM_RBUTTONUP = 0x0205

MF_STRING = 0x00000000
MF_GRAYED = 0x00000001
MF_DISABLED = 0x00000002
MF_SEPARATOR = 0x00000800

TPM_LEFTALIGN = 0x0000
TPM_RIGHTBUTTON = 0x0002
TPM_NONOTIFY = 0x0080
TPM_RETURNCMD = 0x0100

SW_HIDE = 0
SW_SHOW = 5
SW_RESTORE = 9


def find_existing_window(title: str = WINDOW_TITLE) -> Optional[int]:
    """Search for an existing top-level window matching title on Windows."""
    if sys.platform != "win32":
        return None
    try:
        import ctypes
        from ctypes import wintypes

        user32 = ctypes.windll.user32
        user32.FindWindowW.argtypes = [wintypes.LPCWSTR, wintypes.LPCWSTR]
        user32.FindWindowW.restype = wintypes.HWND
        hwnd = user32.FindWindowW(None, title)
        return int(hwnd) if hwnd else None
    except Exception:
        return None


def restore_window_by_hwnd(hwnd: int) -> bool:
    """Restore and bring to foreground a Win32 window by HWND."""
    if sys.platform != "win32" or not hwnd:
        return False
    try:
        import ctypes
        from ctypes import wintypes

        user32 = ctypes.windll.user32
        user32.ShowWindow.argtypes = [wintypes.HWND, ctypes.c_int]
        user32.ShowWindow.restype = wintypes.BOOL
        user32.SetForegroundWindow.argtypes = [wintypes.HWND]
        user32.SetForegroundWindow.restype = wintypes.BOOL

        user32.ShowWindow(hwnd, SW_RESTORE)
        user32.ShowWindow(hwnd, SW_SHOW)
        user32.SetForegroundWindow(hwnd)
        return True
    except Exception as e:
        logger.debug(f"Failed to restore window {hwnd}: {e}")
        return False


def activate_or_launch_ui(port: int = 4321, title: str = WINDOW_TITLE) -> bool:
    """Restore an existing UI window if present, otherwise spawn the UI client."""
    hwnd = find_existing_window(title) or find_existing_window(NATIVE_WINDOW_TITLE)
    if hwnd:
        return restore_window_by_hwnd(hwnd)

    if getattr(sys, "frozen", False):
        cmd = [sys.executable, "--port", str(port)]
    else:
        cmd = [sys.executable, "-m", "devtoolkit.cli.main", "--port", str(port)]

    try:
        if sys.platform == "win32":
            creationflags = subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP
            subprocess.Popen(
                cmd,
                creationflags=creationflags,
                close_fds=True,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        else:
            subprocess.Popen(
                cmd,
                start_new_session=True,
                close_fds=True,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        return True
    except Exception as e:
        logger.error(f"Failed to spawn UI process: {e}")
        return False


def activate_or_launch_native_ui(port: int = 4321, title: str = NATIVE_WINDOW_TITLE) -> bool:
    """Restore an existing Native UI window if present, otherwise spawn the Native UI client."""
    hwnd = find_existing_window(title)
    if hwnd:
        return restore_window_by_hwnd(hwnd)

    if getattr(sys, "frozen", False):
        cmd = [sys.executable, "native", "--port", str(port)]
    else:
        cmd = [sys.executable, "-m", "devtoolkit.cli.main", "native", "--port", str(port)]

    try:
        if sys.platform == "win32":
            creationflags = subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP
            subprocess.Popen(
                cmd,
                creationflags=creationflags,
                close_fds=True,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        else:
            subprocess.Popen(
                cmd,
                start_new_session=True,
                close_fds=True,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        return True
    except Exception as e:
        logger.error(f"Failed to spawn Native UI process: {e}")
        return False


if sys.platform == "win32":
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
        class VERSION_OR_TIMEOUT(ctypes.Union):
            _fields_ = [
                ("uTimeout", wintypes.UINT),
                ("uVersion", wintypes.UINT),
            ]

        class GUID(ctypes.Structure):
            _fields_ = [
                ("Data1", wintypes.ULONG),
                ("Data2", wintypes.WORD),
                ("Data3", wintypes.WORD),
                ("Data4", wintypes.BYTE * 8),
            ]

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
            ("version_or_timeout", VERSION_OR_TIMEOUT),
            ("szInfoTitle", wintypes.WCHAR * 64),
            ("dwInfoFlags", wintypes.DWORD),
            ("guidItem", GUID),
            ("hBalloonIcon", wintypes.HICON),
        ]
        _anonymous_ = ["version_or_timeout"]

    kernel32.GetModuleHandleW.argtypes = [wintypes.LPCWSTR]
    kernel32.GetModuleHandleW.restype = wintypes.HMODULE

    user32.OpenDesktopW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    user32.OpenDesktopW.restype = wintypes.HANDLE

    user32.SetThreadDesktop.argtypes = [wintypes.HANDLE]
    user32.SetThreadDesktop.restype = wintypes.BOOL

    user32.RegisterClassExW.argtypes = [ctypes.POINTER(WNDCLASSEX)]
    user32.RegisterClassExW.restype = wintypes.ATOM
    user32.UnregisterClassW.argtypes = [wintypes.LPCWSTR, wintypes.HINSTANCE]
    user32.UnregisterClassW.restype = wintypes.BOOL


    user32.CreateWindowExW.argtypes = (
        wintypes.DWORD, wintypes.LPCWSTR, wintypes.LPCWSTR, wintypes.DWORD,
        wintypes.INT, wintypes.INT, wintypes.INT, wintypes.INT, wintypes.HWND,
        wintypes.HMENU, wintypes.HINSTANCE, wintypes.LPVOID,
    )
    user32.CreateWindowExW.restype = wintypes.HWND


    user32.DestroyWindow.argtypes = [wintypes.HWND]
    user32.DestroyWindow.restype = wintypes.BOOL

    user32.LoadIconW.argtypes = [wintypes.HINSTANCE, ctypes.c_void_p]
    user32.LoadIconW.restype = wintypes.HICON

    user32.CreatePopupMenu.restype = wintypes.HMENU
    user32.AppendMenuW.argtypes = [wintypes.HMENU, wintypes.UINT, wintypes.UINT, wintypes.LPCWSTR]
    user32.AppendMenuW.restype = wintypes.BOOL
    user32.DestroyMenu.argtypes = [wintypes.HMENU]
    user32.DestroyMenu.restype = wintypes.BOOL

    user32.GetCursorPos.argtypes = [ctypes.POINTER(wintypes.POINT)]
    user32.GetCursorPos.restype = wintypes.BOOL

    user32.SetForegroundWindow.argtypes = [wintypes.HWND]
    user32.SetForegroundWindow.restype = wintypes.BOOL

    user32.TrackPopupMenuEx.argtypes = [
        wintypes.HMENU, wintypes.UINT, wintypes.INT, wintypes.INT, wintypes.HWND, ctypes.c_void_p
    ]
    user32.TrackPopupMenuEx.restype = wintypes.UINT

    user32.PostMessageW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
    user32.PostMessageW.restype = wintypes.BOOL

    user32.PostQuitMessage.argtypes = [ctypes.c_int]

    user32.GetMessageW.argtypes = [ctypes.POINTER(wintypes.MSG), wintypes.HWND, wintypes.UINT, wintypes.UINT]
    user32.GetMessageW.restype = wintypes.BOOL

    user32.TranslateMessage.argtypes = [ctypes.POINTER(wintypes.MSG)]
    user32.TranslateMessage.restype = wintypes.BOOL

    user32.DispatchMessageW.argtypes = [ctypes.POINTER(wintypes.MSG)]
    user32.DispatchMessageW.restype = LRESULT

    shell32.Shell_NotifyIconW.argtypes = [wintypes.DWORD, ctypes.POINTER(NOTIFYICONDATAW)]
    shell32.Shell_NotifyIconW.restype = wintypes.BOOL


class DevToolkitTray:
    """Manages the background system tray icon, popup menu, and desktop notifications."""

    def __init__(
        self,
        port: int = 4321,
        host: str = "127.0.0.1",
        on_open_window: Optional[Callable[[], None]] = None,
        on_open_native: Optional[Callable[[], None]] = None,
        on_open_browser: Optional[Callable[[], None]] = None,
        on_rescan: Optional[Callable[[], None]] = None,
        on_reindex: Optional[Callable[[], None]] = None,
        on_exit: Optional[Callable[[], None]] = None,
    ):
        self.port = port
        self.host = host
        self.on_open_window = on_open_window
        self.on_open_native = on_open_native
        self.on_open_browser = on_open_browser
        self.on_rescan = on_rescan
        self.on_reindex = on_reindex
        self.on_exit = on_exit

        self._hwnd: Optional[int] = None
        self._atom = None
        self._hinst = None
        self._wproc = None
        self._nid: Optional[NOTIFYICONDATAW] = None
        self._thread: Optional[threading.Thread] = None
        self._is_running = False
        self._ready_event = threading.Event()

    @property
    def is_running(self) -> bool:
        return self._is_running

    def start(self) -> bool:
        """Start the system tray icon message pump thread."""
        if sys.platform != "win32":
            self._is_running = True
            return True

        if self._is_running:
            return True

        self._ready_event.clear()
        self._thread = threading.Thread(target=self._run_loop, daemon=True, name="DevToolkit-TrayThread")
        self._thread.start()
        self._ready_event.wait(timeout=3.0)
        return self._is_running

    def stop(self) -> None:
        """Remove tray icon and terminate the message pump thread."""
        if not self._is_running:
            return

        self._is_running = False
        if sys.platform == "win32" and self._hwnd:
            try:
                user32.PostMessageW(self._hwnd, WM_CLOSE, 0, 0)
            except Exception:
                pass

        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2.0)
        self._thread = None

    def show_notification(self, title: str, message: str, icon_type: int = NIIF_INFO) -> bool:
        """Display a balloon notification attached to the system tray icon."""
        if sys.platform != "win32" or not self._is_running or not self._hwnd:
            return False

        try:
            nid = NOTIFYICONDATAW()
            nid.cbSize = ctypes.sizeof(NOTIFYICONDATAW)
            nid.hWnd = self._hwnd
            nid.uID = 1001
            nid.uFlags = NIF_INFO
            nid.szInfo = str(message)[:255]
            nid.szInfoTitle = str(title)[:63]
            nid.dwInfoFlags = icon_type
            return bool(shell32.Shell_NotifyIconW(NIM_MODIFY, ctypes.byref(nid)))
        except Exception as e:
            logger.debug(f"Failed to display tray notification: {e}")
            return False

    def _get_icon_handle(self):
        """Retrieve standard or custom application icon handle."""
        try:
            # Check if custom icon exists beside app or in assets
            for candidate in ["assets/icon.ico", "icon.ico"]:
                p = Path(candidate)
                if p.is_file():
                    h = user32.LoadImageW(None, str(p.resolve()), 1, 0, 0, 0x00000010 | 0x00000040)
                    if h:
                        return h
            # Default: standard Windows application icon (IDI_APPLICATION = 32512)
            return user32.LoadIconW(None, ctypes.cast(32512, wintypes.LPCWSTR))
        except Exception:
            return None

    def _window_proc(self, hwnd, msg, wparam, lparam):
        if msg == WM_CLOSE:
            user32.DestroyWindow(hwnd)
            return 0
        elif msg == WM_DESTROY:
            user32.PostQuitMessage(0)
            return 0
        elif msg == WM_TRAYICON:
            if lparam in (WM_LBUTTONUP, WM_LBUTTONDBLCLK):
                self._handle_primary_click()
                return 0
            elif lparam == WM_RBUTTONUP:
                self._show_context_menu()
                return 0
        return user32.DefWindowProcW(hwnd, msg, wparam, lparam)

    def _run_loop(self):
        # Attach to the interactive user desktop if running from background session
        try:
            hdesk = user32.OpenDesktopW("Default", 0, False, 0x01FF)
            if hdesk:
                user32.SetThreadDesktop(hdesk)
        except Exception:
            pass

        self._wproc = WNDPROC(self._window_proc)
        self._hinst = kernel32.GetModuleHandleW(None)
        self._class_name = f"DevToolkitTray_{id(self)}_{int(time.time())}"

        self._wc = WNDCLASSEX(
            cbSize=ctypes.sizeof(WNDCLASSEX),
            style=0,
            lpfnWndProc=self._wproc,
            cbClsExtra=0,
            cbWndExtra=0,
            hInstance=self._hinst,
            hIcon=None,
            hCursor=None,
            hbrBackground=6,
            lpszMenuName=None,
            lpszClassName=self._class_name,
            hIconSm=None,
        )

        self._atom = user32.RegisterClassExW(ctypes.byref(self._wc))
        if not self._atom:
            self._ready_event.set()
            return

        self._hwnd = user32.CreateWindowExW(
            0, self._class_name, None, 0x80000000, 0, 0, 0, 0, 0, None, self._hinst, None
        )
        if not self._hwnd:
            self._ready_event.set()
            return

        hicon = self._get_icon_handle()
        tip_text = f"DevToolkit ⚡ Workstation Inspector (Port {self.port})"[:127]
        self._nid = NOTIFYICONDATAW(
            cbSize=ctypes.sizeof(NOTIFYICONDATAW),
            hWnd=self._hwnd,
            uID=1001,
            uFlags=NIF_MESSAGE | NIF_ICON | NIF_TIP,
            uCallbackMessage=WM_TRAYICON,
            hIcon=hicon,
            szTip=tip_text,
        )

        shell32.Shell_NotifyIconW(NIM_ADD, ctypes.byref(self._nid))
        self._is_running = True
        self._ready_event.set()

        msg = wintypes.MSG()
        while user32.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:
            user32.TranslateMessage(ctypes.byref(msg))
            user32.DispatchMessageW(ctypes.byref(msg))

        # Cleanup on exit
        if self._nid:
            try:
                shell32.Shell_NotifyIconW(NIM_DELETE, ctypes.byref(self._nid))
            except Exception:
                pass
        if self._class_name and self._hinst:
            try:
                user32.UnregisterClassW(self._class_name, self._hinst)
            except Exception:
                pass
        self._is_running = False


    def _show_context_menu(self):
        """Build and display the native Win32 context popup menu."""
        hmenu = user32.CreatePopupMenu()
        try:
            user32.AppendMenuW(hmenu, MF_STRING, ID_OPEN_WINDOW, "Open DevToolkit Window (Embedded)")
            user32.AppendMenuW(hmenu, MF_STRING, ID_OPEN_NATIVE, "Open Native Inspector (Desktop)")
            user32.AppendMenuW(hmenu, MF_STRING, ID_OPEN_BROWSER, "Open in Web Browser")
            user32.AppendMenuW(hmenu, MF_SEPARATOR, 0, None)
            user32.AppendMenuW(hmenu, MF_STRING, ID_RESCAN, "Re-scan Workstation Environment")
            user32.AppendMenuW(hmenu, MF_STRING, ID_REINDEX, "Search Engine Re-index")
            user32.AppendMenuW(hmenu, MF_SEPARATOR, 0, None)
            user32.AppendMenuW(hmenu, MF_STRING | MF_GRAYED, ID_STATUS, f"Status: Running (Port {self.port})")
            user32.AppendMenuW(hmenu, MF_STRING, ID_EXIT, "Exit DevToolkit")

            pt = wintypes.POINT()
            user32.GetCursorPos(ctypes.byref(pt))
            user32.SetForegroundWindow(self._hwnd)

            cmd = user32.TrackPopupMenuEx(
                hmenu,
                TPM_RETURNCMD | TPM_NONOTIFY | TPM_RIGHTBUTTON,
                pt.x,
                pt.y,
                self._hwnd,
                None,
            )
            user32.PostMessageW(self._hwnd, WM_NULL, 0, 0)

            if cmd == ID_OPEN_WINDOW:
                self._handle_primary_click()
            elif cmd == ID_OPEN_NATIVE:
                self._handle_open_native()
            elif cmd == ID_OPEN_BROWSER:
                self._handle_open_browser()
            elif cmd == ID_RESCAN:
                self._handle_rescan()
            elif cmd == ID_REINDEX:
                self._handle_reindex()
            elif cmd == ID_EXIT:
                self._handle_exit()
        finally:
            user32.DestroyMenu(hmenu)

    def _handle_primary_click(self):
        """Single-click / double-click action to restore or launch window."""
        if self.on_open_window:
            try:
                self.on_open_window()
                return
            except Exception as e:
                logger.debug(f"on_open_window callback error: {e}")

        activate_or_launch_ui(port=self.port)

    def _handle_open_native(self):
        """Open Native UI desktop window."""
        if self.on_open_native:
            try:
                self.on_open_native()
                return
            except Exception as e:
                logger.debug(f"on_open_native callback error: {e}")

        activate_or_launch_native_ui(port=self.port)

    def _handle_open_browser(self):
        """Open web dashboard in default browser."""
        if self.on_open_browser:
            try:
                self.on_open_browser()
                return
            except Exception:
                pass
        webbrowser.open(f"http://{self.host}:{self.port}")

    def _handle_rescan(self):
        """Trigger background workstation environment audit."""
        if self.on_rescan:
            try:
                self.on_rescan()
                return
            except Exception:
                pass

        def _worker():
            try:
                import urllib.request
                req = urllib.request.Request(
                    f"http://{self.host}:{self.port}/api/audit",
                    data=b"{}",
                    headers={"Content-Type": "application/json", "User-Agent": "DevToolkit-Tray"},
                    method="POST",
                )
                with urllib.request.urlopen(req, timeout=30.0) as resp:
                    if resp.status == 200:
                        self.show_notification(
                            "DevToolkit",
                            "Workstation environment re-scanned successfully!",
                        )
            except Exception as e:
                logger.warning(f"Tray re-scan trigger failed: {e}")

        threading.Thread(target=_worker, daemon=True).start()

    def _handle_reindex(self):
        """Trigger background search re-indexing."""
        if self.on_reindex:
            try:
                self.on_reindex()
                return
            except Exception:
                pass

        def _worker():
            try:
                import urllib.request
                req = urllib.request.Request(
                    f"http://{self.host}:{self.port}/api/search/reindex",
                    data=b"{}",
                    headers={"Content-Type": "application/json", "User-Agent": "DevToolkit-Tray"},
                    method="POST",
                )
                with urllib.request.urlopen(req, timeout=10.0) as resp:
                    if resp.status == 200:
                        self.show_notification(
                            "DevToolkit Search",
                            "Workstation search re-indexing started in background.",
                        )
            except Exception as e:
                logger.warning(f"Tray re-index trigger failed: {e}")

        threading.Thread(target=_worker, daemon=True).start()

    def _handle_exit(self):
        """Terminate the daemon and close any open client windows."""
        if sys.platform == "win32":
            for t in [WINDOW_TITLE, NATIVE_WINDOW_TITLE]:
                hwnd = find_existing_window(t)
                if hwnd:
                    try:
                        user32.PostMessageW(hwnd, WM_CLOSE, 0, 0)
                    except Exception:
                        pass

        if self.on_exit:
            try:
                self.on_exit()
                return
            except Exception:
                pass

        from devtoolkit.daemon.manager import stop_daemon
        stop_daemon()
