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


class NodeInspector(BaseInspector):
    id = "node"
    name = "Node.js"
    category = "runtime"
    categories = ["runtime", "web"]
    description = "Node.js runtime, npm, and modern JavaScript package managers"

    def inspect(self, runner: SafeRunner) -> ToolReport:
        node_bin = runner.resolve_binary("node", tool_id=self.id)
        if not node_bin:
            return ToolReport(
                id=self.id,
                name=self.name,
                category=self.category,
                categories=self.categories,
                installed=False,
                status=HealthStatus.NOT_FOUND,
            )

        # Probe version: `node -v` -> "v24.20.0"
        res = runner.run_command([str(node_bin), "-v"])
        version = res.stdout.lstrip("v").strip() if res.ok else None

        companions = []
        diagnostics = []

        # Check companions: npm, pnpm, yarn, corepack
        for companion_name in ["npm", "pnpm", "yarn", "corepack"]:
            comp_bin = runner.resolve_binary(companion_name)
            if comp_bin:
                comp_ver_res = runner.run_command([str(comp_bin), "--version"])
                comp_ver = comp_ver_res.stdout.strip() if comp_ver_res.ok else None
                companions.append(
                    CompanionTool(
                        name=companion_name,
                        installed=True,
                        version=comp_ver,
                        binary_path=str(comp_bin),
                    )
                )
            else:
                companions.append(CompanionTool(name=companion_name, installed=False))

        npm_found = any(c.installed for c in companions if c.name == "npm")
        if not npm_found:
            diagnostics.append(
                DiagnosticIssue(
                    level=DiagnosticLevel.WARNING,
                    message="npm package manager is not detected alongside Node.js.",
                    suggested_fix="corepack enable",
                )
            )

        status = HealthStatus.HEALTHY if npm_found else HealthStatus.WARNING

        return ToolReport(
            id=self.id,
            name=self.name,
            category=self.category,
            categories=self.categories,
            installed=True,
            version=version,
            binary_path=str(node_bin),
            home_path=str(node_bin.parent),
            status=status,
            companions=companions,
            diagnostics=diagnostics,
            metadata={"prefix": str(node_bin.parent)},
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
        path_bins = runner.resolve_all_binaries("node")
        trace.append(f"Found {len(path_bins)} 'node' binary candidates in system PATH")
        for idx, pb in enumerate(path_bins):
            is_act = (idx == 0) and bool(base_rep.binary_path) and (str(pb).lower() == str(base_rep.binary_path).lower())
            ver = base_rep.version if is_act else None
            if not ver:
                ver_res = runner.run_command([str(pb), "-v"], timeout=2.0)
                if ver_res.ok and ver_res.stdout:
                    ver = ver_res.stdout.lstrip("v").strip()
            det = "Active binary in system PATH" if is_act else "Alternate binary in PATH"
            if "nvm" in str(pb).lower():
                det = "Managed by NVM (Node Version Manager)"
            elif "fnm" in str(pb).lower():
                det = "Managed by fnm (Fast Node Manager)"
            elif "volta" in str(pb).lower():
                det = "Managed by Volta"
            _add_inst(pb.parent, pb, ver, "PATH", is_act, det)

        # 2. Check NVM / fnm directories
        nvm_home = runner.read_env("NVM_HOME")
        if nvm_home and Path(nvm_home).exists():
            trace.append(f"Inspecting NVM_HOME at {nvm_home}")
            nvm_path = Path(nvm_home)
            for sub in nvm_path.iterdir():
                if sub.is_dir() and (sub / "node.exe").is_file():
                    is_act = bool(base_rep.binary_path) and (str(sub / "node.exe").lower() == str(base_rep.binary_path).lower())
                    _add_inst(sub, sub / "node.exe", sub.name.lstrip("v"), "NVM", is_act, f"NVM Installed Version ({sub.name})")

        # 3. Registry uninstaller entries
        reg_apps = OSInventory.find_app_locations("Node.js")
        trace.append(f"Found {len(reg_apps)} Node.js installations in Windows Registry")
        for reg_p in reg_apps:
            reg_bin = reg_p / "node.exe"
            b_target = reg_bin if reg_bin.exists() else None
            is_act = bool(base_rep.binary_path and b_target and str(b_target).lower() == str(base_rep.binary_path).lower())
            _add_inst(reg_p, b_target, None, "Registry", is_act, "Discovered via Windows Registry uninstall inventory")

        # 4. Discovery Pipeline (4-Layer & FastSearchEngine)
        for disc_root in runner.discovery.discover_all_tool_instances(self.id):
            cand_bin = disc_root / "node.exe"
            if not cand_bin.is_file():
                cand_bin = disc_root / "bin" / "node.exe"
            b_target = cand_bin if cand_bin.is_file() else None
            is_act = bool(base_rep.binary_path and b_target and str(b_target).lower() == str(base_report.binary_path).lower() if base_report and base_report.binary_path else False)
            _add_inst(disc_root, b_target, None, "Discovery Pipeline", is_act, "Discovered via 4-Layer / FastSearchEngine signatures")

        # 4. Monitored Environment Variables Alignment
        env_vars: list[EnvVarStatus] = []
        active_home = base_rep.home_path

        # NODE_PATH
        nodepath = runner.read_env("NODE_PATH")
        if nodepath:
            np_exists = Path(nodepath).exists()
            env_vars.append(
                EnvVarStatus(
                    name="NODE_PATH",
                    value=nodepath,
                    status="aligned" if np_exists else "divergent",
                    target_path=nodepath,
                    message="Directory exists on disk" if np_exists else "Configured path does not exist on disk!",
                )
            )
        else:
            env_vars.append(
                EnvVarStatus(
                    name="NODE_PATH",
                    value=None,
                    status="aligned",
                    message="Not set (standard node_modules traversal active)",
                )
            )

        # NVM_HOME
        if nvm_home:
            nh_exists = Path(nvm_home).exists()
            env_vars.append(
                EnvVarStatus(
                    name="NVM_HOME",
                    value=nvm_home,
                    status="aligned" if nh_exists else "divergent",
                    target_path=nvm_home,
                    message="NVM installation directory found" if nh_exists else "Configured NVM_HOME path does not exist!",
                )
            )

        # NVM_SYMLINK
        nvm_sym = runner.read_env("NVM_SYMLINK")
        if nvm_sym:
            ns_exists = Path(nvm_sym).exists()
            is_aligned = active_home and (str(Path(nvm_sym).resolve()).lower() == str(Path(active_home).resolve()).lower())
            env_vars.append(
                EnvVarStatus(
                    name="NVM_SYMLINK",
                    value=nvm_sym,
                    status="aligned" if is_aligned else ("divergent" if ns_exists else "missing"),
                    target_path=nvm_sym,
                    message="Points to active Node runtime" if is_aligned else "Diverges from currently active Node installation",
                )
            )

        # 5. Deep Domain Telemetry & Raw Dumps
        telemetry: dict[str, Any] = {
            "is_lts": False,
        }
        if base_rep.version:
            try:
                major = int(base_rep.version.split(".")[0])
                telemetry["is_lts"] = (major % 2 == 0)
                telemetry["release_line"] = f"Node.js v{major}.x ({'Active LTS' if major % 2 == 0 else 'Current'})"
            except Exception:
                pass

        raw_dumps: dict[str, str] = {}
        if base_rep.binary_path:
            # Process versions
            v_res = runner.run_command([base_rep.binary_path, "-p", "JSON.stringify(process.versions, null, 2)"], timeout=2.5)
            if v_res.ok and v_res.stdout:
                raw_dumps['node -p "process.versions"'] = v_res.stdout
                try:
                    import json
                    pv = json.loads(v_res.stdout)
                    telemetry["v8_version"] = pv.get("v8")
                    telemetry["uv_version"] = pv.get("uv")
                    telemetry["openssl_version"] = pv.get("openssl")
                except Exception:
                    pass

            # npm global prefix & root
            npm_bin = runner.resolve_binary("npm")
            if npm_bin:
                pref_res = runner.run_command([str(npm_bin), "config", "get", "prefix"], timeout=2.5)
                if pref_res.ok and pref_res.stdout:
                    telemetry["npm_global_prefix"] = pref_res.stdout.strip()

                root_res = runner.run_command([str(npm_bin), "root", "-g"], timeout=2.5)
                if root_res.ok and root_res.stdout:
                    telemetry["global_node_modules"] = root_res.stdout.strip()

                cfg_res = runner.run_command([str(npm_bin), "config", "list"], timeout=3.0)
                if cfg_res.ok and cfg_res.stdout:
                    raw_dumps["npm config list"] = cfg_res.stdout

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
