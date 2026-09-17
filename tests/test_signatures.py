"""Tests for content signature detection."""

from pathlib import Path
from devtoolkit.core.signatures import (
    is_android_sdk,
    is_android_studio,
    is_flutter_sdk,
    is_go_sdk,
    is_jdk,
    is_rust_sdk,
    scan_roots_for_tools,
)


def test_signature_android_sdk(tmp_path):
    sdk_dir = tmp_path / "custom_sdk"
    sdk_dir.mkdir()
    platform_tools = sdk_dir / "platform-tools"
    platform_tools.mkdir()
    (platform_tools / "adb.exe").write_text("dummy", encoding="utf-8")
    (platform_tools / "adb").write_text("dummy", encoding="utf-8")
    (sdk_dir / "build-tools").mkdir()

    assert is_android_sdk(sdk_dir) is True
    assert is_jdk(sdk_dir) is False


def test_signature_jdk(tmp_path):
    jdk_dir = tmp_path / "custom_jdk"
    jdk_dir.mkdir()
    bin_dir = jdk_dir / "bin"
    bin_dir.mkdir()
    (bin_dir / "java.exe").write_text("dummy", encoding="utf-8")
    (bin_dir / "javac.exe").write_text("dummy", encoding="utf-8")
    (bin_dir / "java").write_text("dummy", encoding="utf-8")
    (bin_dir / "javac").write_text("dummy", encoding="utf-8")

    assert is_jdk(jdk_dir) is True
    assert is_android_sdk(jdk_dir) is False


def test_scan_roots_signature(tmp_path):
    root = tmp_path / "dev_root"
    root.mkdir()

    # Create dummy SDK in subfolder
    sdk = root / "unnamed_android_folder"
    sdk.mkdir()
    (sdk / "platform-tools").mkdir()
    (sdk / "platform-tools" / "adb.exe").write_text("dummy", encoding="utf-8")
    (sdk / "platform-tools" / "adb").write_text("dummy", encoding="utf-8")
    (sdk / "platforms").mkdir()

    results = scan_roots_for_tools([root], max_depth=1)
    assert sdk in results["android"]
