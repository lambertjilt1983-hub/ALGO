@echo off
REM AlgoTrade Pro - Setup Script for Windows

echo 🚀 AlgoTrade Pro - Setup Script
echo ================================

REM Check Python version
echo ✓ Checking Python version...
python --version

REM Create virtual environment
echo ✓ Creating virtual environment...
python -m venv venv

REM Activate virtual environment
echo ✓ Activating virtual environment...
call venv\Scripts\activate.bat

REM Install backend dependencies
echo ✓ Installing backend dependencies...
cd backend
pip install -r requirements.txt -q

REM Create .env if it doesn't exist
if not exist ..\\.env (
    echo ✓ Creating .env file...
    copy ..\\.env.example ..\\.env
    echo ⚠️  Please update .env with your settings
)

cd ..

REM Setup frontend
echo ✓ Setting up frontend...
cd frontend
call npm install
cd ..

echo.
echo ✅ Setup completed successfully!
echo.
echo 📝 Next steps:
echo 1. Update .env with your broker API credentials
echo 2. Setup PostgreSQL database if not using docker-compose
echo 3. Run migrations: python -m alembic upgrade head
echo 4. Start backend: python -m app.main
echo 5. In another terminal, start frontend: cd frontend && npm run dev
echo.
echo 🌐 Access:
echo    Frontend: http://localhost:3000
echo    Backend API: http://localhost:8000
echo    API Docs: http://localhost:8000/docs
echo.
echo Or use Docker Compose:
echo    docker-compose up -d
echo.
