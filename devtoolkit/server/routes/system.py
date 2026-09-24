"""System and Configuration API routes."""

from pathlib import Path
from fastapi import APIRouter, HTTPException

from devtoolkit.core.config import add_search_path, load_config, remove_search_path, remove_search_path_by_index
from devtoolkit.core.runner import SafeRunner
from devtoolkit.server.models import SearchPathRequest

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

