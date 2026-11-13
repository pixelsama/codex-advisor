[CmdletBinding()]
param(
    [switch] $SessionOnly
)

$ErrorActionPreference = 'Stop'

$codexDirectory = if ($env:CODEX_HOME) {
    $env:CODEX_HOME
} else {
    Join-Path $env:USERPROFILE '.codex'
}
$pluginDirectory = Split-Path -Parent $PSScriptRoot
$manifest = Get-Content -Raw -LiteralPath (Join-Path $pluginDirectory '.codex-plugin\plugin.json') | ConvertFrom-Json
if ($manifest.name -ne 'codex-advisor' -or $manifest.version -notmatch '^\d+\.\d+\.\d+$') {
    throw 'This installer requires a released Codex Advisor plugin.'
}
$cache = Join-Path $codexDirectory 'plugins\cache\advisor-market\codex-advisor'
if (-not (Test-Path -LiteralPath $cache -PathType Container)) {
    throw 'Install codex-advisor@advisor-market in Codex first.'
}

& py -3 -c 'import sys; sys.exit(sys.version_info < (3, 10))'
if ($LASTEXITCODE -ne 0) {
    throw 'Python 3.10 or newer must be available through py -3.'
}

$binDirectory = Join-Path $env:USERPROFILE '.local\bin'
$commandFile = Join-Path $binDirectory 'codex-advisor.cmd'
$resolverFile = Join-Path $binDirectory 'codex-advisor-launcher.py'
$resolverSource = Join-Path $PSScriptRoot 'terminal-launcher.py'
if (-not (Test-Path -LiteralPath $resolverSource -PathType Leaf)) {
    throw 'The terminal launcher is missing from this plugin package.'
}
$launcher = @'
@echo off
setlocal EnableExtensions DisableDelayedExpansion
py -3 -X utf8 "%~dp0codex-advisor-launcher.py" %*
exit /b %ERRORLEVEL%
'@
$launcher = ($launcher -replace '\r?\n', "`r`n") + "`r`n"

New-Item -ItemType Directory -Path $binDirectory -Force | Out-Null
foreach ($destination in $commandFile, $resolverFile) {
    $existing = Get-Item -LiteralPath $destination -Force -ErrorAction SilentlyContinue
    if ($existing -and ($existing.PSIsContainer -or ($existing.Attributes -band [IO.FileAttributes]::ReparsePoint))) {
        throw "Refusing to replace a directory or linked file: $destination"
    }
}
if (Test-Path -LiteralPath $commandFile) {
    if ([IO.File]::ReadAllText($commandFile) -cne $launcher) {
        $backup = "$commandFile.$([DateTime]::Now.ToString('yyyyMMdd-HHmmss-fff')).bak"
        [IO.File]::Copy($commandFile, $backup, $false)
        Write-Output "Previous command backed up to $backup"
    }
}
Copy-Item -LiteralPath $resolverSource -Destination $resolverFile -Force
[IO.File]::WriteAllText($commandFile, $launcher, [Text.Encoding]::ASCII)

function Test-BinOnPath([string] $pathValue) {
    foreach ($entry in ($pathValue -split ';')) {
        $entry = [Environment]::ExpandEnvironmentVariables($entry.Trim().Trim('"'))
        if ($entry.TrimEnd('\', '/') -ieq $binDirectory) { return $true }
    }
    return $false
}

if (-not (Test-BinOnPath $env:Path)) {
    $env:Path = "$binDirectory;$env:Path"
}

Write-Output "Created $commandFile"
if (-not $SessionOnly) {
    $userPath = [Environment]::GetEnvironmentVariable('Path', 'User')
    if (-not (Test-BinOnPath $userPath)) {
        $updatedPath = if ($userPath) { $userPath.TrimEnd(';') + ';' + $binDirectory } else { $binDirectory }
        try {
            [Environment]::SetEnvironmentVariable('Path', $updatedPath, 'User')
        } catch {
            throw "Could not update the user PATH. Run this setup in your Windows PowerShell terminal, or run the launcher directly: $commandFile"
        }
    }
}
Write-Output 'Run codex-advisor status to verify, or codex-advisor to open the configuration page.'
