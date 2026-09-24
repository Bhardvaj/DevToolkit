"""DevToolkit: Extensible Developer Workstation Auditor and Utility Suite."""

import os
import subprocess
from pathlib import Path


def _resolve_version() -> str:
    """Resolve application version dynamically from environment, stamped build file, or git."""
    # 1. Environment variable override
    env_ver = os.environ.get("DEVTOOLKIT_VERSION", "").strip().lstrip("v")
    if env_ver:
        return env_ver

    # 2. Stamped _version.py generated during CI build/packaging
    try:
        from devtoolkit._version import __version__ as _stamped_ver
        if _stamped_ver:
            return str(_stamped_ver).strip().lstrip("v")
    except ImportError:
        pass

    # 3. If installed as a package with metadata
    try:
        import importlib.metadata
        pkg_ver = importlib.metadata.version("devtoolkit")
        if pkg_ver:
            return pkg_ver.strip().lstrip("v")
    except Exception:
        pass

    # 4. If running inside a git checkout, query git describe
    try:
        pkg_dir = Path(__file__).resolve().parent.parent
        res = subprocess.run(
            ["git", "describe", "--tags", "--abbrev=0"],
            cwd=pkg_dir,
            capture_output=True,
            text=True,
            timeout=1.5,
        )
        if res.returncode == 0 and res.stdout.strip():
            return res.stdout.strip().lstrip("v")
    except Exception:
        pass

    # 5. Fallback: parse pyproject.toml
    try:
        pyproj = Path(__file__).resolve().parent.parent / "pyproject.toml"
        if pyproj.is_file():
            with open(pyproj, "r", encoding="utf-8") as f:
                for line in f:
                    if line.strip().startswith("version ="):
                        return line.split("=")[1].strip().strip('"').strip("'").lstrip("v")
    except Exception:
        pass

    return "0.5.1"


__version__ = _resolve_version()

