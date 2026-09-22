"""Python Runtime & Package Manager Inspector."""

import re
import sys
from pathlib import Path
from datetime import datetime, timezone
from devtoolkit.core.base import BaseInspector
from devtoolkit.core.inventory import OSInventory
from devtoolkit.core.models import (
    CompanionTool,
    DeepTelemetryReport,
    DiagnosticIssue,
    DiagnosticLevel,
    DiscoveredInstance,
    EnvVarStatus,
    HealthStatus,
    ToolReport,
)
from devtoolkit.core.runner import SafeRunner


class PythonInspector(BaseInspector):
    id = "python"
    name = "Python"
    category = "runtime"
    categories = ["runtime", "scripting", "ai"]
    description = "Python interpreter, pip, uv, poetry, and virtualenv tooling"

    def inspect(self, runner: SafeRunner) -> ToolReport:
        py_bin = (
            runner.resolve_binary("python", tool_id=self.id)
            or runner.resolve_binary("python3", tool_id=self.id)
            or runner.resolve_binary("py", tool_id=self.id)
        )
        if not py_bin:
            return ToolReport(
                id=self.id,
                name=self.name,
                category=self.category,
                categories=self.categories,
                installed=False,
                status=HealthStatus.NOT_FOUND,
            )

        res = runner.run_command([str(py_bin), "--version"])
        version = None
        if res.ok and res.stdout:
            parts = res.stdout.split()
            if len(parts) >= 2:
                version = parts[1]

        companions = []
        diagnostics = []

        # Check companions: pip, uv, poetry, conda, pipenv
        for comp_name in ["pip", "uv", "poetry", "conda", "pipenv"]:
            comp_bin = runner.resolve_binary(comp_name)
            if comp_bin:
                comp_ver_res = runner.run_command([str(comp_bin), "--version"])
                comp_ver = None
                if comp_ver_res.ok and comp_ver_res.stdout:
                    m = re.search(r"(\d+\.\d+(\.\d+)?)", comp_ver_res.stdout)
                    comp_ver = m.group(1) if m else comp_ver_res.stdout.split()[0]
                companions.append(
                    CompanionTool(
                        name=comp_name,
                        installed=True,
                        version=comp_ver,
                        binary_path=str(comp_bin),
                    )
                )
            else:
                companions.append(CompanionTool(name=comp_name, installed=False))

        pip_found = any(c.installed for c in companions if c.name == "pip")
        if not pip_found:
            diagnostics.append(
                DiagnosticIssue(
                    level=DiagnosticLevel.WARNING,
                    message="pip package manager is not installed in the global environment.",
                    suggested_fix="python -m ensurepip --upgrade",
                )
            )

        status = HealthStatus.HEALTHY if pip_found else HealthStatus.WARNING

        return ToolReport(
            id=self.id,
            name=self.name,
            category=self.category,
            categories=self.categories,
            installed=True,
            version=version,
            binary_path=str(py_bin),
            home_path=str(py_bin.parent),
            status=status,
            companions=companions,
            diagnostics=diagnostics,
            metadata={"base_prefix": sys.base_prefix, "prefix": sys.prefix},
        )

    def deep_inspect(self, runner: SafeRunner, base_report: Optional[ToolReport] = None) -> DeepTelemetryReport:
        base_rep = base_report if base_report is not None else self.inspect(runner)
        trace: list[str] = [f"Base inspection complete. installed={base_rep.installed}"]
        instances: list[DiscoveredInstance] = []
        seen_paths: set[str] = set()

        def _add_inst(p: Path, bin_p: Path | None, ver: str | None, src: str, active: bool, details: str | None = None):
            key = str(bin_p or p).lower() if sys.platform == "win32" else str(bin_p or p)
            if key not in seen_paths:
                seen_paths.add(key)
                instances.append(
                    DiscoveredInstance(
                        path=str(p),
                        binary_path=str(bin_p) if bin_p else None,
                        version=ver,
                        source=src,
                        is_active=active,
                        details=details,
                    )
                )

        # 1. PATH binaries
        path_bins = runner.resolve_all_binaries("python")
        trace.append(f"Found {len(path_bins)} 'python' binary candidates in system PATH")
        for idx, pb in enumerate(path_bins):
            is_act = (idx == 0) and bool(base_rep.binary_path) and (str(pb).lower() == str(base_rep.binary_path).lower())
            ver = base_rep.version if is_act else None
            if not ver:
                ver_res = runner.run_command([str(pb), "--version"], timeout=2.0)
                if ver_res.ok and ver_res.stdout:
                    ver = ver_res.stdout.split()[-1]
            det = "Active binary in system PATH" if is_act else "Alternate binary in PATH"
            if "windowsapps" in str(pb).lower():
                det = "Microsoft Store App Execution Alias"
            _add_inst(pb.parent, pb, ver, "PATH", is_act, det)

        # 2. Python Launcher (py -0p)
        py_launcher = runner.resolve_binary("py")
        if py_launcher:
            trace.append("Querying Windows Python Launcher (py -0p)")
            py_res = runner.run_command([str(py_launcher), "-0p"], timeout=2.5)
            if py_res.ok and py_res.stdout:
                # Format: " -V:3.14 *        D:\UtilitySoftware\.venv\Scripts\python.exe"
                for line in py_res.stdout.splitlines():
                    parts = line.strip().split()
                    if len(parts) >= 2 and any(ext in parts[-1].lower() for ext in [".exe", "python"]):
                        target_exe = Path(parts[-1])
                        tag = parts[0].replace("-V:", "").replace("-", "")
                        is_act = bool(base_rep.binary_path) and (str(target_exe).lower() == str(base_rep.binary_path).lower())
                        _add_inst(target_exe.parent, target_exe, tag, "PyLauncher", is_act, f"Python Launcher registry entry ({tag})")

        # 3. Registry uninstaller entries
        reg_apps = OSInventory.find_app_locations("Python")
        trace.append(f"Found {len(reg_apps)} Python installations in Windows Registry")
        for reg_p in reg_apps:
            reg_bin = reg_p / "python.exe"
            b_target = reg_bin if reg_bin.exists() else None
            is_act = bool(base_rep.binary_path and b_target and str(b_target).lower() == str(base_rep.binary_path).lower())
            _add_inst(reg_p, b_target, None, "Registry", is_act, "Discovered via Windows Registry uninstall inventory")

        # 4. Discovery Pipeline (4-Layer & FastSearchEngine)
        for disc_root in runner.discovery.discover_all_tool_instances(self.id):
            cand_bin = disc_root / "python.exe"
            if not cand_bin.is_file():
                cand_bin = disc_root / "Scripts" / "python.exe"
            b_target = cand_bin if cand_bin.is_file() else None
            is_act = bool(base_rep.binary_path and b_target and str(b_target).lower() == str(base_rep.binary_path).lower())
            _add_inst(disc_root, b_target, None, "Discovery Pipeline", is_act, "Discovered via 4-Layer / FastSearchEngine signatures")

        # 4. Monitored Environment Variables Alignment
        env_vars: list[EnvVarStatus] = []
        active_home = base_rep.home_path

        # PYTHONPATH
        pythonpath = runner.read_env("PYTHONPATH")
        if pythonpath:
            p_exists = Path(pythonpath).exists()
            env_vars.append(
                EnvVarStatus(
                    name="PYTHONPATH",
                    value=pythonpath,
                    status="aligned" if p_exists else "divergent",
                    target_path=pythonpath,
                    message="Directory exists on disk" if p_exists else "Configured path does not exist on disk!",
                )
            )
        else:
            env_vars.append(
                EnvVarStatus(
                    name="PYTHONPATH",
                    value=None,
                    status="aligned",
                    message="Not set (standard site-packages resolution active)",
                )
            )

        # PYTHONHOME
        pythonhome = runner.read_env("PYTHONHOME")
        if pythonhome:
            ph_exists = Path(pythonhome).exists()
            is_aligned = active_home and (str(Path(pythonhome).resolve()).lower() == str(Path(active_home).resolve()).lower())
            status = "aligned" if is_aligned else ("divergent" if ph_exists else "missing")
            env_vars.append(
                EnvVarStatus(
                    name="PYTHONHOME",
                    value=pythonhome,
                    status=status,
                    target_path=active_home,
                    message="Points to active Python home" if is_aligned else f"Diverges from active Python home ({active_home})",
                )
            )
        else:
            env_vars.append(
                EnvVarStatus(
                    name="PYTHONHOME",
                    value=None,
                    status="aligned",
                    message="Not set (using default interpreter home)",
                )
            )

        # VIRTUAL_ENV
        venv = runner.read_env("VIRTUAL_ENV")
        if venv:
            v_exists = Path(venv).exists()
            env_vars.append(
                EnvVarStatus(
                    name="VIRTUAL_ENV",
                    value=venv,
                    status="aligned" if v_exists else "divergent",
                    target_path=venv,
                    message="Active virtual environment detected" if v_exists else "Virtual environment directory does not exist!",
                )
            )

        # 5. Deep Domain Telemetry
        telemetry: dict[str, Any] = {
            "is_virtualenv": bool(venv) or (sys.prefix != sys.base_prefix),
            "virtual_env_path": venv or (sys.prefix if sys.prefix != sys.base_prefix else None),
            "architecture": "64-bit AMD64" if sys.maxsize > 2**32 else "32-bit x86",
            "py_launcher_installed": py_launcher is not None,
        }

        # Query site-packages & pip cache if python is installed
        raw_dumps: dict[str, str] = {}
        if base_rep.binary_path:
            # -VV dump
            vv_res = runner.run_command([base_rep.binary_path, "-VV"], timeout=2.5)
            if vv_res.ok and vv_res.stdout:
                raw_dumps["python -VV"] = vv_res.stdout
                telemetry["build_info"] = vv_res.stdout

            # sysconfig paths
            sysc_res = runner.run_command([base_rep.binary_path, "-m", "sysconfig"], timeout=3.0)
            if sysc_res.ok and sysc_res.stdout:
                raw_dumps["python -m sysconfig"] = sysc_res.stdout

            # site-packages
            site_res = runner.run_command(
                [base_rep.binary_path, "-c", "import site; print(';'.join(site.getsitepackages()))"],
                timeout=2.5,
            )
            if site_res.ok and site_res.stdout:
                telemetry["site_packages"] = [p.strip() for p in site_res.stdout.split(";") if p.strip()]

            # pip cache dir
            pip_cache_res = runner.run_command([base_rep.binary_path, "-m", "pip", "cache", "dir"], timeout=2.5)
            if pip_cache_res.ok and pip_cache_res.stdout:
                telemetry["pip_cache_dir"] = pip_cache_res.stdout

        return DeepTelemetryReport(
            tool_id=self.id,
            timestamp=datetime.now(timezone.utc).isoformat(),
            probe_latency_ms=0,
            instances=instances,
            env_vars=env_vars,
            telemetry=telemetry,
            raw_dumps=raw_dumps,
            discovery_trace=trace,
        )
