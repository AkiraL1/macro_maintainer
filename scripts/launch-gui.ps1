#Requires -Version 5.1
<#
.SYNOPSIS
  Launch the Macro Maintainer CustomTkinter control panel.

.EXAMPLE
  .\scripts\launch-gui.ps1
#>
[CmdletBinding()]
param(
    [string]$WorkspaceRoot = ""
)

$ErrorActionPreference = "Stop"

function Resolve-ProjectRoot {
    param([string]$Start)
    if ($Start) {
        return (Resolve-Path -LiteralPath $Start).Path
    }
    return (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..")).Path
}

$Root = Resolve-ProjectRoot -Start $WorkspaceRoot
$activate = Join-Path $Root ".venv\Scripts\Activate.ps1"
if (Test-Path -LiteralPath $activate) {
    . $activate
}

Push-Location -LiteralPath $Root
try {
    python -m pip install -e ".[gui]" -q 2>$null | Out-Null
    python -m event_maintainer.gui
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
} finally {
    Pop-Location
}
