param([int]$Epochs = 6)
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$Python = "python"

# 快速篩選只跑 A/B；不建立耗時的 shuffled 負對照資產。
$conditions = @("imagenet_init", "densepose_true_init")
$seeds = @(17, 42)
foreach ($condition in $conditions) {
    foreach ($seed in $seeds) {
        Write-Host "`n===== 快速篩選：$condition / seed $seed =====" -ForegroundColor Cyan
        & $Python "$Root\scripts\train_transfer.py" --condition $condition --seed $seed --epochs $Epochs --resume
        if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    }
}
& $Python "$Root\scripts\summarize.py"
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
& $Python "$Root\scripts\plot_curves.py"
exit $LASTEXITCODE
