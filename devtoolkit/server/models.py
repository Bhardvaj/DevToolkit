"""Pydantic request and response models for DevToolkit local API server."""

from typing import List, Optional
from pydantic import BaseModel


class OpenFolderRequest(BaseModel):
    path: str


class SearchPathRequest(BaseModel):
    path: Optional[str] = None
    index: Optional[int] = None


class AuditRequest(BaseModel):
    categories: Optional[List[str]] = None
    tool_ids: Optional[List[str]] = None


class KillPortRequest(BaseModel):
    port: int
    force: bool = False


class ProjectAuditRequest(BaseModel):
    path: str


class SelectFolderRequest(BaseModel):
    initial_path: Optional[str] = None


class ApplyFixRequest(BaseModel):
    command: str


class OpenFileRequest(BaseModel):
    path: str


class RevealFileRequest(BaseModel):
    path: str


class SearchQueryAPIRequest(BaseModel):
    query: str = ""
    case_sensitive: bool = False
    whole_word: bool = False
    match_path: bool = False
    is_regex: bool = False
    category: str = "all"
    scope: str = "all"
    size_filter: str = "any"
    date_filter: str = "any"
    ext_filter: str = ""
    sort_by: str = "relevance"
    sort_desc: bool = False
    limit: int = 500
    offset: int = 0

