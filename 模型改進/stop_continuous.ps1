$ErrorActionPreference = 'Stop'
$folder = Join-Path $PSScriptRoot 'results\continuous'
New-Item -ItemType Directory -Force -Path $folder | Out-Null
New-Item -ItemType File -Force -Path (Join-Path $folder 'STOP') | Out-Null
Write-Host 'Stop requested. Training stops after the epoch checkpoint; preparation stops after the current stage.'
