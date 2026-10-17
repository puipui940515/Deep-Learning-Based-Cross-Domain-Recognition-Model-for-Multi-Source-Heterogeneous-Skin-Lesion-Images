param([string]$Python = 'C:\anaconda3\python.exe', [switch]$CheckOnly)
$ErrorActionPreference = 'Stop'
$entry = Join-Path $PSScriptRoot 'queue\run_continuous.py'
if ($CheckOnly) { & $Python -X utf8 -u $entry --check-only }
else { & $Python -X utf8 -u $entry }
if ($LASTEXITCODE -ne 0) { throw 'Queue stopped. Inspect results/continuous/required_nf2_v2 logs. NF2 is required, never silently skipped.' }
