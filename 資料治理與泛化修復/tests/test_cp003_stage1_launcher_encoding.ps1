$ErrorActionPreference = "Stop"

$Launcher = (Resolve-Path (Join-Path $PSScriptRoot "..\scripts\run_cp003_stage1.ps1")).Path
$Tokens = $null
$ParseErrors = $null
[System.Management.Automation.Language.Parser]::ParseFile(
    $Launcher,
    [ref]$Tokens,
    [ref]$ParseErrors
) | Out-Null

if ($ParseErrors.Count -ne 0) {
    $Messages = ($ParseErrors | ForEach-Object { $_.Message }) -join " | "
    throw "Windows PowerShell parser rejected launcher: $Messages"
}

Write-Output "Windows PowerShell launcher parse OK"
