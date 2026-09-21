"""Parallel Win32 pruned directory crawler for ultra-fast user-mode indexing."""

from concurrent.futures import ThreadPoolExecutor, as_completed
import os
from pathlib import Path
import time
from typing import List, Optional, Set

from devtoolkit.core.search.index import SearchIndex
from devtoolkit.core.search.models import IndexStats, SearchResult

DEFAULT_PRUNE_NAMES: Set[str] = {
    "$recycle.bin",
    "system volume information",
    "winsxs",
    "driverstore",
    "node_modules",
    "bower_components",
    ".git",
    ".svn",
    ".hg",
    "__pycache__",
    ".venv",
    "venv",
    "env",
    "site-packages",
    "temp",
    "tmp",
    ".cache",
    "package-cache",
    "cached_packages",
    "obj",
    "bin/obj",
    ".gradle",
    ".cargo/registry",
    "crashdumps",
}


class ParallelPrunedCrawler:
    """Multi-threaded filesystem crawler with aggressive non-developer subtree pruning."""

    def __init__(
        self,
        max_workers: int = 16,
        max_depth: int = 6,
        prune_names: Optional[Set[str]] = None,
    ) -> None:
        self.max_workers = max_workers
        self.max_depth = max_depth
        self.prune_names = prune_names or DEFAULT_PRUNE_NAMES

    def crawl_roots(self, roots: List[Path], index: SearchIndex) -> IndexStats:
        """Crawl one or more root directories and populate the search index."""
        t0 = time.perf_counter()
        valid_roots = [r.resolve() for r in roots if r.exists() and r.is_dir()]
        if not valid_roots:
            return IndexStats(total_files=0, total_dirs=0, duration_ms=0.0, roots_scanned=[])

        # Discover top-level tasks to distribute across thread pool
        top_tasks: List[str] = []
        for root in valid_roots:
            top_tasks.append(str(root))
            try:
                with os.scandir(str(root)) as it:
                    for entry in it:
                        try:
                            if entry.is_dir():
                                dname = entry.name.lower()
                                if dname not in self.prune_names and not dname.startswith("."):
                                    top_tasks.append(entry.path)
                            elif entry.is_file():
                                index.add_entry(
                                    path=entry.path,
                                    name=entry.name,
                                    is_dir=False,
                                    size=0,
                                    mtime=0.0,
                                )
                        except (PermissionError, OSError):
                            continue
            except (PermissionError, OSError):
                continue

        # Crawl directories in parallel
        # We start sub-crawls from depth 1 for the expanded top tasks
        sub_targets = [p for p in top_tasks if p not in [str(r) for r in valid_roots]]
        if not sub_targets:
            sub_targets = [str(r) for r in valid_roots]

        all_batch_results: List[SearchResult] = []
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            futures = [
                executor.submit(self._crawl_directory, target, current_depth=1)
                for target in sub_targets
            ]
            for fut in as_completed(futures):
                try:
                    entries = fut.result()
                    if entries:
                        all_batch_results.extend(entries)
                except Exception:
                    pass

        if all_batch_results:
            index.add_entries_batch(all_batch_results)

        t1 = time.perf_counter()
        duration_ms = (t1 - t0) * 1000.0

        return IndexStats(
            total_files=index.total_files,
            total_dirs=index.total_dirs,
            duration_ms=duration_ms,
            roots_scanned=[str(r) for r in valid_roots],
            engine_used="ParallelPrunedCrawler",
        )

    def _crawl_directory(self, dir_path: str, current_depth: int) -> List[SearchResult]:
        results: List[SearchResult] = []
        if current_depth > self.max_depth:
            return results

        try:
            with os.scandir(dir_path) as it:
                subdirs = []
                for entry in it:
                    try:
                        if entry.is_dir():
                            dname = entry.name.lower()
                            if dname not in self.prune_names and not dname.startswith("."):
                                results.append(
                                    SearchResult(
                                        path=entry.path,
                                        name=entry.name,
                                        is_dir=True,
                                    )
                                )
                                subdirs.append(entry.path)
                        elif entry.is_file():
                            results.append(
                                SearchResult(
                                    path=entry.path,
                                    name=entry.name,
                                    is_dir=False,
                                )
                            )
                    except (PermissionError, OSError):
                        continue

            for sub in subdirs:
                results.extend(self._crawl_directory(sub, current_depth + 1))
        except (PermissionError, OSError):
            pass

        return results
