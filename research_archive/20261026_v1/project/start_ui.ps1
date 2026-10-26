param(
    [string]$Python = (Join-Path $PSScriptRoot '.venv-skindetect-recovery-20261023\Scripts\python.exe'),
    [int]$Port = 8765,
    [ValidateSet('auto', 'cpu', 'cuda')][string]$Device = 'auto',
    [switch]$NoOpen,
    [switch]$CheckOnly
)
$ErrorActionPreference = 'Stop'
if (-not (Test-Path -LiteralPath $Python)) {
    throw "Python not found: $Python. Supply -Python with the restored Python 3.12 environment."
}
# The dedicated venv contains the exact historical packages; do not inject a C-drive user site.
$runtimeDirectory = Join-Path $PSScriptRoot 'recovery_20261023\environment'
$env:TEMP = Join-Path $runtimeDirectory 'tmp'
$env:TMP = $env:TEMP
$env:PIP_CACHE_DIR = 'D:\SkinDetect_Cache\pip'
$env:PYTHONDONTWRITEBYTECODE = '1'
New-Item -ItemType Directory -Force $env:TEMP | Out-Null
$uiArgs = @((Join-Path $PSScriptRoot 'ui_prototype\server.py'), '--port', "$Port", '--device', $Device)
if ($NoOpen) { $uiArgs += '--no-open' }
& $Python -B -s -c "import sys, torch, torchvision, numpy; from PIL import Image; print(f'Runtime OK: {sys.executable} | torch {torch.__version__} | CUDA {torch.cuda.is_available()}')"
if ($LASTEXITCODE -ne 0) { throw "Runtime dependencies failed for $Python. See recovery_20261023\environment." }
if ($CheckOnly) { exit 0 }
& $Python -B -s @uiArgs
exit $LASTEXITCODE
