#Requires -Version 5.1

<#

.SYNOPSIS

  Run one unattended macro_maintainer session via Cursor Agent CLI (headless).



.DESCRIPTION

  Reads scripts/prompts/update-database.txt and invokes:

    agent -p --force --trust --approve-mcps --workspace <root> <prompt>

  Default: stream-json + human-readable log (tools, assistant, thinking blocks).

  Raw JSONL: scripts/logs/maintain-<timestamp>.jsonl



.PARAMETER PlainText

  Use legacy text output (less detail, no tool/thinking breakdown).



.PARAMETER AgentModel

  e.g. claude-4.6-sonnet-medium-thinking for explicit thinking model.



.EXAMPLE

  .\scripts\run-maintain-agent.ps1

  .\scripts\run-maintain-agent.ps1 -AgentModel claude-4.6-sonnet-medium-thinking

  .\scripts\run-maintain-agent.ps1 -PlainText

#>

[CmdletBinding()]

param(

    [string]$WorkspaceRoot = "",

    [string]$PromptFile = "",

    [switch]$SkipStatusCheck,

    [switch]$PlainText,

    [string]$AgentModel = "",

    [switch]$Unattended

)



$ErrorActionPreference = "Stop"

. (Join-Path $PSScriptRoot "lib\agent-stream-log.ps1")



function Resolve-ProjectRoot {

    param([string]$Start)

    if ($Start) {

        return (Resolve-Path -LiteralPath $Start).Path

    }

    return (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..")).Path

}



function Resolve-AgentCommand {

    foreach ($name in @("agent", "cursor-agent")) {

        $cmd = Get-Command $name -ErrorAction SilentlyContinue

        if ($cmd) {

            return $cmd

        }

    }

    return $null

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



function Write-LogLine {

    param([string]$Message, [string]$LogPath)

    Write-MaintainLogLine -Message $Message -LogPath $LogPath

}



$Root = Resolve-ProjectRoot -Start $WorkspaceRoot

if (-not $PromptFile) {

    $PromptFile = Join-Path $PSScriptRoot "prompts\update-database.txt"

}

if (-not (Test-Path -LiteralPath $PromptFile)) {

    throw "Prompt file not found: $PromptFile"

}



$LogDir = Join-Path $Root "scripts\logs"

$RuntimeDir = Join-Path $Root "scripts\.runtime"

New-Item -ItemType Directory -Force -Path $LogDir | Out-Null

New-Item -ItemType Directory -Force -Path $RuntimeDir | Out-Null



$Timestamp = Get-Date -Format "yyyyMMdd-HHmmss"

$LogPath = Join-Path $LogDir "maintain-$Timestamp.log"

$RawJsonlPath = Join-Path $LogDir "maintain-$Timestamp.jsonl"



Write-LogLine "Project root: $Root" $LogPath

Write-LogLine "Prompt file: $PromptFile" $LogPath

Write-LogLine "Log mode: $(if ($PlainText) { 'plain-text' } else { 'stream-json (verbose)' })" $LogPath

if ($AgentModel) {

    Write-LogLine "Agent model: $AgentModel" $LogPath

}

if (-not $PlainText) {

    Write-LogLine "Raw stream: $RawJsonlPath" $LogPath

}



$AgentCmd = Resolve-AgentCommand

if (-not $AgentCmd) {

    $msg = "Cursor Agent CLI not found. Install cursor-agent and ensure 'agent' is on PATH."

    Write-LogLine "ERROR: $msg" $LogPath

    exit 1

}

Write-LogLine "agent CLI: $($AgentCmd.Source)" $LogPath



if (-not $SkipStatusCheck) {

    Write-LogLine "Checking agent status..." $LogPath

    Push-Location -LiteralPath $Root

    try {

        & $AgentCmd.Name status 2>&1 | ForEach-Object {

            $s = $_.ToString()

            Write-Host $s

            Add-Content -LiteralPath $LogPath -Value $s -Encoding UTF8

        }

        if ($LASTEXITCODE -ne 0) {

            Write-LogLine "ERROR: agent status failed (exit $LASTEXITCODE). Run: agent login" $LogPath

            exit 1

        }

    } finally {

        Pop-Location

    }

    Write-LogLine "agent status OK" $LogPath

}



$venvActivate = Find-PythonVenvActivate -Root $Root

if ($venvActivate) {

    Write-LogLine "Activating venv: $venvActivate" $LogPath

    . $venvActivate

} else {

    Write-LogLine "No local venv found; using system Python on PATH" $LogPath

}



$PromptBody = Get-Content -LiteralPath $PromptFile -Raw -Encoding UTF8
$PromptRel = "scripts/prompts/update-database.txt"
# Short bootstrap avoids Cursor CLI truncating/redacting long -p payloads (stream shows "<prompt N chars>").
$Prompt = @"
Read and fully execute the maintenance workflow in $PromptRel ($($PromptBody.Length) chars).
Start by reading that file and .cursor/skills/maintain-events/SKILL.md, then follow every step.
"@

Write-LogLine "Starting agent (headless)..." $LogPath

Write-LogLine "Prompt file: $PromptFile ($($PromptBody.Length) chars); bootstrap $($Prompt.Length) chars" $LogPath



$agentArgs = @(

    "-p",

    "--force",

    "--trust",

    "--approve-mcps",

    "--workspace", $Root

)

if ($AgentModel) {

    $agentArgs += @("--model", $AgentModel)

}

if (-not $PlainText) {

    $agentArgs += @(

        "--output-format", "stream-json",

        "--stream-partial-output"

    )

}

$agentArgs += $Prompt



Push-Location -LiteralPath $Root

try {

    if ($PlainText) {

        & $AgentCmd.Name @agentArgs 2>&1 | ForEach-Object {

            $s = $_.ToString()

            Write-Host $s

            Add-Content -LiteralPath $LogPath -Value $s -Encoding UTF8

        }

        $exitCode = $LASTEXITCODE

    } else {
        $agentExePath = $AgentCmd.Source
        if (-not $agentExePath) { $agentExePath = $AgentCmd.Path }
        if (-not $agentExePath) { throw "Cannot resolve agent executable path." }
        New-Item -ItemType File -Force -Path $RawJsonlPath | Out-Null
        $exitCode = Invoke-AgentWithStreamLog -AgentExe $agentExePath -AgentArgs $agentArgs -LogPath $LogPath -RawJsonlPath $RawJsonlPath
    }

} catch {

    Write-LogLine "ERROR: agent threw: $_" $LogPath

    if (-not $Unattended) {

        Write-Host ""

        Read-Host "Press Enter to close"

    }

    exit 1

} finally {

    Pop-Location

}



if ($null -eq $exitCode) { $exitCode = 0 }

Write-LogLine "agent finished with exit code $exitCode" $LogPath

if (-not $Unattended -and $exitCode -ne 0) {

    Write-Host ""

    Write-Host "Failed. Log: $LogPath" -ForegroundColor Red

    Read-Host "Press Enter to close"

}

exit $exitCode

