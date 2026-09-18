"""Aggregated API router for DevToolkit."""

from fastapi import APIRouter

from devtoolkit.server.routes.actions import router as actions_router
from devtoolkit.server.routes.audit import router as audit_router
from devtoolkit.server.routes.ports import router as ports_router
from devtoolkit.server.routes.project import router as project_router
from devtoolkit.server.routes.system import router as system_router

api_router = APIRouter()
api_router.include_router(system_router)
api_router.include_router(audit_router)
api_router.include_router(ports_router)
api_router.include_router(project_router)
api_router.include_router(actions_router)
