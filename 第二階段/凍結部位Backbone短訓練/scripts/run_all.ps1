$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$OutputRoot = Join-Path $Root "results"
New-Item -ItemType Directory -Force -Path $OutputRoot | Out-Null
Start-Transcript -LiteralPath (Join-Path $OutputRoot "console.log") -Append
try {
    $Conditions = @("imagenet_frozen", "densepose_true_frozen", "densepose_shuffled_frozen")
    $Seeds = @(17, 42, 2026)
    foreach ($Condition in $Conditions) {
        foreach ($Seed in $Seeds) {
            $Result = Join-Path $OutputRoot "$Condition\seed$Seed\result.json"
            if (Test-Path -LiteralPath $Result) {
                Write-Host "Skip completed: $Condition seed=$Seed"
                continue
            }
            Write-Host "Start: $Condition seed=$Seed at $(Get-Date -Format o)"
            & python (Join-Path $PSScriptRoot "train_frozen.py") --condition $Condition --seed $Seed
            if ($LASTEXITCODE -ne 0) { throw "$Condition seed=$Seed failed with exit code $LASTEXITCODE" }
            Write-Host "Complete: $Condition seed=$Seed at $(Get-Date -Format o)"
        }
    }
    & python (Join-Path $PSScriptRoot "summarize.py")
    if ($LASTEXITCODE -ne 0) { throw "Summary failed with exit code $LASTEXITCODE" }
}
finally {
    Stop-Transcript
}
