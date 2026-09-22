"""Automated tests for Everything-class query parser and execution engine."""

from datetime import datetime, timedelta
import time
import pytest

from devtoolkit.core.search.index import SearchIndex
from devtoolkit.core.search.models import SearchQueryParams, SearchResult
from devtoolkit.core.search.query import (
    EverythingQueryParser,
    execute_search,
    parse_size_bytes,
    parse_date_filter_range,
)


def test_parse_size_bytes():
    assert parse_size_bytes("500b") == 500
    assert parse_size_bytes("10kb") == 10 * 1024
    assert parse_size_bytes("2.5mb") == int(2.5 * 1024 * 1024)
    assert parse_size_bytes("1gb") == 1024 * 1024 * 1024
    assert parse_size_bytes("invalid") is None


def test_everything_query_parser_tokens():
    # Basic tokens
    tokens = EverythingQueryParser.parse("python exe")
    assert len(tokens) == 2
    assert tokens[0].raw == "python"
    assert tokens[1].raw == "exe"

    # Quotes
    tokens_q = EverythingQueryParser.parse('"Visual Studio Code" ext:exe')
    assert len(tokens_q) == 2
    assert tokens_q[0].raw == "Visual Studio Code"
    assert tokens_q[1].exts == {"exe"}

    # Negation
    tokens_not = EverythingQueryParser.parse("test !venv !node_modules")
    assert len(tokens_not) == 3
    assert not tokens_not[0].is_not
    assert tokens_not[1].is_not
    assert tokens_not[1].raw == "venv"
    assert tokens_not[2].is_not
    assert tokens_not[2].raw == "node_modules"

    # OR branch
    tokens_or = EverythingQueryParser.parse("main.py|index.ts")
    assert len(tokens_or) == 1
    assert tokens_or[0].or_alternatives is not None
    assert len(tokens_or[0].or_alternatives) == 2

    # Functions: size and dm
    tokens_func = EverythingQueryParser.parse("size:>10mb dm:today folder:")
    assert len(tokens_func) == 3
    assert tokens_func[0].min_size == 10 * 1024 * 1024
    assert tokens_func[1].min_mtime is not None
    assert tokens_func[2].is_dir is True


def test_execute_search_filters_and_syntax():
    index = SearchIndex()
    now = time.time()

    # Populate dummy files
    index.add_entry(path="D:/Dev/app/main.py", name="main.py", is_dir=False, size=1500, mtime=now)
    index.add_entry(path="D:/Dev/app/utils.py", name="utils.py", is_dir=False, size=3500, mtime=now - 86400 * 2)
    index.add_entry(path="D:/Dev/app/runner.exe", name="runner.exe", is_dir=False, size=5 * 1024 * 1024, mtime=now)
    index.add_entry(path="D:/Dev/app/README.md", name="README.md", is_dir=False, size=800, mtime=now)
    index.add_entry(path="D:/Dev/app/build.zip", name="build.zip", is_dir=False, size=20 * 1024 * 1024, mtime=now)
    index.add_entry(path="D:/Dev/app/src", name="src", is_dir=True, size=0, mtime=now)
    index.add_entry(path="D:/Dev/app/tests", name="tests", is_dir=True, size=0, mtime=now)

    # 1. Simple search
    res1 = execute_search(index, SearchQueryParams(query="main.py"))
    assert res1.total_matches == 1
    assert res1.results[0].name == "main.py"

    # 2. Extension filter in query
    res_ext = execute_search(index, SearchQueryParams(query="ext:py"))
    assert res_ext.total_matches == 2
    names = {r.name for r in res_ext.results}
    assert names == {"main.py", "utils.py"}

    # 3. Negation
    res_neg = execute_search(index, SearchQueryParams(query="ext:py !main"))
    assert res_neg.total_matches == 1
    assert res_neg.results[0].name == "utils.py"

    # 4. OR branch
    res_or = execute_search(index, SearchQueryParams(query="main.py|runner.exe"))
    assert res_or.total_matches == 2
    or_names = {r.name for r in res_or.results}
    assert or_names == {"main.py", "runner.exe"}

    # 5. Visual Category: Code
    res_code = execute_search(index, SearchQueryParams(category="code"))
    assert res_code.total_matches == 2  # main.py and utils.py

    # 6. Visual Category: Executables
    res_exe = execute_search(index, SearchQueryParams(category="exe"))
    assert res_exe.total_matches == 1
    assert res_exe.results[0].name == "runner.exe"

    # 7. Visual Category: Archives
    res_arc = execute_search(index, SearchQueryParams(category="archive"))
    assert res_arc.total_matches == 1
    assert res_arc.results[0].name == "build.zip"

    # 8. Visual Category: Folders
    res_folders = execute_search(index, SearchQueryParams(category="folder"))
    assert res_folders.total_matches == 2
    folder_names = {r.name for r in res_folders.results}
    assert folder_names == {"src", "tests"}

    # 9. Visual Size Filter: Large (1MB - 16MB)
    res_large = execute_search(index, SearchQueryParams(size_filter="large"))
    assert res_large.total_matches == 1
    assert res_large.results[0].name == "runner.exe"

    # 10. Sorting by size descending
    res_sort = execute_search(index, SearchQueryParams(sort_by="size", sort_desc=True))
    assert res_sort.results[0].name == "build.zip"  # 20MB
    assert res_sort.results[1].name == "runner.exe" # 5MB

    # 11. Pagination
    res_page = execute_search(index, SearchQueryParams(limit=2, offset=0))
    assert len(res_page.results) == 2
    assert res_page.total_matches == 7
    assert res_page.limit == 2
    assert res_page.offset == 0
