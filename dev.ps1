# dev.ps1 — One-command local dev for Windows
# Starts Flask on :5328 and Next.js on :3000
# All /api/python/* calls are proxied by Next.js automatically (next.config.js rewrite)
#
# Usage: .\dev.ps1

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$apiDir = Join-Path $root "api"
$venvPython = Join-Path $apiDir ".venv\Scripts\python.exe"

# Ensure venv exists
if (-not (Test-Path $venvPython)) {
    Write-Host "[setup] Creating Python venv..." -ForegroundColor Yellow
    python -m venv (Join-Path $apiDir ".venv")
    & $venvPython -m pip install -q flask python-dotenv supabase vercel-runtime
    Write-Host "[setup] Done." -ForegroundColor Yellow
}

# Start Flask in background
Write-Host "`n[Flask] Starting on http://localhost:5328 ..." -ForegroundColor Cyan
$flask = Start-Process -FilePath $venvPython `
    -ArgumentList "-m", "flask", "--app", "index", "run", "--port", "5328", "--debug" `
    -WorkingDirectory $apiDir `
    -NoNewWindow -PassThru

# Give Flask a moment
Start-Sleep -Seconds 2

if ($flask.HasExited) {
    Write-Host "[Flask] Failed to start. Check api/.env and imports." -ForegroundColor Red
    exit 1
}

Write-Host "[Flask] Running (PID $($flask.Id))"
Write-Host "[Next.js] Starting on http://localhost:3000 ..."
Write-Host "Open http://localhost:3000 in your browser. Press Ctrl+C to stop both.`n" -ForegroundColor Green

try {
    Set-Location $root
    npm run dev
} finally {
    Write-Host "`n[dev.ps1] Stopping Flask..." -ForegroundColor Yellow
    Stop-Process -Id $flask.Id -Force -ErrorAction SilentlyContinue
    Write-Host "[dev.ps1] Done." -ForegroundColor Yellow
}