import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

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


class GoInspector(BaseInspector):
    id = "golang"
    name = "Go"
    category = "runtime"
    categories = ["runtime", "backend"]
    description = "Go Programming Language runtime and compiler"

    def inspect(self, runner: SafeRunner) -> ToolReport:
        go_bin = runner.find_binary("go", tool_id=self.id)
        if not go_bin:
            return ToolReport(
                id=self.id,
                name=self.name,
                category=self.category,
                categories=self.categories,
                description=self.description,
                installed=False,
                status=HealthStatus.NOT_FOUND,
                diagnostics=[DiagnosticIssue(level=DiagnosticLevel.ERROR, message="Go compiler is not installed", suggested_fix="Install Go from https://go.dev/dl/")],
            )

        res = runner.run_command(["go", "version"])
        version = None
        if res.ok and res.stdout:
            # "go version go1.22.1 windows/amd64"
            m = re.search(r"go(\d+\.\d+(\.\d+)?)", res.stdout)
            if m:
                version = m.group(1)

        # Inspect env vars
        env_res = runner.run_command(["go", "env", "-json"])
        gopath = None
        goroot = None
        if env_res.ok and env_res.stdout:
            try:
                env_data = json.loads(env_res.stdout)
                gopath = env_data.get("GOPATH")
                goroot = env_data.get("GOROOT")
            except Exception:
                pass

        diagnostics: list[DiagnosticIssue] = []
        status = HealthStatus.HEALTHY
        if not gopath:
            diagnostics.append(DiagnosticIssue(level=DiagnosticLevel.WARNING, message="GOPATH is not defined", suggested_fix="export GOPATH=$HOME/go"))
            status = HealthStatus.WARNING

        # Companions
        companions = []
        for c in ["gopls", "golangci-lint", "dlv"]:
            cb = runner.find_binary(c)
            companions.append(CompanionTool(name=c, installed=cb is not None, binary_path=str(cb) if cb else None))

        return ToolReport(
            id=self.id,
            name=self.name,
            category=self.category,
            categories=self.categories,
            description=self.description,
            installed=True,
            version=version,
            binary_path=str(go_bin),
            home_path=goroot or str(go_bin.parent.parent),
            status=status,
            companions=companions,
            diagnostics=diagnostics,
            metadata={"GOPATH": gopath, "GOROOT": goroot},
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
        path_bins = runner.resolve_all_binaries("go")
        trace.append(f"Found {len(path_bins)} 'go' binary candidates in system PATH")
        for idx, pb in enumerate(path_bins):
            is_act = (idx == 0) and bool(base_rep.binary_path) and (str(pb).lower() == str(base_rep.binary_path).lower())
            ver = base_rep.version if is_act else None
            _add_inst(pb.parent.parent, pb, ver, "PATH", is_act, "Active binary in system PATH" if is_act else "Alternate binary in PATH")

        # 2. Registry uninstall inventory
        reg_apps = OSInventory.find_app_locations("Go Programming Language")
        for reg_p in reg_apps:
            reg_bin = reg_p / "bin" / ("go.exe" if sys.platform == "win32" else "go")
            b_target = reg_bin if reg_bin.exists() else None
            is_act = bool(base_rep.binary_path and b_target and str(b_target).lower() == str(base_rep.binary_path).lower())
            _add_inst(reg_p, b_target, None, "Registry", is_act, "Official Go Windows Installer")

        # 3. Discovery Pipeline (4-Layer & FastSearchEngine)
        for disc_root in runner.discovery.discover_all_tool_instances(self.id):
            cand_bin = disc_root / "bin" / ("go.exe" if sys.platform == "win32" else "go")
            if not cand_bin.is_file():
                cand_bin = disc_root / ("go.exe" if sys.platform == "win32" else "go")
            b_target = cand_bin if cand_bin.is_file() else None
            is_act = bool(base_rep.binary_path and b_target and str(b_target).lower() == str(base_rep.binary_path).lower())
            _add_inst(disc_root, b_target, None, "Discovery Pipeline", is_act, "Discovered via 4-Layer / FastSearchEngine signatures")

        # 3. Monitored Environment Variables Alignment
        env_vars: list[EnvVarStatus] = []
        active_home = base_rep.home_path

        # GOROOT
        goroot_env = runner.read_env("GOROOT")
        if goroot_env:
            gr_exists = Path(goroot_env).exists()
            is_aligned = active_home and (str(Path(goroot_env).resolve()).lower() == str(Path(active_home).resolve()).lower())
            env_vars.append(
                EnvVarStatus(
                    name="GOROOT",
                    value=goroot_env,
                    status="aligned" if is_aligned else ("divergent" if gr_exists else "missing"),
                    target_path=active_home or goroot_env,
                    message="Matches active Go root" if is_aligned else "Diverges from active Go installation root!",
                )
            )
        else:
            env_vars.append(
                EnvVarStatus(
                    name="GOROOT",
                    value=base_rep.metadata.get("GOROOT"),
                    status="aligned",
                    message="Using automatic Go compiler root resolution",
                )
            )

        # GOPATH
        gopath_env = runner.read_env("GOPATH") or base_rep.metadata.get("GOPATH")
        if gopath_env:
            gp_exists = Path(gopath_env).exists()
            env_vars.append(
                EnvVarStatus(
                    name="GOPATH",
                    value=gopath_env,
                    status="aligned" if gp_exists else "divergent",
                    target_path=gopath_env,
                    message="Workspace directory exists" if gp_exists else "GOPATH directory not created yet",
                )
            )

        # GOPROXY
        goproxy = runner.read_env("GOPROXY")
        if goproxy:
            env_vars.append(
                EnvVarStatus(
                    name="GOPROXY",
                    value=goproxy,
                    status="aligned",
                    message="Custom module proxy mirror configured",
                )
            )

        # 4. Deep Domain Telemetry & Raw Dumps
        telemetry: dict[str, Any] = {
            "GOPATH": base_rep.metadata.get("GOPATH") or "Not configured",
            "GOROOT": base_rep.metadata.get("GOROOT") or "Not configured",
        }

        raw_dumps: dict[str, str] = {}
        if base_rep.binary_path:
            # go version
            ver_res = runner.run_command([base_rep.binary_path, "version"], timeout=2.0)
            if ver_res.ok and ver_res.stdout:
                raw_dumps["go version"] = ver_res.stdout

            # go env -json
            env_res = runner.run_command([base_rep.binary_path, "env", "-json"], timeout=3.0)
            if env_res.ok and env_res.stdout:
                raw_dumps["go env -json"] = env_res.stdout
                try:
                    data = json.loads(env_res.stdout)
                    telemetry["target_os_arch"] = f"{data.get('GOOS', '')}/{data.get('GOARCH', '')}"
                    telemetry["cgo_enabled"] = data.get("CGO_ENABLED") == "1"
                    telemetry["goproxy"] = data.get("GOPROXY")
                    telemetry["gomodcache"] = data.get("GOMODCACHE")
                    telemetry["compiler"] = data.get("GOVERSION")
                except Exception:
                    pass

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


GolangInspector = GoInspector
