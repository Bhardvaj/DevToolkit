"""Tests for DiscoveryPipeline."""

from pathlib import Path
from devtoolkit.core.discovery import DiscoveryPipeline
from devtoolkit.core.runner import SafeRunner
from devtoolkit.core.signatures import SIGNATURE_CHECKERS


def test_discovery_pipeline_methods():
    runner = SafeRunner()
    pipeline = DiscoveryPipeline(runner)

    # Calling discover methods returns Path or None without crashing
    android_sdk = pipeline.discover_android_sdk()
    assert android_sdk is None or android_sdk.exists()

    studio = pipeline.discover_android_studio()
    assert studio is None or studio.exists()

    java_home = pipeline.discover_java_home()
    assert java_home is None or java_home.exists()

    flutter = pipeline.discover_flutter_sdk()
    assert flutter is None or flutter.exists()


def test_universal_discovery_all_22_tools():
    runner = SafeRunner()
    pipeline = DiscoveryPipeline(runner)

    for tool_id in SIGNATURE_CHECKERS:
        found = pipeline.discover_tool(tool_id)
        assert found is None or found.exists(), f"Discovered path for {tool_id} does not exist: {found}"

        instances = pipeline.discover_all_tool_instances(tool_id)
        assert isinstance(instances, list)
        for inst in instances:
            assert inst.exists(), f"Discovered instance for {tool_id} does not exist: {inst}"


def test_zero_path_search_engine_discovery(tmp_path, monkeypatch):
    """Verify that a tool absent from PATH is discovered via Layer 4 FastSearchEngine."""
    custom_tools = tmp_path / "custom_tools"
    custom_tools.mkdir()

    # Create portable MinGW installation in custom directory
    portable_mingw = custom_tools / "portable_mingw"
    portable_mingw.mkdir()
    (portable_mingw / "bin").mkdir()
    (portable_mingw / "bin" / "gcc.exe").write_text("dummy", encoding="utf-8")
    (portable_mingw / "include").mkdir()

    runner = SafeRunner()
    monkeypatch.setattr(runner, "resolve_binary", lambda *args, **kwargs: None)
    pipeline = DiscoveryPipeline(runner)

    # Mock user config search_paths to include custom_tools
    pipeline._user_config.search_paths = [str(custom_tools)]
    pipeline.clear_scan_cache()

    discovered = pipeline.discover_tool("c_compiler")
    assert discovered is not None
    assert discovered.resolve() == portable_mingw.resolve()

    all_instances = pipeline.discover_all_tool_instances("c_compiler")
    assert any(inst.resolve() == portable_mingw.resolve() for inst in all_instances)
