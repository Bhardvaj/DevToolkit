"""In-memory compact search index for sub-millisecond querying."""

from fnmatch import fnmatchcase
from pathlib import Path
import re
import sys
import threading
from typing import Dict, Iterable, List, Optional, Set

from devtoolkit.core.search.models import SearchQuery, SearchResult


def format_bytes(bytes_count: int) -> str:
    """Format bytes count into human-readable string (e.g. 11.4 MB)."""
    if bytes_count < 1024:
        return f"{bytes_count} B"
    elif bytes_count < 1024 * 1024:
        return f"{bytes_count / 1024:.1f} KB"
    elif bytes_count < 1024 * 1024 * 1024:
        return f"{bytes_count / (1024 * 1024):.1f} MB"
    else:
        return f"{bytes_count / (1024 * 1024 * 1024):.2f} GB"


class SearchIndex:
    """High-performance in-memory search index with O(1) hash maps and pattern matching."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._entries: List[SearchResult] = []
        self._name_map: Dict[str, List[int]] = {}
        self._path_map: Dict[str, int] = {}
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

    def estimate_memory_bytes(self) -> int:
        """Estimate total in-memory footprint of the index in bytes."""
        with self._lock:
            base_mem = sys.getsizeof(self._entries) + sys.getsizeof(self._name_map) + sys.getsizeof(self._path_map)
            count = len(self._entries)
            if count == 0:
                return base_mem

            # Sample first N items for sub-millisecond calculation speed
            sample_size = min(count, 200)
            sample_bytes = 0
            for i in range(sample_size):
                e = self._entries[i]
                sample_bytes += sys.getsizeof(e) + sys.getsizeof(e.path) + sys.getsizeof(e.name)

            avg_entry_bytes = sample_bytes / sample_size
            total_entries_mem = int(avg_entry_bytes * count)

            # Map overhead: sample keys and index lists
            map_sample_size = min(len(self._name_map), 200)
            map_sample_bytes = 0
            for k, (key, val) in enumerate(self._name_map.items()):
                if k >= map_sample_size:
                    break
                map_sample_bytes += sys.getsizeof(key) + sys.getsizeof(val) + (len(val) * 8)

            avg_map_entry = (map_sample_bytes / map_sample_size) if map_sample_size > 0 else 0
            total_map_mem = int(avg_map_entry * len(self._name_map))

            # Path map overhead
            path_sample_size = min(len(self._path_map), 200)
            path_sample_bytes = 0
            for k, (key, val) in enumerate(self._path_map.items()):
                if k >= path_sample_size:
                    break
                path_sample_bytes += sys.getsizeof(key) + sys.getsizeof(val)
            avg_path_entry = (path_sample_bytes / path_sample_size) if path_sample_size > 0 else 0
            total_path_mem = int(avg_path_entry * len(self._path_map))

            return base_mem + total_entries_mem + total_map_mem + total_path_mem

    def clear(self) -> None:
        """Reset the index."""
        with self._lock:
            self._entries.clear()
            self._name_map.clear()
            self._path_map.clear()
            self._total_files = 0
            self._total_dirs = 0

    def add_entry(self, path: str, name: str, is_dir: bool, size: int = 0, mtime: float = 0.0) -> None:
        """Add a single entry to the index and update lookup tables."""
        with self._lock:
            norm_p = Path(path).as_posix()
            existing_idx = self._path_map.get(norm_p)
            if existing_idx is not None:
                old_res = self._entries[existing_idx]
                if old_res.is_dir != is_dir:
                    if is_dir:
                        self._total_dirs += 1
                        self._total_files = max(0, self._total_files - 1)
                    else:
                        self._total_files += 1
                        self._total_dirs = max(0, self._total_dirs - 1)
                self._entries[existing_idx] = SearchResult(path=path, name=name, is_dir=is_dir, size=size, mtime=mtime)
                if old_res.name.lower() != name.lower():
                    old_indices = self._name_map.get(old_res.name.lower(), [])
                    if existing_idx in old_indices:
                        old_indices.remove(existing_idx)
                    lower_name = name.lower()
                    if lower_name not in self._name_map:
                        self._name_map[lower_name] = [existing_idx]
                    else:
                        self._name_map[lower_name].append(existing_idx)
                return

            idx = len(self._entries)
            res = SearchResult(path=path, name=name, is_dir=is_dir, size=size, mtime=mtime)
            self._entries.append(res)
            self._path_map[norm_p] = idx
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
                norm_p = Path(item.path).as_posix()
                self._path_map[norm_p] = idx
                if item.is_dir:
                    self._total_dirs += 1
                else:
                    self._total_files += 1
                lower_name = item.name.lower()
                if lower_name not in self._name_map:
                    self._name_map[lower_name] = [idx]
                else:
                    self._name_map[lower_name].append(idx)

    def remove_entry(self, path: str) -> bool:
        """Remove a single file or directory from the index in O(1) time."""
        with self._lock:
            norm_p = Path(path).as_posix()
            idx = self._path_map.get(norm_p)
            if idx is None:
                # Case-insensitive fallback for Windows paths
                norm_lower = norm_p.lower()
                for k, v in self._path_map.items():
                    if k.lower() == norm_lower:
                        idx = v
                        norm_p = k
                        break
            if idx is None:
                return False

            last_idx = len(self._entries) - 1
            removed = self._entries[idx]

            if removed.is_dir:
                self._total_dirs = max(0, self._total_dirs - 1)
            else:
                self._total_files = max(0, self._total_files - 1)

            if idx != last_idx:
                last_item = self._entries[last_idx]
                self._entries[idx] = last_item
                last_norm_p = Path(last_item.path).as_posix()
                self._path_map[last_norm_p] = idx

                last_name_indices = self._name_map.get(last_item.name.lower(), [])
                for j in range(len(last_name_indices)):
                    if last_name_indices[j] == last_idx:
                        last_name_indices[j] = idx
                        break

            self._entries.pop()
            del self._path_map[norm_p]

            rem_indices = self._name_map.get(removed.name.lower(), [])
            if idx in rem_indices:
                rem_indices.remove(idx)
            if not rem_indices and removed.name.lower() in self._name_map:
                del self._name_map[removed.name.lower()]

            return True

    def rename_entry(self, old_path: str, new_path: str) -> bool:
        """Update an entry when renamed or moved on disk."""
        with self._lock:
            norm_old = Path(old_path).as_posix()
            idx = self._path_map.get(norm_old)
            if idx is None:
                norm_lower = norm_old.lower()
                for k, v in self._path_map.items():
                    if k.lower() == norm_lower:
                        idx = v
                        norm_old = k
                        break

            new_name = Path(new_path).name
            if idx is not None:
                old_item = self._entries[idx]
                new_res = SearchResult(
                    path=new_path,
                    name=new_name,
                    is_dir=old_item.is_dir,
                    size=old_item.size,
                    mtime=old_item.mtime,
                )
                self._entries[idx] = new_res
                del self._path_map[norm_old]
                self._path_map[Path(new_path).as_posix()] = idx

                if old_item.name.lower() != new_name.lower():
                    old_indices = self._name_map.get(old_item.name.lower(), [])
                    if idx in old_indices:
                        old_indices.remove(idx)
                    lower_new = new_name.lower()
                    if lower_new not in self._name_map:
                        self._name_map[lower_new] = [idx]
                    else:
                        self._name_map[lower_new].append(idx)
                return True
            else:
                is_dir = Path(new_path).is_dir() if Path(new_path).exists() else False
                try:
                    st = Path(new_path).stat() if Path(new_path).exists() else None
                    sz = st.st_size if st and not is_dir else 0
                    mt = st.st_mtime if st else 0.0
                except Exception:
                    sz, mt = 0, 0.0
                self.add_entry(new_path, new_name, is_dir, sz, mt)
                return True

    def update_entry(self, path: str, size: Optional[int] = None, mtime: Optional[float] = None) -> bool:
        """Update metadata of a modified file."""
        with self._lock:
            norm_p = Path(path).as_posix()
            idx = self._path_map.get(norm_p)
            if idx is None:
                norm_lower = norm_p.lower()
                for k, v in self._path_map.items():
                    if k.lower() == norm_lower:
                        idx = v
                        norm_p = k
                        break

            if idx is not None:
                e = self._entries[idx]
                new_sz = size if size is not None else e.size
                new_mt = mtime if mtime is not None else e.mtime
                self._entries[idx] = SearchResult(
                    path=e.path,
                    name=e.name,
                    is_dir=e.is_dir,
                    size=new_sz,
                    mtime=new_mt,
                )
                return True
            else:
                p = Path(path)
                if p.exists():
                    try:
                        st = p.stat()
                        is_dir = p.is_dir()
                        self.add_entry(path, p.name, is_dir, st.st_size if not is_dir else 0, st.st_mtime)
                        return True
                    except Exception:
                        pass
                return False

    def remove_directory_tree(self, dir_path: str) -> int:
        """Recursively remove a directory and all contained sub-items from index."""
        with self._lock:
            norm_dir = Path(dir_path).as_posix().rstrip("/")
            norm_dir_lower = norm_dir.lower()
            prefix_lower = norm_dir_lower + "/"
            matching_paths = [
                p for p in list(self._path_map.keys())
                if p.lower() == norm_dir_lower or p.lower().startswith(prefix_lower)
            ]
            for p in matching_paths:
                self.remove_entry(p)
            return len(matching_paths)

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
