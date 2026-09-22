"""Data models for DevToolkit standalone high-performance search engine."""

from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional


@dataclass(slots=True)
class SearchResult:
    """Represents an indexed or discovered filesystem entry."""

    path: str
    name: str
    is_dir: bool = False
    size: int = 0
    mtime: float = 0.0

    @property
    def path_obj(self) -> Path:
        return Path(self.path)


@dataclass
class SearchQuery:
    """Configures parameters for an index or filesystem search."""

    pattern: str
    is_regex: bool = False
    case_sensitive: bool = False
    files_only: bool = False
    directories_only: bool = False
    max_results: Optional[int] = None


@dataclass
class IndexStats:
    """Performance telemetry and statistics for an index operation."""

    total_files: int = 0
    total_dirs: int = 0
    duration_ms: float = 0.0
    roots_scanned: List[str] = field(default_factory=list)
    engine_used: str = "ParallelCrawler"


@dataclass(slots=True)
class SearchItemDTO:
    """Serialized representation of a matched search item."""

    name: str
    path: str
    folder: str
    is_dir: bool
    size: int
    size_formatted: str
    mtime: float
    mtime_formatted: str
    ext: str


@dataclass
class SearchQueryParams:
    """Comprehensive parameters for Everything-class query execution."""

    query: str = ""
    case_sensitive: bool = False
    whole_word: bool = False
    match_path: bool = False
    is_regex: bool = False
    category: str = "all"  # all, code, exe, doc, archive, media, folder
    scope: str = "all"      # all, files, folders
    size_filter: str = "any"  # any, empty, tiny, small, medium, large, huge, gigantic
    date_filter: str = "any"  # any, today, yesterday, past7, past30, thisyear, pastyear
    ext_filter: str = ""    # e.g. "py", "exe;dll"
    sort_by: str = "relevance"   # relevance, name, path, size, mtime, ext
    sort_desc: bool = False
    limit: int = 500
    offset: int = 0


@dataclass
class SearchQueryResult:
    """Structured response payload returned by the search engine."""

    results: List[SearchItemDTO] = field(default_factory=list)
    total_matches: int = 0
    total_indexed: int = 0
    duration_ms: float = 0.0
    query: str = ""
    offset: int = 0
    limit: int = 500

