"""Project readiness auditor API routes."""

from pathlib import Path
from fastapi import APIRouter

from devtoolkit.modules.utilities.project_auditor import ProjectAuditReport, ProjectAuditor
from devtoolkit.server.models import ProjectAuditRequest

router = APIRouter(prefix="/api", tags=["project"])


@router.post("/project/audit", response_model=ProjectAuditReport)
def post_audit_project(req: ProjectAuditRequest):
    auditor = ProjectAuditor()
    return auditor.audit_project(Path(req.path))
