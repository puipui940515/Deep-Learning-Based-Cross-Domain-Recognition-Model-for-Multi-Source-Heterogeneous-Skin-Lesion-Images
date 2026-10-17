$ErrorActionPreference = "Stop"

$Python = "C:\anaconda3\python.exe"
$Runner = Join-Path $PSScriptRoot "run_cp003_stage1.py"

if (-not (Test-Path -LiteralPath $Python -PathType Leaf)) {
    throw "Training Python was not found: $Python"
}

if (-not (Test-Path -LiteralPath $Runner -PathType Leaf)) {
    throw "Stage 1 runner was not found: $Runner"
}

& $Python $Runner
if ($LASTEXITCODE -ne 0) {
    exit $LASTEXITCODE
}

exit 0
