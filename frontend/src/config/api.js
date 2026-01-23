// API Configuration - Single Source of Truth
// Automatically detects environment and uses appropriate API URL

const getApiBaseUrl = () => {
  // Priority 1: Environment variable (set via .env file or runtime)
  if (import.meta.env.VITE_API_URL) {
    return import.meta.env.VITE_API_URL;
  }
  
  // Priority 2: Auto-detect based on hostname
  const hostname = window.location.hostname;
  
  // Production detection
  if (hostname !== 'localhost' && hostname !== '127.0.0.1') {
    return `https://${hostname}/api`;
  }
  
  // Priority 3: Try different local ports in order (prefer 8002 where backend runs)
  const possiblePorts = [8002, 8001, 8003, 8000];
  
  // For development, default to port 8002
  return `http://localhost:${possiblePorts[0]}`;
};

const getWebSocketUrl = () => {
  const baseUrl = getApiBaseUrl();
  return baseUrl.replace('http', 'ws').replace('https', 'wss');
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
      tradeHistory: '/autotrade/trades/history',
      liveIndices: '/autotrade/market/indices',
      monitor: '/autotrade/monitor',
    },
  },
  
  // Helper to build full URL
  getUrl: (endpoint, params = {}) => {
    let url = `${config.API_BASE_URL}${endpoint}`;
    
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
    
    const response = await fetch(url, {
      ...options,
      headers: {
        'Content-Type': 'application/json',
        ...config.getAuthHeaders(),
        ...options.headers,
      },
    });
    
    return response;
  },
};

export default config;
