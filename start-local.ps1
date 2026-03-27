# start-local.ps1
# Starts the Agent-Ops API using the .env.local configuration.

$env:APP_ENV = "local"

Write-Host "Starting Agent-Ops API [env=local]..." -ForegroundColor Cyan
Write-Host "API docs → http://localhost:8000/docs" -ForegroundColor Green
Write-Host "Press Ctrl+C to stop.`n" -ForegroundColor Yellow

uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload --log-level info

