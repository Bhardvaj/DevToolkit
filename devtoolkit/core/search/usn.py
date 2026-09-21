"""NTFS USN Change Journal volume reader via Win32 DeviceIoControl."""

import ctypes
from ctypes import wintypes
import os
from pathlib import Path
import sys
import time
from typing import Dict, List, Optional, Tuple

from devtoolkit.core.search.index import SearchIndex
from devtoolkit.core.search.models import IndexStats, SearchResult

FSCTL_ENUM_USN_DATA = 0x000900B3
GENERIC_READ = 0x80000000
FILE_SHARE_READ = 0x00000001
FILE_SHARE_WRITE = 0x00000002
OPEN_EXISTING = 3
FILE_ATTRIBUTE_NORMAL = 0x80
INVALID_HANDLE_VALUE = wintypes.HANDLE(-1).value

if sys.platform == "win32":
    class MFT_ENUM_DATA_V0(ctypes.Structure):
        _fields_ = [
            ("StartFileReferenceNumber", ctypes.c_uint64),
            ("LowUsn", ctypes.c_longlong),
            ("HighUsn", ctypes.c_longlong),
        ]

    class USN_RECORD_V2_HEADER(ctypes.Structure):
        _fields_ = [
            ("RecordLength", wintypes.DWORD),
            ("MajorVersion", wintypes.WORD),
            ("MinorVersion", wintypes.WORD),
            ("FileReferenceNumber", ctypes.c_uint64),
            ("ParentFileReferenceNumber", ctypes.c_uint64),
            ("Usn", ctypes.c_longlong),
            ("TimeStamp", wintypes.LARGE_INTEGER),
            ("Reason", wintypes.DWORD),
            ("SourceInfo", wintypes.DWORD),
            ("SecurityId", wintypes.DWORD),
            ("FileAttributes", wintypes.DWORD),
            ("FileNameLength", wintypes.WORD),
            ("FileNameOffset", wintypes.WORD),
        ]


class NTFSUSNReader:
    """Direct NTFS USN Change Journal volume scanner (active when elevated as Administrator)."""

    @staticmethod
    def is_elevated() -> bool:
        """Check if current process has Administrator privileges on Windows."""
        if sys.platform != "win32":
            return False
        try:
            return bool(ctypes.windll.shell32.IsUserAnAdmin())
        except Exception:
            return False

    def can_read_volume(self, drive_letter: str) -> bool:
        """Check if the volume handle for drive_letter can be opened with read permissions."""
        if not self.is_elevated():
            return False
        clean_drive = drive_letter.strip().rstrip("\\/")
        if len(clean_drive) == 1:
            clean_drive += ":"
        vol_path = f"\\\\.\\{clean_drive}"
        kernel32 = ctypes.windll.kernel32
        h = kernel32.CreateFileW(
            vol_path,
            GENERIC_READ,
            FILE_SHARE_READ | FILE_SHARE_WRITE,
            None,
            OPEN_EXISTING,
            FILE_ATTRIBUTE_NORMAL,
            None,
        )
        if h == INVALID_HANDLE_VALUE or h == -1:
            return False
        kernel32.CloseHandle(h)
        return True

    def scan_volume(self, drive_letter: str, index: SearchIndex) -> Optional[IndexStats]:
        """Stream USN records directly from the volume if elevated."""
        if not self.can_read_volume(drive_letter):
            return None

        clean_drive = drive_letter.strip().rstrip("\\/")
        if len(clean_drive) == 1:
            clean_drive += ":"
        vol_path = f"\\\\.\\{clean_drive}"
        kernel32 = ctypes.windll.kernel32

        h = kernel32.CreateFileW(
            vol_path,
            GENERIC_READ,
            FILE_SHARE_READ | FILE_SHARE_WRITE,
            None,
            OPEN_EXISTING,
            FILE_ATTRIBUTE_NORMAL,
            None,
        )
        if h == INVALID_HANDLE_VALUE or h == -1:
            return None

        t0 = time.perf_counter()
        try:
            # Map: FileReferenceNumber -> (name, ParentFileReferenceNumber, is_dir)
            nodes: Dict[int, Tuple[str, int, bool]] = {}
            buffer_size = 64 * 1024  # 64 KB buffer
            out_buf = (ctypes.c_char * buffer_size)()
            bytes_returned = wintypes.DWORD()

            enum_data = MFT_ENUM_DATA_V0(0, 0, 0x7FFFFFFFFFFFFFFF)

            while True:
                success = kernel32.DeviceIoControl(
                    h,
                    FSCTL_ENUM_USN_DATA,
                    ctypes.byref(enum_data),
                    ctypes.sizeof(enum_data),
                    out_buf,
                    buffer_size,
                    ctypes.byref(bytes_returned),
                    None,
                )
                if not success or bytes_returned.value <= 8:
                    break

                # First 8 bytes is the next StartFileReferenceNumber
                next_frn = ctypes.c_uint64.from_buffer_copy(out_buf[:8]).value
                enum_data.StartFileReferenceNumber = next_frn

                offset = 8
                while offset < bytes_returned.value:
                    rec_header = USN_RECORD_V2_HEADER.from_buffer_copy(out_buf[offset : offset + ctypes.sizeof(USN_RECORD_V2_HEADER)])
                    if rec_header.RecordLength == 0:
                        break

                    name_offset = offset + rec_header.FileNameOffset
                    name_len = rec_header.FileNameLength
                    name_bytes = out_buf[name_offset : name_offset + name_len]
                    try:
                        file_name = name_bytes.decode("utf-16le")
                    except Exception:
                        file_name = ""

                    is_dir = bool(rec_header.FileAttributes & 0x10)  # FILE_ATTRIBUTE_DIRECTORY
                    nodes[rec_header.FileReferenceNumber] = (file_name, rec_header.ParentFileReferenceNumber, is_dir)
                    offset += rec_header.RecordLength

            # Reconstruct full paths for all nodes
            path_cache: Dict[int, str] = {}
            drive_prefix = clean_drive.upper() + "\\"

            def resolve_path(frn: int) -> str:
                if frn in path_cache:
                    return path_cache[frn]
                if frn not in nodes:
                    return drive_prefix
                name, parent_frn, _ = nodes[frn]
                if not name or parent_frn == frn:
                    path_cache[frn] = drive_prefix
                    return drive_prefix
                parent_path = resolve_path(parent_frn)
                full = os.path.join(parent_path, name)
                path_cache[frn] = full
                return full

            batch: List[SearchResult] = []
            for frn, (name, parent_frn, is_dir) in nodes.items():
                if name:
                    full_p = resolve_path(frn)
                    batch.append(SearchResult(path=full_p, name=name, is_dir=is_dir))

            index.add_entries_batch(batch)
            t1 = time.perf_counter()

            return IndexStats(
                total_files=index.total_files,
                total_dirs=index.total_dirs,
                duration_ms=(t1 - t0) * 1000.0,
                roots_scanned=[drive_prefix],
                engine_used="NTFS_USN_Journal",
            )
        finally:
            kernel32.CloseHandle(h)
