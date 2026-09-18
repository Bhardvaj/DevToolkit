"""Pydantic request and response models for DevToolkit local API server."""

from typing import List, Optional
from pydantic import BaseModel


class OpenFolderRequest(BaseModel):
    path: str


class SearchPathRequest(BaseModel):
    path: str


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
