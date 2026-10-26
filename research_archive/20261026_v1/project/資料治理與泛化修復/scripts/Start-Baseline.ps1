param([switch]$Resume)
$ErrorActionPreference = 'Stop'
$projectRoot = 'D:\SkinDetect_base'
$areaRoot = Join-Path $projectRoot '資料治理與泛化修復'
$configRoot = Join-Path $areaRoot 'configs\five_model_baseline_20261019_v1'
$jobRoot = Join-Path $areaRoot 'results\baseline_20261019_v1'
$python = Join-Path $projectRoot '.venv-skindetect\Scripts\python.exe'
$gate = Join-Path $configRoot 'ACCEPTANCE.json'
& $python -B (Join-Path $PSScriptRoot 'check_baseline_gate.py') --record $gate
if ($LASTEXITCODE -ne 0) { throw 'Baseline acceptance/fingerprint check failed; no task launched' }
$activeTrainers = @(Get-CimInstance Win32_Process -Filter "Name = 'python.exe'" | Where-Object {
    $_.CommandLine -like '*SkinDetect_base*train_regularized.py*'
})
if ($activeTrainers.Count -gt 0) { throw 'An existing SkinDetect trainer is running; refusing overlap' }
$taskName = 'SkinDetect_Baseline_20261019_v1'
if ($Resume) {
    if (-not (Test-Path -LiteralPath (Join-Path $jobRoot 'job.json'))) { throw 'No original job.json; refusing fresh restart' }
    if (Test-Path -LiteralPath (Join-Path $jobRoot 'STOP')) { throw 'Remove the job STOP file before explicit Resume' }
    $taskName += '_resume_' + (Get-Date -Format 'yyyyMMdd_HHmmss')
} elseif (Test-Path -LiteralPath $jobRoot) {
    throw 'Formal output already exists; use -Resume for the SAME experiment'
}
if (Get-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue) { throw 'Task already exists; refusing overwrite' }
$arguments = '-B -u "' + (Join-Path $PSScriptRoot 'baseline_job.py') + '" --suite "' + (Join-Path $configRoot 'suite.json') + '" --output-root "' + $jobRoot + '"'
if ($Resume) { $arguments += ' --resume' }
$action = New-ScheduledTaskAction -Execute $python -Argument $arguments -WorkingDirectory $projectRoot
$principal = New-ScheduledTaskPrincipal -UserId ([System.Security.Principal.WindowsIdentity]::GetCurrent().Name) -LogonType Interactive -RunLevel Limited
$settings = New-ScheduledTaskSettingsSet -Hidden -ExecutionTimeLimit ([TimeSpan]::Zero) -MultipleInstances IgnoreNew -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries
Register-ScheduledTask -TaskName $taskName -Action $action -Principal $principal -Settings $settings -Description 'SkinDetect approved first baseline: five independent arms x seeds 1,2,3; no Test selection.' | Out-Null
Start-ScheduledTask -TaskName $taskName
$receipt = [ordered]@{task_name=$taskName; python=$python; arguments=$arguments; output_root=$jobRoot; resume=[bool]$Resume; launched=(Get-Date -Format o)}
$receiptPath = Join-Path $configRoot ('launch_' + (Get-Date -Format 'yyyyMMdd_HHmmss') + '.json')
$receipt | ConvertTo-Json | Set-Content -LiteralPath $receiptPath -Encoding UTF8
$receipt | ConvertTo-Json
