"""Port management and process termination API routes."""

from typing import List
from fastapi import APIRouter

from devtoolkit.modules.utilities.ports import PortInfo, PortKillResult, PortManager
from devtoolkit.server.models import KillPortRequest

router = APIRouter(prefix="/api", tags=["ports"])


@router.get("/ports", response_model=List[PortInfo])
def get_ports(dev_only: bool = False):
    pm = PortManager()
    return pm.list_ports(dev_only=dev_only)


@router.post("/ports/kill", response_model=PortKillResult)
def post_kill_port(req: KillPortRequest):
    pm = PortManager()
    return pm.kill_port(req.port, force=req.force)
