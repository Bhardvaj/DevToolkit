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
