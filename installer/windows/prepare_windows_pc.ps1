[CmdletBinding()]
param(
    [switch]$CheckOnly,
    [switch]$SkipPythonDeps,
    [switch]$SkipFrontendDeps
)

$ErrorActionPreference = "Stop"

function Write-Step {
    param([string]$Message)
    Write-Host ""
    Write-Host "▶ $Message"
}

function Get-BootstrapPython {
    $py = Get-Command py -ErrorAction SilentlyContinue
    if ($py) {
        return @{
            File = $py.Source
            Args = @("-3.12")
            Label = "py -3.12"
        }
    }

    $python = Get-Command python -ErrorAction SilentlyContinue
    if ($python) {
        return @{
            File = $python.Source
            Args = @()
            Label = $python.Source
        }
    }

    throw "Python was not found. Install Python 3.12, then retry."
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

    return $null
}

function Invoke-CheckedCommand {
    param(
        [Parameter(Mandatory = $true)]
        [string]$FilePath,
        [string[]]$Arguments = @(),
        [Parameter(Mandatory = $true)]
        [string]$FailureMessage
    )

    & $FilePath @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw $FailureMessage
    }
}

$RepoRoot = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
Set-Location $RepoRoot

$Version = (Get-Content (Join-Path $RepoRoot "VERSION") -Raw).Trim()
if (-not $Version) {
    throw "VERSION file is missing or empty."
}

$Node = Get-Command node -ErrorAction SilentlyContinue
if (-not $Node) {
    throw "Node.js was not found. Install Node.js LTS, then retry."
}

$Npm = Get-Command npm -ErrorAction SilentlyContinue
if (-not $Npm) {
    throw "npm was not found. Install Node.js LTS, then retry."
}

$BootstrapPython = Get-BootstrapPython

Write-Host "============================================================"
Write-Host "  BSIE Windows Machine Prep v$Version"
Write-Host "============================================================"
Write-Host "Repo:    $RepoRoot"
Write-Host "Python:  $($BootstrapPython.Label)"
Write-Host "Node:    $($Node.Source)"
Write-Host "npm:     $($Npm.Source)"

$InnoSetup = Get-InnoSetupCompiler
if ($InnoSetup) {
    Write-Host "ISCC:    $InnoSetup"
}
else {
    Write-Host "ISCC:    not found (release builds will need Inno Setup 6)"
}

if ($CheckOnly) {
    Write-Host ""
    Write-Host "Check-only mode complete."
    exit 0
}

$VenvPython = Join-Path $RepoRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $VenvPython)) {
    Write-Step "Creating .venv with Python 3.12"
    Invoke-CheckedCommand -FilePath $BootstrapPython.File -Arguments ($BootstrapPython.Args + @("-m", "venv", ".venv")) -FailureMessage "Failed to create .venv"
}
else {
    Write-Step "Using existing .venv"
}

Write-Step "Upgrading pip tooling"
Invoke-CheckedCommand -FilePath $VenvPython -Arguments @("-m", "pip", "install", "--upgrade", "pip", "setuptools", "wheel") -FailureMessage "Failed to upgrade pip tooling"

if (-not $SkipPythonDeps) {
    Write-Step "Installing Python dependencies"
    Invoke-CheckedCommand -FilePath $VenvPython -Arguments @("-m", "pip", "install", "-r", "requirements.txt") -FailureMessage "Failed to install Python requirements"
}
else {
    Write-Step "Skipping Python dependency install"
}

if (-not $SkipFrontendDeps) {
    Write-Step "Installing frontend dependencies"
    Push-Location (Join-Path $RepoRoot "frontend")
    try {
        Invoke-CheckedCommand -FilePath $Npm.Source -Arguments @("install") -FailureMessage "Failed to install frontend dependencies"
    }
    finally {
        Pop-Location
    }
}
else {
    Write-Step "Skipping frontend dependency install"
}

Write-Host ""
Write-Host "============================================================"
Write-Host "  Windows machine is ready for BSIE"
Write-Host "============================================================"
Write-Host "Next steps:"
Write-Host "  Dev backend : .\.venv\Scripts\python.exe app.py"
Write-Host "  Dev frontend: cd frontend; npm run dev"
Write-Host "  App URL     : http://localhost:6776"
Write-Host "  API URL     : http://localhost:8757/api"
Write-Host "  Release     : powershell -ExecutionPolicy Bypass -File installer/windows/build_release.ps1"
