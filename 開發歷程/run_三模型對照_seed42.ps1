<#
.SYNOPSIS
    三模型架構對照，固定 seed 42、固定資料、固定有效 batch。

.DESCRIPTION
    依序跑三個設定，每個都走完 train → postprocess（溫度校準＋熱力圖稽核）→ plot。

      M1  ResNet18      224   基準（既有 seed17 的同設定）
      M2  ConvNeXt-Tiny 224   相對 M1 只改「架構」
      M3  ConvNeXt-Tiny 384   相對 M2 只改「輸入解析度」

    三者的有效 batch size 都是 32（以 gradient_accumulation 補償），
    避免把「架構差異」和「批次大小差異」混在一起。

    資料一律使用 資料治理與泛化修復/data/unified_manifest_v1.csv（22,536 張，
    HAM10000／BCN20000／PAD-UFES-20）。ISIC 擴充集尚未建 manifest、尚未過重疊
    稽核，因此本次不納入 —— 理由見 開發歷程/端到端流程規格_v2_2026-09-10.md。

.PARAMETER Resume
    每個項目都加 --resume。中斷後再跑同一行指令即可續訓。

.PARAMETER Only
    只跑指定項目，例如 -Only M2。預設三個都跑。

.EXAMPLE
    powershell -ExecutionPolicy Bypass -File .\開發歷程\run_三模型對照_seed42.ps1
    powershell -ExecutionPolicy Bypass -File .\開發歷程\run_三模型對照_seed42.ps1 -Resume
#>

[CmdletBinding()]
param(
    [switch]$Resume,
    [ValidateSet("M1", "M2", "M3")]
    [string[]]$Only
)

# 從腳本自身位置推導專案根目錄，不依賴呼叫端的變數或當前目錄。
$Root  = Split-Path -Parent $PSScriptRoot
$Stage = Join-Path $Root "基底模型發展_可切換正式訓練"
$Cfg   = Join-Path $Stage "config"
$Runner = Join-Path $Stage "scripts\run_formal.py"
$LogDir = Join-Path $Root "開發歷程\訓練紀錄"
$Stamp  = Get-Date -Format "yyyyMMdd_HHmmss"

$Jobs = @(
    [PSCustomObject]@{ Id = "M1"; Name = "ResNet18 224";      Config = Join-Path $Cfg "formal_full_v1_seed42.json";      Hours = "約 2.5–3 小時" }
    [PSCustomObject]@{ Id = "M2"; Name = "ConvNeXt-Tiny 224"; Config = Join-Path $Cfg "formal_convnext224_seed42.json"; Hours = "約 6–8 小時" }
    [PSCustomObject]@{ Id = "M3"; Name = "ConvNeXt-Tiny 384"; Config = Join-Path $Cfg "formal_convnext384_seed42.json"; Hours = "約 18–24 小時" }
)
if ($Only) { $Jobs = $Jobs | Where-Object { $Only -contains $_.Id } }

function Line([string]$Text, [string]$Colour = "Cyan") {
    Write-Host ""
    Write-Host ("=" * 70) -ForegroundColor $Colour
    Write-Host $Text -ForegroundColor $Colour
    Write-Host ("=" * 70) -ForegroundColor $Colour
}

# ---------------------------------------------------------------- 起跑前檢查
Line "起跑前檢查"
Write-Host "專案根目錄　$Root"

$abort = $false

if (-not (Test-Path -LiteralPath $Runner)) {
    Write-Host "找不到 run_formal.py：$Runner" -ForegroundColor Red; $abort = $true
}

foreach ($job in $Jobs) {
    if (Test-Path -LiteralPath $job.Config) {
        Write-Host "[$($job.Id)] 設定檔 OK　$(Split-Path -Leaf $job.Config)" -ForegroundColor DarkGray
    } else {
        Write-Host "[$($job.Id)] 找不到設定檔　$($job.Config)" -ForegroundColor Red; $abort = $true
    }
}

$gate = Join-Path $Root "資料治理與泛化修復\reports\pipeline_gate.json"
if (Test-Path -LiteralPath $gate) {
    $passed = (Get-Content -Raw -LiteralPath $gate -Encoding UTF8 | ConvertFrom-Json).passed
    if ($passed) {
        Write-Host "治理閘門　passed" -ForegroundColor DarkGray
    } else {
        Write-Host "治理閘門未通過，train.py 會直接中止" -ForegroundColor Red; $abort = $true
    }
} else {
    Write-Host "找不到治理閘門檔案：$gate" -ForegroundColor Red; $abort = $true
}

& python -c "import torch,sys; ok=torch.cuda.is_available(); print('torch',torch.__version__,'cuda',ok, torch.cuda.get_device_name(0) if ok else ''); sys.exit(0 if ok else 3)"
if ($LASTEXITCODE -eq 3) {
    Write-Host "CUDA 不可用。要用 CPU 跑會慢到不可行，先確認環境。" -ForegroundColor Red; $abort = $true
} elseif ($LASTEXITCODE -ne 0) {
    Write-Host "python 或 torch 有問題（exit $LASTEXITCODE）" -ForegroundColor Red; $abort = $true
}

if ($abort) { Write-Host ""; Write-Host "檢查未通過，未啟動任何訓練。" -ForegroundColor Red; exit 1 }

New-Item -ItemType Directory -Force -Path $LogDir | Out-Null
Write-Host "紀錄目錄　$LogDir" -ForegroundColor DarkGray
Write-Host "續訓模式　$($Resume.IsPresent)" -ForegroundColor DarkGray

# ---------------------------------------------------------------- 依序執行
$results = @()
foreach ($job in $Jobs) {
    Line "[$($job.Id)] $($job.Name)　$($job.Hours)"
    $log = Join-Path $LogDir "$($Stamp)_$($job.Id).log"
    Write-Host "設定　$($job.Config)"
    Write-Host "紀錄　$log"
    Write-Host "開始　$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')"
    Write-Host ""

    $started = Get-Date
    $cmdArgs = @($Runner, "--config", $job.Config)
    if ($Resume) { $cmdArgs += "--resume" }

    & python @cmdArgs 2>&1 | Tee-Object -FilePath $log
    $code = $LASTEXITCODE
    $spent = (Get-Date) - $started

    $results += [PSCustomObject]@{
        項目 = $job.Id; 模型 = $job.Name
        結果 = if ($code -eq 0) { "完成" } else { "失敗 exit $code" }
        耗時 = "{0:hh\:mm\:ss}" -f $spent
        紀錄 = Split-Path -Leaf $log
    }

    if ($code -eq 0) {
        Write-Host ""
        Write-Host "[$($job.Id)] 完成，耗時 $("{0:hh\:mm\:ss}" -f $spent)" -ForegroundColor Green
    } else {
        Write-Host ""
        Write-Host "[$($job.Id)] 失敗（exit $code），繼續下一項。詳見 $log" -ForegroundColor Red
    }
}

# ---------------------------------------------------------------- 收尾
Line "全部結束" "Green"
$results | Format-Table -AutoSize | Out-String -Width 200 | Write-Host

Write-Host "結果位置：" -ForegroundColor Yellow
foreach ($job in $Jobs) {
    $name = (Get-Content -Raw -LiteralPath $job.Config -Encoding UTF8 | ConvertFrom-Json).experiment_id
    $dir = Join-Path $Stage "results\$($name)_seed42"
    $mark = if (Test-Path -LiteralPath (Join-Path $dir "result.json")) { "有 result.json" } else { "無 result.json" }
    Write-Host "  [$($job.Id)] $dir　$mark" -ForegroundColor DarkGray
}

Write-Host ""
Write-Host "醒來後看三件事：" -ForegroundColor Yellow
Write-Host "  1. 各 result.json 的三來源 BA —— 但這是單 seed，不能當正式結論" -ForegroundColor DarkGray
Write-Host "  2. 各 calibration.json 的 temperature —— seed17 是 0.8569，若都小於 1 就不是偶然" -ForegroundColor DarkGray
Write-Host "  3. 各 heatmap_audit/summary.json 的 flip_hot_iou —— seed17 是 0.524" -ForegroundColor DarkGray
Write-Host ""
Write-Host "提醒：本次三個項目都是 pilot（單 seed）。依 開發歷程/格式約定.md，" -ForegroundColor Yellow
Write-Host "      單 seed 結果須標記 pilot: true，不得作為正式結論。" -ForegroundColor Yellow
