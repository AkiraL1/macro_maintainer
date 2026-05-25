#Requires -Version 5.1
<#
  Parse Cursor Agent --output-format stream-json lines into human-readable log lines.
#>

function Write-MaintainLogLine {
    param([string]$Message, [string]$LogPath)
    $line = "[{0}] {1}" -f (Get-Date -Format "yyyy-MM-dd HH:mm:ss"), $Message
    Write-Host $line
    Add-Content -LiteralPath $LogPath -Value $line -Encoding UTF8
}

function Get-ShellCommandFromToolCall {
    param($ToolCall)
    if (-not $ToolCall) { return $null }
    if ($ToolCall.shellToolCall) {
        return $ToolCall.shellToolCall.args.command
    }
    if ($ToolCall.PSObject.Properties['shellToolCall']) {
        return $ToolCall.shellToolCall.args.command
    }
    return ($ToolCall | ConvertTo-Json -Compress -Depth 6)
}

function Format-AgentStreamEvent {
    param(
        [string]$JsonLine,
        [ref]$AssistantBuffer
    )
    if ([string]::IsNullOrWhiteSpace($JsonLine)) { return $null }
    try {
        $obj = $JsonLine | ConvertFrom-Json
    } catch {
        return "[RAW] $JsonLine"
    }

    switch ($obj.type) {
        'system' {
            $model = $obj.model
            $sid = $obj.session_id
            return "[AGENT] session=$sid model=$model cwd=$($obj.cwd)"
        }
        'user' {
            $text = ($obj.message.content | Where-Object { $_.type -eq 'text' } | ForEach-Object { $_.text }) -join ''
            if ($text.Length -gt 200) { $text = $text.Substring(0, 200) + '...' }
            return "[USER] $text"
        }
        'tool_call' {
            $cmd = Get-ShellCommandFromToolCall $obj.tool_call
            $sub = $obj.subtype
            if ($cmd) {
                return "[TOOL $sub] $cmd"
            }
            return "[TOOL $sub] $(Get-ShellCommandFromToolCall $obj.tool_call)"
        }
        'assistant' {
            $parts = @()
            foreach ($block in $obj.message.content) {
                if ($block.type -eq 'thinking' -and $block.text) {
                    $t = $block.text
                    if ($t.Length -gt 800) { $t = $t.Substring(0, 800) + '...' }
                    $parts += "[THINK] $t"
                } elseif ($block.type -eq 'text' -and $block.text) {
                    $null = $AssistantBuffer.Value.Append($block.text)
                }
            }
            if ($parts.Count -gt 0) { return ($parts -join "`n") }
            return $null
        }
        'result' {
            $lines = @()
            if ($AssistantBuffer.Value.Length -gt 0) {
                $body = $AssistantBuffer.Value.ToString()
                if ($body.Length -gt 4000) {
                    $body = $body.Substring(0, 4000) + '...'
                }
                $lines += "[ASSISTANT] $body"
                $null = $AssistantBuffer.Value.Clear()
            }
            $dur = $obj.duration_ms
            $sub = $obj.subtype
            $preview = $obj.result
            if ($preview -and $preview.Length -gt 500) {
                $preview = $preview.Substring(0, 500) + '...'
            }
            $lines += "[RESULT $sub] ${dur}ms $preview"
            return ($lines -join "`n")
        }
        default {
            return "[EVENT $($obj.type)] $JsonLine"
        }
    }
}

function Invoke-AgentWithStreamLog {
    param(
        [string]$AgentExe,
        [string[]]$AgentArgs,
        [string]$LogPath,
        [string]$RawJsonlPath
    )
    if (-not $AgentExe) { throw "AgentExe is required." }
    if (-not $LogPath) { throw "LogPath is required." }
    if (-not $RawJsonlPath) { throw "RawJsonlPath is required." }

    $assistantBuffer = New-Object System.Text.StringBuilder
    $displayArgs = @($AgentArgs)
    if ($displayArgs.Length -gt 0 -and $displayArgs[-1].Length -gt 120) {
        $displayArgs[-1] = "<prompt $($displayArgs[-1].Length) chars>"
    }
    $argStr = ($displayArgs | ForEach-Object {
        if ($_ -match '\s') { "`"$_`"" } else { $_ }
    }) -join ' '
    Write-MaintainLogLine "agent cmd: $AgentExe $argStr" $LogPath

    $prevEap = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'
    try {
        & $AgentExe @AgentArgs 2>&1 | ForEach-Object {
            $line = $_.ToString()
            if (-not $line.Trim()) { return }
            Add-Content -LiteralPath $RawJsonlPath -Value $line -Encoding UTF8
            $formatted = Format-AgentStreamEvent -JsonLine $line -AssistantBuffer ([ref]$assistantBuffer)
            if ($formatted) {
                foreach ($part in ($formatted -split "`n")) {
                    Write-MaintainLogLine $part $LogPath
                }
            }
        }
        return $LASTEXITCODE
    } finally {
        $ErrorActionPreference = $prevEap
    }
}
