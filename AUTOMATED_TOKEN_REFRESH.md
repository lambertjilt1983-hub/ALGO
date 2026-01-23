# Automated Token Refresh System

## Overview

This system provides **complete automation** for broker token lifecycle management, including automatic detection of token expiration, intelligent refresh attempts, and user-friendly notifications when re-authentication is needed.

## Architecture

### Components

#### 1. Backend Token Manager (`backend/app/core/token_manager.py`)
- **Purpose**: Automated token validation and refresh logic
- **Key Features**:
  - `validate_zerodha_token()`: Tests token validity via API call
  - `refresh_zerodha_token()`: Detects OAuth limitation, returns requires_reauth
  - `get_balance_with_fallback()`: Main method - tries real API, catches expired tokens, returns appropriate status

#### 2. Token Refresh Routes (`backend/app/routes/token_refresh.py`)
- **Purpose**: REST endpoints for token management
- **Endpoints**:
  - `GET /api/tokens/status/{broker_id}`: Check if token is valid
  - `POST /api/tokens/refresh/{broker_id}`: Attempt refresh
  - `GET /api/tokens/validate-all`: Check all user's tokens

#### 3. Background Tasks (`backend/app/core/background_tasks.py`)
- **Purpose**: Periodic token validation
- **Features**:
  - Runs every 30 minutes by default
  - Checks all user tokens for validity
  - Logs warnings for expired tokens
  - Sends notifications to frontend

#### 4. Frontend Token Manager (`frontend/src/utils/tokenManager.js`)
- **Purpose**: Client-side token monitoring and refresh
- **Methods**:
  - `checkTokenStatus(brokerId)`: Check token validity
  - `attemptTokenRefresh(brokerId)`: Try to refresh token
  - `validateAllTokens()`: Check all tokens
  - `startMonitoring(brokerId, callback)`: Monitor token with callback
  - `handleTokenExpired(brokerId, callback)`: Auto-retry with backoff

## How It Works

### Scenario 1: Token Expiration During API Call

```
1. Frontend: fetchBrokerBalance() called
2. Backend: GET /brokers/balance/{broker_id}
3. TokenManager: Tries kite.margins() with current token
4. Error: "Incorrect `api_key` or `access_token`" (24-hour limit)
5. TokenManager: Returns { status: 'token_expired', requires_reauth: true }
6. Frontend: Detects token_expired status
7. Frontend: Calls handleZerodhaLogin() to show OAuth dialog
8. User: Completes Zerodha login
9. Backend: /brokers/zerodha/callback receives request_token
10. Backend: Exchanges for new access_token, stores in DB
11. Frontend: Auto-retries fetchBrokerBalance() with new token
12. Success: Real data displayed
```

### Scenario 2: Proactive Token Validation (Background Task)

```
Every 30 minutes:
1. Background Task: validate_all_tokens()
2. Loop: Check each user's Zerodha token
3. For expired tokens:
   - Log warning
   - Mark in database
   - Frontend notification queue
4. Next time frontend calls balance endpoint:
   - Gets token_expired response
   - Triggers re-auth flow
```

### Scenario 3: Frontend Monitoring

```
1. Dashboard mounts: tokenManager.startMonitoring(brokerId)
2. Every 5 minutes: checkTokenStatus(brokerId)
3. If token_expired:
   - Call handleTokenExpired()
   - Attempt refresh (up to 3 times)
   - If still expired: Show re-auth prompt
4. User clicks re-auth: handleZerodhaLogin()
```

## Configuration

### Environment Variables

```bash
# Token expiration check interval (milliseconds)
REACT_APP_TOKEN_CHECK_INTERVAL=300000  # 5 minutes

# Max retry attempts for token refresh
TOKEN_REFRESH_MAX_ATTEMPTS=3

# Background task interval (minutes)
BACKGROUND_TASK_INTERVAL=30
```

### Database Schema

Token status is stored with broker credentials:

```python
class BrokerCredential(Base):
    __tablename__ = "broker_credentials"
    
    id: int  # Primary key
    api_key: str  # Encrypted
    api_secret: str  # Encrypted
    access_token: str  # Plain text (expires after 24 hours)
    is_active: bool
    created_at: datetime
    updated_at: datetime  # Updated when token refreshed
```

## Zerodha API Token Lifecycle

### Token Expiration

- **Duration**: 24 hours
- **Trigger**: After successful OAuth authentication
- **Error**: "Incorrect `api_key` or `access_token`" (Zerodha returns 403)
- **Location**: Stored in `broker_credentials.access_token` (plain text)

### Token Refresh

- **OAuth Type**: Server-side with user interaction required
- **Cannot Silently Refresh**: Zerodha requires user re-login
- **Process**:
  1. User clicks "Reconnect Broker"
  2. Redirected to Zerodha login page
  3. After login, Zerodha redirects to backend callback
  4. Backend exchanges request_token for new access_token
  5. New token stored in database
  6. Frontend auto-retries API calls

## Status Codes

### Token Response Statuses

```json
{
  "status": "success",
  "data_source": "real_zerodha_api"
}
```

```json
{
  "status": "token_expired",
  "requires_reauth": true,
  "action": "redirect_to_zerodha_login",
  "message": "Access token expired. Please re-authenticate with Zerodha."
}
```

```json
{
  "status": "error",
  "message": "API error description"
}
```

## Usage

### In Dashboard Component

```jsx
import tokenManager from '../utils/tokenManager';

function Dashboard() {
  useEffect(() => {
    // Start monitoring when component mounts
    brokers.forEach(broker => {
      tokenManager.startMonitoring(
        broker.id,
        handleTokenExpired,
        300000  // Check every 5 minutes
      );
    });

    return () => {
      // Stop all monitoring when component unmounts
      tokenManager.stopAllMonitoring();
    };
  }, [brokers]);

  const handleTokenExpired = async (brokerId, status) => {
    console.log(`Token expired for broker ${brokerId}`);
    // Auto-trigger re-auth
    handleZerodhaLogin(brokerId);
  };
}
```

### Manual Token Check

```javascript
// Check single broker token
const status = await tokenManager.checkTokenStatus(brokerId);
console.log(status);

// Check all tokens
const allStatus = await tokenManager.validateAllTokens();
console.log(allStatus);

// Trigger refresh
const result = await tokenManager.attemptTokenRefresh(brokerId);
```

## Error Handling

### Frontend Error Detection

```javascript
// In fetchBrokerBalance()
if (balanceData.status === 'token_expired' || balanceData.requires_reauth) {
  // Token expired - auto-trigger re-auth
  setTimeout(() => {
    handleZerodhaLogin(brokerId);
  }, 1000);
}
```

### Backend Error Detection

```python
# In TokenManager.get_balance_with_fallback()
try:
    margins = kite.margins()
    # Token valid - return real data
except Exception as e:
    if "Incorrect" in str(e):
        # Token expired
        return {
            "status": "token_expired",
            "requires_reauth": True,
            "action": "redirect_to_zerodha_login"
        }
```

## Logging

### Backend Logs

```
[INFO] Token validation: broker_id=4, status=valid
[WARN] Token validation failed: broker_id=4, error=Incorrect api_key or access_token
[INFO] Token validation task completed: jobs=1
```

### Frontend Logs

```
Starting token monitoring for broker 4, interval: 300000ms
Broker 4 balance response: {status: 'success', ...}
Token expired for broker 4, triggering re-auth
Stopping token monitoring for broker 4
```

## Installation

### Backend Dependencies

```bash
pip install APScheduler==3.10.4
pip install kiteconnect==5.0.1
pip install cryptography==41.0.7
```

### Frontend Setup

Token manager is automatically available in Dashboard component:

```javascript
import tokenManager from './utils/tokenManager';
```

## Testing

### Manual Testing Steps

1. **Setup Test Broker**
   ```bash
   python create_test_user.py
   python setup_broker.py  # For Zerodha
   ```

2. **Trigger Token Expiration**
   ```bash
   python reset_access_token.py  # Clears current token
   ```

3. **Test Auto-Detection**
   - Open frontend dashboard
   - Wait for balance fetch
   - System should detect expired token
   - Should trigger re-auth automatically

4. **Test Complete Flow**
   - Trigger token expiration
   - Wait for auto-detection
   - Click re-auth when prompted
   - Complete Zerodha login
   - Verify real data displays

### Unit Tests

```python
# backend/tests/test_token_manager.py
from app.core.token_manager import token_manager

def test_validate_token():
    credential = get_test_credential()
    is_valid = token_manager.validate_zerodha_token(credential)
    assert isinstance(is_valid, bool)

def test_refresh_token():
    result = token_manager.refresh_zerodha_token(broker_id, db)
    assert result['status'] in ['success', 'requires_reauth', 'error']
```

## Troubleshooting

### Issue: Token validation always returns "invalid"

**Solution**: Check that Zerodha credentials are correctly decrypted
```python
from app.core.security import encryption_manager
api_key = encryption_manager.decrypt_credentials(credential.api_key)
print(f"Decrypted: {api_key}")  # Should show actual key
```

### Issue: Background task not running

**Solution**: Check APScheduler is installed
```bash
pip install APScheduler==3.10.4
python -c "from apscheduler.schedulers.background import BackgroundScheduler; print('APScheduler OK')"
```

### Issue: Frontend not detecting token expiration

**Solution**: Verify console logs and browser network tab
```javascript
// In fetchBrokerBalance()
console.log('Balance response:', balanceData);
if (balanceData.status === 'token_expired') {
  console.log('Token expired detected!');
}
```

### Issue: Re-auth flow not completing

**Solution**: Check callback URL and backend logs
```bash
tail -f backend/logs/*.log | grep callback
```

## Future Enhancements

1. **Silent Token Refresh**: Explore if Zerodha provides refresh token mechanism
2. **Multi-Broker Support**: Handle multiple broker token expiration independently
3. **Notification System**: Email/SMS alerts when tokens expire
4. **Token History**: Track token lifecycle for debugging
5. **Preemptive Refresh**: Refresh before 24-hour mark
6. **User Preferences**: Let users configure check intervals

## Support

For issues with token management, check:
1. Backend logs: `backend/logs/`
2. Browser console: Chrome DevTools → Console tab
3. Database: Verify token stored with `check_broker_4.py`
4. Zerodha API status: Visit Zerodha console for any API restrictions
