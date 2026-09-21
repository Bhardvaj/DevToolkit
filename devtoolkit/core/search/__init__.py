"""DevToolkit Standalone High-Performance Search Engine.

Modeled after voidtools Everything algorithms:
- Sequential NTFS USN Journal streaming via Win32 DeviceIoControl when elevated
- Parallel multi-threaded pruned Win32 directory crawler when non-elevated
- In-memory compact search index with sub-millisecond query evaluation
"""

from devtoolkit.core.search.crawler import ParallelPrunedCrawler
from devtoolkit.core.search.engine import FastSearchEngine
from devtoolkit.core.search.index import SearchIndex
from devtoolkit.core.search.models import IndexStats, SearchQuery, SearchResult
from devtoolkit.core.search.usn import NTFSUSNReader

__all__ = [
    "FastSearchEngine",
    "SearchIndex",
    "SearchResult",
    "SearchQuery",
    "IndexStats",
    "ParallelPrunedCrawler",
    "NTFSUSNReader",
]
