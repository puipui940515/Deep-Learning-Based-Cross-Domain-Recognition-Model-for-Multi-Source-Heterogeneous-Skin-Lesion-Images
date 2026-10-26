param([switch]$Resume,[switch]$Status,[switch]$CheckOnly)
$ErrorActionPreference='Stop'
$project=Split-Path (Split-Path $PSScriptRoot -Parent) -Parent
$python=Join-Path $project '.venv-skindetect-recovery-20261023\Scripts\python.exe'
$runner=Join-Path $PSScriptRoot 'run_v2_alpha025.py'
$root=Join-Path $project '資料治理與泛化修復\results\v2_512_alpha025_20261024_v1'
if($Status){& $python -B -X utf8 $runner --status;return}
if($CheckOnly){& $python -B -X utf8 $runner --check-only;if($LASTEXITCODE){throw 'Preflight failed'};return}
if(-not (Test-Path -LiteralPath (Join-Path $root 'EXECUTION_GATE.json'))){throw 'New execution gate missing'}
$state=Join-Path $root 'state.json'
if(Test-Path -LiteralPath $state){
    $s=Get-Content -LiteralPath $state -Raw -Encoding UTF8|ConvertFrom-Json
    if($s.status -eq 'completed'){throw 'Already completed; no relaunch'}
    if($s.status -eq 'running'){throw 'Existing running state; inspect PID; never launch duplicate'}
    if($s.status -eq 'failed'){throw 'Failed state requires review, not automatic retry/Resume'}
    if(-not $Resume){throw 'Existing state requires explicitly applicable Resume'}
}
if(Test-Path -LiteralPath (Join-Path $root 'STOP')){throw 'STOP preserved; review reason before any Resume'}
$id=Get-Date -Format 'yyyyMMdd_HHmmss_fff'
$arguments=@('-B','-u','-X','utf8',('"'+$runner+'"'))
if($Resume){$arguments+='--resume'}
$child=Start-Process -FilePath $python -ArgumentList $arguments -WorkingDirectory $project -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $root "controller_$id.stdout.log") -RedirectStandardError (Join-Path $root "controller_$id.stderr.log")
[ordered]@{at=(Get-Date -Format o);controller_pid=$child.Id;python=$python;arguments=$arguments;working_directory=$project;resume=[bool]$Resume;wall_clock_cap_seconds=$null}|ConvertTo-Json|Set-Content -LiteralPath (Join-Path $root "launch_$id.json") -Encoding utf8
$child|Select-Object Id,ProcessName
