"""Global keyboard hotkey listener for DevToolkit Spotlight."""

from __future__ import annotations

import logging
import sys
import threading
import time
from typing import Callable, Optional

logger = logging.getLogger(__name__)

# Win32 Constants
MOD_ALT = 0x0001
MOD_CONTROL = 0x0002
MOD_SHIFT = 0x0004
MOD_WIN = 0x0008
MOD_NOREPEAT = 0x4000

WM_HOTKEY = 0x0312
WM_QUIT = 0x0012
VK_SPACE = 0x20


def parse_hotkey_string(hotkey_str: str) -> tuple[int, int]:
    """Parse string representation of hotkey into (modifiers, vk_code).

    Examples:
        'alt+space' -> (MOD_ALT | MOD_NOREPEAT, VK_SPACE)
        'ctrl+shift+space' -> (MOD_CONTROL | MOD_SHIFT | MOD_NOREPEAT, VK_SPACE)
    """
    parts = [p.strip().lower() for p in hotkey_str.split("+")]
    modifiers = MOD_NOREPEAT
    vk_code = VK_SPACE

    for part in parts[:-1]:
        if part in ("alt", "menu"):
            modifiers |= MOD_ALT
        elif part in ("ctrl", "control"):
            modifiers |= MOD_CONTROL
        elif part == "shift":
            modifiers |= MOD_SHIFT
        elif part in ("win", "windows", "super"):
            modifiers |= MOD_WIN

    SPECIAL_KEYS = {
        "space": 0x20,
        "spacebar": 0x20,
        "tab": 0x09,
        "enter": 0x0D,
        "return": 0x0D,
        "escape": 0x1B,
        "esc": 0x1B,
        "backspace": 0x08,
        "delete": 0x2E,
        "del": 0x2E,
        "insert": 0x2D,
        "home": 0x24,
        "end": 0x23,
        "pageup": 0x21,
        "pagedown": 0x22,
        "up": 0x26,
        "down": 0x28,
        "left": 0x25,
        "right": 0x27,
        "`": 0xC0,
        "~": 0xC0,
        "grave": 0xC0,
        "tilde": 0xC0,
        "-": 0xBD,
        "=": 0xBB,
        "[": 0xDB,
        "]": 0xDD,
        "\\": 0xDC,
        ";": 0xBA,
        "'": 0xDE,
        ",": 0xBC,
        ".": 0xBE,
        "/": 0xBF,
    }

    key = parts[-1] if parts else "space"
    if key in SPECIAL_KEYS:
        vk_code = SPECIAL_KEYS[key]
    elif len(key) == 1 and key.isalnum():
        vk_code = ord(key.upper())
    elif key.startswith("f") and key[1:].isdigit():
        vk_code = 0x6F + int(key[1:])  # VK_F1 is 0x70

    return modifiers, vk_code


class GlobalHotkeyListener:
    """Threaded Win32 RegisterHotKey listener."""

    def __init__(
        self,
        hotkey_str: str = "alt+space",
        fallback_hotkey_str: str = "alt+shift+space",
        on_hotkey: Optional[Callable[[], None]] = None,
    ) -> None:
        self.hotkey_str = hotkey_str
        self.fallback_hotkey_str = fallback_hotkey_str
        self.on_hotkey = on_hotkey
        self._thread: Optional[threading.Thread] = None
        self._thread_id: Optional[int] = None
        self._is_running = False
        self._hotkey_id = 0x5001

    def start(self) -> bool:
        """Start the background hotkey message loop."""
        if sys.platform != "win32":
            logger.warning("Global hotkeys only supported on Windows.")
            return False

        if self._is_running:
            return True

        self._is_running = True
        self._thread = threading.Thread(target=self._run_loop, name="SpotlightHotkeyThread", daemon=True)
        self._thread.start()
        return True

    def _run_loop(self) -> None:
        import ctypes
        from ctypes import wintypes

        user32 = ctypes.windll.user32
        kernel32 = ctypes.windll.kernel32

        self._thread_id = kernel32.GetCurrentThreadId()
        modifiers, vk_code = parse_hotkey_string(self.hotkey_str)

        # Force thread message queue creation
        msg = wintypes.MSG()
        user32.PeekMessageW(ctypes.byref(msg), None, 0, 0, 0)

        # Register hotkey on current thread
        success = user32.RegisterHotKey(None, self._hotkey_id, modifiers, vk_code)
        if not success:
            logger.warning(
                f"Failed to register global hotkey '{self.hotkey_str}'. Attempting fallback '{self.fallback_hotkey_str}'..."
            )
            # Try fallback hotkey
            fb_modifiers, fb_vk_code = parse_hotkey_string(self.fallback_hotkey_str)
            success = user32.RegisterHotKey(None, self._hotkey_id, fb_modifiers, fb_vk_code)
            if success:
                logger.info(f"Registered fallback hotkey: {self.fallback_hotkey_str}")
            else:
                logger.error(f"Could not register primary '{self.hotkey_str}' or fallback '{self.fallback_hotkey_str}'.")
        else:
            logger.info(f"Registered global hotkey '{self.hotkey_str}' successfully.")

        try:
            while self._is_running:
                res = user32.GetMessageW(ctypes.byref(msg), None, 0, 0)
                if res <= 0 or msg.message == WM_QUIT:
                    break

                if msg.message == WM_HOTKEY and msg.wParam == self._hotkey_id:
                    if self.on_hotkey:
                        try:
                            self.on_hotkey()
                        except Exception as e:
                            logger.error(f"Error in on_hotkey callback: {e}")

                user32.TranslateMessage(ctypes.byref(msg))
                user32.DispatchMessageW(ctypes.byref(msg))
        finally:
            user32.UnregisterHotKey(None, self._hotkey_id)
            self._is_running = False

    def stop(self) -> None:
        """Unregister hotkey and stop the listener thread."""
        if not self._is_running:
            return

        self._is_running = False
        if sys.platform == "win32" and self._thread_id:
            try:
                import ctypes
                user32 = ctypes.windll.user32
                user32.PostThreadMessageW(self._thread_id, WM_QUIT, 0, 0)
            except Exception:
                pass

        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=1.0)
        self._thread = None

