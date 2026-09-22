"""Everything-class search query parser and high-performance in-memory executor."""

from datetime import datetime, timedelta
from fnmatch import fnmatchcase
from pathlib import Path
import re
import sys
import time
from typing import Callable, Dict, List, Optional, Set, Tuple

from devtoolkit.core.search.index import SearchIndex, format_bytes
from devtoolkit.core.search.models import SearchItemDTO, SearchQueryParams, SearchQueryResult, SearchResult

# Popular workstation category extensions
CATEGORY_EXTENSIONS: Dict[str, Set[str]] = {
    "code": {
        "py", "pyw", "js", "mjs", "cjs", "ts", "tsx", "jsx", "java", "c", "cpp", "cc", "cxx",
        "h", "hpp", "hxx", "rs", "go", "cs", "fs", "json", "yaml", "yml", "toml", "xml",
        "html", "htm", "css", "scss", "sass", "less", "sql", "sh", "bash", "zsh", "ps1",
        "psm1", "bat", "cmd", "dart", "php", "rb", "swift", "kt", "kts", "gradle", "lua",
        "r", "pl", "asm", "zig", "nim", "v", "cmake", "make", "dockerfile", "vue", "svelte"
    },
    "exe": {
        "exe", "msi", "dll", "bat", "cmd", "ps1", "vbs", "sh", "bin", "com", "scr", "sys"
    },
    "doc": {
        "md", "txt", "pdf", "doc", "docx", "xls", "xlsx", "ppt", "pptx", "csv", "tsv",
        "log", "rtf", "rst", "org", "tex", "epub", "ini", "cfg", "conf", "env"
    },
    "archive": {
        "zip", "rar", "7z", "tar", "gz", "tgz", "bz2", "tbz2", "xz", "txz", "iso", "cab",
        "dmg", "jar", "war", "ear", "whl"
    },
    "media": {
        "png", "jpg", "jpeg", "gif", "bmp", "svg", "webp", "ico", "tif", "tiff", "mp4",
        "mkv", "avi", "mov", "wmv", "flv", "webm", "mp3", "wav", "flac", "aac", "ogg", "m4a"
    },
}

SIZE_PRESETS: Dict[str, Tuple[int, int]] = {
    "empty": (0, 0),
    "tiny": (0, 10 * 1024),                    # 0 - 10 KB
    "small": (10 * 1024, 100 * 1024),          # 10 - 100 KB
    "medium": (100 * 1024, 1024 * 1024),       # 100 KB - 1 MB
    "large": (1024 * 1024, 16 * 1024 * 1024),  # 1 - 16 MB
    "huge": (16 * 1024 * 1024, 128 * 1024 * 1024),  # 16 - 128 MB
    "gigantic": (128 * 1024 * 1024, sys.maxsize),    # > 128 MB
}


def format_mtime(timestamp: float) -> str:
    """Format Unix timestamp into readable local date/time."""
    if timestamp <= 0:
        return "—"
    try:
        dt = datetime.fromtimestamp(timestamp)
        return dt.strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        return "—"


def parse_size_bytes(value_str: str) -> Optional[int]:
    """Parse size string with units like '100mb', '10kb', '500b' into bytes."""
    v = value_str.strip().lower()
    m = re.match(r"^([0-9]+(?:\.[0-9]+)?)\s*([a-z]*)$", v)
    if not m:
        return None
    num = float(m.group(1))
    unit = m.group(2)
    if unit in ("g", "gb", "gbyte", "gbytes"):
        return int(num * 1024 * 1024 * 1024)
    elif unit in ("m", "mb", "mbyte", "mbytes"):
        return int(num * 1024 * 1024)
    elif unit in ("k", "kb", "kbyte", "kbytes"):
        return int(num * 1024)
    else:
        return int(num)


def parse_date_filter_range(filter_name: str) -> Tuple[float, float]:
    """Calculate (min_mtime, max_mtime) for preset date filters."""
    now = datetime.now()
    today_start = datetime(now.year, now.month, now.day)

    fn = filter_name.lower().strip()
    if fn == "today":
        return today_start.timestamp(), float("inf")
    elif fn == "yesterday":
        y_start = today_start - timedelta(days=1)
        return y_start.timestamp(), today_start.timestamp()
    elif fn in ("past7", "pastweek"):
        start = now - timedelta(days=7)
        return start.timestamp(), float("inf")
    elif fn in ("past30", "pastmonth"):
        start = now - timedelta(days=30)
        return start.timestamp(), float("inf")
    elif fn in ("thisweek",):
        start = today_start - timedelta(days=today_start.weekday())
        return start.timestamp(), float("inf")
    elif fn in ("thismonth",):
        start = datetime(now.year, now.month, 1)
        return start.timestamp(), float("inf")
    elif fn in ("thisyear",):
        start = datetime(now.year, 1, 1)
        return start.timestamp(), float("inf")
    elif fn in ("pastyear",):
        start = now - timedelta(days=365)
        return start.timestamp(), float("inf")
    return 0.0, float("inf")


class QueryToken:
    """Represents a parsed query clause with polarity and matching semantics."""

    def __init__(
        self,
        raw: str,
        is_not: bool = False,
        is_regex: bool = False,
        case_sensitive: bool = False,
        match_path: bool = False,
        whole_word: bool = False,
        path_only: Optional[str] = None,
        exts: Optional[Set[str]] = None,
        min_size: Optional[int] = None,
        max_size: Optional[int] = None,
        min_mtime: Optional[float] = None,
        max_mtime: Optional[float] = None,
        is_dir: Optional[bool] = None,
        or_alternatives: Optional[List["QueryToken"]] = None,
    ) -> None:
        self.raw = raw
        self.is_not = is_not
        self.is_regex = is_regex
        self.case_sensitive = case_sensitive
        self.match_path = match_path
        self.whole_word = whole_word
        self.path_only = path_only
        self.exts = exts
        self.min_size = min_size
        self.max_size = max_size
        self.min_mtime = min_mtime
        self.max_mtime = max_mtime
        self.is_dir = is_dir
        self.or_alternatives = or_alternatives

        self._compiled_regex: Optional[re.Pattern] = None
        if is_regex and raw:
            flags = 0 if case_sensitive else re.IGNORECASE
            try:
                self._compiled_regex = re.compile(raw, flags)
            except re.error:
                self._compiled_regex = re.compile(re.escape(raw), flags)
        elif whole_word and raw:
            flags = 0 if case_sensitive else re.IGNORECASE
            escaped = re.escape(raw)
            self._compiled_regex = re.compile(rf"\b{escaped}\b", flags)

    def matches(self, entry: SearchResult) -> bool:
        """Evaluate whether a SearchResult entry matches this token clause."""
        res = self._eval_positive(entry)
        return (not res) if self.is_not else res

    def _eval_positive(self, entry: SearchResult) -> bool:
        # Check OR alternatives
        if self.or_alternatives:
            for alt in self.or_alternatives:
                if alt.matches(entry):
                    return True
            return False

        # Directory / file scope
        if self.is_dir is not None:
            if entry.is_dir != self.is_dir:
                return False

        # Extension filter
        if self.exts is not None:
            if entry.is_dir:
                return False
            name_parts = entry.name.rsplit(".", 1)
            entry_ext = name_parts[1].lower() if len(name_parts) > 1 else ""
            if entry_ext not in self.exts:
                return False

        # Size filter
        if self.min_size is not None and entry.size < self.min_size:
            return False
        if self.max_size is not None and entry.size > self.max_size:
            return False

        # Date modified filter
        if self.min_mtime is not None and entry.mtime < self.min_mtime:
            return False
        if self.max_mtime is not None and entry.mtime > self.max_mtime:
            return False

        # Path-only check
        if self.path_only is not None:
            check_p = entry.path if self.case_sensitive else entry.path.lower()
            target_p = self.path_only if self.case_sensitive else self.path_only.lower()
            if target_p not in check_p:
                return False

        # If no text pattern, passing metadata criteria is sufficient
        if not self.raw:
            return True

        # Target string: full path or name
        target_str = entry.path if self.match_path else entry.name

        # Regex / whole word matching
        if self._compiled_regex is not None:
            return bool(self._compiled_regex.search(target_str))

        # Wildcard matching
        if any(c in self.raw for c in ("*", "?", "[", "]")):
            pattern = self.raw if self.case_sensitive else self.raw.lower()
            subject = target_str if self.case_sensitive else target_str.lower()
            return fnmatchcase(subject, pattern)

        # Standard substring matching
        sub = self.raw if self.case_sensitive else self.raw.lower()
        sub_target = target_str if self.case_sensitive else target_str.lower()
        return sub in sub_target


class EverythingQueryParser:
    """Parses Everything-style search query strings into structured QueryTokens."""

    @staticmethod
    def parse(query_str: str, default_case: bool = False, default_path: bool = False, default_regex: bool = False, default_word: bool = False) -> List[QueryToken]:
        if not query_str.strip():
            return []

        # Tokenize handling quotes: foo "bar baz" ext:py
        token_strings: List[str] = []
        raw_tokens = re.findall(r'(?:[^\s"]|"(?:\\.|[^"])*")+', query_str)
        for t in raw_tokens:
            cleaned = t.strip()
            if cleaned.startswith('"') and cleaned.endswith('"') and len(cleaned) >= 2:
                cleaned = cleaned[1:-1]
            if cleaned:
                token_strings.append(cleaned)

        parsed_tokens: List[QueryToken] = []
        for raw in token_strings:
            is_not = False
            token_body = raw
            if token_body.startswith("!") and len(token_body) > 1:
                is_not = True
                token_body = token_body[1:]

            # Check OR branch (|)
            if "|" in token_body and not token_body.startswith(("regex:", "path:", "ext:")):
                parts = [p.strip() for p in token_body.split("|") if p.strip()]
                if len(parts) > 1:
                    alts = [
                        EverythingQueryParser._parse_single(p, default_case, default_path, default_regex, default_word)
                        for p in parts
                    ]
                    parsed_tokens.append(QueryToken(raw=token_body, is_not=is_not, or_alternatives=alts))
                    continue

            single = EverythingQueryParser._parse_single(token_body, default_case, default_path, default_regex, default_word)
            single.is_not = is_not
            parsed_tokens.append(single)

        return parsed_tokens

    @staticmethod
    def _parse_single(token: str, default_case: bool, default_path: bool, default_regex: bool, default_word: bool) -> QueryToken:
        low = token.lower()

        # folder: / dir:
        if low in ("folder:", "dir:", "is:folder", "is:dir"):
            return QueryToken(raw="", is_dir=True)
        # file:
        if low in ("file:", "is:file"):
            return QueryToken(raw="", is_dir=False)

        # ext:<ext1;ext2>
        if low.startswith("ext:"):
            ext_part = token[4:].lower().strip()
            exts = {e.strip().lstrip(".") for e in re.split(r"[;,]", ext_part) if e.strip()}
            return QueryToken(raw="", exts=exts)

        # size:<expr>
        if low.startswith("size:"):
            expr = token[5:].strip().lower()
            if expr in SIZE_PRESETS:
                mn, mx = SIZE_PRESETS[expr]
                return QueryToken(raw="", min_size=mn, max_size=mx)
            # Check range min..max
            if ".." in expr:
                p1, p2 = expr.split("..", 1)
                mn = parse_size_bytes(p1)
                mx = parse_size_bytes(p2)
                return QueryToken(raw="", min_size=mn, max_size=mx)
            # Check operators >, >=, <, <=, =
            m_op = re.match(r"^([><=]+)\s*(.+)$", expr)
            if m_op:
                op, val_str = m_op.group(1), m_op.group(2)
                val = parse_size_bytes(val_str)
                if val is not None:
                    if op in (">", ">="):
                        return QueryToken(raw="", min_size=val)
                    elif op in ("<", "<="):
                        return QueryToken(raw="", max_size=val)
                    elif op == "=":
                        return QueryToken(raw="", min_size=val, max_size=val)
            val = parse_size_bytes(expr)
            if val is not None:
                return QueryToken(raw="", min_size=val)

        # dm:<expr> (date modified)
        if low.startswith("dm:") or low.startswith("date:"):
            prefix_len = 3 if low.startswith("dm:") else 5
            expr = token[prefix_len:].strip().lower()
            if expr in ("today", "yesterday", "past7", "pastweek", "past30", "pastmonth", "thisweek", "thismonth", "thisyear", "pastyear"):
                mn, mx = parse_date_filter_range(expr)
                return QueryToken(raw="", min_mtime=mn, max_mtime=mx)
            # Specific year e.g. 2026
            m_year = re.match(r"^(\d{4})$", expr)
            if m_year:
                y = int(m_year.group(1))
                t_start = datetime(y, 1, 1).timestamp()
                t_end = datetime(y + 1, 1, 1).timestamp()
                return QueryToken(raw="", min_mtime=t_start, max_mtime=t_end)
            # Specific year-month e.g. 2026-09
            m_ym = re.match(r"^(\d{4})-(\d{1,2})$", expr)
            if m_ym:
                y, m = int(m_ym.group(1)), int(m_ym.group(2))
                t_start = datetime(y, m, 1).timestamp()
                next_y, next_m = (y + 1, 1) if m == 12 else (y, m + 1)
                t_end = datetime(next_y, next_m, 1).timestamp()
                return QueryToken(raw="", min_mtime=t_start, max_mtime=t_end)

        # path:<text>
        if low.startswith("path:"):
            return QueryToken(raw="", path_only=token[5:], case_sensitive=default_case)

        # regex:<pattern>
        if low.startswith("regex:"):
            return QueryToken(raw=token[6:], is_regex=True, case_sensitive=default_case, match_path=default_path)

        # case:<pattern>
        if low.startswith("case:"):
            return QueryToken(raw=token[5:], case_sensitive=True, match_path=default_path, whole_word=default_word)

        # Standard text pattern
        return QueryToken(
            raw=token,
            is_regex=default_regex,
            case_sensitive=default_case,
            match_path=default_path,
            whole_word=default_word,
        )


def execute_search(index: SearchIndex, params: SearchQueryParams) -> SearchQueryResult:
    """Execute Everything-class query with visual filters, sorting, and pagination."""
    start_time = time.perf_counter()

    # 1. Parse typed query string into tokens
    tokens = EverythingQueryParser.parse(
        params.query,
        default_case=params.case_sensitive,
        default_path=params.match_path,
        default_regex=params.is_regex,
        default_word=params.whole_word,
    )

    # 2. Prepare visual filters
    category_exts: Optional[Set[str]] = None
    category_folder_only = False
    if params.category and params.category.lower() != "all":
        cat = params.category.lower()
        if cat == "folder" or cat == "folders":
            category_folder_only = True
        elif cat in CATEGORY_EXTENSIONS:
            category_exts = CATEGORY_EXTENSIONS[cat]

    custom_exts: Optional[Set[str]] = None
    if params.ext_filter and params.ext_filter.strip():
        custom_exts = {e.strip().lower().lstrip(".") for e in re.split(r"[;,]", params.ext_filter) if e.strip()}

    # Visual scope
    scope_files_only = params.scope == "files"
    scope_folders_only = params.scope == "folders" or category_folder_only

    # Visual size filter
    vis_min_size: Optional[int] = None
    vis_max_size: Optional[int] = None
    if params.size_filter and params.size_filter.lower() in SIZE_PRESETS:
        vis_min_size, vis_max_size = SIZE_PRESETS[params.size_filter.lower()]

    # Visual date filter
    vis_min_mtime: Optional[float] = None
    vis_max_mtime: Optional[float] = None
    if params.date_filter and params.date_filter.lower() != "any":
        vis_min_mtime, vis_max_mtime = parse_date_filter_range(params.date_filter)

    # 3. Filter through index entries (thread-safe snapshot of references)
    with index._lock:
        all_entries = list(index._entries)

    matched: List[SearchResult] = []

    for entry in all_entries:
        # Visual Scope Check
        if scope_files_only and entry.is_dir:
            continue
        if scope_folders_only and not entry.is_dir:
            continue

        # Visual Category Check
        if category_exts is not None:
            if entry.is_dir:
                continue
            name_parts = entry.name.rsplit(".", 1)
            ext = name_parts[1].lower() if len(name_parts) > 1 else ""
            if ext not in category_exts:
                continue

        # Custom extension filter check
        if custom_exts is not None:
            if entry.is_dir:
                continue
            name_parts = entry.name.rsplit(".", 1)
            ext = name_parts[1].lower() if len(name_parts) > 1 else ""
            if ext not in custom_exts:
                continue

        # Visual Size Check
        if vis_min_size is not None and entry.size < vis_min_size:
            continue
        if vis_max_size is not None and entry.size > vis_max_size:
            continue

        # Visual Date Modified Check
        if vis_min_mtime is not None and entry.mtime < vis_min_mtime:
            continue
        if vis_max_mtime is not None and entry.mtime > vis_max_mtime:
            continue

        # Evaluate query tokens (Boolean AND)
        passed_tokens = True
        for tok in tokens:
            if not tok.matches(entry):
                passed_tokens = False
                break

        if passed_tokens:
            matched.append(entry)

    total_matches = len(matched)

    # 4. Multi-column Sorting
    sort_by = (params.sort_by or "name").lower()
    sort_desc = params.sort_desc

    if sort_by == "size":
        matched.sort(key=lambda e: e.size, reverse=sort_desc)
    elif sort_by == "mtime" or sort_by == "date":
        matched.sort(key=lambda e: e.mtime, reverse=sort_desc)
    elif sort_by == "path" or sort_by == "folder":
        matched.sort(key=lambda e: e.path.lower(), reverse=sort_desc)
    elif sort_by == "ext" or sort_by == "type":
        def _ext_key(e: SearchResult):
            if e.is_dir:
                return ""
            parts = e.name.rsplit(".", 1)
            return parts[1].lower() if len(parts) > 1 else ""
        matched.sort(key=_ext_key, reverse=sort_desc)
    else:  # default: name
        matched.sort(key=lambda e: e.name.lower(), reverse=sort_desc)

    # 5. Pagination / Slice
    offset = max(0, params.offset)
    limit = max(1, min(params.limit, 2000))
    paged_entries = matched[offset : offset + limit]

    # 6. Convert to SearchItemDTO
    results: List[SearchItemDTO] = []
    for e in paged_entries:
        parts = e.name.rsplit(".", 1)
        ext = ("DIR" if e.is_dir else ("." + parts[1].lower() if len(parts) > 1 else ""))
        parent_folder = str(Path(e.path).parent) if not e.is_dir else str(Path(e.path))
        results.append(
            SearchItemDTO(
                name=e.name,
                path=e.path,
                folder=parent_folder,
                is_dir=e.is_dir,
                size=e.size,
                size_formatted="—" if e.is_dir else format_bytes(e.size),
                mtime=e.mtime,
                mtime_formatted=format_mtime(e.mtime),
                ext=ext,
            )
        )

    duration_ms = (time.perf_counter() - start_time) * 1000.0

    return SearchQueryResult(
        results=results,
        total_matches=total_matches,
        duration_ms=round(duration_ms, 2),
        query=params.query,
        offset=offset,
        limit=limit,
    )
