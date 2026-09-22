"""Workstation action handlers (file explorer, folder selector, environment fixes)."""

import os
import subprocess
import sys
from pathlib import Path
from typing import Optional
from fastapi import APIRouter, HTTPException

from devtoolkit.server.models import (
    ApplyFixRequest,
    OpenFileRequest,
    OpenFolderRequest,
    RevealFileRequest,
    SelectFolderRequest,
)

router = APIRouter(prefix="/api", tags=["actions"])


@router.post("/action/open-file")
def open_file(req: OpenFileRequest):
    """Launch file using default system file association."""
    raw_path = req.path.strip().strip('"').strip("'")
    p = Path(raw_path)
    if not p.exists():
        raise HTTPException(status_code=404, detail=f"File '{raw_path}' does not exist.")

    if sys.platform == "win32":
        try:
            os.startfile(str(p))
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to open file: {e}")
    elif sys.platform == "darwin":
        subprocess.run(["open", str(p)])
    else:
        subprocess.run(["xdg-open", str(p)])

    return {"status": "ok", "opened": str(p)}


@router.post("/action/reveal-file")
def reveal_file(req: RevealFileRequest):
    """Highlight file in Windows Explorer or native file manager."""
    raw_path = req.path.strip().strip('"').strip("'")
    p = Path(raw_path)
    if not p.exists():
        raise HTTPException(status_code=404, detail=f"Path '{raw_path}' does not exist.")

    if sys.platform == "win32":
        subprocess.run(["explorer.exe", f"/select,{str(p.resolve())}"])
    elif sys.platform == "darwin":
        subprocess.run(["open", "-R", str(p)])
    else:
        subprocess.run(["xdg-open", str(p.parent)])

    return {"status": "ok", "revealed": str(p)}


@router.post("/action/open-folder")
def open_folder(req: OpenFolderRequest):
    raw_path = req.path.strip().strip('"').strip("'")
    p = Path(raw_path)
    if not p.exists():
        raise HTTPException(status_code=404, detail=f"Path '{raw_path}' does not exist on disk.")

    target = str(p if p.is_dir() else p.parent)
    if sys.platform == "win32":
        try:
            os.startfile(target)
        except Exception:
            subprocess.run(["explorer.exe", target])
    elif sys.platform == "darwin":
        subprocess.run(["open", target])
    else:
        subprocess.run(["xdg-open", target])

    return {"status": "ok", "opened": target}


@router.post("/action/select-folder")
def post_select_folder(req: Optional[SelectFolderRequest] = None):
    initial = (req.initial_path or "").strip().strip('"').strip("'") if req else ""
    if initial == ".":
        initial = str(Path(".").resolve())

    if sys.platform == "win32":
        try:
            clean_initial = initial.replace("'", "''")
            ps_script = f"""
Add-Type -AssemblyName System.Windows.Forms
$dialog = New-Object System.Windows.Forms.FolderBrowserDialog
$dialog.Description = 'Select project folder for DevToolkit'
$dialog.ShowNewFolderButton = $true
if ('{clean_initial}' -and (Test-Path '{clean_initial}')) {{
    $dialog.SelectedPath = '{clean_initial}'
}}
$form = New-Object System.Windows.Forms.Form
$form.TopMost = $true
if ($dialog.ShowDialog($form) -eq [System.Windows.Forms.DialogResult]::OK) {{
    [Console]::OutputEncoding = [System.Text.Encoding]::UTF8
    Write-Output $dialog.SelectedPath
}}
"""
            res = subprocess.run(
                ["powershell", "-NoProfile", "-WindowStyle", "Hidden", "-Command", ps_script],
                capture_output=True,
                text=True,
                timeout=60,
                creationflags=0x08000000,
            )
            selected = res.stdout.strip()
            if selected:
                return {"status": "ok", "path": str(Path(selected).resolve())}
            return {"status": "cancelled", "path": None}
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
    elif sys.platform == "darwin":
        try:
            cmd = ["osascript", "-e", 'POSIX path of (choose folder with prompt "Select project folder")']
            res = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
            selected = res.stdout.strip()
            if selected:
                return {"status": "ok", "path": str(Path(selected).resolve())}
            return {"status": "cancelled", "path": None}
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
    else:
        for prog in [["zenity", "--file-selection", "--directory", "--title=Select project folder"], ["kdialog", "--getexistingdirectory"]]:
            try:
                res = subprocess.run(prog, capture_output=True, text=True, timeout=60)
                selected = res.stdout.strip()
                if selected:
                    return {"status": "ok", "path": str(Path(selected).resolve())}
            except Exception:
                continue
        return {"status": "cancelled", "path": None}


@router.post("/action/apply-fix")
def post_apply_fix(req: ApplyFixRequest):
    cmd_str = req.command.strip()
    if not cmd_str:
        raise HTTPException(status_code=400, detail="Empty command")

    # Safe guard: only automatically execute setx on Windows
    if sys.platform == "win32" and cmd_str.lower().startswith("setx "):
        import shlex
        try:
            parts = shlex.split(cmd_str)
            res = SafeRunner().run_command(parts, timeout=3.0)
            if res.ok:
                return {"status": "ok", "message": f"Applied fix successfully: {cmd_str}"}
            else:
                return {"status": "error", "message": res.stderr or "Command failed"}
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    return {"status": "info", "message": f"Command copied. Execute in terminal: {cmd_str}"}
