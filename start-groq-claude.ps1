# Auto-start LiteLLM proxy and launch Claude Code connected to GLM 4.7 Flash

$env:PYTHONUTF8 = "1"
$env:PYTHONIOENCODING = "utf-8"

# Load GLM_API_KEY and GROQ_API_KEY from .env if present
if (Test-Path "$PSScriptRoot\.env") {
    Get-Content "$PSScriptRoot\.env" | ForEach-Object {
        if ($_ -match '^\s*GLM_API_KEY\s*=\s*(.+)$') {
            $env:GLM_API_KEY = $matches[1].Trim()
        }
        if ($_ -match '^\s*GROQ_API_KEY\s*=\s*(.+)$') {
            $env:GROQ_API_KEY = $matches[1].Trim()
        }
    }
}

# Check if LiteLLM proxy is running on port 4000
$proxyRunning = $false
try {
    $resp = Invoke-WebRequest -Uri "http://127.0.0.1:4000/health" -UseBasicParsing -TimeoutSec 2 -ErrorAction SilentlyContinue
    if ($resp.StatusCode -eq 200) {
        $proxyRunning = $true
    }
} catch {
    $proxyRunning = $false
}

if (-not $proxyRunning) {
    Write-Host "Starting LiteLLM proxy with GLM 4.7 Flash..." -ForegroundColor Cyan
    $proxyProcess = Start-Process -FilePath "$PSScriptRoot\.venv\Scripts\python.exe" `
        -ArgumentList "`"$PSScriptRoot\run_proxy.py`"" `
        -PassThru -WindowStyle Hidden
    Start-Sleep -Seconds 3
}

$env:ANTHROPIC_BASE_URL = "http://127.0.0.1:4000"
$env:ANTHROPIC_AUTH_TOKEN = "glm-proxy-token"
$env:MAX_THINKING_TOKENS = "0"
$env:CLAUDE_CODE_DISABLE_THINKING = "1"
$env:CLAUDE_CODE_DISABLE_UNKNOWN_MODEL_WINDOW_ENFORCEMENT = "1"

Write-Host "Launching Claude Code connected to GLM 4.7 Flash..." -ForegroundColor Green
& claude $args
