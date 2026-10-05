"""Tests for SafeRunner subprocess handling and path resolution."""

import sys
from devtoolkit.core.runner import SafeRunner


def test_safe_runner_timeout():
    runner = SafeRunner(default_timeout=0.5)
    # Run a command that takes longer than timeout
    if sys.platform == "win32":
        cmd = ["powershell", "-Command", "Start-Sleep -Seconds 2"]
    else:
        cmd = ["sleep", "2"]

    res = runner.run_command(cmd, timeout=0.5)
    assert res.timed_out is True
    assert not res.ok


def test_safe_runner_success():
    runner = SafeRunner()
    res = runner.run_command([sys.executable, "-c", "print('hello devtoolkit')"])
    assert res.ok is True
    assert res.stdout == "hello devtoolkit"
    assert res.exit_code == 0


def test_safe_runner_resolve_binary():
    runner = SafeRunner()
    # Python executable should always resolve
    py_path = runner.resolve_binary("python")
    assert py_path is not None
    assert py_path.exists()


def test_safe_runner_zero_path_discovery(tmp_path, monkeypatch):
    """Verify SafeRunner resolves a binary outside PATH via discovery."""
    custom_dir = tmp_path / "custom_tools"
    custom_dir.mkdir()
    tool_dir = custom_dir / "portable_sqlite"
    tool_dir.mkdir()
    fake_sqlite = tool_dir / "sqlite3.exe"
    fake_sqlite.write_text("dummy", encoding="utf-8")

    monkeypatch.setattr("shutil.which", lambda name: None)

    runner = SafeRunner()
    # Mock where.exe to return nothing as well
    monkeypatch.setattr(runner, "run_command", lambda cmd, **kwargs: type("Obj", (), {"ok": False, "stdout": "", "timed_out": False})())

    runner.discovery._user_config.search_paths = [str(custom_dir)]
    runner.discovery.clear_scan_cache()

    resolved = runner.resolve_binary("sqlite3", tool_id="sqlite")
    assert resolved is not None
    assert resolved.resolve() == fake_sqlite.resolve()

    all_resolved = runner.resolve_all_binaries("sqlite3", tool_id="sqlite")
    assert any(p.resolve() == fake_sqlite.resolve() for p in all_resolved)


def test_safe_runner_creationflags(monkeypatch):
    """Verify SafeRunner passes CREATE_NO_WINDOW and SW_HIDE on Windows."""
    captured_kwargs = {}

    def mock_subprocess_run(cmd, **kwargs):
        captured_kwargs.update(kwargs)
        res_mock = type("MockCompletedProcess", (), {})()
        res_mock.returncode = 0
        res_mock.stdout = "ok"
        res_mock.stderr = ""
        return res_mock

    monkeypatch.setattr("subprocess.run", mock_subprocess_run)

    runner = SafeRunner()
    runner.run_command(["dummy_command"])

    if sys.platform == "win32":
        import subprocess

        assert captured_kwargs.get("creationflags") == getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)
        startupinfo = captured_kwargs.get("startupinfo")
        assert startupinfo is not None
        assert startupinfo.wShowWindow == subprocess.SW_HIDE

