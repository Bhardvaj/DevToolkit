"""High-performance standalone search engine coordinating USN and Parallel Crawler strategies."""

from datetime import datetime, timezone
from pathlib import Path
import sys
from typing import Any, Dict, Iterable, List, Optional, Set

from devtoolkit.core.config import load_config
from devtoolkit.core.search.crawler import ParallelPrunedCrawler
from devtoolkit.core.search.index import SearchIndex, format_bytes
from devtoolkit.core.search.models import IndexStats, SearchQuery, SearchResult
from devtoolkit.core.search.usn import NTFSUSNReader
from devtoolkit.core.search.watcher import LiveDirectoryWatcher, create_directory_watcher


def get_process_ram_bytes() -> int:
    """Get current process working set RAM in bytes without third-party dependencies."""
    if sys.platform == "win32":
        try:
            import ctypes
            from ctypes import wintypes

            class PROCESS_MEMORY_COUNTERS(ctypes.Structure):
                _fields_ = [
                    ("cb", wintypes.DWORD),
                    ("PageFaultCount", wintypes.DWORD),
                    ("PeakWorkingSetSize", ctypes.c_size_t),
                    ("WorkingSetSize", ctypes.c_size_t),
                    ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
                    ("QuotaPagedPoolUsage", ctypes.c_size_t),
                    ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
                    ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                    ("PagefileUsage", ctypes.c_size_t),
                    ("PeakPagefileUsage", ctypes.c_size_t),
                ]

            counters = PROCESS_MEMORY_COUNTERS()
            counters.cb = ctypes.sizeof(PROCESS_MEMORY_COUNTERS)
            kernel32 = ctypes.windll.kernel32
            kernel32.GetCurrentProcess.restype = wintypes.HANDLE
            handle = kernel32.GetCurrentProcess()

            func = getattr(kernel32, "K32GetProcessMemoryInfo", None)
            if not func:
                func = getattr(ctypes.windll.psapi, "GetProcessMemoryInfo", None)
            if func:
                func.argtypes = [wintypes.HANDLE, ctypes.POINTER(PROCESS_MEMORY_COUNTERS), wintypes.DWORD]
                func.restype = wintypes.BOOL
                if func(handle, ctypes.byref(counters), ctypes.sizeof(counters)):
                    return int(counters.WorkingSetSize)
        except Exception:
            pass
    else:
        try:
            import resource
            usage = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
            if sys.platform == "darwin":
                return usage
            return usage * 1024
        except Exception:
            pass
    return 0


class FastSearchEngine:
    """Zero-dependency, standalone file & folder search engine modeled after Everything algorithms.
    
    Provides sub-millisecond in-memory lookups across indexed roots using:
    - Direct NTFS USN Journal streaming via DeviceIoControl when elevated
    - Parallel multi-threaded pruned Win32 directory scanning when non-elevated
    """

    def __init__(self, max_workers: int = 16, max_depth: int = 6) -> None:
        self.index = SearchIndex()
        self.crawler = ParallelPrunedCrawler(max_workers=max_workers, max_depth=max_depth)
        self.usn_reader = NTFSUSNReader()
        self._last_stats: Optional[IndexStats] = None
        self._is_indexing: bool = False
        self._last_indexed_at: Optional[str] = None
        self._watchers: List[LiveDirectoryWatcher] = []
        self._indexed_roots: List[Path] = []
        try:
            cfg = load_config()
            self._realtime_enabled: bool = getattr(cfg, "realtime_search", True)
        except Exception:
            self._realtime_enabled = True

    @property
    def total_entries(self) -> int:
        return self.index.total_entries

    @property
    def total_files(self) -> int:
        return self.index.total_files

    @property
    def total_dirs(self) -> int:
        return self.index.total_dirs

    @property
    def last_stats(self) -> Optional[IndexStats]:
        return self._last_stats

    @property
    def is_indexing(self) -> bool:
        return self._is_indexing

    @property
    def last_indexed_at(self) -> Optional[str]:
        return self._last_indexed_at

    @property
    def realtime_enabled(self) -> bool:
        return self._realtime_enabled

    def clear(self) -> None:
        self._stop_watchers()
        self.index.clear()
        self._last_stats = None
        self._last_indexed_at = None
        self._indexed_roots = []

    def _start_watchers(self) -> None:
        self._stop_watchers()
        if not self._realtime_enabled:
            return
        for root in self._indexed_roots:
            if root.exists() and root.is_dir():
                watcher = create_directory_watcher(str(root), self.index)
                watcher.start()
                self._watchers.append(watcher)

    def _stop_watchers(self) -> None:
        for watcher in self._watchers:
            try:
                watcher.stop()
            except Exception:
                pass
        self._watchers.clear()

    def enable_realtime(self, enabled: bool) -> None:
        """Dynamically toggle live filesystem change watchers."""
        self._realtime_enabled = bool(enabled)
        if self._realtime_enabled:
            self._start_watchers()
        else:
            self._stop_watchers()

    def get_telemetry(self) -> Dict[str, Any]:
        """Return comprehensive engine telemetry, memory footprints, and indexing status."""
        search_mem = self.index.estimate_memory_bytes()
        proc_ram = get_process_ram_bytes()
        stats = self._last_stats
        status = "indexing" if self._is_indexing else ("ready" if stats and stats.total_files > 0 else "idle")
        active_watchers = len([w for w in self._watchers if getattr(w, "is_running", False)])
        is_live = bool(self._realtime_enabled and active_watchers > 0 and status == "ready")

        return {
            "status": status,
            "is_indexing": self._is_indexing,
            "engine_used": stats.engine_used if stats else "None",
            "total_files": self.total_files,
            "total_dirs": self.total_dirs,
            "total_entries": self.total_entries,
            "duration_ms": round(stats.duration_ms, 2) if stats else 0.0,
            "roots_scanned": stats.roots_scanned if stats else [],
            "search_memory_bytes": search_mem,
            "search_memory_formatted": format_bytes(search_mem),
            "process_ram_bytes": proc_ram,
            "process_ram_formatted": format_bytes(proc_ram),
            "last_indexed_at": self._last_indexed_at,
            "realtime_enabled": self._realtime_enabled,
            "is_live": is_live,
            "active_watchers": active_watchers,
        }

    def index_roots(self, roots: List[Path], force_crawler: bool = False) -> IndexStats:
        """Index one or more root directories using the fastest accessible strategy."""
        valid_roots = [r.resolve() for r in roots if r.exists() and r.is_dir()]
        self._indexed_roots = list(valid_roots)
        if not valid_roots:
            self._stop_watchers()
            stats = IndexStats(total_files=0, total_dirs=0, duration_ms=0.0, roots_scanned=[])
            self._last_stats = stats
            return stats

        self._is_indexing = True
        try:
            # Check if we can use NTFS USN Journal for whole drive roots
            can_usn = not force_crawler and sys.platform == "win32" and self.usn_reader.is_elevated()

            crawler_roots: List[Path] = []
            usn_stats: Optional[IndexStats] = None

            for root in valid_roots:
                # Check if root is a drive root like 'C:\' or 'D:\'
                is_drive_root = (
                    sys.platform == "win32"
                    and len(str(root).rstrip("\\/")) <= 3
                    and str(root)[1:2] == ":"
                )
                if can_usn and is_drive_root:
                    drive_letter = str(root)[:2]
                    usn_res = self.usn_reader.scan_volume(drive_letter, self.index)
                    if usn_res:
                        usn_stats = usn_res
                    else:
                        crawler_roots.append(root)
                else:
                    crawler_roots.append(root)

            if crawler_roots:
                crawler_stats = self.crawler.crawl_roots(crawler_roots, self.index)
                if usn_stats:
                    combined_duration = usn_stats.duration_ms + crawler_stats.duration_ms
                    all_scanned = usn_stats.roots_scanned + crawler_stats.roots_scanned
                    stats = IndexStats(
                        total_files=self.index.total_files,
                        total_dirs=self.index.total_dirs,
                        duration_ms=combined_duration,
                        roots_scanned=all_scanned,
                        engine_used="Hybrid_USN_and_Crawler",
                    )
                else:
                    stats = crawler_stats
            elif usn_stats:
                stats = usn_stats
            else:
                stats = IndexStats(total_files=0, total_dirs=0, duration_ms=0.0, roots_scanned=[])

            self._last_stats = stats
            self._last_indexed_at = datetime.now(timezone.utc).isoformat()

            # Start real-time watchers for active roots if enabled
            if self._realtime_enabled:
                self._start_watchers()

            return stats
        finally:
            self._is_indexing = False

    def find_exact(self, name: str, case_sensitive: bool = False) -> List[SearchResult]:
        """Find entries matching exact name in O(1) time (<0.1ms)."""
        return self.index.find_exact(name, case_sensitive=case_sensitive)

    def find_exact_names(self, names: Iterable[str], case_sensitive: bool = False) -> Dict[str, List[SearchResult]]:
        """Batch lookup for multiple exact filenames in <1ms."""
        return self.index.find_exact_names(names, case_sensitive=case_sensitive)

    def find_files(self, pattern: str, case_sensitive: bool = False, max_results: Optional[int] = None) -> List[Path]:
        """Convenience method returning Paths for matching files."""
        results = self.index.find_pattern(
            pattern,
            case_sensitive=case_sensitive,
            files_only=True,
            max_results=max_results,
        )
        return [r.path_obj for r in results]

    def find_directories(self, pattern: str, case_sensitive: bool = False, max_results: Optional[int] = None) -> List[Path]:
        """Convenience method returning Paths for matching directories."""
        results = self.index.find_pattern(
            pattern,
            case_sensitive=case_sensitive,
            directories_only=True,
            max_results=max_results,
        )
        return [r.path_obj for r in results]

    def search(self, query: SearchQuery) -> List[SearchResult]:
        """Execute a structured SearchQuery against the in-memory index."""
        return self.index.search(query)

    def search_text(
        self,
        pattern: str,
        is_regex: bool = False,
        case_sensitive: bool = False,
        files_only: bool = False,
        directories_only: bool = False,
        max_results: Optional[int] = None,
    ) -> List[SearchResult]:
        """Quick search method for text or wildcard pattern."""
        query = SearchQuery(
            pattern=pattern,
            is_regex=is_regex,
            case_sensitive=case_sensitive,
            files_only=files_only,
            directories_only=directories_only,
            max_results=max_results,
        )
        return self.index.search(query)


_global_search_engine: Optional[FastSearchEngine] = None


def get_search_engine() -> FastSearchEngine:
    """Get or create the global shared FastSearchEngine instance."""
    global _global_search_engine
    if _global_search_engine is None:
        _global_search_engine = FastSearchEngine()
    return _global_search_engine

