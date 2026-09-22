"""Native Win32 ReadDirectoryChangesW live filesystem change monitor."""

from pathlib import Path
import struct
import sys
import threading
import time
from typing import Callable, Optional, Set

from devtoolkit.core.search.index import SearchIndex

IGNORED_DIR_NAMES: Set[str] = {
    ".git",
    ".svn",
    ".hg",
    "node_modules",
    "__pycache__",
    ".pytest_cache",
    ".venv",
    "venv",
    "build",
    "dist",
    "target",
    ".idea",
    ".vscode",
}

# Win32 Constants
FILE_LIST_DIRECTORY = 0x0001
FILE_SHARE_READ = 0x0001
FILE_SHARE_WRITE = 0x0002
FILE_SHARE_DELETE = 0x0004
OPEN_EXISTING = 3
FILE_FLAG_BACKUP_SEMANTICS = 0x02000000

FILE_NOTIFY_CHANGE_FILE_NAME = 0x00000001
FILE_NOTIFY_CHANGE_DIR_NAME = 0x00000002
FILE_NOTIFY_CHANGE_ATTRIBUTES = 0x00000004
FILE_NOTIFY_CHANGE_SIZE = 0x00000008
FILE_NOTIFY_CHANGE_LAST_WRITE = 0x00000010
FILE_NOTIFY_CHANGE_CREATION = 0x00000040

FILE_NOTIFY_FLAGS = (
    FILE_NOTIFY_CHANGE_FILE_NAME
    | FILE_NOTIFY_CHANGE_DIR_NAME
    | FILE_NOTIFY_CHANGE_SIZE
    | FILE_NOTIFY_CHANGE_LAST_WRITE
    | FILE_NOTIFY_CHANGE_CREATION
)

FILE_ACTION_ADDED = 1
FILE_ACTION_REMOVED = 2
FILE_ACTION_MODIFIED = 3
FILE_ACTION_RENAMED_OLD_NAME = 4
FILE_ACTION_RENAMED_NEW_NAME = 5


class LiveDirectoryWatcher:
    """Base interface for directory watchers."""

    def __init__(self, root_path: str, index: SearchIndex, on_change: Optional[Callable[[], None]] = None) -> None:
        self.root_path = root_path
        self.index = index
        self.on_change = on_change
        self.is_running = False

    def start(self) -> None:
        pass

    def stop(self) -> None:
        pass


class Win32DirectoryWatcher(LiveDirectoryWatcher):
    """High-performance Windows directory change monitor using kernel32.ReadDirectoryChangesW.
    
    Operates without third-party dependencies (like watchdog or pywin32), listening
    directly to kernel filesystem events with sub-millisecond in-memory index dispatch.
    """

    def __init__(self, root_path: str, index: SearchIndex, on_change: Optional[Callable[[], None]] = None) -> None:
        super().__init__(root_path, index, on_change)
        self._thread: Optional[threading.Thread] = None
        self._handle = None
        self._stop_event = threading.Event()
        self._last_renamed_old: Optional[str] = None

    def start(self) -> None:
        if self.is_running or sys.platform != "win32":
            return
        root = Path(self.root_path)
        if not root.exists() or not root.is_dir():
            return

        import ctypes
        from ctypes import wintypes

        kernel32 = ctypes.windll.kernel32
        handle = kernel32.CreateFileW(
            str(root),
            FILE_LIST_DIRECTORY,
            FILE_SHARE_READ | FILE_SHARE_WRITE | FILE_SHARE_DELETE,
            None,
            OPEN_EXISTING,
            FILE_FLAG_BACKUP_SEMANTICS,
            None,
        )

        if handle == -1 or handle == 0xFFFFFFFF or handle is None:
            return

        self._handle = handle
        self._stop_event.clear()
        self.is_running = True
        self._thread = threading.Thread(target=self._watch_loop, name=f"Win32Watcher-{root.name}", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        if not self.is_running:
            return
        self.is_running = False
        self._stop_event.set()

        if sys.platform == "win32" and self._handle:
            try:
                import ctypes
                kernel32 = ctypes.windll.kernel32
                # Cancel pending I/O on the handle
                cancel_io = getattr(kernel32, "CancelIoEx", None)
                if cancel_io:
                    cancel_io(self._handle, None)
                kernel32.CloseHandle(self._handle)
            except Exception:
                pass
            finally:
                self._handle = None

        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=1.0)
            self._thread = None

    def _watch_loop(self) -> None:
        import ctypes
        from ctypes import wintypes

        kernel32 = ctypes.windll.kernel32
        buffer_size = 65536
        buffer = ctypes.create_string_buffer(buffer_size)
        bytes_returned = wintypes.DWORD(0)

        root = Path(self.root_path).resolve()

        while self.is_running and not self._stop_event.is_set():
            success = kernel32.ReadDirectoryChangesW(
                self._handle,
                buffer,
                buffer_size,
                True,  # bWatchSubtree: watch full directory tree
                FILE_NOTIFY_FLAGS,
                ctypes.byref(bytes_returned),
                None,
                None,
            )

            if not success or bytes_returned.value == 0:
                if not self.is_running:
                    break
                time.sleep(0.05)
                continue

            # Process FILE_NOTIFY_INFORMATION structures in the buffer
            offset = 0
            raw_bytes = buffer.raw[: bytes_returned.value]

            while offset < len(raw_bytes):
                if offset + 12 > len(raw_bytes):
                    break

                next_offset, action, filename_len = struct.unpack_from("<III", raw_bytes, offset)
                filename_start = offset + 12
                filename_end = filename_start + filename_len

                if filename_end > len(raw_bytes):
                    break

                filename_bytes = raw_bytes[filename_start:filename_end]
                try:
                    rel_path_str = filename_bytes.decode("utf-16-le")
                except Exception:
                    rel_path_str = ""

                if rel_path_str:
                    self._dispatch_action(root, rel_path_str, action)

                if next_offset == 0:
                    break
                offset += next_offset

            if self.on_change:
                try:
                    self.on_change()
                except Exception:
                    pass

    def _dispatch_action(self, root: Path, rel_path_str: str, action: int) -> None:
        rel_path = Path(rel_path_str)
        # Prune ignored directory trees
        for part in rel_path.parts:
            if part.lower() in IGNORED_DIR_NAMES:
                return

        full_path_obj = root / rel_path
        full_path = str(full_path_obj)
        name = full_path_obj.name

        try:
            if action == FILE_ACTION_ADDED:
                is_dir = full_path_obj.is_dir() if full_path_obj.exists() else False
                st = full_path_obj.stat() if full_path_obj.exists() else None
                sz = st.st_size if st and not is_dir else 0
                mt = st.st_mtime if st else time.time()
                self.index.add_entry(full_path, name, is_dir, sz, mt)

            elif action == FILE_ACTION_REMOVED:
                # Remove entry or directory tree
                removed = self.index.remove_entry(full_path)
                if not removed:
                    self.index.remove_directory_tree(full_path)

            elif action == FILE_ACTION_MODIFIED:
                if full_path_obj.exists():
                    st = full_path_obj.stat()
                    is_dir = full_path_obj.is_dir()
                    sz = st.st_size if not is_dir else 0
                    self.index.update_entry(full_path, sz, st.st_mtime)

            elif action == FILE_ACTION_RENAMED_OLD_NAME:
                self._last_renamed_old = full_path

            elif action == FILE_ACTION_RENAMED_NEW_NAME:
                if self._last_renamed_old:
                    self.index.rename_entry(self._last_renamed_old, full_path)
                    self._last_renamed_old = None
                else:
                    is_dir = full_path_obj.is_dir() if full_path_obj.exists() else False
                    st = full_path_obj.stat() if full_path_obj.exists() else None
                    sz = st.st_size if st and not is_dir else 0
                    mt = st.st_mtime if st else time.time()
                    self.index.add_entry(full_path, name, is_dir, sz, mt)

        except Exception:
            pass


def create_directory_watcher(
    root_path: str,
    index: SearchIndex,
    on_change: Optional[Callable[[], None]] = None,
) -> LiveDirectoryWatcher:
    """Factory creating platform-optimized live directory watcher."""
    if sys.platform == "win32":
        return Win32DirectoryWatcher(root_path, index, on_change)
    return LiveDirectoryWatcher(root_path, index, on_change)
