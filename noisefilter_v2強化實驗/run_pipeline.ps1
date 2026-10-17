param(
    [string]$Python = 'C:\anaconda3\python.exe',
    [ValidateSet('check', 'prepare', 'all', 'evaluate', 'report')]
    [string]$Stage = 'check'
)

$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
if (-not (Test-Path -LiteralPath $Python -PathType Leaf)) {
    throw "Python not found: $Python"
}

# Resolve and expose the user site in THIS shell, including child processes.
$userSiteOutput = & $Python -c 'import site; print(site.getusersitepackages())'
if ($LASTEXITCODE -ne 0) { throw 'Cannot resolve Python user-site directory.' }
$runtimeSite = ($userSiteOutput | Select-Object -Last 1).Trim()
$savedPythonPath = $env:PYTHONPATH
$savedEncoding = $env:PYTHONIOENCODING
try {
    $env:PYTHONPATH = $runtimeSite
    if ($savedPythonPath) { $env:PYTHONPATH += [IO.Path]::PathSeparator + $savedPythonPath }
    $env:PYTHONIOENCODING = 'utf-8'
    Write-Host "Python: $Python"
    Write-Host "User site: $runtimeSite"
    $probe = "import torch, torchvision, numpy, PIL, scipy, sklearn, pandas, matplotlib, tqdm, requests, pytest; print('torch=', torch.__version__); print('torch_file=', torch.__file__); print('cuda=', torch.cuda.is_available())"
    & $Python -c $probe
    if ($LASTEXITCODE -ne 0) {
        Write-Host 'Runtime import failed. Installing project requirements into this Python user site...'
        & $Python -m pip install --user -r (Join-Path $projectRoot 'requirements.txt') pytest
        if ($LASTEXITCODE -ne 0) {
            throw 'Dependency installation failed. Training was NOT started. Keep the pip error output for diagnosis.'
        }
        & $Python -c $probe
        if ($LASTEXITCODE -ne 0) {
            throw 'Runtime still cannot import dependencies after installation. Training was NOT started.'
        }
    }
    $pipeline = Join-Path $PSScriptRoot 'scripts\pipeline.py'
    if ($Stage -in @('all', 'prepare')) {
        & $Python -c "import torch; assert torch.cuda.is_available(), 'CUDA unavailable; refusing an unintended CPU training run'"
        if ($LASTEXITCODE -ne 0) { throw 'CUDA check failed. Training was NOT started.' }
        & $Python -u $pipeline --stage check
        if ($LASTEXITCODE -ne 0) { throw 'Pipeline checks failed. Training was NOT started.' }
    }
    & $Python -u $pipeline --stage $Stage
    if ($LASTEXITCODE -ne 0) { throw "Pipeline stopped with exit code $LASTEXITCODE. See the output and results/logs." }
} finally {
    $env:PYTHONPATH = $savedPythonPath
    $env:PYTHONIOENCODING = $savedEncoding
}
