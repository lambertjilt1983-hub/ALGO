# AlgoTrade Pro - Production Deployment Script for Windows
# Run with: powershell -ExecutionPolicy Bypass -File deploy.ps1

Write-Host "🚀 AlgoTrade Pro - Production Deployment" -ForegroundColor Cyan
Write-Host "=========================================" -ForegroundColor Cyan

# Check if Docker is installed
if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    Write-Host "❌ Docker is not installed!" -ForegroundColor Red
    Write-Host "Please install Docker Desktop from: https://www.docker.com/products/docker-desktop" -ForegroundColor Yellow
    exit 1
}

# Check if .env exists
if (-not (Test-Path .env)) {
    Write-Host "⚠️  .env file not found!" -ForegroundColor Yellow
    Write-Host "Creating from template..." -ForegroundColor Yellow
    Copy-Item .env.production.example .env
    
    # Generate secret keys
    Write-Host "🔐 Generating secure keys..." -ForegroundColor Green
    $secretKey = -join ((48..57) + (65..90) + (97..122) | Get-Random -Count 64 | ForEach-Object {[char]$_})
    $encryptionKey = -join ((48..57) + (65..90) + (97..122) | Get-Random -Count 32 | ForEach-Object {[char]$_})
    
    # Update .env file
    (Get-Content .env) -replace 'GENERATE_RANDOM_64_CHAR_STRING_HERE', $secretKey | Set-Content .env
    (Get-Content .env) -replace 'GENERATE_RANDOM_32_CHAR_STRING_HERE', $encryptionKey | Set-Content .env
    
    Write-Host "✅ .env file created with secure keys" -ForegroundColor Green
    Write-Host ""
    Write-Host "⚠️  IMPORTANT: Edit .env and add your:" -ForegroundColor Yellow
    Write-Host "   - Domain name" -ForegroundColor Yellow
    Write-Host "   - Email for SSL" -ForegroundColor Yellow
    Write-Host "   - Database password" -ForegroundColor Yellow
    Write-Host "   - Broker API keys" -ForegroundColor Yellow
    Write-Host ""
    Read-Host "Press Enter after updating .env file"
}

# Setup directories
Write-Host "🔧 Setting up directories..." -ForegroundColor Green
New-Item -ItemType Directory -Force -Path traefik/logs | Out-Null
New-Item -ItemType File -Force -Path traefik/acme.json | Out-Null
New-Item -ItemType Directory -Force -Path backups | Out-Null

# Pull images
Write-Host "📥 Pulling Docker images..." -ForegroundColor Green
docker compose -f docker-compose.production.yml pull

# Start services
Write-Host "🚀 Starting services..." -ForegroundColor Green
docker compose -f docker-compose.production.yml up -d

# Wait for services
Write-Host "⏳ Waiting for services to start..." -ForegroundColor Yellow
Start-Sleep -Seconds 10

# Check status
Write-Host ""
Write-Host "📊 Service Status:" -ForegroundColor Cyan
docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"

Write-Host ""
Write-Host "✅ Deployment complete!" -ForegroundColor Green
Write-Host ""
Write-Host "🌐 Access your application:" -ForegroundColor Cyan
Write-Host "   Frontend: https://yourdomain.com" -ForegroundColor White
Write-Host "   Backend API: https://api.yourdomain.com" -ForegroundColor White
Write-Host "   API Docs: https://api.yourdomain.com/docs" -ForegroundColor White
Write-Host ""
Write-Host "📝 Next steps:" -ForegroundColor Yellow
Write-Host "   1. Update DNS records to point to this server" -ForegroundColor White
Write-Host "   2. Wait for SSL certificates (2-5 minutes)" -ForegroundColor White
Write-Host "   3. Test the application" -ForegroundColor White
Write-Host ""
Write-Host "📊 Useful commands:" -ForegroundColor Cyan
Write-Host "   View logs: docker compose -f docker-compose.production.yml logs -f" -ForegroundColor White
Write-Host "   Restart: docker compose -f docker-compose.production.yml restart" -ForegroundColor White
Write-Host "   Stop: docker compose -f docker-compose.production.yml down" -ForegroundColor White
