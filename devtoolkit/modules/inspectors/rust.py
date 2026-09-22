import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

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


class RustInspector(BaseInspector):
    id = "rust"
    name = "Rust / Cargo"
    category = "runtime"
    categories = ["runtime", "compiler"]
    description = "Rust compiler (rustc), Cargo package manager, and rustup toolchains"

    def inspect(self, runner: SafeRunner) -> ToolReport:
        rustc_bin = runner.resolve_binary("rustc", tool_id=self.id)
        if not rustc_bin:
            return ToolReport(
                id=self.id,
                name=self.name,
                category=self.category,
                categories=self.categories,
                installed=False,
                status=HealthStatus.NOT_FOUND,
            )

        # Output format: "rustc 1.79.0 (129f3b996 2024-06-10)"
        res = runner.run_command([str(rustc_bin), "--version"])
        version = None
        if res.ok and res.stdout:
            m = re.search(r"rustc\s+([0-9.]+)", res.stdout)
            version = m.group(1) if m else res.stdout

        companions = []
        diagnostics = []

        # Check Cargo and rustup
        for tool_name in ["cargo", "rustup"]:
            t_bin = runner.resolve_binary(tool_name)
            if t_bin:
                t_res = runner.run_command([str(t_bin), "--version"])
                t_ver = None
                if t_res.ok and t_res.stdout:
                    m = re.search(r"[0-9.]+", t_res.stdout)
                    t_ver = m.group(0) if m else None
                companions.append(
                    CompanionTool(
                        name=tool_name,
                        installed=True,
                        version=t_ver,
                        binary_path=str(t_bin),
                    )
                )
            else:
                companions.append(CompanionTool(name=tool_name, installed=False))

        cargo_found = any(c.installed for c in companions if c.name == "cargo")
        if not cargo_found:
            diagnostics.append(
                DiagnosticIssue(
                    level=DiagnosticLevel.WARNING,
                    message="Cargo package manager is not found alongside rustc.",
                    suggested_fix="rustup component add cargo",
                )
            )

        status = HealthStatus.HEALTHY if cargo_found else HealthStatus.WARNING

        return ToolReport(
            id=self.id,
            name=self.name,
            category=self.category,
            categories=self.categories,
            installed=True,
            version=version,
            binary_path=str(rustc_bin),
            home_path=str(rustc_bin.parent),
            status=status,
            companions=companions,
            diagnostics=diagnostics,
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

        # 1. System PATH binaries
        path_bins = runner.resolve_all_binaries("rustc")
        trace.append(f"Found {len(path_bins)} 'rustc' binary candidates in system PATH")
        for idx, pb in enumerate(path_bins):
            is_act = (idx == 0) and bool(base_rep.binary_path) and (str(pb).lower() == str(base_rep.binary_path).lower())
            ver = base_rep.version if is_act else None
            _add_inst(pb.parent, pb, ver, "PATH", is_act, "Active binary in system PATH" if is_act else "Alternate binary in PATH")

        # 2. Standard Cargo Home Bin
        std_cargo_bin = Path.home() / ".cargo" / "bin" / ("rustc.exe" if sys.platform == "win32" else "rustc")
        if std_cargo_bin.exists():
            is_act = bool(base_rep.binary_path) and (str(std_cargo_bin).lower() == str(base_rep.binary_path).lower())
            _add_inst(std_cargo_bin.parent, std_cargo_bin, None, "Default", is_act, "Rustup standard ~/.cargo/bin location")

        # 3. Discovery Pipeline (4-Layer & FastSearchEngine)
        for disc_root in runner.discovery.discover_all_tool_instances(self.id):
            cand_bin = disc_root / "bin" / ("rustc.exe" if sys.platform == "win32" else "rustc")
            if not cand_bin.is_file():
                cand_bin = disc_root / ("rustc.exe" if sys.platform == "win32" else "rustc")
            b_target = cand_bin if cand_bin.is_file() else None
            is_act = bool(base_rep.binary_path and b_target and str(b_target).lower() == str(base_rep.binary_path).lower())
            _add_inst(disc_root, b_target, None, "Discovery Pipeline", is_act, "Discovered via 4-Layer / FastSearchEngine signatures")

        # 3. Monitored Environment Variables Alignment
        env_vars: list[EnvVarStatus] = []

        # CARGO_HOME
        cargo_home = runner.read_env("CARGO_HOME")
        std_cargo = Path.home() / ".cargo"
        if cargo_home:
            c_exists = Path(cargo_home).exists()
            env_vars.append(
                EnvVarStatus(
                    name="CARGO_HOME",
                    value=cargo_home,
                    status="aligned" if c_exists else "divergent",
                    target_path=cargo_home,
                    message="Custom Cargo directory exists" if c_exists else "Configured CARGO_HOME does not exist!",
                )
            )
        else:
            env_vars.append(
                EnvVarStatus(
                    name="CARGO_HOME",
                    value=str(std_cargo) if std_cargo.exists() else None,
                    status="aligned",
                    message="Using default ~/.cargo directory" if std_cargo.exists() else "Default ~/.cargo directory not created yet",
                )
            )

        # RUSTUP_HOME
        rustup_home = runner.read_env("RUSTUP_HOME")
        std_rustup = Path.home() / ".rustup"
        if rustup_home:
            r_exists = Path(rustup_home).exists()
            env_vars.append(
                EnvVarStatus(
                    name="RUSTUP_HOME",
                    value=rustup_home,
                    status="aligned" if r_exists else "divergent",
                    target_path=rustup_home,
                    message="Custom Rustup toolchain root exists" if r_exists else "Configured RUSTUP_HOME does not exist!",
                )
            )
        else:
            env_vars.append(
                EnvVarStatus(
                    name="RUSTUP_HOME",
                    value=str(std_rustup) if std_rustup.exists() else None,
                    status="aligned",
                    message="Using default ~/.rustup directory" if std_rustup.exists() else "Default ~/.rustup directory not created yet",
                )
            )

        # 4. Deep Domain Telemetry & Raw Dumps
        telemetry: dict[str, Any] = {
            "has_cargo": any(c.installed for c in base_rep.companions if c.name == "cargo"),
            "has_rustup": any(c.installed for c in base_rep.companions if c.name == "rustup"),
        }

        raw_dumps: dict[str, str] = {}
        if base_rep.binary_path:
            # rustc -vV (host triple, commit hash, date)
            vv_res = runner.run_command([base_rep.binary_path, "-vV"], timeout=2.5)
            if vv_res.ok and vv_res.stdout:
                raw_dumps["rustc -vV"] = vv_res.stdout
                for line in vv_res.stdout.splitlines():
                    if line.startswith("host:"):
                        telemetry["host_triple"] = line.split(":")[-1].strip()
                    elif line.startswith("commit-hash:"):
                        telemetry["commit_hash"] = line.split(":")[-1].strip()[:9]
                    elif line.startswith("release:"):
                        telemetry["compiler_release"] = line.split(":")[-1].strip()

            # rustup show
            rustup_bin = runner.resolve_binary("rustup")
            if rustup_bin:
                show_res = runner.run_command([str(rustup_bin), "show"], timeout=3.0)
                if show_res.ok and show_res.stdout:
                    raw_dumps["rustup show"] = show_res.stdout
                    for line in show_res.stdout.splitlines():
                        if "(default)" in line:
                            telemetry["default_toolchain"] = line.split()[0].strip()

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
