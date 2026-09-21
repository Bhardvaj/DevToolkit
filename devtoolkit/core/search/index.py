"""In-memory compact search index for sub-millisecond querying."""

from fnmatch import fnmatchcase
import re
import threading
from typing import Dict, Iterable, List, Optional, Set

from devtoolkit.core.search.models import SearchQuery, SearchResult


class SearchIndex:
    """High-performance in-memory search index with O(1) hash maps and pattern matching."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._entries: List[SearchResult] = []
        self._name_map: Dict[str, List[int]] = {}
        self._total_files: int = 0
        self._total_dirs: int = 0

    @property
    def total_entries(self) -> int:
        with self._lock:
            return len(self._entries)

    @property
    def total_files(self) -> int:
        with self._lock:
            return self._total_files

    @property
    def total_dirs(self) -> int:
        with self._lock:
            return self._total_dirs

    def clear(self) -> None:
        """Reset the index."""
        with self._lock:
            self._entries.clear()
            self._name_map.clear()
            self._total_files = 0
            self._total_dirs = 0

    def add_entry(self, path: str, name: str, is_dir: bool, size: int = 0, mtime: float = 0.0) -> None:
        """Add a single entry to the index and update lookup tables."""
        with self._lock:
            idx = len(self._entries)
            res = SearchResult(path=path, name=name, is_dir=is_dir, size=size, mtime=mtime)
            self._entries.append(res)
            if is_dir:
                self._total_dirs += 1
            else:
                self._total_files += 1

            lower_name = name.lower()
            if lower_name not in self._name_map:
                self._name_map[lower_name] = [idx]
            else:
                self._name_map[lower_name].append(idx)

    def add_entries_batch(self, batch: List[SearchResult]) -> None:
        """Add a batch of SearchResult records efficiently."""
        with self._lock:
            start_idx = len(self._entries)
            self._entries.extend(batch)
            for i, item in enumerate(batch):
                idx = start_idx + i
                if item.is_dir:
                    self._total_dirs += 1
                else:
                    self._total_files += 1
                lower_name = item.name.lower()
                if lower_name not in self._name_map:
                    self._name_map[lower_name] = [idx]
                else:
                    self._name_map[lower_name].append(idx)

    def find_exact(self, name: str, case_sensitive: bool = False) -> List[SearchResult]:
        """Find entries matching the exact filename (O(1) lookup)."""
        with self._lock:
            lower = name.lower()
            indices = self._name_map.get(lower, [])
            if not indices:
                return []
            if not case_sensitive:
                return [self._entries[i] for i in indices]
            return [self._entries[i] for i in indices if self._entries[i].name == name]

    def find_exact_names(self, names: Iterable[str], case_sensitive: bool = False) -> Dict[str, List[SearchResult]]:
        """Batch lookup for multiple exact filenames in < 1ms."""
        results: Dict[str, List[SearchResult]] = {}
        with self._lock:
            for name in names:
                matches = self.find_exact(name, case_sensitive=case_sensitive)
                if matches:
                    results[name] = matches
        return results

    def find_pattern(
        self,
        glob_pattern: str,
        case_sensitive: bool = False,
        files_only: bool = False,
        directories_only: bool = False,
        max_results: Optional[int] = None,
    ) -> List[SearchResult]:
        """Find entries matching a wildcard pattern (e.g. '*.exe', 'flutter*')."""
        results: List[SearchResult] = []
        pattern = glob_pattern if case_sensitive else glob_pattern.lower()

        with self._lock:
            for entry in self._entries:
                if files_only and entry.is_dir:
                    continue
                if directories_only and not entry.is_dir:
                    continue

                check_name = entry.name if case_sensitive else entry.name.lower()
                if fnmatchcase(check_name, pattern):
                    results.append(entry)
                    if max_results and len(results) >= max_results:
                        break
        return results

    def find_regex(
        self,
        regex_pattern: str,
        case_sensitive: bool = False,
        files_only: bool = False,
        directories_only: bool = False,
        max_results: Optional[int] = None,
    ) -> List[SearchResult]:
        """Find entries matching a regular expression."""
        flags = 0 if case_sensitive else re.IGNORECASE
        compiled = re.compile(regex_pattern, flags)
        results: List[SearchResult] = []

        with self._lock:
            for entry in self._entries:
                if files_only and entry.is_dir:
                    continue
                if directories_only and not entry.is_dir:
                    continue

                if compiled.search(entry.name) or compiled.search(entry.path):
                    results.append(entry)
                    if max_results and len(results) >= max_results:
                        break
        return results

    def search(self, query: SearchQuery) -> List[SearchResult]:
        """Execute a structured SearchQuery against the in-memory index."""
        if query.is_regex:
            return self.find_regex(
                query.pattern,
                case_sensitive=query.case_sensitive,
                files_only=query.files_only,
                directories_only=query.directories_only,
                max_results=query.max_results,
            )
        if any(c in query.pattern for c in ("*", "?", "[", "]")):
            return self.find_pattern(
                query.pattern,
                case_sensitive=query.case_sensitive,
                files_only=query.files_only,
                directories_only=query.directories_only,
                max_results=query.max_results,
            )
        # Substring / exact match
        results: List[SearchResult] = []
        pat = query.pattern if query.case_sensitive else query.pattern.lower()
        with self._lock:
            for entry in self._entries:
                if query.files_only and entry.is_dir:
                    continue
                if query.directories_only and not entry.is_dir:
                    continue
                check_val = entry.name if query.case_sensitive else entry.name.lower()
                if pat in check_val:
                    results.append(entry)
                    if query.max_results and len(results) >= query.max_results:
                        break
        return results
