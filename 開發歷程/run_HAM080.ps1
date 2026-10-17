<#
.SYNOPSIS
    HAM10000 突破 0.80 實驗排程 —— W0 確認階段。

.DESCRIPTION
    對應 開發歷程/HAM10000_突破0.80_實驗排程.md 的 W0。
    補齊 v8（ConvNeXt-Tiny / ImageNet / 384）的 seed 2026，
    然後以三個 seed 判定是否通過門檻：
        三 seed 平均 validation Balanced Accuracy >= 80.0%
        且樣本標準差 <= 1.0 個百分點

    HAM10000 test split 全程不使用。本腳本不會讀取或評估 test。

.PARAMETER Stage
    W0      執行完整 W0 流程（驗證閘門 -> 訓練 seed 2026 -> 彙總 -> 判定）
    report  只用既有結果重新判定，不訓練

.PARAMETER Python
    Python 直譯器。預設 "python"；若 PATH 上沒有正確環境，改成完整路徑，
    例如 -Python "C:\anaconda3\python.exe"

.PARAMETER SkipGate
    跳過根目錄驗證閘門（僅在剛跑過時使用）

.PARAMETER Epochs
    覆寫訓練輪數。省略則使用 第二階段/config/stage2.json 的設定

.EXAMPLE
    powershell -ExecutionPolicy Bypass -File ".\開發歷程\run_HAM080.ps1"

.EXAMPLE
    powershell -ExecutionPolicy Bypass -File ".\開發歷程\run_HAM080.ps1" -Stage report

.EXAMPLE
    powershell -ExecutionPolicy Bypass -File ".\開發歷程\run_HAM080.ps1" -Python "C:\anaconda3\python.exe"
#>
[CmdletBinding()]
param(
    [ValidateSet("W0", "report")] [string]$Stage = "W0",
    [string]$Python = "python",
    [switch]$SkipGate,
    [int]$Epochs = 0
)

$ErrorActionPreference = "Stop"
try { [Console]::OutputEncoding = [System.Text.Encoding]::UTF8 } catch { }

$ScriptDir   = Split-Path -Parent $MyInvocation.MyCommand.Path
$Root        = Split-Path -Parent $ScriptDir          # 專案根目錄
$Results     = Join-Path $Root "第二階段\results"
$TargetSeeds = @(17, 42, 2026)
$NewSeed     = 2026
$MinMean     = 80.0    # 通過門檻：三 seed 平均 BA
$MaxStd      = 1.0     # 通過門檻：樣本標準差上限（百分點）
$Classes     = @("AKIEC", "BCC", "BKL", "DF", "NV", "VASC", "MEL")

function Write-Section([string]$Text) {
    Write-Host ""
    Write-Host ("=" * 66) -ForegroundColor DarkGray
    Write-Host $Text -ForegroundColor Cyan
    Write-Host ("=" * 66) -ForegroundColor DarkGray
}

function Read-JsonFile([string]$Path) {
    # 專案內的 result.json 多為 utf-8-sig，需先去掉 BOM
    $raw = Get-Content -Raw -Encoding UTF8 -LiteralPath $Path
    return ($raw.TrimStart([char]0xFEFF) | ConvertFrom-Json)
}

function Invoke-Step([string]$Label, [string[]]$Arguments) {
    Write-Host ""
    Write-Host ">> $Label" -ForegroundColor Yellow
    Write-Host "   $Python $($Arguments -join ' ')" -ForegroundColor DarkGray
    & $Python @Arguments
    if ($LASTEXITCODE -ne 0) {
        Write-Host "步驟失敗（exit $LASTEXITCODE）：$Label" -ForegroundColor Red
        exit $LASTEXITCODE
    }
}

function Get-SampleStd([double[]]$Values) {
    if ($Values.Count -lt 2) { return [double]::NaN }
    $mean = ($Values | Measure-Object -Average).Average
    $sum  = 0.0
    foreach ($v in $Values) { $sum += [Math]::Pow($v - $mean, 2) }
    return [Math]::Sqrt($sum / ($Values.Count - 1))
}

# ---------------------------------------------------------------- 前置檢查
Write-Section "HAM10000 突破 0.80 實驗排程　W0：確認 v8（384）"

Push-Location $Root
try {
    Write-Host "專案根目錄　$Root"
    Write-Host "階段　　　　$Stage"
    Write-Host "Python　　　$Python"

    if (-not (Test-Path -LiteralPath (Join-Path $Root "第二階段\scripts\train.py"))) {
        Write-Host "找不到 第二階段\scripts\train.py，請確認是從專案內執行本腳本。" -ForegroundColor Red
        exit 2
    }

    $baselineMissing = @()
    foreach ($seed in @(17, 42)) {
        if (-not (Test-Path -LiteralPath (Join-Path $Results "v8_seed$seed.json"))) {
            $baselineMissing += $seed
        }
    }
    if ($baselineMissing.Count -gt 0) {
        Write-Host "缺少 v8 既有結果 seed：$($baselineMissing -join ', ')" -ForegroundColor Red
        Write-Host "W0 的前提是 v8 已有 seed 17 與 42 的結果。" -ForegroundColor Red
        exit 2
    }

    # ------------------------------------------------------------ 訓練
    if ($Stage -eq "W0") {
        if (-not $SkipGate) {
            Invoke-Step "根目錄驗證閘門" @("驗證\run_all.py")

            $gatePath = Join-Path $Root "驗證\reports\validation_gate.json"
            if (Test-Path -LiteralPath $gatePath) {
                $gate = Read-JsonFile $gatePath
                if (-not $gate.passed) {
                    Write-Host "validation_gate.json 的 passed 不為 true，依協定不得開始訓練。" -ForegroundColor Red
                    exit 3
                }
                Write-Host "   驗證閘門通過" -ForegroundColor Green
            }
        } else {
            Write-Host "`n（已指定 -SkipGate，略過驗證閘門）" -ForegroundColor DarkYellow
        }

        $trainArgs = @("第二階段\scripts\train.py", "--version", "v8", "--seed", "$NewSeed", "--resume")
        if ($Epochs -gt 0) { $trainArgs += @("--epochs", "$Epochs") }
        Invoke-Step "訓練 v8 / seed $NewSeed（384，可續訓）" $trainArgs

        Invoke-Step "第二階段結果彙總" @("第二階段\scripts\summarize_results.py")
    } else {
        Write-Host "`n（report 模式：不訓練，只用既有結果判定）" -ForegroundColor DarkYellow
    }

    # ------------------------------------------------------------ 判定
    Write-Section "W0 判定"

    $records = @()
    foreach ($seed in $TargetSeeds) {
        $path = Join-Path $Results "v8_seed$seed.json"
        if (-not (Test-Path -LiteralPath $path)) {
            Write-Host "缺少結果：v8_seed$seed.json" -ForegroundColor Red
            continue
        }
        $doc = Read-JsonFile $path
        if ($doc.test_used) {
            Write-Host "v8_seed$seed.json 的 test_used 為 true —— 違反 test 封存協定，中止。" -ForegroundColor Red
            exit 4
        }
        $records += [pscustomobject]@{
            Seed      = $seed
            BA        = [double]$doc.best.val.balanced_accuracy * 100.0
            MacroF1   = [double]$doc.best.val.macro_f1 * 100.0
            Accuracy  = [double]$doc.best.val.accuracy * 100.0
            TrainBA   = [double]$doc.best.train.balanced_accuracy * 100.0
            Epoch     = [int]$doc.best.epoch
            Recalls   = @($doc.best.val.recall_per_class | ForEach-Object { [double]$_ * 100.0 })
        }
    }

    if ($records.Count -lt 2) {
        Write-Host "可用結果不足兩個 seed，無法判定。" -ForegroundColor Red
        exit 5
    }

    Write-Host ""
    Write-Host ("{0,-6} {1,8} {2,9} {3,9} {4,9} {5,6}" -f "seed", "valBA", "macroF1", "valAcc", "trainBA", "epoch")
    Write-Host ("-" * 56) -ForegroundColor DarkGray
    foreach ($r in $records) {
        Write-Host ("{0,-6} {1,8:N2} {2,9:N2} {3,9:N2} {4,9:N2} {5,6}" -f $r.Seed, $r.BA, $r.MacroF1, $r.Accuracy, $r.TrainBA, $r.Epoch)
    }

    $values = @($records | ForEach-Object { $_.BA })
    $mean   = ($values | Measure-Object -Average).Average
    $std    = Get-SampleStd $values

    Write-Host ""
    Write-Host ("平均 validation BA　{0:N2}%（n={1}）" -f $mean, $records.Count)
    Write-Host ("樣本標準差 s　　　　{0:N2} pp" -f $std)
    Write-Host ("2s　　　　　　　　　{0:N2} pp" -f (2 * $std))

    # 逐類 recall 平均
    Write-Host ""
    Write-Host "逐類 recall 平均（%）" -ForegroundColor Cyan
    $classMeans = @()
    for ($i = 0; $i -lt $Classes.Count; $i++) {
        $vals = @($records | ForEach-Object { $_.Recalls[$i] })
        $classMeans += [pscustomobject]@{
            Class = $Classes[$i]
            Mean  = ($vals | Measure-Object -Average).Average
        }
    }
    foreach ($c in ($classMeans | Sort-Object Mean)) {
        $colour = if ($c.Mean -lt 75) { "Yellow" } else { "Gray" }
        Write-Host ("  {0,-6} {1,6:N1}" -f $c.Class, $c.Mean) -ForegroundColor $colour
    }
    Write-Host "  （黃色為低於 75% 的類別，是 W2 弱類專項的對象）" -ForegroundColor DarkGray

    # 通過判定
    $complete = ($records.Count -eq $TargetSeeds.Count)
    $passed   = $complete -and ($mean -ge $MinMean) -and ($std -le $MaxStd)

    Write-Section "結論"
    if (-not $complete) {
        Write-Host "尚未集滿三個 seed（目前 $($records.Count) 個），依全域原則只能標記為 pilot。" -ForegroundColor Yellow
        $verdict = "incomplete"
    } elseif ($passed) {
        Write-Host ("W0 通過：三 seed 平均 {0:N2}% >= {1:N1}%，s = {2:N2} pp <= {3:N1} pp" -f $mean, $MinMean, $std, $MaxStd) -ForegroundColor Green
        Write-Host "目標達成。排程性質改為「鞏固與推高」，下一步 W1（零訓練加乘）。" -ForegroundColor Green
        $verdict = "passed"
    } elseif ($mean -lt 79.0) {
        Write-Host ("W0 未通過且觸發停損：三 seed 平均 {0:N2}% < 79.0%" -f $mean) -ForegroundColor Red
        Write-Host "依排程第四節，須回頭檢查 v8 的訓練紀錄是否有異常，不得直接進入 W1。" -ForegroundColor Red
        $verdict = "stop_loss"
    } else {
        Write-Host ("W0 未通過：平均 {0:N2}%（門檻 {1:N1}%），s = {2:N2} pp（上限 {3:N1} pp）" -f $mean, $MinMean, $std, $MaxStd) -ForegroundColor Yellow
        Write-Host "可進入 W1 嘗試零訓練加乘，但不得宣稱已達 0.80。" -ForegroundColor Yellow
        $verdict = "not_passed"
    }

    # ------------------------------------------------------------ 輸出報告
    $report = [ordered]@{
        schema_version         = "skindetect-index-v1"
        generated_at           = (Get-Date).ToUniversalTime().ToString("yyyy-MM-ddTHH:mm:ss+00:00")
        generator              = "開發歷程/run_HAM080.ps1"
        schedule               = "開發歷程/HAM10000_突破0.80_實驗排程.md"
        stage                  = "W0"
        target                 = "HAM10000 validation Balanced Accuracy >= 0.80"
        version                = "v8"
        spec                   = "convnext_tiny / imagenet / 384"
        validation_images      = 1504
        seeds                  = @($records | ForEach-Object { $_.Seed })
        seed_count             = $records.Count
        pilot                  = (-not $complete)
        mean_balanced_accuracy = [Math]::Round($mean / 100.0, 6)
        sample_std_pp          = if ([double]::IsNaN($std)) { $null } else { [Math]::Round($std, 4) }
        per_seed               = @($records | ForEach-Object {
                                     [ordered]@{ seed = $_.Seed
                                                 balanced_accuracy = [Math]::Round($_.BA / 100.0, 6)
                                                 best_epoch = $_.Epoch } })
        per_class_recall_mean  = [ordered]@{}
        gate                   = [ordered]@{ min_mean_pp = $MinMean; max_std_pp = $MaxStd; verdict = $verdict }
        test_used              = $false
    }
    foreach ($c in $classMeans) { $report.per_class_recall_mean[$c.Class] = [Math]::Round($c.Mean / 100.0, 6) }

    $outPath = Join-Path $Results "W0_v8_gate.json"
    $report | ConvertTo-Json -Depth 6 | Out-File -LiteralPath $outPath -Encoding UTF8
    Write-Host ""
    Write-Host "報告已寫入　$outPath" -ForegroundColor Green
    Write-Host ""
    Write-Host "後續：把本次事件補進 開發歷程/build_timeline.py 的 EVENTS，再執行" -ForegroundColor DarkGray
    Write-Host "  $Python `"開發歷程\build_timeline.py`"" -ForegroundColor DarkGray
    Write-Host "  $Python `"開發歷程\check_consistency.py`"" -ForegroundColor DarkGray

    if ($verdict -eq "stop_loss") { exit 6 }
    exit 0
}
finally {
    Pop-Location
}
