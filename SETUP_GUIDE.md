# AlgoTrade Pro - Complete Setup Guide
# =====================================

## 🎯 Quick Setup (5 Minutes)

### Step 1: Install Dependencies

# Backend
cd F:\ALGO\backend
pip install -r requirements.txt

# Frontend
cd F:\ALGO\frontend
npm install

### Step 2: Configure Environment

# Copy example environment file
Copy-Item F:\ALGO\.env.example F:\ALGO\backend\.env

# Edit .env file with your actual credentials
notepad F:\ALGO\backend\.env

### Step 3: Initialize Database

cd F:\ALGO\backend
python -c "from app.core.database import init_db; init_db(); print('Database initialized!')"

### Step 4: Create Admin User

python -c @"
from app.core.database import SessionLocal
from app.models.auth import User
from app.core.security import encryption_manager

db = SessionLocal()
user = User(
    username='admin',
    email='admin@algotradepro.com',
    hashed_password=encryption_manager.hash_password('admin123')
)
db.add(user)
db.commit()
print('Admin user created!')
"@

### Step 5: Start Application

# Use automated script
.\start.ps1

# Or manually in two terminals:
# Terminal 1:
cd F:\ALGO\backend
$env:PYTHONPATH='F:\ALGO\backend'
python -m uvicorn app.main:app --host localhost --port 8000 --reload

# Terminal 2:
cd F:\ALGO\frontend
npm run dev

---

## 🔐 Zerodha Setup

### 1. Create Kite Connect App
1. Visit https://developers.kite.trade/
2. Login with your Zerodha account
3. Click "Create New App"
4. Fill in details:
   - App Name: AlgoTrade Pro
   - Redirect URL: http://localhost:8000/brokers/zerodha/callback
   - Description: Personal algorithmic trading platform
5. Click "Create"
6. Note down your **API Key** and **API Secret**

### 2. Configure AlgoTrade Pro
1. Login to dashboard: http://localhost:3000
2. Click "+ Connect Broker"
3. Select "Zerodha"
4. Enter your API Key and API Secret
5. Click "Save Credentials"

### 3. Authenticate
1. Click "Login to Zerodha" on your broker card
2. Login with your Zerodha credentials
3. Authorize the app
4. You'll be redirected back with access token

---

## 📊 Testing Your Setup

### 1. Health Check
curl http://localhost:8000/health

### 2. API Documentation
Open: http://localhost:8000/docs

### 3. Login Test
curl -X POST http://localhost:8000/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"test","password":"test123"}'

### 4. Balance Check
# Get token from login, then:
curl http://localhost:8000/brokers/balance/1 \
  -H "Authorization: Bearer YOUR_TOKEN_HERE"

---

## 🎨 UI Customization

### Change Theme Colors
Edit: F:\ALGO\frontend\src\index.css

### Modify Dashboard Layout
Edit: F:\ALGO\frontend\src\Dashboard.jsx

### Add New Broker
1. Edit: F:\ALGO\backend\app\routes\broker.py
2. Add broker-specific API integration
3. Update frontend broker selection

---

## 🚀 Production Deployment

### Backend (Ubuntu/Linux)

# Install dependencies
sudo apt update
sudo apt install python3.12 python3-pip nginx supervisor

# Setup virtual environment
cd /var/www/algotrade
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Configure Supervisor
sudo nano /etc/supervisor/conf.d/algotrade.conf

[program:algotrade]
directory=/var/www/algotrade/backend
command=/var/www/algotrade/venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000
user=www-data
autostart=true
autorestart=true
stderr_logfile=/var/log/algotrade/err.log
stdout_logfile=/var/log/algotrade/out.log

# Start service
sudo supervisorctl reread
sudo supervisorctl update
sudo supervisorctl start algotrade

### Frontend (Static Hosting)

# Build for production
cd F:\ALGO\frontend
npm run build

# Deploy to:
# - Vercel: vercel deploy
# - Netlify: netlify deploy
# - AWS S3: aws s3 sync dist/ s3://your-bucket

### Nginx Configuration

server {
    listen 80;
    server_name yourdomain.com;

    location /api {
        proxy_pass http://localhost:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }

    location / {
        root /var/www/algotrade/frontend/dist;
        try_files $uri /index.html;
    }
}

---

## 📈 Performance Optimization

### Backend
1. Use PostgreSQL instead of SQLite for production
2. Enable Redis caching
3. Implement connection pooling
4. Add rate limiting
5. Use Gunicorn with multiple workers

### Frontend
1. Code splitting with lazy loading
2. Enable gzip compression
3. Optimize images
4. Use CDN for static assets
5. Implement service workers for PWA

---

## 🔒 Security Checklist

- [ ] Change default SECRET_KEY in .env
- [ ] Use strong passwords
- [ ] Enable HTTPS in production
- [ ] Configure CORS properly
- [ ] Implement rate limiting
- [ ] Add CSRF protection
- [ ] Enable SQL injection protection (ORM)
- [ ] Sanitize user inputs
- [ ] Implement API key rotation
- [ ] Setup backup and disaster recovery
- [ ] Enable audit logging
- [ ] Use environment variables for secrets
- [ ] Implement 2FA for user accounts
- [ ] Regular security audits

---

## 🐛 Common Issues & Solutions

### Issue: Port already in use
Solution:
```powershell
.\stop.ps1
# Or manually:
Get-Process -Name python,node | Stop-Process -Force
```

### Issue: Database locked
Solution:
```powershell
cd F:\ALGO\backend
Remove-Item algotrade.db
python -c "from app.core.database import init_db; init_db()"
```

### Issue: Module not found
Solution:
```powershell
cd F:\ALGO\backend
pip install -r requirements.txt --upgrade
```

### Issue: npm install fails
Solution:
```powershell
cd F:\ALGO\frontend
Remove-Item -Recurse -Force node_modules
Remove-Item package-lock.json
npm install
```

### Issue: CORS errors
Solution:
1. Ensure backend is on localhost:8000
2. Ensure frontend is on localhost:3000
3. Check F:\ALGO\backend\app\main.py CORS settings
4. Restart both servers

---

## 📞 Support & Resources

### Documentation
- FastAPI: https://fastapi.tiangolo.com/
- React: https://react.dev/
- Kite Connect: https://kite.trade/docs/connect/v3/

### Community
- GitHub Issues: [Report bugs]
- Discord: [Join community]
- Stack Overflow: Tag `algotrade-pro`

### Professional Support
- Email: support@algotradepro.com
- Priority Support: Available for enterprise users

---

## 📝 Development Workflow

### 1. Create Feature Branch
```bash
git checkout -b feature/amazing-new-feature
```

### 2. Make Changes
- Edit backend code in `backend/app/`
- Edit frontend code in `frontend/src/`
- Test changes locally

### 3. Test
```powershell
# Backend tests
cd F:\ALGO\backend
pytest

# Frontend tests
cd F:\ALGO\frontend
npm test
```

### 4. Commit & Push
```bash
git add .
git commit -m "Add amazing new feature"
git push origin feature/amazing-new-feature
```

### 5. Create Pull Request
- Open PR on GitHub
- Request code review
- Merge after approval

---

## 🎯 Next Steps

1. ✅ Complete setup (you're here!)
2. 📖 Read API documentation: http://localhost:8000/docs
3. 🔐 Setup Zerodha Kite Connect
4. 📊 Connect your broker account
5. 💼 Test with paper trading
6. 📈 Create your first strategy
7. 🚀 Go live (after thorough testing!)

---

**Happy Trading! 🚀📈**
