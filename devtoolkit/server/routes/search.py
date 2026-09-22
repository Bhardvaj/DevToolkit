"""Search Engine Telemetry and Manual Re-indexing API routes."""

from pathlib import Path
from typing import List, Optional
from fastapi import APIRouter, BackgroundTasks
from pydantic import BaseModel

from devtoolkit.core.config import load_config
from devtoolkit.core.search import get_search_engine

router = APIRouter(prefix="/api/search", tags=["search"])


class ReindexRequest(BaseModel):
    roots: Optional[List[str]] = None


@router.get("/status")
def get_search_status():
    """Return current search index telemetry, memory footprint, and process RAM."""
    engine = get_search_engine()
    return engine.get_telemetry()


@router.post("/reindex")
def trigger_reindex(req: Optional[ReindexRequest] = None):
    """Trigger an immediate re-index of monitored search roots and return updated telemetry."""
    engine = get_search_engine()

    raw_roots: List[str] = []
    if req and req.roots:
        raw_roots = req.roots
    else:
        config = load_config()
        raw_roots = getattr(config, "search_paths", []) or []

    # If no search roots configured, check common developer directories
    if not raw_roots:
        common_candidates = [Path("D:/Dev"), Path("C:/Dev"), Path.cwd()]
        raw_roots = [str(c) for c in common_candidates if c.exists() and c.is_dir()]

    target_paths = [Path(r).expanduser().resolve() for r in raw_roots if Path(r).exists() and Path(r).is_dir()]

    # Clear previous index and re-index
    engine.clear()
    if target_paths:
        engine.index_roots(target_paths)

    return engine.get_telemetry()

