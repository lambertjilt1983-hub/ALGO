/**
 * Auto Token Refresh Hook
 * Automatically refreshes JWT access tokens every 5 minutes
 * Prevents login expiration and session timeouts
 */
import { useEffect, useRef } from 'react';
import config from '../config/api';

const TOKEN_REFRESH_INTERVAL = 5 * 60 * 1000; // 5 minutes in milliseconds
const tokenRefreshLogLastAt = new Map();

const tokenLog = (level, key, message, minIntervalMs = 0) => {
  const now = Date.now();
  const lastAt = Number(tokenRefreshLogLastAt.get(key) || 0);
  if (minIntervalMs > 0 && (now - lastAt) < minIntervalMs) {
    return;
  }
  tokenRefreshLogLastAt.set(key, now);
  console[level](message);
};

export const useTokenRefresh = () => {
  const refreshTimerRef = useRef(null);

  const refreshAccessToken = async () => {
    try {
      const refreshToken = localStorage.getItem('refresh_token');
      
      if (!refreshToken) {
        tokenLog('warn', 'no_refresh_token', '[TokenRefresh] No refresh token found - skipping refresh', 60000);
        return;
      }

      tokenLog('log', 'refresh_attempt', '[TokenRefresh] Attempting to refresh access token...', 60000);

      const response = await fetch(`${config.API_BASE_URL}/auth/refresh?refresh_token=${encodeURIComponent(refreshToken)}`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
      });

      if (response.ok) {
        const data = await response.json();
        
        // Update access token in localStorage
        localStorage.setItem('access_token', data.access_token);
        
        tokenLog('log', 'refresh_ok', '[TokenRefresh] ✓ Access token refreshed successfully', 60000);
        
        return true;
      } else {
        const errorData = await response.json();
        console.error('[TokenRefresh] ✗ Token refresh failed:', errorData.detail);
        
        // If refresh token is invalid, clear storage and force re-login
        if (response.status === 401 || response.status === 403) {
          tokenLog('warn', 'refresh_expired', '[TokenRefresh] Refresh token expired - clearing session', 15000);
          localStorage.removeItem('access_token');
          localStorage.removeItem('refresh_token');
          window.location.href = '/'; // Redirect to login
        }
        
        return false;
      }
    } catch (error) {
      console.error('[TokenRefresh] Error refreshing token:', error);
      return false;
    }
  };

  const validateBrokerToken = async () => {
    try {
      const accessToken = localStorage.getItem('access_token');
      
      if (!accessToken) {
        return;
      }

      // Check broker token status
      const response = await fetch(`${config.API_BASE_URL}/api/tokens/validate-all`, {
        headers: {
          'Authorization': `Bearer ${accessToken}`,
        },
      });

      if (response.ok) {
        const data = await response.json();
        const results = data.results || [];
        
        // Check if any broker tokens need re-authentication
        const needsReauth = results.some(r => r.status === 'requires_reauth');
        
        if (needsReauth) {
          tokenLog('warn', 'broker_reauth', '[TokenRefresh] Broker tokens require re-authentication', 60000);
          // You could trigger a notification or modal here
        } else {
          tokenLog('log', 'broker_valid', '[TokenRefresh] ✓ All broker tokens valid', 60000);
        }
      }
    } catch (error) {
      console.error('[TokenRefresh] Error validating broker tokens:', error);
    }
  };

  const startAutoRefresh = () => {
    // Clear any existing timer
    if (refreshTimerRef.current) {
      clearInterval(refreshTimerRef.current);
    }

    // Immediate refresh on start (after 10 seconds delay to allow initial auth)
    setTimeout(() => {
      refreshAccessToken();
      validateBrokerToken();
    }, 10000);

    // Set up periodic refresh every 5 minutes
    refreshTimerRef.current = setInterval(async () => {
      tokenLog('log', 'scheduled_refresh', '[TokenRefresh] Running scheduled token refresh...', 60000);
      await refreshAccessToken();
      await validateBrokerToken();
    }, TOKEN_REFRESH_INTERVAL);

    tokenLog('log', 'auto_refresh_enabled', '[TokenRefresh] Auto-refresh enabled (every 5 minutes)', 15000);
  };

  const stopAutoRefresh = () => {
    if (refreshTimerRef.current) {
      clearInterval(refreshTimerRef.current);
      refreshTimerRef.current = null;
      tokenLog('log', 'auto_refresh_disabled', '[TokenRefresh] Auto-refresh disabled', 15000);
    }
  };

  useEffect(() => {
    const accessToken = localStorage.getItem('access_token');
    
    if (accessToken) {
      tokenLog('log', 'auto_refresh_init', '[TokenRefresh] Initializing auto-refresh...', 15000);
      startAutoRefresh();
    }

    // Cleanup on unmount
    return () => {
      stopAutoRefresh();
    };
  }, []); // Empty dependency array - only run once on mount

  return {
    refreshAccessToken,
    validateBrokerToken,
  };
};

export default useTokenRefresh;
