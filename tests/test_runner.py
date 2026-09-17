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

