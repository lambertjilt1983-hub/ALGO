// API Helper Functions - Use these instead of direct fetch calls
import config from '../config/api';

/**
 * Make an authenticated API call
 * @param {string} endpoint - API endpoint path
 * @param {object} options - Fetch options (method, body, etc.)
 * @param {object} params - URL query parameters
 * @returns {Promise<Response>}
 */
export const apiFetch = async (endpoint, options = {}, params = {}) => {
  const url = config.getUrl(endpoint, params);
  return await config.authFetch(url, options);
};

/**
 * GET request helper
 */
export const apiGet = async (endpoint, params = {}) => {
  return await apiFetch(endpoint, { method: 'GET' }, params);
};

/**
 * POST request helper
 */
export const apiPost = async (endpoint, body = {}, params = {}) => {
  return await apiFetch(endpoint, {
    method: 'POST',
    body: JSON.stringify(body),
  }, params);
};

/**
 * PUT request helper
 */
export const apiPut = async (endpoint, body = {}, params = {}) => {
  return await apiFetch(endpoint, {
    method: 'PUT',
    body: JSON.stringify(body),
  }, params);
};

/**
 * DELETE request helper
 */
export const apiDelete = async (endpoint, params = {}) => {
  return await apiFetch(endpoint, { method: 'DELETE' }, params);
};

/**
 * Handle API response with error handling
 */
export const handleApiResponse = async (response) => {
  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Unknown error' }));
    throw new Error(error.detail || error.message || 'API request failed');
  }
  return await response.json();
};

/**
 * Complete API call with error handling
 */
export const apiCall = async (endpoint, options = {}, params = {}) => {
  try {
    const response = await apiFetch(endpoint, options, params);
    return await handleApiResponse(response);
  } catch (error) {
    console.error(`API Error [${endpoint}]:`, error);
    throw error;
  }
};

// Export config for direct access when needed
export { config };
export default {
  fetch: apiFetch,
  get: apiGet,
  post: apiPost,
  put: apiPut,
  delete: apiDelete,
  call: apiCall,
  config,
};
