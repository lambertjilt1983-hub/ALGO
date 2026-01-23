import axios from 'axios';
import config from '../config/api';

const API_BASE_URL = config.API_BASE_URL;

export const apiClient = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Add auth token to requests
apiClient.interceptors.request.use((config) => {
  const token = localStorage.getItem('access_token');
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// Handle token refresh
apiClient.interceptors.response.use(
  (response) => response,
  async (error) => {
    if (error.response?.status === 401) {
      const refresh_token = localStorage.getItem('refresh_token');
      if (refresh_token) {
        try {
          const response = await axios.post(`${API_BASE_URL}/auth/refresh`, {
            refresh_token,
          });
          localStorage.setItem('access_token', response.data.access_token);
          return apiClient(error.config);
        } catch (err) {
          localStorage.clear();
          window.location.href = '/login';
        }
      }
    }
    return Promise.reject(error);
  }
);

// Auth API
export const authAPI = {
  register: (data) => apiClient.post('/auth/register', data),
  login: (data) => apiClient.post('/auth/login', data),
  getCurrentUser: () => apiClient.get('/auth/me'),
};

// Broker API
export const brokerAPI = {
  addCredentials: (data) => apiClient.post('/brokers/credentials', data),
  listCredentials: () => apiClient.get('/brokers/credentials'),
  getCredentials: (brokerName) => apiClient.get(`/brokers/credentials/${brokerName}`),
  deleteCredentials: (brokerName) => apiClient.delete(`/brokers/credentials/${brokerName}`),
};

// Orders API
export const ordersAPI = {
  placeOrder: (data) => apiClient.post('/orders/', data),
  getOrder: (orderId) => apiClient.get(`/orders/${orderId}`),
  listOrders: () => apiClient.get('/orders/'),
  cancelOrder: (orderId) => apiClient.delete(`/orders/${orderId}`),
};

// Strategies API
export const strategiesAPI = {
  createStrategy: (data) => apiClient.post('/strategies/', data),
  listStrategies: () => apiClient.get('/strategies/'),
  getStrategy: (strategyId) => apiClient.get(`/strategies/${strategyId}`),
  updateStrategy: (strategyId, data) => apiClient.put(`/strategies/${strategyId}`, data),
  deleteStrategy: (strategyId) => apiClient.delete(`/strategies/${strategyId}`),
  backtest: (strategyId, data) => apiClient.post(`/strategies/${strategyId}/backtest`, data),
};

// Market API
export const marketAPI = {
  getLiveIndices: () => apiClient.get('/autotrade/market/indices'),
};
