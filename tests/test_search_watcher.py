"""Automated tests for Real-Time Live Updating, Directory Watcher, and Index Mutations."""

from pathlib import Path
import sys
import time
import pytest

from devtoolkit.core.config import load_config, set_realtime_search
from devtoolkit.core.search.engine import FastSearchEngine
from devtoolkit.core.search.index import SearchIndex
from devtoolkit.core.search.watcher import Win32DirectoryWatcher, create_directory_watcher
from devtoolkit.server.app import app
from devtoolkit.server.routes.search import RealtimeToggleRequest, toggle_realtime


def test_search_index_mutation_operations():
    """Verify O(1) mutations: add, update, rename, remove, and tree removal."""
    idx = SearchIndex()
    p1 = "C:/Projects/app/main.py"
    p2 = "C:/Projects/app/utils.py"
    p3 = "C:/Projects/app/docs/readme.md"

    idx.add_entry(p1, "main.py", False, 100, 1000.0)
    idx.add_entry(p2, "utils.py", False, 200, 1000.0)
    idx.add_entry(p3, "readme.md", False, 50, 1000.0)

    assert idx.total_entries == 3
    assert idx.total_files == 3

    # Update
    updated = idx.update_entry(p1, 150, 2000.0)
    assert updated is True
    res1 = idx.find_exact("main.py")
    assert len(res1) == 1
    assert res1[0].size == 150
    assert res1[0].mtime == 2000.0

    # Rename
    p1_renamed = "C:/Projects/app/index.py"
    renamed = idx.rename_entry(p1, p1_renamed)
    assert renamed is True
    assert len(idx.find_exact("main.py")) == 0
    res_renamed = idx.find_exact("index.py")
    assert len(res_renamed) == 1
    assert res_renamed[0].path == p1_renamed

    # Single Entry Removal
    removed = idx.remove_entry(p2)
    assert removed is True
    assert idx.total_files == 2
    assert len(idx.find_exact("utils.py")) == 0

    # Directory Tree Removal
    docs_dir = "C:/Projects/app/docs"
    tree_removed = idx.remove_directory_tree(docs_dir)
    assert tree_removed == 1
    assert idx.total_files == 1
    assert len(idx.find_exact("readme.md")) == 0
    assert len(idx.find_exact("index.py")) == 1


@pytest.mark.skipif(sys.platform != "win32", reason="Win32 ReadDirectoryChangesW requires Windows")
def test_win32_watcher_live_filesystem(tmp_path: Path):
    """Verify live filesystem events synchronize automatically into in-memory SearchIndex."""
    idx = SearchIndex()
    # Initial scan of tmp_path
    initial_file = tmp_path / "hello.txt"
    initial_file.write_text("hello world", encoding="utf-8")
    idx.add_entry(str(initial_file), initial_file.name, False, initial_file.stat().st_size, initial_file.stat().st_mtime)

    assert idx.total_files == 1

    events_fired = []

    def on_change():
        events_fired.append(time.time())

    watcher = create_directory_watcher(str(tmp_path), idx, on_change=on_change)
    watcher.start()
    try:
        assert getattr(watcher, "is_running", False) is True

        # 1. Test live file creation
        created_file = tmp_path / "live_created.py"
        created_file.write_text("print('live')", encoding="utf-8")

        # Wait up to 2 seconds for kernel notification dispatch
        deadline = time.time() + 2.0
        found = False
        while time.time() < deadline:
            matches = idx.find_exact("live_created.py")
            if matches:
                found = True
                break
            time.sleep(0.05)

        assert found is True, "live_created.py should have been automatically added to index"

        # 2. Test live file modification
        created_file.write_text("print('live modified with longer content')", encoding="utf-8")
        deadline = time.time() + 2.0
        updated = False
        while time.time() < deadline:
            matches = idx.find_exact("live_created.py")
            if matches and matches[0].size > 15:
                updated = True
                break
            time.sleep(0.05)

        assert updated is True, "live_created.py size should have updated dynamically in index"

        # 3. Test live file deletion
        created_file.unlink()
        deadline = time.time() + 2.0
        deleted = False
        while time.time() < deadline:
            matches = idx.find_exact("live_created.py")
            if not matches:
                deleted = True
                break
            time.sleep(0.05)

        assert deleted is True, "live_created.py should have been removed from index"

    finally:
        watcher.stop()
        assert getattr(watcher, "is_running", False) is False


def test_fast_search_engine_realtime_lifecycle(tmp_path: Path):
    """Verify FastSearchEngine manages watcher lifecycle, enable_realtime, and telemetry."""
    f1 = tmp_path / "sample.py"
    f1.write_text("content", encoding="utf-8")

    engine = FastSearchEngine()
    engine.clear()
    assert engine.total_entries == 0

    # Index roots
    stats = engine.index_roots([tmp_path])
    assert stats.total_files >= 1
    assert engine.total_files >= 1

    telemetry = engine.get_telemetry()
    assert "realtime_enabled" in telemetry
    assert "is_live" in telemetry
    assert telemetry["status"] == "ready"
    if sys.platform == "win32":
        assert telemetry["realtime_enabled"] is True
        assert telemetry["is_live"] is True
        assert telemetry["active_watchers"] >= 1

    # Disable real-time
    engine.enable_realtime(False)
    tel_disabled = engine.get_telemetry()
    assert tel_disabled["realtime_enabled"] is False
    assert tel_disabled["is_live"] is False
    assert tel_disabled["active_watchers"] == 0

    # Re-enable real-time
    engine.enable_realtime(True)
    tel_enabled = engine.get_telemetry()
    assert tel_enabled["realtime_enabled"] is True
    if sys.platform == "win32":
        assert tel_enabled["is_live"] is True

    engine.clear()
    assert engine.total_entries == 0


def test_api_realtime_toggle_endpoint():
    """Verify toggle_realtime endpoint updates engine and persistent configuration."""
    route_paths = [r.path for r in app.routes]
    assert "/api/search/realtime" in route_paths

    # Disable real-time
    res1 = toggle_realtime(RealtimeToggleRequest(enabled=False))
    assert res1["realtime_enabled"] is False
    assert res1["is_live"] is False
    cfg1 = load_config()
    assert cfg1.realtime_search is False

    # Enable real-time
    res2 = toggle_realtime(RealtimeToggleRequest(enabled=True))
    assert res2["realtime_enabled"] is True
    cfg2 = load_config()
    assert cfg2.realtime_search is True
