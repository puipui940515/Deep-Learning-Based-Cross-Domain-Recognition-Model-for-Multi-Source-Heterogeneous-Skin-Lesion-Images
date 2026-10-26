param([switch]$Status,[switch]$CheckOnly)
$ErrorActionPreference='Stop'
$project=Split-Path (Split-Path $PSScriptRoot -Parent) -Parent
$python=Join-Path $project '.venv-skindetect-recovery-20261023\Scripts\python.exe'
$runner=Join-Path $PSScriptRoot 'run_v2_alpha025.py'
$revision='retry1_20261024_v1'
$root=Join-Path $project "資料治理與泛化修復\results\v2_512_alpha025_20261024_v1\executions\$revision"
$previous=$env:SKINDETECT_ALPHA025_EXECUTION
try {
    $env:SKINDETECT_ALPHA025_EXECUTION=$revision
    if($Status){& $python -B -X utf8 $runner --status;return}
    if($CheckOnly){& $python -B -X utf8 $runner --check-only;if($LASTEXITCODE){throw 'Original startup check failed'};return}
    if(-not (Test-Path -LiteralPath (Join-Path $root 'EXECUTION_GATE.json'))){throw 'Retry1 gate missing'}
    if(Test-Path -LiteralPath (Join-Path $root 'state.json')){throw 'This one-time retry was already initialized; use -Status. No fresh retry or Resume.'}
    if(Test-Path -LiteralPath (Join-Path $root 'STOP')){throw 'Retry1 STOP must be preserved; no launch'}
    $stamp=Get-Date -Format 'yyyyMMdd_HHmmss_fff'
    $arguments=@('-B','-u','-X','utf8',('"'+$runner+'"'))
    $child=Start-Process -FilePath $python -ArgumentList $arguments -WorkingDirectory $project -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $root "controller_$stamp.stdout.log") -RedirectStandardError (Join-Path $root "controller_$stamp.stderr.log")
    [ordered]@{at=(Get-Date -Format o);controller_launcher_pid=$child.Id;python=$python;arguments=$arguments;working_directory=$project;execution_revision=$revision;resume=$false;parent_failed_run_id='d87cb2eef21d47fc8a408aa16b70e641';wall_clock_cap_seconds=$null}|ConvertTo-Json|Set-Content -LiteralPath (Join-Path $root "launch_$stamp.json") -Encoding utf8
    $child|Select-Object Id,ProcessName
} finally {
    $env:SKINDETECT_ALPHA025_EXECUTION=$previous
}
