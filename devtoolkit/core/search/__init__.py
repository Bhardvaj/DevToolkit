"""DevToolkit Standalone High-Performance Search Engine.

Modeled after voidtools Everything algorithms:
- Sequential NTFS USN Journal streaming via Win32 DeviceIoControl when elevated
- Parallel multi-threaded pruned Win32 directory crawler when non-elevated
- In-memory compact search index with sub-millisecond query evaluation
"""

from devtoolkit.core.search.crawler import ParallelPrunedCrawler
from devtoolkit.core.search.engine import FastSearchEngine, get_process_ram_bytes, get_search_engine
from devtoolkit.core.search.index import SearchIndex, format_bytes
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
    "format_bytes",
    "get_search_engine",
    "get_process_ram_bytes",
]
