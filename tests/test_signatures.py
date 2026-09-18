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


def test_signature_dotnet(tmp_path):
    from devtoolkit.core.signatures import is_dotnet_sdk
    dotnet_dir = tmp_path / "custom_dotnet"
    dotnet_dir.mkdir()
    (dotnet_dir / "dotnet.exe").write_text("dummy", encoding="utf-8")
    (dotnet_dir / "sdk").mkdir()

    assert is_dotnet_sdk(dotnet_dir) is True


def test_signature_vscode(tmp_path):
    from devtoolkit.core.signatures import is_vscode
    vscode_dir = tmp_path / "custom_vscode"
    vscode_dir.mkdir()
    (vscode_dir / "Code.exe").write_text("dummy", encoding="utf-8")
    (vscode_dir / "resources" / "app").mkdir(parents=True)

    assert is_vscode(vscode_dir) is True


def test_signature_cmake(tmp_path):
    from devtoolkit.core.signatures import is_cmake
    cmake_dir = tmp_path / "custom_cmake"
    cmake_dir.mkdir()
    (cmake_dir / "bin").mkdir()
    (cmake_dir / "bin" / "cmake.exe").write_text("dummy", encoding="utf-8")
    (cmake_dir / "share").mkdir()

    assert is_cmake(cmake_dir) is True


def test_signature_cuda(tmp_path):
    from devtoolkit.core.signatures import is_cuda_toolkit
    cuda_dir = tmp_path / "custom_cuda"
    cuda_dir.mkdir()
    (cuda_dir / "bin").mkdir()
    (cuda_dir / "bin" / "nvcc.exe").write_text("dummy", encoding="utf-8")
    (cuda_dir / "include").mkdir()

    assert is_cuda_toolkit(cuda_dir) is True


def test_signature_php(tmp_path):
    from devtoolkit.core.signatures import is_php_sdk
    php_dir = tmp_path / "custom_php"
    php_dir.mkdir()
    (php_dir / "php.exe").write_text("dummy", encoding="utf-8")
    (php_dir / "ext").mkdir()

    assert is_php_sdk(php_dir) is True


def test_signature_mingw(tmp_path):
    from devtoolkit.core.signatures import is_mingw
    mingw_dir = tmp_path / "custom_mingw"
    mingw_dir.mkdir()
    (mingw_dir / "bin").mkdir()
    (mingw_dir / "bin" / "gcc.exe").write_text("dummy", encoding="utf-8")
    (mingw_dir / "include").mkdir()

    assert is_mingw(mingw_dir) is True


