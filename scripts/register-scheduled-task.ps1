#Requires -Version 5.1
<#
.SYNOPSIS
  Register or remove Windows Scheduled Task for unattended database maintenance.

.EXAMPLE
  .\scripts\register-scheduled-task.ps1
  .\scripts\register-scheduled-task.ps1 -At "09:30"
  .\scripts\register-scheduled-task.ps1 -EveryMinutes 10
  .\scripts\register-scheduled-task.ps1 -Unregister
  .\scripts\register-scheduled-task.ps1 -IgnoreSettings -EveryMinutes 10
#>
[CmdletBinding()]
param(
    [string]$TaskName = "",
    [string]$At = "",
    [int]$EveryMinutes = -1,
    [switch]$Unregister,
    [switch]$IgnoreSettings,
    [string]$WorkspaceRoot = ""
)

$ErrorActionPreference = "Stop"

function Read-UnattendedConfig {
    param([string]$Root)
    $cfg = [ordered]@{
        enabled       = $false
        task_name     = "MacroMaintainer-UpdateDatabase"
        daily_at      = "08:00"
        every_minutes = 0
    }
    $path = Join-Path $Root "settings.json"
    if (-not (Test-Path -LiteralPath $path)) { return $cfg }
    try {
        $json = Get-Content -LiteralPath $path -Raw -Encoding UTF8 | ConvertFrom-Json
        if ($json.unattended) {
            if ($null -ne $json.unattended.enabled) {
                $cfg.enabled = [bool]$json.unattended.enabled
            }
            if ($json.unattended.task_name) { $cfg.task_name = [string]$json.unattended.task_name }
            if ($json.unattended.daily_at) { $cfg.daily_at = [string]$json.unattended.daily_at }
            if ($null -ne $json.unattended.every_minutes) {
                $cfg.every_minutes = [int]$json.unattended.every_minutes
            }
        }
    } catch {
        Write-Warning "Could not parse settings.json: $_"
    }
    return $cfg
}

$Root = if ($WorkspaceRoot) {
    (Resolve-Path -LiteralPath $WorkspaceRoot).Path
} else {
    (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..")).Path
}

$Cfg = Read-UnattendedConfig -Root $Root
if (-not $TaskName) { $TaskName = $Cfg.task_name }
if (-not $At) { $At = $Cfg.daily_at }
if ($EveryMinutes -lt 0) { $EveryMinutes = $Cfg.every_minutes }

$RunScript = Join-Path $PSScriptRoot "run-maintain-agent.ps1"
if (-not (Test-Path -LiteralPath $RunScript)) {
    throw "Missing run script: $RunScript"
}

if ($Unregister) {
    $existing = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
    if ($existing) {
        Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
        Write-Host "Unregistered scheduled task: $TaskName"
    } else {
        Write-Host "Task not found: $TaskName"
    }
    exit 0
}

if (-not $IgnoreSettings -and -not $Cfg.enabled) {
    $existing = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
    if ($existing) {
        Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
        Write-Host "Removed scheduled task: $TaskName (settings.json unattended.enabled=false)"
    } else {
        Write-Host "Unattended disabled in settings.json; no task registered."
    }
    exit 0
}

$Action = New-ScheduledTaskAction `
    -Execute "powershell.exe" `
    -Argument "-NoProfile -ExecutionPolicy Bypass -File `"$RunScript`" -WorkspaceRoot `"$Root`" -Unattended" `
    -WorkingDirectory $Root

if ($EveryMinutes -gt 0) {
    $startAt = (Get-Date).AddMinutes(1)
    $Trigger = New-ScheduledTaskTrigger `
        -Once `
        -At $startAt `
        -RepetitionInterval (New-TimeSpan -Minutes $EveryMinutes) `
        -RepetitionDuration (New-TimeSpan -Days 3650)
    $timeLimitMinutes = [Math]::Max($EveryMinutes - 1, 1)
    $executionLimit = New-TimeSpan -Minutes $timeLimitMinutes
    $multipleInstances = "IgnoreNew"
} else {
    $Trigger = New-ScheduledTaskTrigger -Daily -At $At
    $executionLimit = New-TimeSpan -Hours 3
    $multipleInstances = "Queue"
}

$Settings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -StartWhenAvailable `
    -ExecutionTimeLimit $executionLimit `
    -MultipleInstances $multipleInstances `
    -RestartCount 1 `
    -RestartInterval (New-TimeSpan -Minutes 30)

$Principal = New-ScheduledTaskPrincipal -UserId $env:USERNAME -LogonType Interactive -RunLevel Limited

Register-ScheduledTask `
    -TaskName $TaskName `
    -Action $Action `
    -Trigger $Trigger `
    -Settings $Settings `
    -Principal $Principal `
    -Description "Unattended macro_maintainer: Cursor Agent runs update-database maintenance." `
    -Force | Out-Null

Write-Host "Registered scheduled task: $TaskName"
if ($EveryMinutes -gt 0) {
    Write-Host "  Repeat:   every $EveryMinutes minute(s) (from ~1 min after registration)"
    Write-Host "  Overlap:  IgnoreNew (skip if previous run still active)"
    Write-Host "  Limit:    $timeLimitMinutes min per run"
} else {
    Write-Host "  Daily at: $At"
}
Write-Host "  Script:   $RunScript"
Write-Host "  Root:     $Root"
Write-Host ""
Write-Host "Test: Get-ScheduledTask -TaskName '$TaskName' | Start-ScheduledTask"
