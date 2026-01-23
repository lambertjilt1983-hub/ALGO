# AlgoTrade Pro - Quick Stop Script
# ===================================

Write-Host "═══════════════════════════════════════════════════════════" -ForegroundColor Red
Write-Host "         Stopping AlgoTrade Pro Servers..." -ForegroundColor Yellow
Write-Host "═══════════════════════════════════════════════════════════" -ForegroundColor Red
Write-Host ""

# Kill Python processes (Backend)
Write-Host "[1/2] Stopping Backend Server..." -ForegroundColor Yellow
$pythonProcesses = Get-Process -Name python -ErrorAction SilentlyContinue | Where-Object {$_.Path -like '*ALGO*'}
if ($pythonProcesses) {
    $pythonProcesses | Stop-Process -Force
    Write-Host "   ✓ Backend stopped" -ForegroundColor Green
} else {
    Write-Host "   ℹ No backend process found" -ForegroundColor Gray
}

# Kill Node processes (Frontend)
Write-Host "[2/2] Stopping Frontend Server..." -ForegroundColor Yellow
$nodeProcesses = Get-Process -Name node -ErrorAction SilentlyContinue | Where-Object {$_.Path -like '*ALGO*'}
if ($nodeProcesses) {
    $nodeProcesses | Stop-Process -Force
    Write-Host "   ✓ Frontend stopped" -ForegroundColor Green
} else {
    Write-Host "   ℹ No frontend process found" -ForegroundColor Gray
}

Write-Host ""
Write-Host "✓ All AlgoTrade Pro servers stopped" -ForegroundColor Green
Write-Host ""
