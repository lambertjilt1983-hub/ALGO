# Clean Backend Restart Script
Write-Host "🔄 CLEAN BACKEND RESTART" -ForegroundColor Yellow
Write-Host ("=" * 50) -ForegroundColor Gray

# Step 1: Kill all Python processes
Write-Host "`n1️⃣  Killing all Python processes..." -ForegroundColor Cyan
Get-Process python -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
Start-Sleep -Seconds 3
Write-Host "   ✓ Processes killed" -ForegroundColor Green

# Step 2: Clear ALL cache
Write-Host "`n2️⃣  Clearing Python cache..." -ForegroundColor Cyan
Set-Location F:\ALGO\backend
Get-ChildItem -Recurse -Filter *.pyc -ErrorAction SilentlyContinue | Remove-Item -Force
Get-ChildItem -Recurse -Directory -Filter __pycache__ -ErrorAction SilentlyContinue | Remove-Item -Recurse -Force
Write-Host "   ✓ Cache cleared" -ForegroundColor Green

# Step 3: Verify correct source code
Write-Host "`n3️⃣  Verifying source code..." -ForegroundColor Cyan
$content = Get-Content "app\routes\auto_trading_simple.py" -Raw
if ($content -match "25157") {
    Write-Host "   ✓ Source has correct NIFTY value (25157.50)" -ForegroundColor Green
} else {
    Write-Host "   ✗ WARNING: Source may have incorrect values!" -ForegroundColor Red
}

# Step 4: Start backend
Write-Host "`n4️⃣  Starting backend server..." -ForegroundColor Cyan
$env:PYTHONPATH = "F:\ALGO\backend"
Write-Host "   Starting on http://0.0.0.0:8002" -ForegroundColor Gray
Write-Host ("=" * 50) -ForegroundColor Gray
Write-Host ""

F:\ALGO\.venv\Scripts\python.exe -m uvicorn app.main:app --host 0.0.0.0 --port 8002 --reload
