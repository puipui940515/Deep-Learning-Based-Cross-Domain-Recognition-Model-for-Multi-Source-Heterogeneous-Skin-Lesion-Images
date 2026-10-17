param(
    [string]$Python = 'C:\anaconda3\python.exe',
    [int]$Port = 8765,
    [ValidateSet('auto', 'cpu', 'cuda')][string]$Device = 'auto',
    [switch]$NoOpen,
    [switch]$CheckOnly
)

$ErrorActionPreference = 'Stop'

if (-not (Test-Path -LiteralPath $Python)) {
    throw "Python not found: $Python. Supply -Python with your Python 3.12 executable."
}

# PyTorch is installed in this interpreter's user-site directory. Some Conda
# or PowerShell sessions set PYTHONNOUSERSITE, which otherwise hides it.
$userSite = (& $Python -c 'import site; print(site.getusersitepackages())').Trim()
if ($LASTEXITCODE -ne 0 -or -not $userSite) {
    throw "Unable to resolve the user-site directory for: $Python"
}
if (Test-Path -LiteralPath $userSite) {
    if ($env:PYTHONPATH) {
        $env:PYTHONPATH = "$userSite$([IO.Path]::PathSeparator)$env:PYTHONPATH"
    } else {
        $env:PYTHONPATH = $userSite
    }
}

$uiArgs = @(
    (Join-Path $PSScriptRoot 'ui_prototype\server.py'),
    '--port', "$Port",
    '--device', $Device
)
if ($NoOpen) { $uiArgs += '--no-open' }

& $Python -c "import sys, torch, torchvision, numpy; from PIL import Image; print(f'Runtime OK: {sys.executable} | torch {torch.__version__} | CUDA {torch.cuda.is_available()}')"
if ($LASTEXITCODE -ne 0) {
    throw "Missing runtime dependencies for $Python. Run: & '$Python' -m pip install -r '.\requirements.txt'"
}

if ($CheckOnly) { exit 0 }

& $Python @uiArgs
exit $LASTEXITCODE
