"""SafeRunner: Subprocess execution with strict timeouts, non-blocking probes, and cross-platform path resolution."""

import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Dict, List, Optional
from pydantic import BaseModel

from devtoolkit.core.models import SystemInfo


class CommandResult(BaseModel):
    command: List[str]
    exit_code: int
    stdout: str
    stderr: str
    timed_out: bool = False

    @property
    def ok(self) -> bool:
        return self.exit_code == 0 and not self.timed_out


class SafeRunner:
    """Executes safe, non-destructive external commands with timeouts and resolves paths."""

    def __init__(self, default_timeout: float = 3.0):
        self.default_timeout = default_timeout

    def run_command(
        self,
        cmd: List[str],
        timeout: Optional[float] = None,
        env: Optional[Dict[str, str]] = None,
    ) -> CommandResult:
        """Run a command with guaranteed timeout and non-blocking capture."""
        effective_timeout = timeout if timeout is not None else self.default_timeout
        
        # Merge custom env with os.environ
        run_env = os.environ.copy()
        if env:
            run_env.update(env)

        try:
            # On Windows, prevent flashing a command prompt console window
            startupinfo = None
            if sys.platform == "win32":
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW

            process = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=effective_timeout,
                env=run_env,
                startupinfo=startupinfo,
                errors="replace",
            )
            return CommandResult(
                command=cmd,
                exit_code=process.returncode,
                stdout=process.stdout.strip(),
                stderr=process.stderr.strip(),
                timed_out=False,
            )
        except subprocess.TimeoutExpired:
            return CommandResult(
                command=cmd,
                exit_code=-1,
                stdout="",
                stderr=f"Command timed out after {effective_timeout}s",
                timed_out=True,
            )
        except Exception as e:
            return CommandResult(
                command=cmd,
                exit_code=-1,
                stdout="",
                stderr=str(e),
                timed_out=False,
            )

    def resolve_binary(
        self,
        name: str,
        extra_paths: Optional[List[str]] = None,
    ) -> Optional[Path]:
        """Resolve full executable path across PATH and optional candidate paths."""
        # 1. Standard shutil.which lookup
        found = shutil.which(name)
        if found:
            return Path(found).resolve()

        # 2. Check candidate extra paths
        if extra_paths:
            extensions = [""]
            if sys.platform == "win32":
                extensions = ["", ".exe", ".cmd", ".bat", ".ps1"]

            for candidate_dir in extra_paths:
                base_dir = Path(candidate_dir).expanduser()
                if not base_dir.exists():
                    continue
                for ext in extensions:
                    target = base_dir / f"{name}{ext}"
                    if target.is_file() and os.access(target, os.X_OK):
                        return target.resolve()

        # 3. Windows where fallback
        if sys.platform == "win32":
            res = self.run_command(["where.exe", name], timeout=2.0)
            if res.ok and res.stdout:
                first_line = res.stdout.splitlines()[0].strip()
                p = Path(first_line)
                if p.exists():
                    return p.resolve()

        return None

    def read_env(self, var_name: str) -> Optional[str]:
        """Safely read an environment variable."""
        val = os.environ.get(var_name)
        return val.strip() if val else None

    def query_winreg(self, key_path: str, value_name: str = "") -> Optional[str]:
        """Read a value from the Windows Registry (HKLM then HKCU) if running on Windows."""
        if sys.platform != "win32":
            return None

        try:
            import winreg

            roots = [winreg.HKEY_LOCAL_MACHINE, winreg.HKEY_CURRENT_USER]
            for root in roots:
                try:
                    with winreg.OpenKey(root, key_path, 0, winreg.KEY_READ | winreg.KEY_WOW64_64KEY) as k:
                        val, _ = winreg.QueryValueEx(k, value_name)
                        if val:
                            return str(val)
                except OSError:
                    continue
        except Exception:
            return None
        return None

    def get_system_info(self) -> SystemInfo:
        """Extract baseline machine operating system and architecture info."""
        return SystemInfo(
            os_name=platform.system(),
            os_release=platform.release(),
            os_version=platform.version(),
            arch=platform.machine(),
            hostname=platform.node(),
            python_version=platform.python_version(),
        )

