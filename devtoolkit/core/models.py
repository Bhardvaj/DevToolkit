"""Pydantic data models representing audit results, tools, and system health."""

from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class HealthStatus(str, Enum):
    HEALTHY = "healthy"
    WARNING = "warning"
    ERROR = "error"
    NOT_FOUND = "not_found"


class DiagnosticLevel(str, Enum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"


class DiagnosticIssue(BaseModel):
    level: DiagnosticLevel
    message: str
    suggested_fix: Optional[str] = None


class CompanionTool(BaseModel):
    name: str
    installed: bool = False
    version: Optional[str] = None
    binary_path: Optional[str] = None


class ToolReport(BaseModel):
    id: str
    name: str
    category: str = "general"
    installed: bool = False
    version: Optional[str] = None
    binary_path: Optional[str] = None
    home_path: Optional[str] = None
    status: HealthStatus = HealthStatus.NOT_FOUND
    companions: List[CompanionTool] = Field(default_factory=list)
    diagnostics: List[DiagnosticIssue] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class SystemInfo(BaseModel):
    os_name: str
    os_release: str
    os_version: str
    arch: str
    hostname: str
    python_version: str


class AuditSummary(BaseModel):
    timestamp: str
    system: SystemInfo
    total_tools: int = 0
    installed_count: int = 0
    healthy_count: int = 0
    warning_count: int = 0
    error_count: int = 0
    not_found_count: int = 0
    reports: List[ToolReport] = Field(default_factory=list)

