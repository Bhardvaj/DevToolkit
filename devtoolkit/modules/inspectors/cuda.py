"""NVIDIA CUDA Toolkit & GPU Accelerator Inspector."""

import os
import re
import sys
from pathlib import Path
from typing import List

from devtoolkit.core.base import BaseInspector
from devtoolkit.core.models import (
    CompanionTool,
    DiagnosticIssue,
    DiagnosticLevel,
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
        nvcc_bin = runner.resolve_binary("nvcc")
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
