param(
    [string]$Python = 'C:\anaconda3\python.exe',
    [int]$Port = 8765,
    [ValidateSet('auto', 'cpu', 'cuda')][string]$Device = 'auto',
    [switch]$NoOpen
)
$ErrorActionPreference = 'Stop'
if (-not (Test-Path -LiteralPath $Python)) {
    throw "Python not found: $Python. Supply -Python with your Python 3.12 executable."
}
$uiArgs = @((Join-Path $PSScriptRoot 'ui_prototype\server.py'), '--port', "$Port", '--device', $Device)
if ($NoOpen) { $uiArgs += '--no-open' }
& $Python -c 'import torch, torchvision, numpy; from PIL import Image'
if ($LASTEXITCODE -ne 0) { throw 'Missing runtime dependencies. Install requirements.txt first.' }
& $Python @uiArgs
exit $LASTEXITCODE
