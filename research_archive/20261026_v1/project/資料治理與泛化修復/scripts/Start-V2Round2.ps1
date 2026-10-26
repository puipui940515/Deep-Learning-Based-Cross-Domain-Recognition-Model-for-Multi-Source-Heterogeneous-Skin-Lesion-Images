param([switch]$Resume)
$ErrorActionPreference='Stop'
$python='.venv-skindetect\Scripts\python.exe'
$taskName='SkinDetect_V2Round2_20261020_v1'
if($Resume){$taskName+='_resume_'+(Get-Date -Format 'yyyyMMdd_HHmmss')}
if(Get-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue){throw 'Existing task; refusing duplicate launch.'}
$root='資料治理與泛化修復\results\v2_optimization_round2_20261020_v1'
$script=Join-Path $PSScriptRoot 'run_v2_round2.py'
$precheck = & $python -B (Join-Path $PSScriptRoot 'preflight_v2_round2.py') --verify-only
if($LASTEXITCODE -ne 0){throw 'Formal runtime gate failed; no training launched.'}
$arguments='-B -u "'+$script+'"'
if($Resume){$arguments+=' --resume'}
$action=New-ScheduledTaskAction -Execute $python -Argument $arguments -WorkingDirectory 'D:\SkinDetect_base'
$principal=New-ScheduledTaskPrincipal -UserId ([System.Security.Principal.WindowsIdentity]::GetCurrent().Name) -LogonType Interactive -RunLevel Limited
$settings=New-ScheduledTaskSettingsSet -Hidden -ExecutionTimeLimit ([TimeSpan]::Zero) -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries
Register-ScheduledTask -TaskName $taskName -Action $action -Principal $principal -Settings $settings -Description 'Authorized two-candidate V2 ImageNet study; max 6 runs, 180 epochs, 25920 loop seconds; no recurring trigger.' | Out-Null
Start-ScheduledTask -TaskName $taskName
[ordered]@{task_name=$taskName;python=$python;arguments=$arguments;resume=[bool]$Resume;launched=(Get-Date -Format o);output_root=$root} | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $root ('launch_'+(Get-Date -Format 'yyyyMMdd_HHmmss')+'.json')) -Encoding utf8
Get-ScheduledTask -TaskName $taskName | Select-Object TaskName,State | ConvertTo-Json -Compress
