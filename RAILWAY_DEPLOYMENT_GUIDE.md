# Railway Deployment Guide - Complete Setup

## Quick Summary

This guide walks you through deploying AlgoTrade Pro on Railway with both backend (FastAPI) and frontend (React/Vite) running correctly.

---

## Part 1: Backend Service (FastAPI)

### Step 1: Deploy Backend Service

1. Go to [Railway Dashboard](https://railway.app)
2. Click **New Project** → **Deploy from GitHub**
3. Connect your GitHub repo and select the project
4. Railway will auto-detect Python and create a backend service

### Step 2: Configure Backend Service Variables

Go to **Backend Service → Variables** and add these:

| Name | Value | Notes |
|------|-------|-------|
| `FERNET_KEY` | `(your-32-byte-base64-key)` | Generate: `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"` |
| `ENCRYPTION_KEY` | `(your-encryption-key)` | Can be same as FERNET_KEY or different |
| `DATABASE_URL` | `(postgresql://...)` | Use Railway PostgreSQL or external DB |
| `ALLOWED_ORIGINS` | `https://your-frontend.up.railway.app` | Copy frontend URL here (set after frontend deploys) |
| `SECRET_KEY` | `(your-secret-key)` | Min 32 characters, random |
| `ALGORITHM` | `HS256` | Keep as is |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | `30` | Token expiry in minutes |
| `REFRESH_TOKEN_EXPIRE_DAYS` | `7` | Refresh token expiry in days |
| `ENVIRONMENT` | `production` | Keep as production for Railway |
| `ZERODHA_API_KEY` | `(your-key)` | Optional: if using Zerodha broker |
| `ZERODHA_API_SECRET` | `(your-secret)` | Optional: if using Zerodha broker |
| `PAPER_TRADING_MODE` | `true` | Keep as true unless live trading tested |
| `LOG_LEVEL` | `INFO` | Logging level |

### Step 3: Backend Start Command

Go to **Backend Service → Settings → Start Command** and set:

```bash
uvicorn app.main:app --host 0.0.0.0 --port $PORT
```

**Important:** Railway automatically assigns a port via `$PORT` variable. Do NOT hardcode 8000.

### Step 4: Copy Backend URL

Once deployed, copy your backend URL:
- Go to **Backend Service → Deployments**
- Copy the public URL (e.g., `https://algo-trade-backend-xyz.up.railway.app`)
- **Save this** - you'll need it for frontend config

---

## Part 2: Frontend Service (React/Vite)

### Step 1: Deploy Frontend Service

1. In Railway **New Project** (or same project)
2. Click **+ New** → **GitHub Repo** → select your repo again
3. Railway should detect Node.js and create frontend service

### Step 2: Configure Frontend Service Variables

Go to **Frontend Service → Variables** and add:

| Name | Value | Notes |
|------|-------|-------|
| `VITE_API_URL` | `https://your-backend.up.railway.app` | Paste backend URL from Step 1 |
| `VITE_APP_NAME` | `AlgoTrade Pro` | App name |
| `VITE_ENVIRONMENT` | `production` | Environment |
| `FRONTEND_PORT` | `$PORT` | Railway's dynamic port |

**For Create React App (instead of Vite):**
- Use `REACT_APP_API_URL` instead of `VITE_API_URL`

### Step 3: Frontend Start Command

Go to **Frontend Service → Settings → Start Command** and set:

**If using Vite:**
```bash
npm install && npm run build && npx serve -s dist -l $PORT
```

**If using Create React App:**
```bash
npm install && npm run build && npx serve -s build -l $PORT
```

### Step 4: Copy Frontend URL

Once deployed, copy your frontend URL:
- Go to **Frontend Service → Deployments**
- Copy the public URL (e.g., `https://algo-trade-frontend-xyz.up.railway.app`)

### Step 5: Update Backend's ALLOWED_ORIGINS

Go back to **Backend Service → Variables** and update:

```
ALLOWED_ORIGINS = https://your-frontend-url.up.railway.app
```

---

## Part 3: Database Setup (PostgreSQL)

### Option A: Use Railway PostgreSQL (Recommended)

1. In your Railway project, click **+ New**
2. Select **PostgreSQL**
3. Railway auto-adds `DATABASE_URL` variable to services

### Option B: External Database

1. Create PostgreSQL database on external provider (AWS RDS, Render, etc.)
2. Copy the connection string
3. Add to **Backend Service → Variables**:
```
DATABASE_URL = postgresql://user:password@host:5432/algotrade
```

---

## Part 4: Environment Variables Summary

### Critical Variables (MUST be set in Railway)

```
FERNET_KEY              ← Encryption key (generate fresh)
ENCRYPTION_KEY          ← Same as FERNET_KEY or different
DATABASE_URL            ← PostgreSQL connection string
ALLOWED_ORIGINS         ← Frontend URL (after frontend deployed)
SECRET_KEY              ← Random secret (min 32 chars)
VITE_API_URL            ← Backend URL (after backend deployed)
```

### How to Generate FERNET_KEY

Run this locally:

```bash
python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

Output example:
```
UtqK_4V8s_NjVGn-hEr6fGKdKvGx9W8lEqR5s-HZhDQ=
```

Copy this into Railway `FERNET_KEY` variable.

---

## Part 5: Deployment Checklist

- [ ] Backend service deployed with correct start command
- [ ] Backend variables set (FERNET_KEY, DATABASE_URL, etc.)
- [ ] Frontend service deployed with correct start command
- [ ] Frontend variables set (VITE_API_URL pointing to backend)
- [ ] Backend ALLOWED_ORIGINS updated with frontend URL
- [ ] Both services redeployed after variable updates
- [ ] Frontend URL accessible in browser
- [ ] Frontend can communicate with backend (check browser console for errors)

---

## Part 6: Verify Deployment

### 1. Backend Health Check

Go to backend URL in browser:
```
https://your-backend.up.railway.app/docs
```

You should see FastAPI Swagger UI (interactive API docs).

### 2. Frontend Health Check

Go to frontend URL in browser:
```
https://your-frontend.up.railway.app
```

You should see your app loaded.

### 3. Check Communication

In frontend browser console (F12):
- No CORS errors
- API calls should reach backend
- Check Network tab - requests to `/api/...` should go to backend

### 4. Check Logs

**Backend logs:**
- Go to **Backend Service → Deployments → Select Recent → Logs**
- Look for errors related to FERNET_KEY or DATABASE_URL

**Frontend logs:**
- Go to **Frontend Service → Deployments → Select Recent → Logs**
- Look for build errors or API connection issues

---

## Part 7: Troubleshooting

### Backend crashes on startup

**Error:** `FERNET_KEY is missing` or `Invalid FERNET_KEY format`

**Fix:**
1. Generate fresh FERNET_KEY (see Part 4)
2. Add to Backend Variables
3. Redeploy backend

### Frontend can't reach backend

**Error:** `CORS error` or `API connection failed`

**Fix:**
1. Check `VITE_API_URL` is correct backend URL
2. Check backend `ALLOWED_ORIGINS` includes frontend URL
3. Redeploy both services

### Database connection failed

**Error:** `DATABASE_URL connection error`

**Fix:**
1. Verify PostgreSQL is running (if using Railway PostgreSQL, check it exists)
2. Check connection string format
3. If using external DB, verify credentials are correct

### Build fails on frontend

**Error:** `npm install` or `npm run build` fails

**Fix:**
1. Check `package.json` exists in frontend folder
2. Check `node_modules` issues - try adding `npm cache clean --force` before install
3. Check Node.js version compatibility

---

## Part 8: Shared Variables (Optional)

If you have multiple backend services sharing secrets:

1. Go to **Backend Service 1 → Variables → FERNET_KEY**
2. Click **Promote to Shared Variable**
3. Select **Backend Service 2** to share it
4. Repeat for other secrets

---

## Part 9: SSL/HTTPS (Automatic)

Railway provides free SSL certificates automatically. Your URLs will be:
- Backend: `https://algo-trade-backend-xxx.up.railway.app`
- Frontend: `https://algo-trade-frontend-xxx.up.railway.app`

No manual SSL setup needed.

---

## Next Steps

1. **Monitor:** Check logs regularly in Railway dashboard
2. **Backup Database:** Set up automated PostgreSQL backups
3. **Custom Domain:** Add custom domain in Railway Service Settings
4. **CI/CD:** Railway auto-deploys on GitHub push (set up GitHub integration)
5. **Scaling:** Monitor CPU/Memory usage and upgrade plan if needed

---

## Quick Reference

| Step | Command/URL |
|------|------------|
| Generate FERNET_KEY | `python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"` |
| Backend health | `https://backend-url/docs` |
| Frontend access | `https://frontend-url` |
| Check backend logs | Railway Dashboard → Backend Service → Deployments → Logs |
| Check frontend logs | Railway Dashboard → Frontend Service → Deployments → Logs |

---

**Last Updated:** January 24, 2026

Good luck with your deployment! 🚀
