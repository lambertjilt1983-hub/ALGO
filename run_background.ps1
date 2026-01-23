# ============================================================
# AlgoTrade Pro - Background Startup Script
# ============================================================
# Runs both backend and frontend in background

Write-Host "" -ForegroundColor Cyan
Write-Host "    AlgoTrade Pro - Background Startup" -ForegroundColor Green
Write-Host "" -ForegroundColor Cyan
Write-Host ""

# Stop existing jobs
Write-Host "[1/4] Cleaning up old jobs..." -ForegroundColor Yellow
Get-Job | Stop-Job -ErrorAction SilentlyContinue
Get-Job | Remove-Job -Force -ErrorAction SilentlyContinue

# Kill existing processes
Write-Host "[2/4] Stopping existing processes..." -ForegroundColor Yellow
Get-Process -Name python,node,uvicorn -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
Start-Sleep -Seconds 2

# Free ports
Write-Host "[3/4] Freeing ports..." -ForegroundColor Yellow
$connections = Get-NetTCPConnection -LocalPort 8000,8002,3000 -ErrorAction SilentlyContinue
if ($connections) {
    $connections | ForEach-Object { Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue }
}
Start-Sleep -Seconds 2

# Start Backend in background (using port 8002 to avoid conflicts)
Write-Host "[4/4] Starting services..." -ForegroundColor Yellow
$backendJob = Start-Job -Name "AlgoBackend" -ScriptBlock {
    cd F:\ALGO\backend
    $env:PYTHONPATH = 'F:\ALGO\backend'
    & F:\ALGO\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8002
}

Write-Host "   Backend starting (Job ID: $($backendJob.Id))..." -ForegroundColor Cyan
Start-Sleep -Seconds 8

# Verify backend
try {
    $health = Invoke-RestMethod 'http://127.0.0.1:8002/health' -TimeoutSec 3
    Write-Host "    Backend running at http://127.0.0.1:8002" -ForegroundColor Green
} catch {
    Write-Host "    Backend may still be starting..." -ForegroundColor Yellow
}

# Start Frontend in background
$frontendJob = Start-Job -Name "AlgoFrontend" -ScriptBlock {
    cd F:\ALGO\frontend
    $env:REACT_APP_API_URL = 'http://localhost:8002'
    npm run dev
}

Write-Host "   Frontend starting (Job ID: $($frontendJob.Id))..." -ForegroundColor Cyan
Start-Sleep -Seconds 5

# Show status
Write-Host ""
Write-Host "" -ForegroundColor Cyan
Write-Host "                   Services Running" -ForegroundColor Green
Write-Host "" -ForegroundColor Cyan
Write-Host ""
Write-Host "  Backend API:   http://127.0.0.1:8002" -ForegroundColor White
Write-Host "  API Docs:      http://127.0.0.1:8002/docs" -ForegroundColor White
Write-Host "  Frontend:      http://localhost:3000 (starting...)" -ForegroundColor White
Write-Host ""
Write-Host "Background Jobs:" -ForegroundColor Yellow
Get-Job | Format-Table -AutoSize
Write-Host ""
Write-Host "Commands:" -ForegroundColor Yellow
Write-Host "  View backend logs:   Receive-Job -Name AlgoBackend -Keep" -ForegroundColor Gray
Write-Host "  View frontend logs:  Receive-Job -Name AlgoFrontend -Keep" -ForegroundColor Gray
Write-Host "  Stop all services:   .\stop.ps1" -ForegroundColor Gray
Write-Host "  Check status:        Get-Job | Format-Table" -ForegroundColor Gray
Write-Host ""
Write-Host " All services started in background!" -ForegroundColor Green
Write-Host ""

