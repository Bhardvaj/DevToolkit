"""System and Configuration API routes."""

from pathlib import Path
from fastapi import APIRouter, HTTPException, Request

from devtoolkit.core.config import (
    add_search_path,
    load_config,
    remove_search_path,
    remove_search_path_by_index,
    set_close_action,
)
from devtoolkit.core.runner import SafeRunner
from devtoolkit.server.models import CloseActionRequest, DaemonNotifyRequest, SearchPathRequest

router = APIRouter(prefix="/api", tags=["system"])



@router.get("/config")
def get_config():
    return load_config()


@router.post("/config/search-paths")
def post_search_path(req: SearchPathRequest):
    if not req.path:
        raise HTTPException(status_code=400, detail="Missing required 'path' parameter.")
    p = Path(req.path).expanduser().resolve()
    if not p.exists() or not p.is_dir():
        raise HTTPException(status_code=400, detail=f"Directory '{req.path}' does not exist on disk.")
    added = add_search_path(str(p))
    return {"status": "ok", "added": added, "config": load_config()}


@router.delete("/config/search-paths")
def delete_search_path(req: SearchPathRequest):
    removed = False
    if req.index is not None:
        removed = remove_search_path_by_index(req.index)
    if not removed and req.path:
        removed = remove_search_path(req.path)
    return {"status": "ok", "removed": removed, "config": load_config()}


@router.get("/system")
def get_system():
    return SafeRunner().get_system_info()


@router.get("/health")
def get_health():
    import os
    import time
    from devtoolkit import __version__

    return {
        "status": "ok",
        "app": "devtoolkit",
        "version": __version__,
        "pid": os.getpid(),
        "timestamp": time.time(),
    }


@router.post("/config/close-action")
def post_close_action(req: CloseActionRequest):
    updated = set_close_action(req.action)
    if not updated:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid close_action '{req.action}'. Expected 'ask', 'minimize', or 'exit'.",
        )
    return {"status": "ok", "action": req.action.lower(), "config": load_config()}


@router.post("/daemon/notify")
def post_daemon_notify(req: DaemonNotifyRequest, request: Request):
    tray = getattr(request.app.state, "tray", None)
    if tray and hasattr(tray, "show_notification"):
        delivered = tray.show_notification(title=req.title, message=req.message, icon_type=req.icon_type)
        return {"status": "ok", "delivered": bool(delivered)}
    return {"status": "ok", "delivered": False, "note": "Tray icon not active"}


@router.get("/daemon/activity")
def get_daemon_activity():
    """Return real-time activity and background task status of the daemon."""
    from devtoolkit.daemon.activity import get_activity_tracker

    return get_activity_tracker().get_status()



