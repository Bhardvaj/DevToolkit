"""Unit tests for Windows desktop application discovery and indexing."""

from pathlib import Path
from devtoolkit.core.search.apps import _clean_app_name, _should_ignore_app, discover_shortcut_applications
from devtoolkit.core.search.index import SearchIndex
from devtoolkit.core.search.models import SearchQueryParams, SearchResult
from devtoolkit.core.search.query import execute_search


def test_clean_app_name():
    assert _clean_app_name("Visual Studio Code.lnk") == "Visual Studio Code"
    assert _clean_app_name("chrome.exe") == "chrome"
    assert _clean_app_name("GitHub Desktop.url") == "GitHub Desktop"


def test_should_ignore_app():
    assert _should_ignore_app("Uninstall Python 3.12") is True
    assert _should_ignore_app("Python 3.12 Readme") is True
    assert _should_ignore_app("Python 3.12") is False
    assert _should_ignore_app("Visual Studio Code") is False


def test_search_app_scope_and_ranking():
    idx = SearchIndex()
    # Add files and apps
    idx.add_entry("C:/Apps/Code.exe", "Visual Studio Code", is_dir=False, entry_type="app", acronym="vsc")
    idx.add_entry("D:/docs/vsc_notes.txt", "vsc_notes.txt", is_dir=False, entry_type="file")
    idx.add_entry("D:/Projects", "Projects", is_dir=True)

    # Search with scope='apps'
    res_apps = execute_search(idx, SearchQueryParams(query="", scope="apps"))
    assert len(res_apps.results) == 1
    assert res_apps.results[0].name == "Visual Studio Code"
    assert res_apps.results[0].entry_type == "app"
    assert res_apps.results[0].ext == "APP"

    # Search acronym 'vsc': app should be ranked top
    res_vsc = execute_search(idx, SearchQueryParams(query="vsc"))
    assert len(res_vsc.results) >= 1
    assert res_vsc.results[0].entry_type == "app"
    assert res_vsc.results[0].name == "Visual Studio Code"

    # Search scope='files' should exclude apps and dirs
    res_files = execute_search(idx, SearchQueryParams(query="", scope="files"))
    assert len(res_files.results) == 1
    assert res_files.results[0].name == "vsc_notes.txt"

