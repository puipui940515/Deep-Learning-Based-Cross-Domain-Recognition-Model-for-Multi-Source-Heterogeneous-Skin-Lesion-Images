param(
    [string]$Python = 'C:\anaconda3\python.exe',
    [ValidateSet('R0','R1','R2','R3','R4','R5','R6','L-PAD','L-BCN','L-HAM')]
    [string]$Run = 'R0',
    [switch]$ThreeSeeds
)
$ErrorActionPreference = 'Stop'
$trainer = Join-Path $PSScriptRoot 'scripts\train.py'
$seeds = @(17)
if ($ThreeSeeds) { $seeds = @(17, 42, 2026) }
foreach ($seed in $seeds) {
    Write-Host "CP005 $Run seed=$seed"
    & $Python -X utf8 -u $trainer --run $Run --seed $seed
    if ($LASTEXITCODE -ne 0) { throw "Stopped: $Run seed=$seed. Subsequent seeds were not started." }
}
