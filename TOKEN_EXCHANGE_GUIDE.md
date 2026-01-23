# How to Fix Token Exchange and Complete Auto Trading Setup

## Problem You Were Facing
After Zerodha login, you were getting redirected back with a `request_token`, but:
1. The token wasn't being saved to the database
2. Every page refresh asked for password again  
3. Backend wasn't properly running (exit code 1)

## What I Fixed

### 1. Backend Startup Issues
- **Installed APScheduler**: `pip install APScheduler==3.10.4` (was missing)
- **Fixed logger method calls** in `background_tasks.py` (log_info → log_error)
- **Fixed indentation error** that was preventing backend from starting
- **Backend now runs successfully on port 8001**

### 2. CORS Configuration
Added your frontend port (5173) to allowed origins in `backend/app/main.py`:
```python
allow_origins=[
    "http://localhost:3000",
    "http://localhost:3001",
    "http://localhost:8080",
    "http://localhost:5173"  # ← Added this for Vite
],
```

### 3. OAuth Callback Flow
Updated `backend/app/routes/broker.py`:
- Changed redirect_uri from localhost:8000 to localhost:5173 (your frontend)
- **Changed response format from RedirectResponse to JSON** so fetch() can read it
- Simplified Zerodha login URL (Zerodha redirect URL is configured in their developer console)

### 4. Frontend Token Exchange
Updated `frontend/src/Dashboard.jsx` → `handleZerodhaCallback()`:
- **Properly handles JSON response** instead of redirects
- Shows clear success/error messages with emojis
- Automatically fetches broker balance after successful token exchange
- Better error handling and logging

## How Auto Trading Authentication Works (Industry Standard)

### OAuth 2.0 Flow for Broker Integration
1. **User clicks "Connect Broker"** → Frontend calls `/brokers/zerodha/login/{broker_id}`
2. **Backend generates login URL** with API key
3. **User redirected to Zerodha** → Enters credentials on Zerodha's site
4. **Zerodha validates** → Redirects back to your frontend with `request_token`
5. **Frontend receives request_token** → Calls `/brokers/zerodha/callback?request_token=...`
6. **Backend exchanges request_token** → Calls Zerodha API with API secret
7. **Zerodha returns access_token** → Valid for 24 hours
8. **Backend saves access_token** → Stores in database
9. **Future API calls use access_token** → Until it expires after 24 hours

### Token Lifecycle
```
Login → Request Token (one-time use)
      → Exchange for Access Token (24-hour validity)
      → Store in DB
      → Use for all API calls
      → Expires after 24 hours
      → Auto-detect expiration
      → Trigger re-authentication
```

## Testing Steps

### Step 1: Ensure Backend is Running
```powershell
cd f:\ALGO\backend
$env:PYTHONPATH="f:\ALGO\backend"
python -m uvicorn app.main:app --host 127.0.0.1 --port 8001
```

You should see:
```
INFO:     Uvicorn running on http://127.0.0.1:8001 (Press CTRL+C to quit)
INFO:     Application startup complete.
```

### Step 2: Ensure Frontend is Running
```powershell
cd f:\ALGO\frontend
npm run dev
```

You should see:
```
VITE v... ready in ...ms
➜  Local:   http://localhost:5173/
```

### Step 3: Complete OAuth Flow
1. **Open browser**: http://localhost:5173
2. **Login**: Username `test`, Password `test123`
3. **Go to Dashboard**: Click on broker section
4. **Click "Connect to Zerodha"** (or similar button)
5. **Zerodha login page opens**: Enter your Zerodha credentials
6. **After Zerodha login**: You'll be redirected back to http://localhost:5173/?request_token=TNCD...
7. **Watch console logs**:
   ```
   🔄 Exchanging Zerodha request token: TNCD9H3jYm1np5cVQGPzHfcSDuQyT4AH
   📥 Callback response status: 200
   ✅ Callback response data: {status: 'success', broker_id: 4}
   🎉 Token exchange successful! Broker ID: 4
   ```
8. **Alert appears**: "✅ Zerodha connected! Access token saved. Real-time trading is now active."
9. **Broker balance updates**: Shows real data instead of "Demo Data"

### Step 4: Verify Token in Database
```powershell
python f:\ALGO\check_broker_4.py
```

You should see:
```
Broker ID 4 Details:
ID: 4
User: 1
Name: Zerodha
Token: YourAccessToken123456789...
Token Length: 32 chars
Status: HAS ACCESS TOKEN
```

### Step 5: Test API Calls
The token will now be used automatically for:
- Fetching account balance: `/brokers/balance/4`
- Placing orders
- Fetching positions
- Market data

## What Happens on Token Expiration (24 Hours Later)

### Automatic Detection & Re-auth Flow
1. **Backend detects expired token** when API call fails
2. **Returns special status**: `{status: 'token_expired', requires_reauth: true}`
3. **Frontend detects this** in `fetchBrokerBalance()`
4. **Automatically triggers** `handleZerodhaLogin()` after 1 second
5. **User sees message**: "Token Expired - Re-authenticating..."
6. **Zerodha login opens** automatically
7. **After re-login**: New token saved, real data resumes

## Troubleshooting

### Problem: Backend won't start
**Solution**:
```powershell
# Check for errors
cd f:\ALGO\backend
$env:PYTHONPATH="f:\ALGO\backend"
python -c "import app.main as m; print('OK')"
```

If you see errors:
- Install missing packages: `pip install -r requirements.txt`
- Check Python version: `python --version` (should be 3.12+)

### Problem: Token not saving
**Check backend logs** when callback is called:
```
ZERODHA CALLBACK RECEIVED
Request Token: TNCD9H3jYm1np5cVQGPzHfcSDuQyT4AH
Status: success
Authenticated user ID: 1
Found broker: ID=4, Name=Zerodha, User=1
Decrypted API key: 30i4qnng2t...
Generating session with Zerodha...
Access token received: YourToken123...
Saving access token to broker ID: 4
Token saved! Verify: YourToken123...
Returning JSON success to frontend
```

If you see "ERROR in callback", the issue is shown in the error message.

### Problem: CORS errors in browser
**Check browser console**:
```
Access to fetch at 'http://localhost:8001/...' from origin 'http://localhost:5173' has been blocked by CORS policy
```

**Solution**: Restart backend (CORS fix is already applied)

### Problem: "Demo Data" still showing after login
**Possible causes**:
1. Token exchange didn't complete (check console logs)
2. Token expired (backend will show `token_expired` status)
3. API key/secret incorrect (check with `python test_decrypt.py`)

## Files Modified

### Backend
1. `backend/requirements.txt` - Added APScheduler==3.10.4
2. `backend/app/main.py` - Added port 5173 to CORS, added startup/shutdown events
3. `backend/app/routes/broker.py` - Changed redirects to JSON responses, updated redirect_uri
4. `backend/app/core/background_tasks.py` - Fixed logger method calls and indentation
5. `backend/app/core/token_manager.py` - Created automated token validation system
6. `backend/app/routes/token_refresh.py` - Created token management API endpoints

### Frontend
1. `frontend/src/Dashboard.jsx` - Updated `handleZerodhaCallback()` with proper JSON handling
2. `frontend/src/utils/tokenManager.js` - Created token monitoring utility
3. `frontend/src/config/api.js` - Updated port priority to [8001, 8002, ...]

## Next Steps

1. **Start both servers** (backend on 8001, frontend on 5173)
2. **Login and click "Connect Broker"**
3. **Complete Zerodha OAuth**
4. **Verify token saved**: Run `python check_broker_4.py`
5. **Test real data**: Check that balance shows real numbers, not demo data
6. **Wait 1 minute**: Refresh page to verify token persists (no re-login needed)

## Industry Best Practices Implemented

✅ **OAuth 2.0 Flow**: Standard authentication for broker APIs  
✅ **JWT for session management**: Secure user sessions  
✅ **Token encryption**: API keys/secrets stored encrypted  
✅ **Automatic token refresh detection**: No manual intervention needed  
✅ **Background token validation**: Periodic checks (every 30 minutes)  
✅ **CORS properly configured**: Secure cross-origin requests  
✅ **Error handling**: Clear error messages for debugging  
✅ **Logging**: Comprehensive logs for troubleshooting  

Your auto trading platform now follows the same architecture as Zerodha Kite Web, Upstox Pro, and other professional trading platforms!
