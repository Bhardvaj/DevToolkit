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


def test_signature_c_compiler_variants(tmp_path):
    from devtoolkit.core.signatures import is_c_compiler
    # Clang
    clang_dir = tmp_path / "clang_root"
    clang_dir.mkdir()
    (clang_dir / "bin").mkdir()
    (clang_dir / "bin" / "clang.exe").write_text("dummy", encoding="utf-8")
    (clang_dir / "include").mkdir()
    assert is_c_compiler(clang_dir) is True

    # MSVC
    msvc_dir = tmp_path / "msvc_root"
    msvc_dir.mkdir()
    (msvc_dir / "vcvarsall.bat").write_text("dummy", encoding="utf-8")
    assert is_c_compiler(msvc_dir) is True


def test_signature_python(tmp_path):
    from devtoolkit.core.signatures import is_python_sdk
    py_dir = tmp_path / "custom_python"
    py_dir.mkdir()
    (py_dir / "python.exe").write_text("dummy", encoding="utf-8")
    (py_dir / "Lib").mkdir()

    assert is_python_sdk(py_dir) is True


def test_signature_node(tmp_path):
    from devtoolkit.core.signatures import is_node_sdk
    node_dir = tmp_path / "custom_node"
    node_dir.mkdir()
    (node_dir / "node.exe").write_text("dummy", encoding="utf-8")
    (node_dir / "npm.cmd").write_text("dummy", encoding="utf-8")

    assert is_node_sdk(node_dir) is True


def test_signature_git(tmp_path):
    from devtoolkit.core.signatures import is_git_install
    git_dir = tmp_path / "custom_git"
    git_dir.mkdir()
    (git_dir / "cmd").mkdir()
    (git_dir / "cmd" / "git.exe").write_text("dummy", encoding="utf-8")
    (git_dir / "usr").mkdir()

    assert is_git_install(git_dir) is True


def test_signature_docker(tmp_path):
    from devtoolkit.core.signatures import is_docker_install
    docker_dir = tmp_path / "custom_docker"
    docker_dir.mkdir()
    (docker_dir / "docker.exe").write_text("dummy", encoding="utf-8")

    assert is_docker_install(docker_dir) is True


def test_signature_rust(tmp_path):
    from devtoolkit.core.signatures import is_rust_sdk
    rust_dir = tmp_path / "custom_rust"
    rust_dir.mkdir()
    (rust_dir / "bin").mkdir()
    (rust_dir / "bin" / "rustc.exe").write_text("dummy", encoding="utf-8")
    (rust_dir / "bin" / "cargo.exe").write_text("dummy", encoding="utf-8")

    assert is_rust_sdk(rust_dir) is True


def test_signature_golang(tmp_path):
    from devtoolkit.core.signatures import is_go_sdk
    go_dir = tmp_path / "custom_go"
    go_dir.mkdir()
    (go_dir / "bin").mkdir()
    (go_dir / "bin" / "go.exe").write_text("dummy", encoding="utf-8")
    (go_dir / "pkg").mkdir()

    assert is_go_sdk(go_dir) is True


def test_signature_simple_tools(tmp_path):
    from devtoolkit.core.signatures import (
        is_bun_install,
        is_gh_install,
        is_kubectl_install,
        is_ollama_install,
        is_sqlite_install,
        is_terraform_install,
    )

    bun_dir = tmp_path / "custom_bun"
    bun_dir.mkdir()
    (bun_dir / "bun.exe").write_text("dummy", encoding="utf-8")
    assert is_bun_install(bun_dir) is True

    gh_dir = tmp_path / "custom_gh"
    gh_dir.mkdir()
    (gh_dir / "bin").mkdir()
    (gh_dir / "bin" / "gh.exe").write_text("dummy", encoding="utf-8")
    assert is_gh_install(gh_dir) is True

    k_dir = tmp_path / "custom_kubectl"
    k_dir.mkdir()
    (k_dir / "kubectl.exe").write_text("dummy", encoding="utf-8")
    assert is_kubectl_install(k_dir) is True

    tf_dir = tmp_path / "custom_tf"
    tf_dir.mkdir()
    (tf_dir / "tofu.exe").write_text("dummy", encoding="utf-8")
    assert is_terraform_install(tf_dir) is True

    ol_dir = tmp_path / "custom_ollama"
    ol_dir.mkdir()
    (ol_dir / "ollama.exe").write_text("dummy", encoding="utf-8")
    assert is_ollama_install(ol_dir) is True

    sq_dir = tmp_path / "custom_sqlite"
    sq_dir.mkdir()
    (sq_dir / "sqlite3.exe").write_text("dummy", encoding="utf-8")
    assert is_sqlite_install(sq_dir) is True



