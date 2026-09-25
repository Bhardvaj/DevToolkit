<#
.SYNOPSIS
    Builds a standalone, zero-dependency DevToolkit.exe executable using PyInstaller.
.DESCRIPTION
    Packages DevToolkit CLI, local FastAPI server, embedded glassmorphic UI,
    and all 10 pluggable tool inspectors into a single portable binary.
.NOTES
    Requires: pyinstaller in your active Python environment.
#>

[CmdletBinding()]
param(
    [string]$OutputDir = "dist",
    [string]$BinaryName = "DevToolkit",
    [string]$PythonExe = ""
)

$ErrorActionPreference = "Stop"

Write-Host "=================================================" -ForegroundColor Cyan
Write-Host " DevToolkit Standalone Distribution Builder      " -ForegroundColor Cyan
Write-Host "=================================================" -ForegroundColor Cyan

# 1. Check Python and Virtual Environment
if (-not $PythonExe) {
    $VenvPython = Join-Path $PSScriptRoot "..\.venv\Scripts\python.exe"
    if (Test-Path $VenvPython) {
        $PythonExe = (Resolve-Path $VenvPython).Path
    } else {
        $SysPython = Get-Command python -ErrorAction SilentlyContinue
        if ($SysPython) {
            $PythonExe = $SysPython.Source
        }
    }
}

if (-not $PythonExe -or -not (Test-Path $PythonExe)) {
    Write-Error "Python executable not found. Please specify -PythonExe or activate your environment."
    exit 1
}

Write-Host "`n[1/4] Using Python: $PythonExe" -ForegroundColor Green

# 2. Check if PyInstaller is installed
$PyInstallerCheck = & $PythonExe -m pip show pyinstaller 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Warning "PyInstaller is not installed in the current environment."
    Write-Host "To install PyInstaller, run:" -ForegroundColor Yellow
    Write-Host "  $PythonExe -m pip install pyinstaller" -ForegroundColor White
    exit 1
}

Write-Host "[2/4] PyInstaller detected." -ForegroundColor Green

# 3. Prepare Build Directory
$WorkspaceRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Set-Location $WorkspaceRoot

$DistPath = Join-Path $WorkspaceRoot $OutputDir
if (Test-Path $DistPath) {
    Write-Host "[3/4] Cleaning previous dist directory: $DistPath" -ForegroundColor Yellow
}

# 4. Run PyInstaller
Write-Host "[4/4] Compiling $BinaryName.exe (Single-file portable binary)..." -ForegroundColor Cyan

$EntryScript = Join-Path $WorkspaceRoot "devtoolkit\cli\main.py"

& $PythonExe -m PyInstaller `
    --noconfirm `
    --clean `
    --onefile `
    --name $BinaryName `
    --distpath $DistPath `
    --workpath (Join-Path $WorkspaceRoot "build") `
    --specpath (Join-Path $WorkspaceRoot "build") `
    --hidden-import "uvicorn" `
    --hidden-import "uvicorn.logging" `
    --hidden-import "uvicorn.loops" `
    --hidden-import "uvicorn.loops.auto" `
    --hidden-import "uvicorn.protocols" `
    --hidden-import "uvicorn.protocols.http" `
    --hidden-import "uvicorn.protocols.http.auto" `
    --hidden-import "uvicorn.protocols.websockets" `
    --hidden-import "uvicorn.protocols.websockets.auto" `
    --hidden-import "uvicorn.lifespan" `
    --hidden-import "uvicorn.lifespan.on" `
    --hidden-import "fastapi" `
    --hidden-import "pydantic" `
    --hidden-import "rich" `
    --hidden-import "typer" `
    --hidden-import "pyyaml" `
    --hidden-import "devtoolkit" `
    --hidden-import "devtoolkit.core" `
    --hidden-import "devtoolkit.daemon" `
    --hidden-import "devtoolkit.client" `
    --hidden-import "devtoolkit.modules.inspectors" `
    --hidden-import "devtoolkit.modules.utilities" `
    --collect-submodules "devtoolkit" `
    --collect-data "devtoolkit" `
    --hidden-import "webview" `
    --hidden-import "webview.platforms" `
    --hidden-import "webview.platforms.winforms" `
    --hidden-import "webview.platforms.edgechromium" `
    $EntryScript


if ($LASTEXITCODE -eq 0) {
    $TargetExe = Join-Path $DistPath "$BinaryName.exe"
    if (Test-Path $TargetExe) {
        $SourceConfig = Join-Path $WorkspaceRoot "devtoolkit.config.yaml"
        if (Test-Path $SourceConfig) {
            Copy-Item -Path $SourceConfig -Destination (Join-Path $DistPath "devtoolkit.config.yaml") -Force
        }
        $Item = Get-Item $TargetExe
        $Size = [math]::Round($Item.Length / 1MB, 2)
        Write-Host "`n[+] SUCCESS: Standalone binary compiled successfully!" -ForegroundColor Green
        Write-Host "  Binary: $TargetExe" -ForegroundColor White
        Write-Host "  Size: $Size MB" -ForegroundColor White
    }
} else {
    Write-Error "Build failed with exit code $LASTEXITCODE."
}

