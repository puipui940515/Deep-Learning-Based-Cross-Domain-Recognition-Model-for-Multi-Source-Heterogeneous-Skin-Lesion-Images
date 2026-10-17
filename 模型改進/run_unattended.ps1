param(
    [string]$Python = 'C:\anaconda3\python.exe',
    [switch]$CheckOnly
)
$ErrorActionPreference = 'Stop'
$entry = Join-Path $PSScriptRoot 'queue\run_unattended.py'
if ($CheckOnly) {
    & $Python -X utf8 -u $entry --check-only
} else {
    & $Python -X utf8 -u $entry
}
if ($LASTEXITCODE -ne 0) { throw 'Queue stopped. Check the log; rerun the same command after resolving the error.' }
