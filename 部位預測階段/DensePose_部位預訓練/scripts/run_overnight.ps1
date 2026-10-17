$ErrorActionPreference = "Stop"
$StageRoot = Split-Path -Parent $PSScriptRoot
$ProjectRoot = Split-Path -Parent (Split-Path -Parent $StageRoot)
$Manifest = Join-Path $StageRoot "data\part_crops.csv"
$Images = Join-Path $ProjectRoot "Dataset\DensePose_COCO\images"
$TrainScript = Join-Path $PSScriptRoot "train_overnight.py"
$OutputRoot = Join-Path $StageRoot "results\overnight_2026-08-24"
New-Item -ItemType Directory -Force -Path $OutputRoot | Out-Null
$TranscriptPath = Join-Path $OutputRoot "overnight_console.log"
Start-Transcript -LiteralPath $TranscriptPath -Append

$Jobs = @(
    [pscustomobject]@{ Name = "true_seed17"; Mode = "true"; Seed = 17; Epochs = 8 },
    [pscustomobject]@{ Name = "true_seed42"; Mode = "true"; Seed = 42; Epochs = 8 },
    [pscustomobject]@{ Name = "shuffled_seed17"; Mode = "shuffled"; Seed = 17; Epochs = 4 }
)

try {
    foreach ($Job in $Jobs) {
        $JobOutput = Join-Path $OutputRoot $Job.Name
        Write-Host "Starting $($Job.Name) at $(Get-Date -Format o)"
        $Arguments = @(
            $TrainScript, "--manifest", $Manifest, "--images", $Images,
            "--output", $JobOutput, "--seed", [string]$Job.Seed,
            "--epochs", [string]$Job.Epochs, "--label-mode", $Job.Mode,
            "--batch-size", "16", "--workers", "0", "--image-size", "224",
            "--max-train-samples", "50000", "--max-val-samples", "10000",
            "--sample-seed", "20260824"
        )
        & python @Arguments
        if ($LASTEXITCODE -ne 0) { throw "$($Job.Name) failed with exit code $LASTEXITCODE" }
        Write-Host "Completed $($Job.Name) at $(Get-Date -Format o)"
    }

    $Summary = foreach ($Job in $Jobs) {
        $ResultPath = Join-Path (Join-Path $OutputRoot $Job.Name) "result_seed$($Job.Seed).json"
        $Result = Get-Content -LiteralPath $ResultPath -Raw | ConvertFrom-Json
        $Best = $Result.history | Sort-Object { $_.validation.balanced_accuracy } -Descending | Select-Object -First 1
        [pscustomobject]@{
            job = $Job.Name; label_mode = $Job.Mode; seed = $Job.Seed; best_epoch = $Best.epoch
            validation_accuracy = $Best.validation.accuracy
            validation_balanced_accuracy = $Best.validation.balanced_accuracy
            validation_macro_f1 = $Best.validation.macro_f1
            validation_loss = $Best.validation.loss; test_used = $Result.test_used
        }
    }
    $Summary | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath (Join-Path $OutputRoot "overnight_summary.json") -Encoding UTF8
    $Summary | Format-Table -AutoSize
}
finally {
    Stop-Transcript
}
