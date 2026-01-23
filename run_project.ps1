# AlgoTrade Pro - Complete Project Startup Script

Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "         AlgoTrade Pro - Complete Setup & Start" -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host ""

# Step 1: Setup database and create user
Write-Host "[1/4] Setting up database and user..." -ForegroundColor Yellow
$setupResult = & 'F:\ALGO\.venv\Scripts\python.exe' 'F:\ALGO\setup_db.py'
Write-Host $setupResult
if ($LASTEXITCODE -ne 0) {
    Write-Host "   Database setup failed!" -ForegroundColor Red
    exit 1
}
Write-Host ""

# Step 2: Kill existing processes
Write-Host "[2/5] Cleaning up existing processes..." -ForegroundColor Yellow
$port8000 = Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue | Select-Object -First 1
if ($port8000) {
    Stop-Process -Id $port8000.OwningProcess -Force -ErrorAction SilentlyContinue
    Write-Host "   Killed process on port 8000" -ForegroundColor Green
}
$port3000 = Get-NetTCPConnection -LocalPort 3000 -State Listen -ErrorAction SilentlyContinue | Select-Object -First 1
if ($port3000) {
    Stop-Process -Id $port3000.OwningProcess -Force -ErrorAction SilentlyContinue
    Write-Host "   Killed process on port 3000" -ForegroundColor Green
}
$port5173 = Get-NetTCPConnection -LocalPort 5173 -State Listen -ErrorAction SilentlyContinue | Select-Object -First 1
if ($port5173) {
    Stop-Process -Id $port5173.OwningProcess -Force -ErrorAction SilentlyContinue
    Write-Host "   Killed process on port 5173" -ForegroundColor Green
}
Start-Sleep -Seconds 2
Write-Host ""

# Step 3: Start Backend
Write-Host "[3/5] Starting FastAPI Backend..." -ForegroundColor Yellow
$backendCmd = "cd F:\ALGO\backend; `$env:PYTHONPATH='F:\ALGO\backend'; F:\ALGO\.venv\Scripts\python.exe -m uvicorn app.main:app --host localhost --port 8000 --reload"
Start-Process powershell -ArgumentList "-NoExit", "-Command", $backendCmd -WindowStyle Hidden

Write-Host "   Waiting for backend..." -ForegroundColor Gray
$backendReady = $false
for ($i = 1; $i -le 30; $i++) {
    Start-Sleep -Seconds 1
    try {
        $response = Invoke-WebRequest -Uri 'http://localhost:8000/docs' -TimeoutSec 2 -ErrorAction SilentlyContinue
        if ($response.StatusCode -eq 200) {
            $backendReady = $true
            break
        }
    } catch {}
    Write-Host "   ." -NoNewline -ForegroundColor Gray
}
Write-Host ""

if ($backendReady) {
    Write-Host "   Backend running on http://localhost:8000" -ForegroundColor Green
} else {
    Write-Host "   Backend may still be starting..." -ForegroundColor Yellow
}
Write-Host ""

# Step 4: Start Frontend
Write-Host "[4/5] Starting Vite Frontend..." -ForegroundColor Yellow
$frontendCmd = "cd F:\ALGO\frontend; npm run dev"
Start-Process powershell -ArgumentList "-NoExit", "-Command", $frontendCmd -WindowStyle Hidden

Write-Host "   Waiting for frontend..." -ForegroundColor Gray
$frontendReady = $false
for ($i = 1; $i -le 20; $i++) {
    Start-Sleep -Seconds 1
    try {
        $response = Invoke-WebRequest -Uri 'http://localhost:3000' -TimeoutSec 2 -ErrorAction SilentlyContinue
        if ($response.StatusCode -eq 200) {
            $frontendReady = $true
            break
        }
    } catch {}
    Write-Host "   ." -NoNewline -ForegroundColor Gray
}
Write-Host ""

if ($frontendReady) {
    Write-Host "   Frontend running on http://localhost:3000" -ForegroundColor Green
} else {
    Write-Host "   Frontend may still be starting..." -ForegroundColor Yellow
}

Write-Host ""

# Step 5: Start Zerodha Redirect Server
Write-Host "[5/5] Starting Zerodha Redirect Server..." -ForegroundColor Yellow
$redirectCmd = "cd F:\ALGO\redirect_server; python -m http.server 5173"
Start-Process powershell -ArgumentList "-NoExit", "-Command", $redirectCmd -WindowStyle Hidden
Start-Sleep -Seconds 2
Write-Host "   Redirect server running on http://localhost:5173" -ForegroundColor Green

Write-Host ""
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "                    SETUP COMPLETE!" -ForegroundColor Green
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Frontend: http://localhost:3000" -ForegroundColor White
Write-Host "Backend:  http://localhost:8000" -ForegroundColor White
Write-Host "API Docs: http://localhost:8000/docs" -ForegroundColor White
Write-Host ""
Write-Host "Login Credentials:" -ForegroundColor Yellow
Write-Host "   Username: test" -ForegroundColor White
Write-Host "   Password: test123" -ForegroundColor White
Write-Host ""
Write-Host "Servers are running in background (hidden)" -ForegroundColor Cyan
Write-Host "To stop: Run stop.ps1 or close PowerShell processes" -ForegroundColor Cyan
Write-Host ""

# Auto-open browser
Start-Process 'http://localhost:3000'
