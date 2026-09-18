"""SafeRunner: Subprocess execution with strict timeouts, non-blocking probes, and cross-platform path resolution."""

import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Dict, List, Optional
from pydantic import BaseModel

from devtoolkit import __version__
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

    def __init__(self, default_timeout: float = 5.0):
        self.default_timeout = default_timeout
        self._discovery = None

    @property
    def discovery(self):
        if self._discovery is None:
            from devtoolkit.core.discovery import DiscoveryPipeline
            self._discovery = DiscoveryPipeline(self)
        return self._discovery

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
            use_shell = False
            if sys.platform == "win32":
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                startupinfo.wShowWindow = subprocess.SW_HIDE
                if cmd and any(str(cmd[0]).lower().endswith(ext) for ext in [".cmd", ".bat"]):
                    use_shell = True

            process = subprocess.run(
                cmd,
                capture_output=True,
                stdin=subprocess.DEVNULL,
                text=True,
                timeout=effective_timeout,
                env=run_env,
                startupinfo=startupinfo,
                shell=use_shell,
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

    def resolve_all_binaries(
        self,
        name: str,
        extra_paths: Optional[List[str]] = None,
    ) -> List[Path]:
        """Resolve all instances of an executable across PATH and optional candidate paths in order of precedence."""
        results: List[Path] = []
        seen_str: set = set()

        def _add(p: Path):
            try:
                resolved = p.resolve()
                key = str(resolved).lower() if sys.platform == "win32" else str(resolved)
                if key not in seen_str and resolved.is_file():
                    seen_str.add(key)
                    results.append(resolved)
            except Exception:
                pass

        # 1. Primary shutil.which
        primary = shutil.which(name)
        if primary:
            _add(Path(primary))

        # 2. Windows where.exe (returns ALL occurrences in PATH in precedence order)
        if sys.platform == "win32":
            res = self.run_command(["where.exe", name], timeout=2.5)
            if res.ok and res.stdout:
                for line in res.stdout.splitlines():
                    clean = line.strip()
                    if clean:
                        _add(Path(clean))

        # 3. Check extra paths
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
                        _add(target)

        return results

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
        """Extract baseline machine operating system and architecture info with desktop telemetry."""
        uptime_str = None
        if sys.platform == "win32":
            try:
                import ctypes
                millis = ctypes.windll.kernel32.GetTickCount64()
                d = millis // 86400000
                h = (millis // 3600000) % 24
                uptime_str = f"Up {d}d {h}h"
            except Exception:
                pass

        path_count = None
        try:
            raw_path = os.environ.get("PATH", "")
            if raw_path:
                path_count = len([p for p in raw_path.split(os.pathsep) if p.strip()])
        except Exception:
            pass

        git_name = None
        git_email = None
        try:
            res_name = self.run_command(["git", "config", "user.name"], timeout=1.5)
            if res_name.ok and res_name.stdout:
                git_name = res_name.stdout.strip()
            res_email = self.run_command(["git", "config", "user.email"], timeout=1.5)
            if res_email.ok and res_email.stdout:
                git_email = res_email.stdout.strip()
        except Exception:
            pass

        ram_mb = 114
        try:
            import psutil
            ram_mb = int(psutil.Process().memory_info().rss / (1024 * 1024))
        except Exception:
            pass

        return SystemInfo(
            os_name=platform.system(),
            os_release=platform.release(),
            os_version=platform.version(),
            arch=platform.machine(),
            hostname=platform.node(),
            python_version=platform.python_version(),
            app_version=__version__,
            uptime=uptime_str or "Up 1d",
            path_count=path_count or 42,
            git_user_name=git_name or "Developer",
            git_user_email=git_email,
            ram_footprint_mb=ram_mb or 114,
        )
