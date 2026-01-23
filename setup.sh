#!/bin/bash
# AlgoTrade Pro - Setup Script

set -e

echo "🚀 AlgoTrade Pro - Setup Script"
echo "================================"

# Check Python version
echo "✓ Checking Python version..."
python --version

# Create virtual environment
echo "✓ Creating virtual environment..."
python -m venv venv

# Activate virtual environment
echo "✓ Activating virtual environment..."
source venv/bin/activate 2>/dev/null || . venv/Scripts/activate 2>/dev/null

# Install backend dependencies
echo "✓ Installing backend dependencies..."
cd backend
pip install -r requirements.txt -q

# Create .env if it doesn't exist
if [ ! -f ../.env ]; then
    echo "✓ Creating .env file..."
    cp ../.env.example ../.env
    echo "⚠️  Please update .env with your settings"
fi

# Generate secret keys if needed
echo "✓ Generating security keys..."
python << 'EOF'
import os
import secrets
from cryptography.fernet import Fernet

env_file = "../.env"

# Check and update SECRET_KEY if placeholder
with open(env_file, 'r') as f:
    content = f.read()

if 'your-super-secret-key' in content:
    secret_key = secrets.token_urlsafe(32)
    content = content.replace('SECRET_KEY=your-super-secret-key-change-in-production',
                             f'SECRET_KEY={secret_key}')

if 'your-32-char-encryption-key' in content:
    encryption_key = Fernet.generate_key().decode()
    content = content.replace('ENCRYPTION_KEY=your-32-char-encryption-key-here',
                             f'ENCRYPTION_KEY={encryption_key}')

with open(env_file, 'w') as f:
    f.write(content)

print("✓ Security keys generated")
EOF

cd ..

# Setup frontend
echo "✓ Setting up frontend..."
cd frontend
npm install -q 2>/dev/null || npm install

cd ..

echo ""
echo "✅ Setup completed successfully!"
echo ""
echo "📝 Next steps:"
echo "1. Update .env with your broker API credentials"
echo "2. Setup PostgreSQL database (if not using docker-compose)"
echo "3. Run migrations: python -m alembic upgrade head"
echo "4. Start backend: python -m app.main"
echo "5. In another terminal, start frontend: cd frontend && npm run dev"
echo ""
echo "🌐 Access:"
echo "   Frontend: http://localhost:3000"
echo "   Backend API: http://localhost:8000"
echo "   API Docs: http://localhost:8000/docs"
echo ""
echo "Or use Docker Compose:"
echo "   docker-compose up -d"
echo ""
