param([int]$Epochs = 30)
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$Python = "python"

& $Python "$Root\scripts\prepare_matched_shuffled.py"
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

$conditions = @("imagenet_init", "densepose_true_init", "densepose_shuffled_matched_init")
$seeds = @(17, 42, 2026)
foreach ($condition in $conditions) {
    foreach ($seed in $seeds) {
        Write-Host "`n===== $condition / seed $seed =====" -ForegroundColor Cyan
        & $Python "$Root\scripts\train_transfer.py" --condition $condition --seed $seed --epochs $Epochs --resume
        if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    }
}
& $Python "$Root\scripts\summarize.py"
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
& $Python "$Root\scripts\plot_curves.py"
exit $LASTEXITCODE
