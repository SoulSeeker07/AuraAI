$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent $PSScriptRoot
$BundledPython = "C:\Users\yrsre\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"
$VenvPackages = Join-Path $ProjectRoot ".venv\Lib\site-packages"
$SourceRoot = Join-Path $ProjectRoot "src"

if (-not (Test-Path -LiteralPath $BundledPython)) {
    throw "Bundled Python was not found at $BundledPython"
}

if (-not (Test-Path -LiteralPath $VenvPackages)) {
    throw "Aura dependencies were not found at $VenvPackages"
}

$env:PYTHONPATH = "$VenvPackages;$SourceRoot;$env:PYTHONPATH"
& $BundledPython (Join-Path $SourceRoot "main.py")
