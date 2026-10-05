"""Native Windows application and process icon extraction using Win32 Shell & GDI+.

Extracts crisp, high-resolution (48x48 / 64x64 / 256x256), arrow-free application
artwork using Windows System ImageList and GDI+ bicubic supersampling.
"""

from __future__ import annotations

import base64
import logging
import os
import sys
import threading
import uuid
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

_icon_cache: Dict[str, Optional[str]] = {}
_cache_lock = threading.Lock()
_gdi_initialized = False
_gdi_init_lock = threading.Lock()
_gdi_available: Optional[bool] = None

# GDI+ PNG Encoder CLSID: {557cf406-1a04-11d3-9a73-0000f81ef32e}
_PNG_CLSID_BYTES = uuid.UUID("{557cf406-1a04-11d3-9a73-0000f81ef32e}").bytes_le

# Windows System ImageList GUID: {46EB5926-582E-4017-9FDF-E8998DAA0950}
_IID_IIMAGELIST_BYTES = uuid.UUID("{46EB5926-582E-4017-9FDF-E8998DAA0950}").bytes_le

_gdi_token = None
_gdi_startup_input = None

# Global Shell ImageList handles
_p_imglist_jumbo = None
_p_imglist_xlarge = None


def _init_gdiplus() -> bool:
    """Initialize Windows GDI+ subsystem and System ImageLists."""
    global _gdi_initialized, _gdi_available, _gdi_token, _gdi_startup_input
    global _p_imglist_jumbo, _p_imglist_xlarge
    with _gdi_init_lock:
        if _gdi_initialized:
            return bool(_gdi_available)

        if sys.platform != "win32":
            _gdi_available = False
            _gdi_initialized = True
            return False

        try:
            import ctypes
            from ctypes import wintypes

            kernel32 = ctypes.windll.kernel32
            ole32 = ctypes.windll.ole32
            shell32 = ctypes.windll.shell32
            comctl32 = ctypes.windll.comctl32

            # Initialize COM on the thread
            ole32.CoInitialize(None)

            # Configure ctypes signatures for 64-bit safety
            kernel32.GlobalLock.argtypes = [wintypes.HGLOBAL]
            kernel32.GlobalLock.restype = ctypes.c_void_p
            kernel32.GlobalSize.argtypes = [wintypes.HGLOBAL]
            kernel32.GlobalSize.restype = ctypes.c_size_t
            kernel32.GlobalUnlock.argtypes = [wintypes.HGLOBAL]
            kernel32.GlobalUnlock.restype = wintypes.BOOL

            ole32.CreateStreamOnHGlobal.argtypes = [wintypes.HGLOBAL, wintypes.BOOL, ctypes.POINTER(ctypes.c_void_p)]
            ole32.CreateStreamOnHGlobal.restype = ctypes.c_long
            ole32.GetHGlobalFromStream.argtypes = [ctypes.c_void_p, ctypes.POINTER(wintypes.HGLOBAL)]
            ole32.GetHGlobalFromStream.restype = ctypes.c_long

            # ImageList_GetIcon: HICON ImageList_GetIcon(HIMAGELIST himl, int i, UINT flags)
            comctl32.ImageList_GetIcon.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_uint]
            comctl32.ImageList_GetIcon.restype = wintypes.HICON

            class GdiplusStartupInput(ctypes.Structure):
                _fields_ = [
                    ("GdiplusVersion", wintypes.UINT),
                    ("DebugEventCallback", ctypes.c_void_p),
                    ("SuppressBackgroundThread", wintypes.BOOL),
                    ("SuppressExternalCodecs", wintypes.BOOL),
                ]

            gdiplus = ctypes.windll.gdiplus
            _gdi_token = ctypes.c_void_p()
            _gdi_startup_input = GdiplusStartupInput(1, None, False, False)
            status = gdiplus.GdiplusStartup(ctypes.byref(_gdi_token), ctypes.byref(_gdi_startup_input), None)
            _gdi_available = status == 0

            # Pre-acquire Windows System ImageLists (JUMBO=256x256, EXTRALARGE=48x48)
            class GUID(ctypes.Structure):
                _fields_ = [
                    ("Data1", wintypes.DWORD),
                    ("Data2", wintypes.WORD),
                    ("Data3", wintypes.WORD),
                    ("Data4", ctypes.c_ubyte * 8),
                ]

            iid_imagelist = GUID.from_buffer_copy(_IID_IIMAGELIST_BYTES)

            p_jumbo = ctypes.c_void_p()
            hr_j = shell32.SHGetImageList(4, ctypes.byref(iid_imagelist), ctypes.byref(p_jumbo))
            if hr_j == 0 and p_jumbo.value:
                _p_imglist_jumbo = p_jumbo

            p_xlarge = ctypes.c_void_p()
            hr_xl = shell32.SHGetImageList(2, ctypes.byref(iid_imagelist), ctypes.byref(p_xlarge))
            if hr_xl == 0 and p_xlarge.value:
                _p_imglist_xlarge = p_xlarge

        except Exception as e:
            logger.debug(f"GDI+/ImageList initialization error: {e}")
            _gdi_available = False

        _gdi_initialized = True
        return bool(_gdi_available)


def _encode_bitmap_to_png_data_url(
    p_bitmap: ctypes.c_void_p,
    target_size: int = 64,
) -> Optional[str]:
    """Resizes (if needed) and serializes a GDI+ bitmap to a PNG data URL."""
    import ctypes
    from ctypes import wintypes

    gdiplus = ctypes.windll.gdiplus
    ole32 = ctypes.windll.ole32
    kernel32 = ctypes.windll.kernel32

    w = wintypes.UINT()
    h = wintypes.UINT()
    gdiplus.GdipGetImageWidth(p_bitmap, ctypes.byref(w))
    gdiplus.GdipGetImageHeight(p_bitmap, ctypes.byref(h))

    p_final = p_bitmap
    p_resized = None

    # Downscale high-res icons (e.g. 256x256 -> target_size) using high-quality bicubic resampling
    if (w.value != target_size or h.value != target_size) and w.value > 0 and h.value > 0:
        p_canvas = ctypes.c_void_p()
        # PixelFormat32bppARGB = 0x26200A
        st_res = gdiplus.GdipCreateBitmapFromScan0(target_size, target_size, 0, 0x26200A, None, ctypes.byref(p_canvas))
        if st_res == 0 and p_canvas:
            p_gfx = ctypes.c_void_p()
            gdiplus.GdipGetImageGraphicsContext(p_canvas, ctypes.byref(p_gfx))
            # InterpolationModeHighQualityBicubic = 7
            gdiplus.GdipSetInterpolationMode(p_gfx, 7)
            # SmoothingModeAntiAlias = 2
            gdiplus.GdipSetSmoothingMode(p_gfx, 2)
            # PixelOffsetModeHalf = 4
            gdiplus.GdipSetPixelOffsetMode(p_gfx, 4)
            # Draw original into target
            gdiplus.GdipDrawImageRectRectI(
                p_gfx, p_bitmap, 0, 0, target_size, target_size, 0, 0, w.value, h.value, 2, None, None, None
            )
            gdiplus.GdipDeleteGraphics(p_gfx)
            p_resized = p_canvas
            p_final = p_canvas

    # Create in-memory IStream
    p_stream = ctypes.c_void_p()
    ole32.CreateStreamOnHGlobal(None, True, ctypes.byref(p_stream))
    if not p_stream or not p_stream.value:
        if p_resized:
            gdiplus.GdipDisposeImage(p_resized)
        return None

    png_clsid = (ctypes.c_ubyte * 16)(*_PNG_CLSID_BYTES)
    st = gdiplus.GdipSaveImageToStream(p_final, p_stream, ctypes.byref(png_clsid), None)

    if p_resized:
        gdiplus.GdipDisposeImage(p_resized)

    if st != 0:
        _release_istream(p_stream)
        return None

    # Read PNG bytes from HGLOBAL
    h_global = wintypes.HGLOBAL()
    ole32.GetHGlobalFromStream(p_stream, ctypes.byref(h_global))

    size = kernel32.GlobalSize(h_global)
    ptr = kernel32.GlobalLock(h_global)
    png_data = ctypes.string_at(ptr, size)
    kernel32.GlobalUnlock(h_global)

    _release_istream(p_stream)

    b64 = base64.b64encode(png_data).decode("ascii")
    return f"data:image/png;base64,{b64}"


def _release_istream(p_stream: ctypes.c_void_p) -> None:
    """Safely invokes IUnknown::Release on an IStream pointer."""
    try:
        import ctypes

        vtbl = ctypes.cast(p_stream.value, ctypes.POINTER(ctypes.POINTER(ctypes.c_void_p))).contents
        # Release is method #2 (QI=0, AddRef=1, Release=2)
        release_fn = ctypes.WINFUNCTYPE(ctypes.c_ulong, ctypes.c_void_p)(vtbl[2])
        release_fn(p_stream.value)
    except Exception:
        pass


def get_app_icon_data_url(path: str, target_size: int = 64) -> Optional[str]:
    """Extract native Windows application icon as a crisp, arrow-free PNG data URL.

    Uses Windows System ImageList (SHIL_JUMBO or SHIL_EXTRALARGE) to ensure
    icons are rendered at native high resolution without shortcut arrow overlays.
    """
    if not path or not isinstance(path, str) or sys.platform != "win32":
        return None

    clean_path = os.path.normpath(path)
    norm_key = clean_path.lower()

    with _cache_lock:
        if norm_key in _icon_cache:
            return _icon_cache[norm_key]

    if not os.path.exists(clean_path):
        with _cache_lock:
            _icon_cache[norm_key] = None
        return None

    if not _init_gdiplus():
        with _cache_lock:
            _icon_cache[norm_key] = None
        return None

    try:
        import ctypes
        from ctypes import wintypes

        shell32 = ctypes.windll.shell32
        user32 = ctypes.windll.user32
        comctl32 = ctypes.windll.comctl32
        gdiplus = ctypes.windll.gdiplus

        class SHFILEINFO(ctypes.Structure):
            _fields_ = [
                ("hIcon", wintypes.HICON),
                ("iIcon", ctypes.c_int),
                ("dwAttributes", wintypes.DWORD),
                ("szDisplayName", wintypes.WCHAR * 260),
                ("szTypeName", wintypes.WCHAR * 80),
            ]

        SHGFI_SYSICONINDEX = 0x00004000
        SHGFI_ICON = 0x00000100
        SHGFI_LARGEICON = 0x00000000  # 32x32 fallback

        sfi = SHFILEINFO()
        # Query system icon index for pure arrow-free extraction
        res = shell32.SHGetFileInfoW(
            clean_path,
            0,
            ctypes.byref(sfi),
            ctypes.sizeof(sfi),
            SHGFI_SYSICONINDEX,
        )

        h_icon = None

        if res and sfi.iIcon >= 0:
            # 1. Try JUMBO (256x256) first for maximum fidelity
            if _p_imglist_jumbo and _p_imglist_jumbo.value:
                # ILD_TRANSPARENT = 0x00000001
                h_icon = comctl32.ImageList_GetIcon(_p_imglist_jumbo, sfi.iIcon, 1)

            # 2. Fall back to EXTRALARGE (48x48)
            if not h_icon and _p_imglist_xlarge and _p_imglist_xlarge.value:
                h_icon = comctl32.ImageList_GetIcon(_p_imglist_xlarge, sfi.iIcon, 1)

        # 3. Fall back to standard SHGetFileInfoW icon extraction
        if not h_icon:
            sfi_fallback = SHFILEINFO()
            res_fb = shell32.SHGetFileInfoW(
                clean_path,
                0,
                ctypes.byref(sfi_fallback),
                ctypes.sizeof(sfi_fallback),
                SHGFI_ICON | SHGFI_LARGEICON,
            )
            if res_fb and sfi_fallback.hIcon:
                h_icon = sfi_fallback.hIcon

        if not h_icon:
            with _cache_lock:
                _icon_cache[norm_key] = None
            return None

        # Convert HICON -> GDI+ Bitmap
        p_bitmap = ctypes.c_void_p()
        st = gdiplus.GdipCreateBitmapFromHICON(h_icon, ctypes.byref(p_bitmap))
        user32.DestroyIcon(h_icon)

        if st != 0 or not p_bitmap:
            with _cache_lock:
                _icon_cache[norm_key] = None
            return None

        data_url = _encode_bitmap_to_png_data_url(p_bitmap, target_size=target_size)
        gdiplus.GdipDisposeImage(p_bitmap)

        with _cache_lock:
            _icon_cache[norm_key] = data_url

        return data_url
    except Exception as e:
        logger.debug(f"Failed to extract native icon for {clean_path}: {e}")
        with _cache_lock:
            _icon_cache[norm_key] = None
        return None


def get_process_icon_data_url(pid: int, target_size: int = 64) -> Optional[str]:
    """Extract native application icon for a running process ID."""
    if sys.platform != "win32" or not pid:
        return None

    cache_key = f"pid_{pid}"
    with _cache_lock:
        if cache_key in _icon_cache:
            return _icon_cache[cache_key]

    try:
        import ctypes
        from ctypes import wintypes

        kernel32 = ctypes.windll.kernel32
        PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
        h_proc = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
        if not h_proc:
            return None

        buf = ctypes.create_unicode_buffer(1024)
        size = wintypes.DWORD(1024)
        res = kernel32.QueryFullProcessImageNameW(h_proc, 0, buf, ctypes.byref(size))
        kernel32.CloseHandle(h_proc)

        if not res:
            return None

        exe_path = buf.value
        data_url = get_app_icon_data_url(exe_path, target_size=target_size)

        with _cache_lock:
            _icon_cache[cache_key] = data_url

        return data_url
    except Exception as e:
        logger.debug(f"Failed to extract process icon for PID {pid}: {e}")
        return None


def warm_icons_background(paths: List[str]) -> None:
    """Warm up icon cache in a background worker thread."""

    def _worker():
        for p in paths:
            try:
                get_app_icon_data_url(p)
            except Exception:
                pass

    t = threading.Thread(target=_worker, daemon=True, name="SpotlightIconWarmer")
    t.start()
