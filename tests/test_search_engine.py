"""Automated tests for DevToolkit Standalone FastSearchEngine and Layer 4 discovery."""

from pathlib import Path
import sys
import pytest

from devtoolkit.core.search.crawler import ParallelPrunedCrawler
from devtoolkit.core.search.engine import FastSearchEngine
from devtoolkit.core.search.index import SearchIndex
from devtoolkit.core.search.models import IndexStats, SearchQuery, SearchResult
from devtoolkit.core.search.usn import NTFSUSNReader
from devtoolkit.core.signatures import scan_roots_for_tools, SIGNATURE_CHECKERS


def test_search_index_exact_and_batch():
    idx = SearchIndex()
    idx.add_entry(path="/tools/bin/javac.exe", name="javac.exe", is_dir=False, size=1024)
    idx.add_entry(path="/tools/bin/JAVAC.EXE", name="JAVAC.EXE", is_dir=False, size=1024)
    idx.add_entry(path="/sdk/flutter/bin/flutter.bat", name="flutter.bat", is_dir=False)
    idx.add_entry(path="/sdk/flutter", name="flutter", is_dir=True)

    assert idx.total_entries == 4
    assert idx.total_files == 3
    assert idx.total_dirs == 1

    # Case-insensitive exact lookup
    res = idx.find_exact("javac.exe")
    assert len(res) == 2

    # Case-sensitive exact lookup
    res_cs = idx.find_exact("javac.exe", case_sensitive=True)
    assert len(res_cs) == 1
    assert res_cs[0].name == "javac.exe"

    # Batch lookup
    batch = idx.find_exact_names(["javac.exe", "flutter.bat", "non_existent.exe"])
    assert "javac.exe" in batch
    assert "flutter.bat" in batch
    assert "non_existent.exe" not in batch
    assert len(batch["flutter.bat"]) == 1


def test_search_index_pattern_and_regex():
    idx = SearchIndex()
    idx.add_entry(path="C:/Dev/tool_a.exe", name="tool_a.exe", is_dir=False)
    idx.add_entry(path="C:/Dev/tool_b.dll", name="tool_b.dll", is_dir=False)
    idx.add_entry(path="C:/Dev/tool_folder", name="tool_folder", is_dir=True)

    # Pattern match *.exe
    exe_matches = idx.find_pattern("*.exe")
    assert len(exe_matches) == 1
    assert exe_matches[0].name == "tool_a.exe"

    # Pattern match with directories_only
    dir_matches = idx.find_pattern("tool_*", directories_only=True)
    assert len(dir_matches) == 1
    assert dir_matches[0].name == "tool_folder"

    # Regex match
    reg_matches = idx.find_regex(r"tool_[ab]\.(exe|dll)")
    assert len(reg_matches) == 2


def test_search_index_query_interface():
    idx = SearchIndex()
    idx.add_entry(path="/app/lib/test.py", name="test.py", is_dir=False)
    idx.add_entry(path="/app/lib/other.py", name="other.py", is_dir=False)

    # Substring search
    q1 = SearchQuery(pattern="test", files_only=True)
    res1 = idx.search(q1)
    assert len(res1) == 1
    assert res1[0].name == "test.py"

    # Clear index
    idx.clear()
    assert idx.total_entries == 0


def test_parallel_crawler_pruning(tmp_path):
    # Setup simulated directory structure
    allowed_dir = tmp_path / "Tools" / "bin"
    allowed_dir.mkdir(parents=True)
    (allowed_dir / "javac.exe").write_text("dummy")

    # Pruned directories
    git_dir = tmp_path / "Project" / ".git"
    git_dir.mkdir(parents=True)
    (git_dir / "javac.exe").write_text("should_be_pruned")

    node_dir = tmp_path / "Project" / "node_modules"
    node_dir.mkdir(parents=True)
    (node_dir / "javac.exe").write_text("should_be_pruned")

    index = SearchIndex()
    crawler = ParallelPrunedCrawler(max_workers=2, max_depth=4)
    stats = crawler.crawl_roots([tmp_path], index)

    assert stats.total_files > 0
    matches = index.find_exact("javac.exe")

    # Only the allowed file should be indexed
    assert len(matches) == 1
    assert "node_modules" not in matches[0].path
    assert ".git" not in matches[0].path
    assert matches[0].path == str(allowed_dir / "javac.exe")


def test_ntfs_usn_reader_graceful_non_admin():
    reader = NTFSUSNReader()
    # On Windows or Linux, calling can_read_volume on an arbitrary path should return bool without crash
    can_read = reader.can_read_volume("Z:")
    assert isinstance(can_read, bool)
    assert reader.scan_volume("Z:", SearchIndex()) is None


def test_fast_search_engine_integration(tmp_path):
    # Create test hierarchy
    bin_dir = tmp_path / "MySDK" / "bin"
    bin_dir.mkdir(parents=True)
    (bin_dir / "cargo.exe").write_text("dummy")
    (bin_dir / "rustc.exe").write_text("dummy")

    engine = FastSearchEngine(max_workers=2, max_depth=4)
    stats = engine.index_roots([tmp_path])

    assert stats.total_files >= 2
    assert engine.total_files >= 2

    # Test find_files
    files = engine.find_files("*.exe")
    assert len(files) == 2
    assert any(f.name == "cargo.exe" for f in files)
    assert any(f.name == "rustc.exe" for f in files)

    # Test batch lookup
    exact = engine.find_exact_names(["cargo.exe", "rustc.exe", "missing.exe"])
    assert "cargo.exe" in exact
    assert "rustc.exe" in exact
    assert "missing.exe" not in exact

    # Test clear
    engine.clear()
    assert engine.total_entries == 0


def test_scan_roots_for_tools_mock(tmp_path):
    # Create a simulated JDK root
    jdk_root = tmp_path / "custom_jdk"
    jdk_bin = jdk_root / "bin"
    jdk_bin.mkdir(parents=True)
    exe_suffix = ".exe" if sys.platform == "win32" else ""
    (jdk_bin / f"javac{exe_suffix}").write_text("dummy")
    (jdk_bin / f"java{exe_suffix}").write_text("dummy")

    # Create a simulated Flutter SDK
    flutter_root = tmp_path / "custom_flutter"
    flutter_bin = flutter_root / "bin"
    flutter_bin.mkdir(parents=True)
    (flutter_root / "packages" / "flutter").mkdir(parents=True)
    bat_suffix = ".bat" if sys.platform == "win32" else ""
    (flutter_bin / f"flutter{bat_suffix}").write_text("dummy")

    # Run scan_roots_for_tools
    results = scan_roots_for_tools([tmp_path], max_depth=4)

    assert "java" in results
    assert "flutter" in results
    assert any(p == jdk_root.resolve() for p in results["java"])
    assert any(p == flutter_root.resolve() for p in results["flutter"])


def test_scan_roots_non_existent():
    results = scan_roots_for_tools([Path("Z:/NonExistentPath12345")])
    assert isinstance(results, dict)
    assert len(results) == len(SIGNATURE_CHECKERS)
    assert all(len(v) == 0 for v in results.values())
