#Requires -Version 5.1
<#
.SYNOPSIS
  Initialize macro_maintainer SQLite (3 tables) via the official CLI.

.DESCRIPTION
  Creates or verifies schema for events, event_duplicates, maintenance_logs.
  Does not run raw SQL — delegates to:
    python -m event_maintainer.main init-db

  Optionally copies .env.example to .env when .env is missing.

.EXAMPLE
  .\scripts\init-db.ps1
.EXAMPLE
  .\scripts\init-db.ps1 -WorkspaceRoot "F:\path\to\macro_maintainer" -SkipEnvCopy
#>
[CmdletBinding()]
param(
    [string]$WorkspaceRoot = "",
    [switch]$SkipEnvCopy
)

$ErrorActionPreference = "Stop"

function Resolve-ProjectRoot {
    param([string]$Start)
    if ($Start) {
        return (Resolve-Path -LiteralPath $Start).Path
    }
    return (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..")).Path
}

function Find-PythonVenvActivate {
    param([string]$Root)
    foreach ($rel in @(".venv\Scripts\Activate.ps1", "venv\Scripts\Activate.ps1")) {
        $path = Join-Path $Root $rel
        if (Test-Path -LiteralPath $path) {
            return $path
        }
    }
    return $null
}

function Ensure-DotEnv {
    param([string]$Root)
    $envFile = Join-Path $Root ".env"
    $example = Join-Path $Root ".env.example"
    if (Test-Path -LiteralPath $envFile) {
        Write-Host ".env already exists: $envFile"
        return
    }
    if (-not (Test-Path -LiteralPath $example)) {
        Write-Warning ".env missing and .env.example not found; using defaults (EVENT_DB_PATH=./macro_maintainer.sqlite3)."
        return
    }
    Copy-Item -LiteralPath $example -Destination $envFile
    Write-Host "Created .env from .env.example — review EVENT_DB_PATH; enable Mem0 after pip install -e `".[mem0]`" and API keys."
}

function Invoke-MaintainerCli {
    param(
        [string]$Root,
        [string]$Subcommand
    )
    # Schema init does not need Mem0; .env.example defaults MEM0_ENABLED=true.
    $prevMem0 = $env:MEM0_ENABLED
    $env:MEM0_ENABLED = "false"
    Push-Location -LiteralPath $Root
    $prevEap = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    try {
        $lines = @(& python -m event_maintainer.main $Subcommand 2>&1)
        $code = $LASTEXITCODE
        if ($code -ne 0) {
            throw "event_maintainer.main $Subcommand failed (exit $code): $($lines -join [Environment]::NewLine)"
        }
        return ($lines | Out-String).Trim()
    } finally {
        $ErrorActionPreference = $prevEap
        Pop-Location
        if ($null -eq $prevMem0) {
            Remove-Item Env:MEM0_ENABLED -ErrorAction SilentlyContinue
        } else {
            $env:MEM0_ENABLED = $prevMem0
        }
    }
}

$Root = Resolve-ProjectRoot -Start $WorkspaceRoot
Write-Host "Project root: $Root"

if (-not $SkipEnvCopy) {
    Ensure-DotEnv -Root $Root
}

$venvActivate = Find-PythonVenvActivate -Root $Root
if ($venvActivate) {
    Write-Host "Activating venv: $venvActivate"
    . $venvActivate
} else {
    Write-Warning "No .venv found; using system Python. Run: python -m venv .venv; pip install -e `".[dev]`""
}

$python = Get-Command python -ErrorAction SilentlyContinue
if (-not $python) {
    throw "python not found on PATH. Create a venv and install: pip install -e `".[dev]`""
}

Write-Host "Running init-db..."
$initJson = Invoke-MaintainerCli -Root $Root -Subcommand "init-db"
Write-Host $initJson

Write-Host ""
Write-Host "db-status:"
$statusJson = Invoke-MaintainerCli -Root $Root -Subcommand "db-status"
Write-Host $statusJson

Write-Host ""
Write-Host "Done. Next: python -m event_maintainer.main category-audit"
