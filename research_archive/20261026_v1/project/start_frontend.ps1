# 本機前端 + V2 API；預設只開預覽，不載入模型或占用 GPU。
param(
    [string]$Python = (Join-Path $PSScriptRoot '.venv-skindetect-recovery-20261023\Scripts\python.exe'),
    [ValidateRange(1024, 65535)][int]$Port = 8766,
    [switch]$EnableModels,
    [ValidateSet('cuda', 'cpu')][string]$Device = 'cuda'
)
$ErrorActionPreference = 'Stop'
$env:PIP_CACHE_DIR = 'D:\SkinDetect_Cache\pip'
$frontendServer = Join-Path $PSScriptRoot 'ui_prototype\ensemble_server.py'
if (-not (Test-Path -LiteralPath $frontendServer)) { throw "Frontend service missing: $frontendServer" }
if (-not (Get-Command $Python -ErrorAction SilentlyContinue)) { throw 'Python unavailable. Supply -Python with an available executable.' }
$frontendArgs = @('-B', '-u', $frontendServer, '--project', $PSScriptRoot, '--port', "$Port", '--device', $Device)
# EnableModels 是明確的執行開關；B 未釋放 GPU 時請保留預設，不使用此參數。
if ($EnableModels) { $frontendArgs += '--enable-models' }
& $Python @frontendArgs
exit $LASTEXITCODE

