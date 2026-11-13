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
$relativeScript = 'plugins\cache\advisor-market\codex-advisor\{0}\scripts\advisorctl.py' -f $manifest.version
$advisorScript = Join-Path $codexDirectory $relativeScript
if (-not (Test-Path -LiteralPath $advisorScript -PathType Leaf)) {
    throw "Install Codex Advisor $($manifest.version) from advisor-market first."
}

& py -3 -c 'import sys; sys.exit(sys.version_info < (3, 10))'
if ($LASTEXITCODE -ne 0) {
    throw 'Python 3.10 or newer must be available through py -3.'
}

$binDirectory = Join-Path $env:USERPROFILE '.local\bin'
$commandFile = Join-Path $binDirectory 'codex-advisor.cmd'
$launcher = @'
@echo off
setlocal EnableExtensions DisableDelayedExpansion
set "ADVISOR_CODEX_DIR=%CODEX_HOME%"
if not defined ADVISOR_CODEX_DIR set "ADVISOR_CODEX_DIR=%USERPROFILE%\.codex"
set "ADVISOR_SCRIPT=%ADVISOR_CODEX_DIR%\@ADVISOR_SCRIPT@"
if not exist "%ADVISOR_SCRIPT%" (
    echo The configured Advisor version is missing. Run the terminal-command setup for your installed version. 1>&2
    exit /b 1
)
py -3 -X utf8 "%ADVISOR_SCRIPT%" %*
exit /b %ERRORLEVEL%
'@
$launcher = ($launcher -replace '\r?\n', "`r`n") + "`r`n"
$launcher = $launcher.Replace('@ADVISOR_SCRIPT@', $relativeScript)

New-Item -ItemType Directory -Path $binDirectory -Force | Out-Null
if (Test-Path -LiteralPath $commandFile) {
    if ((Get-Item -LiteralPath $commandFile).Attributes -band [IO.FileAttributes]::ReparsePoint) {
        throw "Refusing to replace a linked file: $commandFile"
    }
    if ([IO.File]::ReadAllText($commandFile) -cne $launcher) {
        $backup = "$commandFile.$([DateTime]::Now.ToString('yyyyMMdd-HHmmss-fff')).bak"
        [IO.File]::Copy($commandFile, $backup, $false)
        Write-Output "Previous command backed up to $backup"
    }
}
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
