"""NVIDIA CUDA Toolkit & GPU Accelerator Inspector."""

import os
import re
import sys
from pathlib import Path
from typing import List, Optional

from devtoolkit.core.base import BaseInspector
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


class CudaInspector(BaseInspector):
    id = "cuda"
    name = "NVIDIA CUDA Toolkit"
    category = "ai"
    categories = ["ai", "compiler", "hardware"]
    description = "NVIDIA CUDA Compiler (nvcc), GPU computing toolkit, and driver integration"

    def inspect(self, runner: SafeRunner) -> ToolReport:
        nvcc_bin = runner.resolve_binary("nvcc", tool_id=self.id)
        cuda_dir = None

        # Check CUDA_PATH or default Program Files locations if not on PATH
        if not nvcc_bin:
            cuda_path_env = os.environ.get("CUDA_PATH")
            if cuda_path_env and Path(cuda_path_env).is_dir():
                cand = Path(cuda_path_env) / "bin" / ("nvcc.exe" if sys.platform == "win32" else "nvcc")
                if cand.is_file():
                    nvcc_bin = cand
                    cuda_dir = Path(cuda_path_env)

            if not nvcc_bin and sys.platform == "win32":
                cuda_parent = Path("C:/Program Files/NVIDIA GPU Computing Toolkit/CUDA")
                if cuda_parent.is_dir():
                    # Pick latest version directory
                    versions = sorted(cuda_parent.iterdir(), reverse=True)
                    for v in versions:
                        cand = v / "bin" / "nvcc.exe"
                        if cand.is_file():
                            nvcc_bin = cand
                            cuda_dir = v
                            break

        # Check nvidia-smi companion for GPU existence
        smi_bin = runner.resolve_binary("nvidia-smi")
        if not smi_bin and sys.platform == "win32":
            cand_smi = Path("C:/Windows/System32/nvidia-smi.exe")
            if cand_smi.is_file():
                smi_bin = cand_smi

        gpu_name = None
        driver_ver = None
        smi_ok = False
        if smi_bin:
            smi_res = runner.run_command([str(smi_bin), "--query-gpu=gpu_name,driver_version", "--format=csv,noheader"])
            if smi_res.ok and smi_res.stdout.strip():
                smi_ok = True
                parts = smi_res.stdout.strip().splitlines()[0].split(",")
                if len(parts) >= 2:
                    gpu_name = parts[0].strip()
                    driver_ver = parts[1].strip()

        # If neither nvcc nor nvidia-smi is found, not installed
        if not nvcc_bin and not smi_ok:
            return ToolReport(
                id=self.id,
                name=self.name,
                category=self.category,
                categories=self.categories,
                installed=False,
                status=HealthStatus.NOT_FOUND,
            )

        # Version probe for nvcc
        version = None
        if nvcc_bin:
            res = runner.run_command([str(nvcc_bin), "--version"])
            if res.ok and res.stdout.strip():
                # e.g. "Cuda compilation tools, release 12.6, V12.6.85"
                m = re.search(r"release\s+([\d\.]+)", res.stdout)
                version = m.group(1) if m else res.stdout.splitlines()[-1].strip()

        companions: List[CompanionTool] = []

        # Companion: nvidia-smi
        companions.append(
            CompanionTool(
                name="nvidia-smi",
                installed=smi_ok,
                version=f"Driver {driver_ver}" if driver_ver else ("Present" if smi_ok else None),
                binary_path=str(smi_bin) if smi_bin else None,
            )
        )

        # Companion: GPU Device
        if gpu_name:
            companions.append(
                CompanionTool(
                    name="gpu",
                    installed=True,
                    version=gpu_name,
                )
            )

        diagnostics: List[DiagnosticIssue] = []

        if smi_ok and not nvcc_bin:
            diagnostics.append(
                DiagnosticIssue(
                    level=DiagnosticLevel.INFO,
                    message="NVIDIA GPU is detected, but CUDA Compiler (nvcc) is not installed. Deep learning frameworks like PyTorch or JAX require CUDA Toolkit for native compiling.",
                    suggested_fix="Install NVIDIA CUDA Toolkit from https://developer.nvidia.com/cuda-downloads",
                )
            )

        is_on_path = runner.resolve_binary("nvcc") is not None
        if nvcc_bin and not is_on_path and cuda_dir:
            diagnostics.append(
                DiagnosticIssue(
                    level=DiagnosticLevel.WARNING,
                    message="CUDA Toolkit is installed, but nvcc compiler is not in your system PATH.",
                    suggested_fix=f'Add "{cuda_dir / "bin"}" to your PATH environment variable.',
                )
            )

        status = HealthStatus.HEALTHY if nvcc_bin else HealthStatus.WARNING

        home_dir = str(cuda_dir) if cuda_dir else (str(nvcc_bin.parent.parent) if nvcc_bin else None)

        return ToolReport(
            id=self.id,
            name=self.name,
            category=self.category,
            categories=self.categories,
            installed=True,
            version=version or (f"Driver {driver_ver}" if driver_ver else None),
            binary_path=str(nvcc_bin) if nvcc_bin else (str(smi_bin) if smi_bin else None),
            home_path=home_dir,
            status=status,
            companions=companions,
            diagnostics=diagnostics,
            metadata={"gpu_name": gpu_name, "driver_version": driver_ver, "nvcc_installed": nvcc_bin is not None},
        )

    def deep_inspect(self, runner: SafeRunner, base_report: Optional[ToolReport] = None) -> DeepTelemetryReport:
        if base_report is None:
            base_report = self.inspect(runner)
        from datetime import datetime
        raw_dumps = {}
        trace = ["Starting NVIDIA CUDA Toolkit deep inspection probe"]
        instances: List[DiscoveredInstance] = []
        env_vars: List[EnvVarStatus] = []
        detailed_diag: List[DiagnosticIssue] = list(base_report.diagnostics)
        remediations: List[str] = []

        seen_bins = set()

        # Primary resolved binary (nvcc or nvidia-smi)
        if base_report.binary_path:
            p_bin = Path(base_report.binary_path)
            seen_bins.add(str(p_bin).lower())
            instances.append(
                DiscoveredInstance(
                    path=base_report.home_path or str(p_bin.parent),
                    binary_path=str(p_bin),
                    version=base_report.version,
                    source="Active PATH",
                    is_active=True,
                    details=f"Active CUDA/GPU executable ({p_bin.name})",
                )
            )

        # Multi-instance discovery across PATH for nvcc
        for bin_p in runner.resolve_all_binaries("nvcc"):
            if str(bin_p).lower() not in seen_bins:
                seen_bins.add(str(bin_p).lower())
                is_act = bool(base_report.binary_path and str(bin_p).lower() == str(base_report.binary_path).lower())
                ver_str = None
                res_v = runner.run_command([str(bin_p), "--version"], timeout=2.0)
                if res_v.ok and res_v.stdout:
                    m = re.search(r"release\s+([\d\.]+)", res_v.stdout)
                    ver_str = m.group(1) if m else None
                instances.append(
                    DiscoveredInstance(
                        path=str(bin_p.parent.parent),
                        binary_path=str(bin_p),
                        version=ver_str,
                        source="PATH (nvcc)",
                        is_active=is_act,
                        details="Alternate nvcc compiler found in PATH",
                    )
                )

        # Scan Windows standard CUDA versions directory
        if sys.platform == "win32":
            cuda_dir = Path("C:/Program Files/NVIDIA GPU Computing Toolkit/CUDA")
            if cuda_dir.is_dir():
                for v_dir in sorted(cuda_dir.iterdir(), reverse=True):
                    cand_nvcc = v_dir / "bin" / "nvcc.exe"
                    if cand_nvcc.is_file() and str(cand_nvcc).lower() not in seen_bins:
                        seen_bins.add(str(cand_nvcc).lower())
                        instances.append(
                            DiscoveredInstance(
                                path=str(v_dir),
                                binary_path=str(cand_nvcc),
                                version=v_dir.name.lstrip("v"),
                                source="Standard Installation",
                                is_active=False,
                                details=f"NVIDIA CUDA Toolkit {v_dir.name} installation",
                            )
                        )

        # Discovery Pipeline instances (Layer 2-4 Discovery)
        for disc_p in runner.discovery.discover_all_tool_instances(self.id):
            cand_bin = disc_p / "bin" / ("nvcc.exe" if sys.platform == "win32" else "nvcc")
            if not cand_bin.is_file():
                cand_bin = disc_p / ("nvcc.exe" if sys.platform == "win32" else "nvcc")
            b_target = cand_bin if cand_bin.is_file() else None
            k = str(b_target or disc_p).lower()
            if k not in seen_bins:
                seen_bins.add(k)
                instances.append(
                    DiscoveredInstance(
                        path=str(disc_p),
                        binary_path=str(b_target) if b_target else None,
                        version=None,
                        source="Discovery Pipeline",
                        is_active=bool(base_report.binary_path and b_target and str(b_target).lower() == str(base_report.binary_path).lower()),
                        details="Discovered CUDA Toolkit (Layer 2-4)",
                    )
                )

        trace.append(f"Discovered {len(instances)} CUDA Toolkit instances")

        # 2. Environment Variables Alignment
        cuda_path = runner.read_env("CUDA_PATH")
        target_root = base_report.home_path
        if cuda_path:
            is_match = bool(target_root and Path(cuda_path).resolve() == Path(target_root).resolve())
            env_vars.append(
                EnvVarStatus(
                    name="CUDA_PATH",
                    value=cuda_path,
                    status="aligned" if is_match else "divergent",
                    target_path=target_root,
                    message="Matches resolved CUDA Toolkit installation" if is_match else f"Points to '{cuda_path}' which differs from active '{target_root}'",
                )
            )
            if not is_match and target_root:
                remediations.append(f'setx CUDA_PATH "{target_root}"')
        else:
            env_vars.append(
                EnvVarStatus(
                    name="CUDA_PATH",
                    value=None,
                    status="missing",
                    target_path=target_root,
                    message="Unset. PyTorch, TensorFlow, and nvcc toolchains require CUDA_PATH.",
                )
            )
            if target_root:
                remediations.append(f'setx CUDA_PATH "{target_root}"')

        cuda_home = runner.read_env("CUDA_HOME")
        env_vars.append(
            EnvVarStatus(
                name="CUDA_HOME",
                value=cuda_home,
                status="aligned" if cuda_home else "missing",
                target_path=target_root,
                message="Points to CUDA root" if cuda_home else "Unset (PyTorch / C++ extensions fallback to CUDA_PATH)",
            )
        )

        # 3. CLI Telemetry Dumps
        nvcc_bin = runner.resolve_binary("nvcc")
        if nvcc_bin:
            res_nv = runner.run_command([str(nvcc_bin), "--version"], timeout=2.5)
            if res_nv.ok and res_nv.stdout:
                raw_dumps["nvcc --version"] = res_nv.stdout.strip()

        smi_bin = runner.resolve_binary("nvidia-smi")
        if not smi_bin and sys.platform == "win32":
            cand_smi = Path("C:/Windows/System32/nvidia-smi.exe")
            if cand_smi.is_file():
                smi_bin = cand_smi

        if smi_bin:
            res_smi = runner.run_command([str(smi_bin)], timeout=3.0)
            if res_smi.ok and res_smi.stdout:
                raw_dumps["nvidia-smi"] = res_smi.stdout.strip()

            res_q = runner.run_command(
                [str(smi_bin), "--query-gpu=name,driver_version,memory.total,compute_cap", "--format=csv"],
                timeout=2.0,
            )
            if res_q.ok and res_q.stdout:
                raw_dumps["GPU Hardware Telemetry (CSV)"] = res_q.stdout.strip()

        trace.append("Completed NVIDIA CUDA Toolkit deep telemetry probes")

        return DeepTelemetryReport(
            tool_id=self.id,
            timestamp=datetime.now().isoformat(),
            probe_latency_ms=0,
            instances=instances,
            env_vars=env_vars,
            telemetry={
                "gpu_name": base_report.metadata.get("gpu_name"),
                "driver_version": base_report.metadata.get("driver_version"),
                "nvcc_installed": base_report.metadata.get("nvcc_installed", False),
                "home_path": base_report.home_path,
            },
            raw_dumps=raw_dumps,
            detailed_diagnostics=detailed_diag,
            remediation_commands=remediations,
            discovery_trace=trace,
        )

