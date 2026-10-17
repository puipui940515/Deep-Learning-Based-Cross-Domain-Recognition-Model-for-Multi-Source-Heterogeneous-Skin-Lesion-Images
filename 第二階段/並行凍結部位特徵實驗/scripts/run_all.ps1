$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$Results = Join-Path $Root "results"
New-Item -ItemType Directory -Force -Path $Results | Out-Null
Start-Transcript -LiteralPath (Join-Path $Results "console.log") -Append
try {
    $Conditions = @("imagenet_teacher", "densepose_true_teacher", "densepose_shuffled_teacher")
    $Seeds = @(17, 42, 2026)
    foreach ($Condition in $Conditions) {
        foreach ($Seed in $Seeds) {
            $Result = Join-Path $Results "$Condition\seed$Seed\result.json"
            if (Test-Path -LiteralPath $Result) { Write-Host "Skip completed: $Condition seed=$Seed"; continue }
            Write-Host "Start: $Condition seed=$Seed at $(Get-Date -Format o)"
            & python (Join-Path $PSScriptRoot "train_parallel.py") --condition $Condition --seed $Seed
            if ($LASTEXITCODE -ne 0) { throw "$Condition seed=$Seed failed with exit code $LASTEXITCODE" }
            Write-Host "Complete: $Condition seed=$Seed at $(Get-Date -Format o)"
        }
    }
    & python (Join-Path $PSScriptRoot "summarize.py")
    if ($LASTEXITCODE -ne 0) { throw "Summary failed with exit code $LASTEXITCODE" }
}
finally { Stop-Transcript }
