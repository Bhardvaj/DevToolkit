"""Pydantic data models for DevToolkit Daemon state and status."""

from typing import Any, Dict, Optional
from pydantic import BaseModel, Field


class DaemonState(BaseModel):
    """Persistent state record for active DevToolkit daemon process."""

    pid: int
    port: int = 4321
    host: str = "127.0.0.1"
    version: str = ""
    started_at: str = ""
    status: str = "running"


class DaemonStatusResponse(BaseModel):
    """Structured response model for daemon status queries."""

    running: bool
    pid: Optional[int] = None
    port: Optional[int] = None
    host: Optional[str] = None
    version: Optional[str] = None
    uptime_seconds: Optional[float] = None
    state_path: Optional[str] = None
    search_status: Optional[Dict[str, Any]] = None
    message: str = ""
