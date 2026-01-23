#!/bin/bash

echo "🚀 AlgoTrade Pro - Production Deployment Script"
echo "================================================"

# Check if running as root
if [ "$EUID" -ne 0 ]; then 
    echo "❌ Please run as root (use sudo)"
    exit 1
fi

# Install Docker if not installed
if ! command -v docker &> /dev/null; then
    echo "📦 Installing Docker..."
    curl -fsSL https://get.docker.com -o get-docker.sh
    sh get-docker.sh
    usermod -aG docker $SUDO_USER
fi

# Install Docker Compose
if ! docker compose version &> /dev/null; then
    echo "📦 Installing Docker Compose..."
    apt-get update
    apt-get install -y docker-compose-plugin
fi

# Check if .env exists
if [ ! -f .env ]; then
    echo "⚠️  .env file not found!"
    echo "Creating from template..."
    cp .env.production.example .env
    
    # Generate secret keys
    echo "🔐 Generating secure keys..."
    SECRET_KEY=$(openssl rand -hex 32)
    ENCRYPTION_KEY=$(openssl rand -hex 16)
    
    # Update .env file
    sed -i "s/GENERATE_RANDOM_64_CHAR_STRING_HERE/$SECRET_KEY/" .env
    sed -i "s/GENERATE_RANDOM_32_CHAR_STRING_HERE/$ENCRYPTION_KEY/" .env
    
    echo "✅ .env file created with secure keys"
    echo "⚠️  IMPORTANT: Edit .env and add your:"
    echo "   - Domain name"
    echo "   - Email for SSL"
    echo "   - Database password"
    echo "   - Broker API keys"
    echo ""
    read -p "Press Enter after updating .env file..."
fi

# Setup Traefik
echo "🔧 Setting up Traefik (SSL/HTTPS)..."
mkdir -p traefik/logs
touch traefik/acme.json
chmod 600 traefik/acme.json

# Setup backup directory
echo "💾 Setting up backup directory..."
mkdir -p backups

# Pull images
echo "📥 Pulling Docker images..."
docker compose -f docker-compose.production.yml pull

# Start services
echo "🚀 Starting services..."
docker compose -f docker-compose.production.yml up -d

# Wait for services to be ready
echo "⏳ Waiting for services to start..."
sleep 10

# Check status
echo ""
echo "📊 Service Status:"
docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"

echo ""
echo "✅ Deployment complete!"
echo ""
echo "🌐 Access your application:"
echo "   Frontend: https://yourdomain.com"
echo "   Backend API: https://api.yourdomain.com"
echo "   API Docs: https://api.yourdomain.com/docs"
echo ""
echo "📝 Next steps:"
echo "   1. Update DNS records to point to this server"
echo "   2. Wait for SSL certificates to be issued (2-5 minutes)"
echo "   3. Test the application"
echo ""
echo "📊 Useful commands:"
echo "   View logs: docker compose -f docker-compose.production.yml logs -f"
echo "   Restart: docker compose -f docker-compose.production.yml restart"
echo "   Stop: docker compose -f docker-compose.production.yml down"
echo "   Backup DB: docker exec algotrade_db_prod pg_dump -U algotrade trading_db > backup.sql"
