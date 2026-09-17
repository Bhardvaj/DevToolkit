"""Port Manager & Killer utility for developer workstations."""

import csv
import io
import re
import sys
from typing import Dict, List, Optional, Set
from pydantic import BaseModel

from devtoolkit.core.runner import SafeRunner

COMMON_DEV_PORTS: Set[int] = {
    3000, 3001, 3002, 4000, 4200, 5000, 5001, 5173, 5174,
    8000, 8080, 8081, 8888, 9000, 9001, 27017, 5432, 3306, 6379, 4321
}

CRITICAL_PROCESS_NAMES: Set[str] = {
    "system",
    "system idle process",
    "svchost.exe",
    "smss.exe",
    "csrss.exe",
    "wininit.exe",
    "services.exe",
    "lsass.exe",
    "explorer.exe",
    "spoolsv.exe",
}


class PortInfo(BaseModel):
    port: int
    protocol: str = "TCP"
    pid: int
    process_name: str
    address: str = "127.0.0.1"
    is_dev_port: bool = False
    is_system_critical: bool = False


class PortKillResult(BaseModel):
    success: bool
    port: int
    pid: int
    process_name: str
    message: str


class PortManager:
    """Discovers listening TCP sockets and safely manages lingering processes."""

    def __init__(self, runner: Optional[SafeRunner] = None):
        self.runner = runner or SafeRunner(default_timeout=3.0)

    def get_process_map(self) -> Dict[int, str]:
        """Map running PIDs to process names."""
        process_map: Dict[int, str] = {}
        if sys.platform == "win32":
            res = self.runner.run_command(["tasklist", "/FO", "CSV", "/NH"], timeout=3.0)
            if res.ok and res.stdout:
                try:
                    reader = csv.reader(io.StringIO(res.stdout))
                    for row in reader:
                        if len(row) >= 2:
                            name = row[0].strip()
                            try:
                                pid = int(row[1].strip())
                                process_map[pid] = name
                            except ValueError:
                                continue
                except Exception:
                    pass
        return process_map

    def list_ports(self, dev_only: bool = False) -> List[PortInfo]:
        """List all active listening TCP ports with process details."""
        ports: List[PortInfo] = []
        process_map = self.get_process_map()

        if sys.platform == "win32":
            res = self.runner.run_command(["netstat", "-ano", "-p", "tcp"], timeout=3.0)
            if res.ok and res.stdout:
                seen_keys = set()
                for line in res.stdout.splitlines():
                    line = line.strip()
                    if "LISTENING" not in line:
                        continue

                    # Pattern: TCP   127.0.0.1:4321   0.0.0.0:0   LISTENING   1234
                    parts = line.split()
                    if len(parts) >= 5:
                        proto = parts[0].upper()
                        local_addr = parts[1]
                        try:
                            pid = int(parts[-1])
                        except ValueError:
                            continue

                        # Extract port from local_addr (handle IPv4 and IPv6 [::]:port)
                        port = None
                        addr = local_addr
                        if ":" in local_addr:
                            addr_part, port_str = local_addr.rsplit(":", 1)
                            try:
                                port = int(port_str)
                                addr = addr_part.strip("[]")
                            except ValueError:
                                continue

                        if port is None:
                            continue

                        key = (port, pid)
                        if key in seen_keys:
                            continue
                        seen_keys.add(key)

                        p_name = process_map.get(pid, f"PID {pid}")
                        is_dev = port in COMMON_DEV_PORTS
                        is_crit = pid in (0, 4) or p_name.lower() in CRITICAL_PROCESS_NAMES

                        if dev_only and not is_dev:
                            continue

                        ports.append(
                            PortInfo(
                                port=port,
                                protocol=proto,
                                pid=pid,
                                process_name=p_name,
                                address=addr,
                                is_dev_port=is_dev,
                                is_system_critical=is_crit,
                            )
                        )
        else:
            # Unix / macOS fallback
            res = self.runner.run_command(["lsof", "-iTCP", "-sTCP:LISTEN", "-P", "-n"], timeout=3.0)
            if res.ok and res.stdout:
                seen_ports = set()
                for line in res.stdout.splitlines()[1:]:
                    parts = line.split()
                    if len(parts) >= 9:
                        p_name = parts[0]
                        try:
                            pid = int(parts[1])
                        except ValueError:
                            continue

                        endpoint = parts[8]
                        if ":" in endpoint:
                            port_str = endpoint.rsplit(":", 1)[1]
                            try:
                                port = int(port_str)
                            except ValueError:
                                continue

                            if port in seen_ports:
                                continue
                            seen_ports.add(port)

                            is_dev = port in COMMON_DEV_PORTS
                            is_crit = pid in (0, 1) or p_name.lower() in CRITICAL_PROCESS_NAMES

                            if dev_only and not is_dev:
                                continue

                            ports.append(
                                PortInfo(
                                    port=port,
                                    protocol="TCP",
                                    pid=pid,
                                    process_name=p_name,
                                    address="127.0.0.1",
                                    is_dev_port=is_dev,
                                    is_system_critical=is_crit,
                                )
                            )

        # Sort by dev ports first, then port number
        ports.sort(key=lambda p: (not p.is_dev_port, p.port))
        return ports

    def kill_port(self, target_port: int, force: bool = False) -> PortKillResult:
        """Kill the process occupying the specified port with safety checks."""
        active_ports = self.list_ports()
        matches = [p for p in active_ports if p.port == target_port]

        if not matches:
            return PortKillResult(
                success=False,
                port=target_port,
                pid=-1,
                process_name="Unknown",
                message=f"No active process found listening on port {target_port}.",
            )

        target = matches[0]

        if target.is_system_critical and not force:
            return PortKillResult(
                success=False,
                port=target_port,
                pid=target.pid,
                process_name=target.process_name,
                message=f"Refusing to kill system-critical process '{target.process_name}' (PID {target.pid}).",
            )

        if sys.platform == "win32":
            kill_res = self.runner.run_command(["taskkill", "/PID", str(target.pid), "/F"])
            if kill_res.ok:
                return PortKillResult(
                    success=True,
                    port=target_port,
                    pid=target.pid,
                    process_name=target.process_name,
                    message=f"Successfully terminated '{target.process_name}' (PID {target.pid}) on port {target_port}.",
                )
            else:
                return PortKillResult(
                    success=False,
                    port=target_port,
                    pid=target.pid,
                    process_name=target.process_name,
                    message=f"Failed to terminate process: {kill_res.stderr or kill_res.stdout}",
                )
        else:
            kill_res = self.runner.run_command(["kill", "-9", str(target.pid)])
            return PortKillResult(
                success=kill_res.ok,
                port=target_port,
                pid=target.pid,
                process_name=target.process_name,
                message=f"Terminated process {target.pid} on port {target_port}." if kill_res.ok else kill_res.stderr,
            )

