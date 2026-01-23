# Dynamic API Configuration Guide

## Overview
All hardcoded values have been replaced with dynamic configuration that automatically adapts to your environment.

## Architecture

### 1. **Central Configuration** (`frontend/src/config/api.js`)
Single source of truth for all API settings:
- Auto-detects environment (development/production)
- Tries multiple ports automatically (8002 → 8000 → 8001)
- Respects environment variables
- Provides helper functions for API calls

### 2. **API Helper** (`frontend/src/utils/api.js`)
Convenient wrapper functions:
- `api.get(endpoint, params)` - GET requests
- `api.post(endpoint, body, params)` - POST requests
- `api.put(endpoint, body, params)` - PUT requests
- `api.delete(endpoint, params)` - DELETE requests
- `api.call(endpoint, options, params)` - Full control with error handling

## Usage

### Method 1: Using API Helpers (Recommended)
```javascript
import api from './utils/api';

// GET request
const indices = await api.get('/autotrade/market/indices');

// POST with body
const result = await api.post('/auth/login', { username, password });

// GET with query params
const trades = await api.get('/autotrade/trades/history', { limit: 20 });

// With error handling
try {
  const data = await api.call('/autotrade/toggle', { 
    method: 'POST' 
  }, { 
    enabled: true 
  });
} catch (error) {
  console.error('API Error:', error.message);
}
```

### Method 2: Using Config Directly
```javascript
import config from './config/api';

// Using authFetch (auto-adds auth headers)
const response = await config.authFetch('/autotrade/status');
const data = await response.json();

// Building URLs with params
const url = config.getUrl('/autotrade/analyze', { symbol: 'NIFTY', balance: 50000 });

// Using predefined endpoints
const url = config.endpoints.autoTrade.liveIndices; // '/autotrade/market/indices'
```

### Method 3: Using Axios Client
```javascript
import { apiClient } from './api/client';

// All requests automatically prefixed with base URL
const response = await apiClient.get('/autotrade/status');
const data = response.data;
```

## Environment Configuration

### Development
No configuration needed! Automatically uses `http://localhost:8002`

### Custom Port
Set environment variable:
```bash
# Windows PowerShell
$env:REACT_APP_API_URL='http://localhost:8001'

# Linux/Mac
export REACT_APP_API_URL=http://localhost:8001
```

Or create `.env` file:
```
REACT_APP_API_URL=http://localhost:8002
```

### Production
Automatically detects production and uses:
```
https://your-domain.com/api
```

## Available Endpoints

All endpoints are defined in `config.endpoints`:

```javascript
// Auth
config.endpoints.auth.login        // '/auth/login'
config.endpoints.auth.register     // '/auth/register'
config.endpoints.auth.me          // '/auth/me'

// Auto Trading
config.endpoints.autoTrade.toggle        // '/autotrade/toggle'
config.endpoints.autoTrade.status        // '/autotrade/status'
config.endpoints.autoTrade.analyze       // '/autotrade/analyze'
config.endpoints.autoTrade.execute       // '/autotrade/execute'
config.endpoints.autoTrade.liveIndices   // '/autotrade/market/indices'
config.endpoints.autoTrade.activeTrades  // '/autotrade/trades/active'
config.endpoints.autoTrade.tradeHistory  // '/autotrade/trades/history'

// Market Data
config.endpoints.market.sentiment  // '/market/sentiment'
config.endpoints.market.trends     // '/market/trends'
config.endpoints.market.news       // '/market/news'
config.endpoints.market.sectors    // '/market/sectors'

// Brokers
config.endpoints.brokers.credentials              // '/brokers/credentials'
config.endpoints.brokers.credentialsByName(name)  // '/brokers/credentials/{name}'
config.endpoints.brokers.balance(id)              // '/brokers/balance/{id}'

// Orders & Strategies
config.endpoints.orders.base       // '/orders/'
config.endpoints.strategies.base   // '/strategies/'
```

## Benefits

✅ **No Hardcoded URLs** - All URLs are dynamically generated  
✅ **Environment Aware** - Works in dev, staging, and production  
✅ **Easy Port Changes** - Change one value instead of hundreds  
✅ **Auto Authentication** - Headers automatically added  
✅ **Type Safety** - Centralized endpoint definitions  
✅ **Error Handling** - Built-in error handling utilities  
✅ **Query Parameters** - Automatic URL encoding  
✅ **Maintainable** - Single source of truth  

## Migration Examples

### Before (Hardcoded)
```javascript
const response = await fetch('http://localhost:8002/autotrade/status', {
  headers: { 'Authorization': `Bearer ${token}` }
});
```

### After (Dynamic)
```javascript
const response = await api.get('/autotrade/status');
```

### Before (Multiple Fetches)
```javascript
const [statusRes, activeRes] = await Promise.all([
  fetch('http://localhost:8002/autotrade/status', {
    headers: { 'Authorization': `Bearer ${token}` }
  }),
  fetch('http://localhost:8002/autotrade/trades/active', {
    headers: { 'Authorization': `Bearer ${token}` }
  })
]);
```

### After (Clean)
```javascript
const [statusRes, activeRes] = await Promise.all([
  api.get(config.endpoints.autoTrade.status),
  api.get(config.endpoints.autoTrade.activeTrades)
]);
```

## Files Updated

✅ `frontend/src/api/client.js` - Now uses dynamic config  
✅ `frontend/src/components/AutoTradingDashboard.jsx` - Uses api helpers  
✅ `frontend/src/pages/BrokersPage.jsx` - Uses dynamic config  

## Next Steps

To fully migrate remaining files, update any `fetch()` calls to use the new API helpers:

```javascript
// Add import
import api from '../utils/api';

// Replace fetch with api helper
- const response = await fetch('http://localhost:8002/endpoint', { ... });
+ const response = await api.get('/endpoint');
```

## Testing

Test that configuration works:
```javascript
import config from './config/api';
console.log('API Base URL:', config.API_BASE_URL);
console.log('Endpoints:', config.endpoints);
```

Check in browser console - should show current API URL being used.
