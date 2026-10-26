param([switch]$Resume, [string]$Python, [switch]$CheckOnly)
$ErrorActionPreference='Stop'
$project=Split-Path (Split-Path $PSScriptRoot -Parent) -Parent
if(-not $Python){$Python=Join-Path $project '.venv-skindetect-recovery-20261023\Scripts\python.exe'}
if(-not (Test-Path -LiteralPath $Python -PathType Leaf)){throw 'Selected Python executable not found.'}
$Python=(Resolve-Path -LiteralPath $Python).Path
if($Python.Contains('"')){throw 'Invalid Python path.'}
if($CheckOnly){
    $checker=Join-Path $project 'recovery_20261023\B_training\startup_repair_20261024_v1\check_startup.py'
    & $Python -B -I -X utf8 $checker --project $project --python $Python
    if($LASTEXITCODE -ne 0){throw 'CPU startup compatibility check failed.'}
    return
}
$root=Join-Path $project '資料治理與泛化修復\results\v2_resolution_20261021_v1'
$statePath=Join-Path $root 'state.json'
if(Test-Path -LiteralPath $statePath){
    $state=Get-Content -LiteralPath $statePath -Raw -Encoding UTF8 | ConvertFrom-Json
    if($state.status -eq 'completed'){throw 'Study completed. No launch, Resume or result refresh is permitted; use -CheckOnly for read-only preparation.'}
}
# The frozen historical runner/gate is not migrated or bypassed by this launcher.
$legacyPython=Join-Path $project '.venv-skindetect\Scripts\python.exe'
if($Python -ne $legacyPython){throw 'Historical runner requires its frozen runtime. Use -CheckOnly; a new study needs a separately approved versioned contract.'}
$taskName='SkinDetect_V2Resolution_20261020_v1'
if($Resume){$taskName+='_resume_'+(Get-Date -Format 'yyyyMMdd_HHmmss')}
if(Get-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue){throw 'Existing task; refusing duplicate launch.'}
$root='資料治理與泛化修復\results\v2_resolution_20261021_v1'
$script=Join-Path $PSScriptRoot 'run_v2_resolution.py'
$precheck = & $python -B (Join-Path $PSScriptRoot 'preflight_v2_resolution.py') --verify-only
if($LASTEXITCODE -ne 0){throw 'Formal runtime gate failed; no training launched.'}
$arguments='-B -u "'+$script+'"'
if($Resume){$arguments+=' --resume'}
$action=New-ScheduledTaskAction -Execute $python -Argument $arguments -WorkingDirectory 'D:\SkinDetect_base'
$principal=New-ScheduledTaskPrincipal -UserId ([System.Security.Principal.WindowsIdentity]::GetCurrent().Name) -LogonType Interactive -RunLevel Limited
$settings=New-ScheduledTaskSettingsSet -Hidden -ExecutionTimeLimit ([TimeSpan]::Zero) -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries
Register-ScheduledTask -TaskName $taskName -Action $action -Principal $principal -Settings $settings -Description 'Authorized 320/512 full three-seed study; 19440/42120 seconds; six runs; no score-based seed cancellation; one-shot task.' | Out-Null
Start-ScheduledTask -TaskName $taskName
[ordered]@{task_name=$taskName;python=$python;arguments=$arguments;resume=[bool]$Resume;launched=(Get-Date -Format o);output_root=$root} | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $root ('launch_'+(Get-Date -Format 'yyyyMMdd_HHmmss')+'.json')) -Encoding utf8
Get-ScheduledTask -TaskName $taskName | Select-Object TaskName,State | ConvertTo-Json -Compress
