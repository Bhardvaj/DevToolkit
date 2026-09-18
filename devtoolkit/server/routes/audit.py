"""Environment audit and tools inspection API routes."""

import json
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from devtoolkit.core.models import AuditSummary, DeepTelemetryReport
from devtoolkit.core.registry import PluginRegistry
from devtoolkit.server.models import AuditRequest

router = APIRouter(prefix="/api", tags=["audit"])
registry = PluginRegistry()


@router.get("/audit", response_model=AuditSummary)
def get_audit():
    return registry.run_audit()


@router.get("/audit/stream")
def stream_audit():
    def event_generator():
        for item in registry.stream_audit():
            yield f"data: {json.dumps(item)}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/audit", response_model=AuditSummary)
def post_audit(req: AuditRequest):
    return registry.run_audit(categories=req.categories, tool_ids=req.tool_ids)


@router.get("/tools")
def get_tools():
    inspectors = registry.list_inspectors()
    return [
        {
            "id": i.id,
            "name": i.name,
            "category": i.category,
            "categories": getattr(i, "categories", [i.category]),
            "description": i.description,
        }
        for i in inspectors
    ]


@router.get("/tool/{tool_id}/deep", response_model=DeepTelemetryReport)
def get_tool_deep(tool_id: str):
    report = registry.run_deep_inspection(tool_id)
    if not report:
        raise HTTPException(status_code=404, detail=f"Tool '{tool_id}' not found")
    return report
