param([switch]$Status,[switch]$CheckOnly)
$ErrorActionPreference='Stop'
$project=Split-Path (Split-Path $PSScriptRoot -Parent) -Parent
$python=Join-Path $project '.venv-skindetect-recovery-20261023\Scripts\python.exe'
$runner=Join-Path $PSScriptRoot 'run_v2_scale512.py'
$root=Join-Path $project '資料治理與泛化修復\results\v2_scale512_seed1_20261025_v1'
if($Status){& $python -B -X utf8 $runner --status;return}
if($CheckOnly){& $python -B -X utf8 $runner --check-only;if($LASTEXITCODE){throw 'Scale startup check failed'};return}
if(Test-Path -LiteralPath (Join-Path $root 'state.json')){throw 'Already initialized: use -Status, no automatic retry or Resume'}
if(Test-Path -LiteralPath (Join-Path $root 'STOP')){throw 'STOP must be preserved; no launch'}
$once=[System.IO.File]::Open((Join-Path $root '.controller_launch_once'),[System.IO.FileMode]::CreateNew,[System.IO.FileAccess]::Write,[System.IO.FileShare]::Read)
$once.Dispose()
$stamp=Get-Date -Format 'yyyyMMdd_HHmmss_fff'
$arguments=@('-B','-u','-X','utf8',('"'+$runner+'"'))
$child=Start-Process -FilePath $python -ArgumentList $arguments -WorkingDirectory $project -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $root "controller_$stamp.stdout.log") -RedirectStandardError (Join-Path $root "controller_$stamp.stderr.log")
[ordered]@{at=(Get-Date -Format o);controller_launcher_pid=$child.Id;python=$python;arguments=$arguments;working_directory=$project;resume=$false;wall_clock_cap_seconds=$null}|ConvertTo-Json|Set-Content -LiteralPath (Join-Path $root "launch_$stamp.json") -Encoding utf8
$child|Select-Object Id,ProcessName
