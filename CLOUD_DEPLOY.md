# Quick Deploy to Cloud Platforms

## 1. Deploy to Railway.app (Easiest)

### Backend
1. Go to [railway.app](https://railway.app)
2. Click "Start a New Project"
3. Select "Deploy from GitHub repo"
4. Select your repository
5. Railway will auto-detect Python
6. Add PostgreSQL database from marketplace
7. Set environment variables in Railway dashboard
8. Deploy!

### Frontend
1. Create new service
2. Select same repository
3. Set root directory to `frontend`
4. Add build command: `npm run build`
5. Add start command: `npm run preview`
6. Set VITE_API_URL to your backend URL
7. Deploy!

**Cost**: ~$20-25/month

---

## 2. Deploy to Render.com

### Backend
```bash
# 1. Create render.yaml in root
services:
  - type: web
    name: algotrade-backend
    runtime: python
    buildCommand: "cd backend && pip install -r requirements.txt"
    startCommand: "cd backend && uvicorn app.main:app --host 0.0.0.0 --port $PORT"
    envVars:
      - key: DATABASE_URL
        fromDatabase:
          name: algotrade-db
          property: connectionString
      - key: SECRET_KEY
        generateValue: true
      - key: ENCRYPTION_KEY
        generateValue: true

  - type: web
    name: algotrade-frontend
    runtime: node
    buildCommand: "cd frontend && npm install && npm run build"
    staticPublishPath: frontend/dist
    
databases:
  - name: algotrade-db
    databaseName: trading_db
    user: algotrade
```

2. Push to GitHub
3. Connect to Render
4. Deploy automatically

**Cost**: ~$25-30/month

---

## 3. Deploy to Vercel (Frontend) + Railway (Backend)

### Frontend on Vercel
```bash
# Install Vercel CLI
npm i -g vercel

# Deploy from frontend directory
cd frontend
vercel --prod
```

### Backend on Railway
Follow Railway instructions above

**Cost**: Free (Vercel) + $10-15/month (Railway)

---

## 4. Deploy to DigitalOcean App Platform

1. Create new app
2. Connect GitHub repository
3. DigitalOcean auto-detects components
4. Add PostgreSQL database
5. Configure environment variables
6. Deploy

**Cost**: ~$30-40/month

---

## 5. Deploy to Heroku

```bash
# Install Heroku CLI
npm install -g heroku

# Login
heroku login

# Create app
heroku create algotrade-backend

# Add PostgreSQL
heroku addons:create heroku-postgresql:mini

# Set environment variables
heroku config:set SECRET_KEY=your-secret-key
heroku config:set ENCRYPTION_KEY=your-encryption-key

# Deploy
git push heroku main
```

**Cost**: ~$25-50/month

---

## 6. Deploy to AWS Elastic Beanstalk

```bash
# Install EB CLI
pip install awsebcli

# Initialize
eb init -p python-3.11 algotrade-backend

# Create environment
eb create algotrade-prod

# Deploy
eb deploy
```

**Cost**: ~$30-60/month

---

## Comparison Table

| Platform | Difficulty | Cost/Month | Free Tier | SSL | Auto-Deploy |
|----------|-----------|------------|-----------|-----|-------------|
| Railway | ⭐ Easy | $20-25 | ✅ $5 credit | ✅ | ✅ |
| Render | ⭐ Easy | $25-30 | ✅ Limited | ✅ | ✅ |
| Vercel + Railway | ⭐⭐ Medium | $10-15 | ✅ Vercel free | ✅ | ✅ |
| DigitalOcean | ⭐⭐ Medium | $30-40 | ❌ | ✅ | ✅ |
| Heroku | ⭐⭐ Medium | $25-50 | ❌ | ✅ | ✅ |
| AWS EB | ⭐⭐⭐ Hard | $30-60 | ✅ 12 months | ✅ | ✅ |
| VPS (Self) | ⭐⭐⭐⭐ Expert | $12-24 | ❌ | ⚙️ Manual | ⚙️ Manual |

---

## Recommended for Beginners

**Railway.app** - Easiest setup, good pricing, automatic SSL, GitHub integration

## Recommended for Production

**VPS (DigitalOcean/Hetzner)** - Full control, better pricing at scale, custom configurations

## Recommended for Scaling

**AWS/GCP/Azure** - Enterprise-grade, highly scalable, many services
