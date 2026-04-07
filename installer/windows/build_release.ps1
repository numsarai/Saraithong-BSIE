[CmdletBinding()]
param(
    [switch]$SkipFrontend,
    [int]$SmokePort = 8762,
    [string]$SmokeUserDataDir = ""
)

$ErrorActionPreference = "Stop"

function Invoke-CheckedCommand {
    param(
        [Parameter(Mandatory = $true)]
        [scriptblock]$Command,
        [Parameter(Mandatory = $true)]
        [string]$FailureMessage
    )

    & $Command
    if ($LASTEXITCODE -ne 0) {
        throw $FailureMessage
    }
}

function Get-InnoSetupCompiler {
    $isccCommand = Get-Command iscc -ErrorAction SilentlyContinue
    if ($isccCommand) {
        return $isccCommand.Source
    }

    $candidates = @(
        (Join-Path ${env:ProgramFiles(x86)} "Inno Setup 6\ISCC.exe"),
        (Join-Path $env:ProgramFiles "Inno Setup 6\ISCC.exe"),
        (Join-Path $env:LOCALAPPDATA "Programs\Inno Setup 6\ISCC.exe")
    ) | Where-Object { $_ }

    foreach ($candidate in $candidates) {
        if (Test-Path $candidate) {
            return $candidate
        }
    }

    throw "Inno Setup 6 (iscc) was not found in PATH or standard install locations."
}

$RepoRoot = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
Set-Location $RepoRoot

$VersionFile = Join-Path $RepoRoot "VERSION"
if (-not (Test-Path $VersionFile)) {
    throw "Missing VERSION file at $VersionFile"
}

$Version = (Get-Content $VersionFile -Raw).Trim()
if (-not $Version) {
    throw "VERSION file is empty"
}

$Python = Join-Path $RepoRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $Python)) {
    throw "Missing virtualenv Python at $Python"
}

$Iscc = Get-InnoSetupCompiler

if (-not $SmokeUserDataDir) {
    $SmokeUserDataDir = Join-Path $env:TEMP "bsie-smoke-$Version"
}

Write-Host "============================================================"
Write-Host "  BSIE Windows Release Build v$Version"
Write-Host "============================================================"

if (-not $SkipFrontend) {
    Write-Host ""
    Write-Host "▶ [1/5] Building React frontend..."
    Push-Location (Join-Path $RepoRoot "frontend")
    try {
        if (-not (Test-Path "node_modules")) {
            Invoke-CheckedCommand -Command { npm install } -FailureMessage "npm install failed"
        }
        Invoke-CheckedCommand -Command { npm run build } -FailureMessage "npm run build failed"
    }
    finally {
        Pop-Location
    }
}
else {
    Write-Host "▶ [1/5] Skipping React frontend build"
}

Write-Host ""
Write-Host "▶ [2/5] Installing Python dependencies..."
Invoke-CheckedCommand -Command { & $Python -m pip install -r requirements.txt --quiet } -FailureMessage "pip install failed"

Write-Host ""
Write-Host "▶ [3/5] Running PyInstaller..."
if (Test-Path "build") {
    Remove-Item "build" -Recurse -Force
}
if (Test-Path "dist") {
    Remove-Item "dist" -Recurse -Force
}
Invoke-CheckedCommand -Command { & $Python -m PyInstaller bsie.spec --noconfirm } -FailureMessage "PyInstaller build failed"

$BundleExe = Join-Path $RepoRoot "dist\BSIE\BSIE.exe"
if (-not (Test-Path $BundleExe)) {
    throw "Expected bundled executable not found at $BundleExe"
}

Write-Host ""
Write-Host "▶ [4/5] Smoke-testing bundled executable..."
Invoke-CheckedCommand -Command {
    & $Python scripts/smoke_bundle.py --target $BundleExe --port $SmokePort --user-data-dir $SmokeUserDataDir
} -FailureMessage "Packaged bundle smoke test failed"

Write-Host ""
Write-Host "▶ [5/5] Building Inno Setup installer..."
Invoke-CheckedCommand -Command { & $Iscc "/DMyAppVersion=$Version" "installer\windows\setup.iss" } -FailureMessage "Inno Setup build failed"

$InstallerPath = Join-Path $RepoRoot "dist\installer\BSIE-Setup-$Version-windows.exe"
if (-not (Test-Path $InstallerPath)) {
    throw "Expected installer not found at $InstallerPath"
}

Write-Host ""
Write-Host "============================================================"
Write-Host "  Windows release build complete"
Write-Host "  Bundle:    $BundleExe"
Write-Host "  Installer: $InstallerPath"
Write-Host "============================================================"
