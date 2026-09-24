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


class DiscoveredInstance(BaseModel):
    """An individual discovered installation or binary of a tool on the workstation."""
    path: str
    binary_path: Optional[str] = None
    version: Optional[str] = None
    source: str = "PATH"  # "PATH" | "Registry" | "SearchRoot" | "IDE_Config" | "Default"
    is_active: bool = False
    details: Optional[str] = None


class EnvVarStatus(BaseModel):
    """Status of a monitored environment variable for a tool."""
    name: str
    value: Optional[str] = None
    status: str = "aligned"  # "aligned" | "divergent" | "missing"
    target_path: Optional[str] = None
    message: Optional[str] = None


class DeepTelemetryReport(BaseModel):
    """Asynchronous deep domain report generated on-demand when inspecting a tool."""
    tool_id: str
    timestamp: str
    probe_latency_ms: int = 0
    instances: List[DiscoveredInstance] = Field(default_factory=list)
    env_vars: List[EnvVarStatus] = Field(default_factory=list)
    telemetry: Dict[str, Any] = Field(default_factory=dict)
    raw_dumps: Dict[str, str] = Field(default_factory=dict)
    discovery_trace: List[str] = Field(default_factory=list)


class ToolReport(BaseModel):
    id: str
    name: str
    category: str = "general"
    categories: List[str] = Field(default_factory=list)
    installed: bool = False
    version: Optional[str] = None
    binary_path: Optional[str] = None
    home_path: Optional[str] = None
    status: HealthStatus = HealthStatus.NOT_FOUND
    companions: List[CompanionTool] = Field(default_factory=list)
    diagnostics: List[DiagnosticIssue] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)
    deep_report: Optional[DeepTelemetryReport] = None

    def model_post_init(self, __context: Any) -> None:
        if not self.categories and self.category:
            self.categories = [self.category]
        elif self.categories and not self.category:
            self.category = self.categories[0]


class SystemInfo(BaseModel):
    os_name: str
    os_release: str
    os_version: str
    arch: str
    hostname: str
    python_version: str
    app_version: str = ""
    uptime: Optional[str] = None
    path_count: Optional[int] = None
    git_user_name: Optional[str] = None
    git_user_email: Optional[str] = None
    ram_footprint_mb: Optional[int] = None


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
