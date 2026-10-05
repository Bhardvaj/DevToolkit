<#
.SYNOPSIS
    Builds the standalone DevToolkitSpotlight.exe client executable using PyInstaller.
.DESCRIPTION
    Packages the DevToolkit Spotlight command palette client into an independent,
    zero-daemon-bundled single-file portable Windows executable.
    Does NOT bundle fastapi, uvicorn, inspectors, or daemon code.
.NOTES
    Requires: pyinstaller in your active Python environment.
#>

[CmdletBinding()]
param(
    [string]$OutputDir = "dist",
    [string]$BinaryName = "DevToolkitSpotlight",
    [string]$PythonExe = ""
)

$ErrorActionPreference = "Stop"

Write-Host "=================================================" -ForegroundColor Cyan
Write-Host " DevToolkit Spotlight Distribution Builder        " -ForegroundColor Cyan
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
if (-not (Test-Path $DistPath)) {
    New-Item -ItemType Directory -Path $DistPath -Force | Out-Null
}

# Stop running instance if any to prevent file lock
Stop-Process -Name $BinaryName -Force -ErrorAction SilentlyContinue

$EntryScript = Join-Path $WorkspaceRoot "clients\spotlight\entry.py"
$IconPath = Join-Path $WorkspaceRoot "assets\devspotlight.ico"
$SpotlightUI = Join-Path $WorkspaceRoot "clients\spotlight\ui"

Write-Host "[3/4] Preparing build targets..." -ForegroundColor Green
Write-Host "      Entry Script : $EntryScript"
Write-Host "      UI Assets    : $SpotlightUI"
Write-Host "      Icon         : $IconPath"

# 4. Run PyInstaller
Write-Host "`n[4/4] Compiling $BinaryName.exe (Standalone zero-daemon client binary)..." -ForegroundColor Cyan

& $PythonExe -m PyInstaller `
    --noconfirm `
    --clean `
    --onefile `
    --windowed `
    --icon $IconPath `
    --add-data "$($SpotlightUI);clients/spotlight/ui" `
    --add-data "$($WorkspaceRoot)\assets;assets" `
    --name $BinaryName `
    --distpath $DistPath `
    --workpath (Join-Path $WorkspaceRoot "build_spotlight") `
    --specpath (Join-Path $WorkspaceRoot "build_spotlight") `
    --hidden-import "webview" `
    --hidden-import "webview.platforms" `
    --hidden-import "webview.platforms.winforms" `
    --hidden-import "webview.platforms.edgechromium" `
    --hidden-import "clr" `
    --hidden-import "clients.spotlight" `
    --hidden-import "clients.spotlight.hotkey" `
    --hidden-import "clients.spotlight.settings" `
    --hidden-import "clients.spotlight.tray" `
    --hidden-import "clients.spotlight.icons" `
    --hidden-import "clients.spotlight.window" `
    --hidden-import "clients.spotlight.dispatcher" `
    --hidden-import "clients.spotlight.modes.calc" `
    --hidden-import "clients.spotlight.modes.actions" `
    --hidden-import "clients.spotlight.modes.default" `
    --hidden-import "clients.spotlight.modes.guide" `
    --hidden-import "clients.spotlight.modes.ports" `
    --hidden-import "clients.spotlight.modes.tools" `
    --hidden-import "clients.spotlight.modes.project" `
    --hidden-import "clients.spotlight.modes.window_walker" `
    --hidden-import "clients.spotlight.matcher" `
    --hidden-import "devtoolkit.client" `
    --hidden-import "devtoolkit.client.api" `
    --exclude-module "uvicorn" `
    --exclude-module "fastapi" `
    --exclude-module "pydantic" `
    --exclude-module "devtoolkit.core" `
    --exclude-module "devtoolkit.server" `
    --exclude-module "devtoolkit.daemon" `
    --exclude-module "devtoolkit.modules" `
    --exclude-module "devtoolkit.modules.inspectors" `
    $EntryScript

if ($LASTEXITCODE -eq 0) {
    $TargetExe = Join-Path $DistPath "$BinaryName.exe"
    if (Test-Path $TargetExe) {
        $FileSize = (Get-Item $TargetExe).Length / 1MB
        Write-Host "`n=================================================" -ForegroundColor Green
        Write-Host " BUILD SUCCESSFUL!                               " -ForegroundColor Green
        Write-Host " Binary : $TargetExe" -ForegroundColor Green
        Write-Host " Size   : $([math]::Round($FileSize, 2)) MB" -ForegroundColor Green
        Write-Host "=================================================" -ForegroundColor Green
    } else {
        Write-Error "Build finished but $TargetExe was not found."
        exit 1
    }
} else {
    Write-Error "PyInstaller compilation failed with exit code $LASTEXITCODE."
    exit $LASTEXITCODE
}
