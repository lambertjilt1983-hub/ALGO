// API Configuration - Single Source of Truth
// Automatically detects environment and uses appropriate API URL

const getApiBaseUrl = () => {
  // Priority 1: Environment variable (set via .env file or runtime)
  if (import.meta.env.VITE_API_URL) {
    return String(import.meta.env.VITE_API_URL).trim().replace(/\/+$/, '');
  }
  // Local-only mode.
  return `http://127.0.0.1:8000`;
};

const normalizeEndpoint = (endpoint) => {
  const value = String(endpoint || '').trim();
  if (!value) return '';
  return value.startsWith('/') ? value : `/${value}`;
};

const hasHeader = (headers, headerName) => {
  if (!headers || typeof headers !== 'object') return false;
  const target = String(headerName || '').toLowerCase();
  return Object.keys(headers).some((key) => String(key || '').toLowerCase() === target);
};

const getWebSocketUrl = () => {
  const baseUrl = getApiBaseUrl();
  return baseUrl.replace('http', 'ws').replace('https', 'wss');
};

const getAltLoopbackUrl = (url) => {
  if (typeof url !== 'string') return null;
  if (url.includes('://localhost:')) return url.replace('://localhost:', '://127.0.0.1:');
  if (url.includes('://127.0.0.1:')) return url.replace('://127.0.0.1:', '://localhost:');
  return null;
};

const TRANSPORT_BACKOFF_BASE_MS = 15000;
const TRANSPORT_BACKOFF_MAX_MS = 180000;

const transportHealth = {
  consecutiveFailures: 0,
  backoffUntil: 0,
  lastError: '',
  lastUrl: '',
};

const isBackoffActive = () => Date.now() < Number(transportHealth.backoffUntil || 0);

const markTransportFailure = (url, error) => {
  transportHealth.consecutiveFailures += 1;
  const multiplier = Math.pow(2, Math.max(0, transportHealth.consecutiveFailures - 1));
  const delayMs = Math.min(TRANSPORT_BACKOFF_BASE_MS * multiplier, TRANSPORT_BACKOFF_MAX_MS);
  transportHealth.backoffUntil = Date.now() + delayMs;
  transportHealth.lastUrl = String(url || '');
  transportHealth.lastError = error instanceof Error
    ? (error.message || 'Transport Error')
    : String(error || 'Transport Error');
};

const markTransportSuccess = () => {
  transportHealth.consecutiveFailures = 0;
  transportHealth.backoffUntil = 0;
  transportHealth.lastError = '';
  transportHealth.lastUrl = '';
};

const buildTransportErrorResponse = () => {
  const remainingMs = Math.max(0, Number(transportHealth.backoffUntil || 0) - Date.now());
  const retryAfterSec = Math.max(1, Math.ceil(remainingMs / 1000));
  const headers = new Headers({
    'x-algo-transport-error': '1',
    'x-algo-backoff-until': String(transportHealth.backoffUntil || 0),
    'retry-after': String(retryAfterSec),
  });
  return new Response(null, { status: 503, statusText: 'Transport Error', headers });
};

// Export centralized configuration
export const config = {
  API_BASE_URL: getApiBaseUrl(),
  WS_BASE_URL: getWebSocketUrl(),
  
  // API Endpoints
  endpoints: {
    // Auth
    auth: {
      register: '/auth/register',
      login: '/auth/login',
      verifyOtp: '/auth/verify-otp',
      refresh: '/auth/refresh',
      me: '/auth/me',
    },
    
    // Brokers
    brokers: {
      credentials: '/brokers/credentials',
      credentialsByName: (name) => `/brokers/credentials/${name}`,
      balance: (id) => `/brokers/balance/${id}`,
      zerodhaLogin: (id) => `/brokers/zerodha/login/${id}`,
      zerodhaCallback: '/brokers/zerodha/callback',
    },
    
    // Orders
    orders: {
      base: '/orders/',
      byId: (id) => `/orders/${id}`,
    },
    
    // Strategies
    strategies: {
      base: '/strategies/',
      byId: (id) => `/strategies/${id}`,
      backtest: (id) => `/strategies/${id}/backtest`,
    },
    
    // Market Data
    market: {
      sentiment: '/market/sentiment',
      trends: '/market/trends',
      news: '/market/news',
      sectors: '/market/sectors',
    },
    
    // Auto Trading
    autoTrade: {
      toggle: '/autotrade/toggle',
      setMode: '/autotrade/mode',
      status: '/autotrade/status',
      analyze: '/autotrade/analyze',
      execute: '/autotrade/execute',
      activeTrades: '/autotrade/trades/active',
      closeTrade: '/autotrade/trades/close',
      tradeHistory: '/autotrade/trades/history',
      report: '/autotrade/report',
      liveIndices: '/autotrade/market/indices',
      monitor: '/autotrade/monitor',
      resetDailyLoss: '/autotrade/reset_daily_loss',
    },

    // Admin
    admin: {
      overview: '/admin/overview',
      updateUser: (id) => `/admin/users/${id}`,
      deleteUser: (id) => `/admin/users/${id}`,
      deleteBroker: (id) => `/admin/brokers/${id}`,
    },
  },
  
  // Helper to build full URL
  getUrl: (endpoint, params = {}) => {
    let url = `${config.API_BASE_URL}${normalizeEndpoint(endpoint)}`;
    
    // Add query parameters if provided
    if (Object.keys(params).length > 0) {
      const queryString = new URLSearchParams(params).toString();
      url += `?${queryString}`;
    }
    
    return url;
  },
  
  // Helper to get auth headers
  getAuthHeaders: () => {
    const token = localStorage.getItem('access_token');
    return token ? { 'Authorization': `Bearer ${token}` } : {};
  },
  
  // Helper for fetch with auth
  authFetch: async (endpoint, options = {}) => {
    // If endpoint is already a full URL, use it; otherwise build the URL
    const url = (typeof endpoint === 'string' && (endpoint.startsWith('http://') || endpoint.startsWith('https://'))) 
      ? endpoint 
      : config.getUrl(endpoint);

    const { includeAuth = true, retryTransportOnce = false, ...restOptions } = options;

    const method = String(restOptions.method || 'GET').toUpperCase();
    const shouldSetJsonContentType = (
      method !== 'GET'
      && method !== 'HEAD'
      && typeof restOptions.body !== 'undefined'
      && !hasHeader(restOptions.headers, 'content-type')
    );

    const requestOptions = {
      ...restOptions,
      headers: {
        ...(shouldSetJsonContentType ? { 'Content-Type': 'application/json' } : {}),
        ...(includeAuth ? config.getAuthHeaders() : {}),
        ...restOptions.headers,
      },
    };

    const canRetry = method === 'GET' || retryTransportOnce;

    if (isBackoffActive()) {
      return buildTransportErrorResponse();
    }

    try {
      const response = await fetch(url, requestOptions);
      const statusCode = Number(response?.status || 0);
      const shouldBackoff = statusCode <= 0 || statusCode === 429 || statusCode >= 500;
      if (shouldBackoff) {
        markTransportFailure(url, new Error(`HTTP ${statusCode || 'network'}`));
      } else {
        markTransportSuccess();
      }
      return response;
    } catch (error) {
      if (!canRetry) {
        markTransportFailure(url, error);
        return buildTransportErrorResponse();
      }

      // Retry once for intermittent transport/decode issues seen in dev (e.g. content-length mismatch).
      // Wrap the retry in its own try/catch so a double-failure still returns a failed-response
      // object instead of re-throwing (avoids redundant browser console stack traces).
      await new Promise((resolve) => setTimeout(resolve, 200));
      try {
        const retryResponse = await fetch(url, {
          ...requestOptions,
          cache: 'no-store',
        });
        markTransportSuccess();
        return retryResponse;
      } catch {
        const altUrl = getAltLoopbackUrl(url);
        if (altUrl) {
          try {
            const altResponse = await fetch(altUrl, {
              ...requestOptions,
              cache: 'no-store',
            });
            markTransportSuccess();
            return altResponse;
          } catch {}
        }
        // Return a synthetic failed response so callers get ok:false without a thrown exception.
        markTransportFailure(url, error);
        return buildTransportErrorResponse();
      }
    }
  },

  isApiBackoffActive: () => isBackoffActive(),

  getApiBackoffInfo: () => ({
    active: isBackoffActive(),
    remainingMs: Math.max(0, Number(transportHealth.backoffUntil || 0) - Date.now()),
    consecutiveFailures: Number(transportHealth.consecutiveFailures || 0),
    lastError: transportHealth.lastError || '',
    lastUrl: transportHealth.lastUrl || '',
  }),

  clearApiBackoff: () => {
    markTransportSuccess();
  },
};

export default config;
