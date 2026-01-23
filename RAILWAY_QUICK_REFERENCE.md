# Railway Variables - Quick Paste Reference

## Backend Service Variables (Copy-Paste Ready)

```
FERNET_KEY=<GENERATE_NEW_KEY>
ENCRYPTION_KEY=<SAME_OR_DIFFERENT_KEY>
DATABASE_URL=postgresql://user:password@host:5432/algotrade
ALLOWED_ORIGINS=https://your-frontend.up.railway.app
SECRET_KEY=<RANDOM_32_CHAR_STRING>
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30
REFRESH_TOKEN_EXPIRE_DAYS=7
ENVIRONMENT=production
ZERODHA_API_KEY=<YOUR_KEY_OR_LEAVE_BLANK>
ZERODHA_API_SECRET=<YOUR_SECRET_OR_LEAVE_BLANK>
PAPER_TRADING_MODE=true
LOG_LEVEL=INFO
ENABLE_LIVE_TRADING=false
ENABLE_NOTIFICATIONS=true
```

## Backend Start Command

```bash
uvicorn app.main:app --host 0.0.0.0 --port $PORT
```

---

## Frontend Service Variables (Copy-Paste Ready)

```
VITE_API_URL=https://your-backend.up.railway.app
VITE_APP_NAME=AlgoTrade Pro
VITE_ENVIRONMENT=production
FRONTEND_PORT=$PORT
VITE_ENABLE_LIVE_TRADING=false
VITE_ENABLE_DEMO_MODE=true
```

## Frontend Start Command (Vite)

```bash
npm install && npm run build && npx serve -s dist -l $PORT
```

## Frontend Start Command (Create React App)

```bash
npm install && npm run build && npx serve -s build -l $PORT
```

---

## How to Generate FERNET_KEY

Run this command locally in terminal:

```bash
python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

Example output (use this format):
```
UtqK_4V8s_NjVGn-hEr6fGKdKvGx9W8lEqR5s-HZhDQ=
```

---

## Deployment Order

1. ✅ Deploy Backend Service
2. ✅ Set Backend Variables (copy FERNET_KEY from above)
3. ✅ Copy Backend URL from Railway
4. ✅ Deploy Frontend Service
5. ✅ Set Frontend Variables (use Backend URL for VITE_API_URL)
6. ✅ Copy Frontend URL from Railway
7. ✅ Update Backend's ALLOWED_ORIGINS with Frontend URL
8. ✅ Redeploy Backend Service (variables changed)

---

## Verify Deployment

| Check | URL |
|-------|-----|
| Backend API Docs | `https://backend-url/docs` |
| Frontend App | `https://frontend-url` |

Both should be accessible and frontend should load without CORS errors.

---

**Key Points:**
- 🔑 Never hardcode `$PORT` - Railway sets it automatically
- 🔒 Generate fresh FERNET_KEY for each deployment
- 🌐 Update ALLOWED_ORIGINS AFTER frontend is deployed
- 📝 Keep .env files in .gitignore (never commit secrets)
- 🔄 Redeploy services after updating variables
