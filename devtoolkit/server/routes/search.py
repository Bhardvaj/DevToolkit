"""Search Engine Telemetry and Manual Re-indexing API routes."""

from pathlib import Path
from typing import List, Optional
from fastapi import APIRouter, BackgroundTasks
from pydantic import BaseModel

from devtoolkit.core.config import load_config
from devtoolkit.core.search import SearchQueryParams, execute_search, get_search_engine
from devtoolkit.server.models import SearchQueryAPIRequest

router = APIRouter(prefix="/api/search", tags=["search"])


@router.post("/query")
def post_search_query(req: SearchQueryAPIRequest):
    """Execute Everything-class search query against in-memory index."""
    engine = get_search_engine()
    params = SearchQueryParams(
        query=req.query,
        case_sensitive=req.case_sensitive,
        whole_word=req.whole_word,
        match_path=req.match_path,
        is_regex=req.is_regex,
        category=req.category,
        scope=req.scope,
        size_filter=req.size_filter,
        date_filter=req.date_filter,
        ext_filter=req.ext_filter,
        sort_by=req.sort_by,
        sort_desc=req.sort_desc,
        limit=req.limit,
        offset=req.offset,
    )
    return execute_search(engine.index, params)


@router.get("/query")
def get_search_query(
    q: str = "",
    case: bool = False,
    whole_word: bool = False,
    match_path: bool = False,
    regex: bool = False,
    category: str = "all",
    scope: str = "all",
    size_filter: str = "any",
    date_filter: str = "any",
    ext_filter: str = "",
    sort_by: str = "relevance",
    sort_desc: bool = False,
    limit: int = 500,
    offset: int = 0,
):
    """GET variant of search query for lightweight url fetching."""
    engine = get_search_engine()
    params = SearchQueryParams(
        query=q,
        case_sensitive=case,
        whole_word=whole_word,
        match_path=match_path,
        is_regex=regex,
        category=category,
        scope=scope,
        size_filter=size_filter,
        date_filter=date_filter,
        ext_filter=ext_filter,
        sort_by=sort_by,
        sort_desc=sort_desc,
        limit=limit,
        offset=offset,
    )
    return execute_search(engine.index, params)



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
    if req and req.roots is not None:
        raw_roots = req.roots
    else:
        config = load_config()
        raw_roots = getattr(config, "search_paths", []) or []

    target_paths = [Path(r).expanduser().resolve() for r in raw_roots if Path(r).exists() and Path(r).is_dir()]

    # Clear previous index and re-index only if target paths exist
    engine.clear()
    if target_paths:
        engine.index_roots(target_paths)

    return engine.get_telemetry()

