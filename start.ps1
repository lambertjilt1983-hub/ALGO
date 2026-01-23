Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "         AlgoTrade Pro v1.0.0 - Starting..." -ForegroundColor Green
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host ""

# Step 1: Clean up all Python and Node processes
Write-Host "[1/5] Cleaning up existing processes..." -ForegroundColor Yellow
Get-Process -Name python,node,uvicorn -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
Start-Sleep -Seconds 3

# Step 2: Force kill processes on required ports
Write-Host "[2/5] Freeing up ports..." -ForegroundColor Yellow

# Kill port 8002 (Backend)
$port8002 = Get-NetTCPConnection -LocalPort 8002 -State Listen -ErrorAction SilentlyContinue
if ($port8002) {
    Write-Host "   Killing process on port 8002..." -ForegroundColor Red
    $port8002 | ForEach-Object { Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue }
    Start-Sleep -Seconds 2
}

# Kill port 3000 (Frontend)
$port3000 = Get-NetTCPConnection -LocalPort 3000 -State Listen -ErrorAction SilentlyContinue
if ($port3000) {
    Write-Host "   Killing process on port 3000..." -ForegroundColor Red
    $port3000 | ForEach-Object { Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue }
    Start-Sleep -Seconds 2
}

# Kill port 5173 (Vite dev server)
$port5173 = Get-NetTCPConnection -LocalPort 5173 -State Listen -ErrorAction SilentlyContinue
if ($port5173) {
    Write-Host "   Killing process on port 5173..." -ForegroundColor Red
    $port5173 | ForEach-Object { Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue }
    Start-Sleep -Seconds 2
}

Write-Host "   All ports cleared" -ForegroundColor Green
Start-Sleep -Seconds 1

# Step 3: Start Backend
Write-Host "[3/5] Starting FastAPI Backend..." -ForegroundColor Yellow

# Clean __pycache__ directories
Get-ChildItem -Path "F:\ALGO\backend" -Recurse -Directory -Filter __pycache__ -ErrorAction SilentlyContinue | Remove-Item -Recurse -Force -ErrorAction SilentlyContinue

$backendCommand = "cd F:\ALGO\backend; `$env:PYTHONPATH='F:\ALGO\backend'; F:\ALGO\.venv\Scripts\python.exe -B -m uvicorn app.main:app --host 0.0.0.0 --port 8002 --reload"
Start-Process powershell -ArgumentList "-NoExit","-Command",$backendCommand -WindowStyle Normal

Write-Host "   Waiting for backend to start..." -ForegroundColor Cyan
Start-Sleep -Seconds 8

# Verify backend with more attempts
$backendOK = $false
for ($i = 1; $i -le 20; $i++) {
    try {
        $resp = Invoke-WebRequest -Uri "http://localhost:8002/health" -UseBasicParsing -TimeoutSec 3 -ErrorAction SilentlyContinue
        if ($resp.StatusCode -eq 200) {
            $backendOK = $true
            Write-Host "   Backend ready!" -ForegroundColor Green
            break
        }
    } catch {
        Write-Host "   Attempt $i/20..." -ForegroundColor Gray
        Start-Sleep -Seconds 2
    }
}

if (-not $backendOK) {
    Write-Host "   Backend failed to start. Check the backend terminal for errors." -ForegroundColor Red
    Write-Host "   Common issues:" -ForegroundColor Yellow
    Write-Host "     - Database not running" -ForegroundColor Yellow
    Write-Host "     - Missing dependencies (run: pip install -r backend/requirements.txt)" -ForegroundColor Yellow
    Write-Host "     - Check logs in backend/logs/" -ForegroundColor Yellow
    exit 1
}

# Step 4: Start Frontend
Write-Host "[4/5] Starting React Frontend..." -ForegroundColor Yellow
$frontendCommand = "cd F:\ALGO\frontend; npm run dev"
Start-Process powershell -ArgumentList "-NoExit","-Command",$frontendCommand -WindowStyle Normal

Write-Host "   Waiting for frontend to start..." -ForegroundColor Cyan
Start-Sleep -Seconds 8

# Verify frontend (check both possible ports)
$frontendOK = $false
$frontendUrl = ""

for ($i = 1; $i -le 20; $i++) {
    # Try port 3000
    try {
        $resp = Invoke-WebRequest -Uri "http://localhost:3000" -UseBasicParsing -TimeoutSec 2 -ErrorAction SilentlyContinue
        if ($resp.StatusCode -eq 200) {
            $frontendOK = $true
            $frontendUrl = "http://localhost:3000"
            Write-Host "   Frontend ready at port 3000!" -ForegroundColor Green
            break
        }
    } catch { }
    
    # Try port 5173 (Vite default)
    try {
        $resp = Invoke-WebRequest -Uri "http://localhost:5173" -UseBasicParsing -TimeoutSec 2 -ErrorAction SilentlyContinue
        if ($resp.StatusCode -eq 200) {
            $frontendOK = $true
            $frontendUrl = "http://localhost:5173"
            Write-Host "   Frontend ready at port 5173!" -ForegroundColor Green
            break
        }
    } catch { }
    
    Write-Host "   Attempt $i/20..." -ForegroundColor Gray
    Start-Sleep -Seconds 2
}

if (-not $frontendOK) {
    Write-Host "   Frontend failed to start. Check the frontend terminal for errors." -ForegroundColor Red
    Write-Host "   Common issues:" -ForegroundColor Yellow
    Write-Host "     - Node modules not installed (run: cd frontend; npm install)" -ForegroundColor Yellow
    Write-Host "     - Port already in use" -ForegroundColor Yellow
}

# Step 5: Summary
Write-Host ""
Write-Host "[5/5] Startup Complete!" -ForegroundColor Green
Write-Host ""
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "            AlgoTrade Pro - System Status" -ForegroundColor Green
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host ""

if ($frontendUrl) {
    Write-Host "  Dashboard:     $frontendUrl" -ForegroundColor White
} else {
    Write-Host "  Dashboard:     http://localhost:3000 or http://localhost:5173" -ForegroundColor White
}

Write-Host "  API Backend:   http://localhost:8002" -ForegroundColor White
Write-Host "  API Docs:      http://localhost:8002/docs" -ForegroundColor White
Write-Host "  Health Check:  http://localhost:8002/health" -ForegroundColor White
Write-Host ""
Write-Host "  Default Login:" -ForegroundColor Yellow
Write-Host "    Username: test" -ForegroundColor White
Write-Host "    Password: test123" -ForegroundColor White
Write-Host ""
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host ""

if ($frontendOK) {
    Write-Host "Opening dashboard in browser..." -ForegroundColor Cyan
    Start-Sleep -Seconds 2
    Start-Process $frontendUrl
}

Write-Host ""
Write-Host "All systems operational! Happy Trading!" -ForegroundColor Green
Write-Host ""
Write-Host "Press Ctrl+C in the backend/frontend terminals to stop servers." -ForegroundColor Gray
Write-Host ""
