/**
 * Auto Token Refresh Hook
 * Automatically refreshes JWT access tokens every 5 minutes
 * Prevents login expiration and session timeouts
 */
import { useEffect, useRef } from 'react';
import config from '../config/api';
import { dedupedConsole, errorDeduped } from '../utils/consoleDeduper';

const TOKEN_REFRESH_INTERVAL = 5 * 60 * 1000; // 5 minutes in milliseconds

const tokenLog = (level, key, message, minIntervalMs = 0) => {
  dedupedConsole(level, `token:${key}`, message, {
    burstWindowMs: Math.max(15000, minIntervalMs || 0),
    flushDelayMs: 1000,
  });
};

export const useTokenRefresh = () => {
  const refreshTimerRef = useRef(null);
  const tokenBackoffUntilRef = useRef(0);

  const refreshAccessToken = async () => {
    try {
      if (typeof document !== 'undefined' && document.hidden) {
        return false;
      }
      if (Date.now() < Number(tokenBackoffUntilRef.current || 0)) {
        return false;
      }

      const refreshToken = localStorage.getItem('refresh_token');
      
      if (!refreshToken) {
        tokenLog('warn', 'no_refresh_token', '[TokenRefresh] No refresh token found - skipping refresh', 60000);
        return;
      }

      tokenLog('log', 'refresh_attempt', '[TokenRefresh] Attempting to refresh access token...', 60000);

      const response = await config.authFetch(`${config.API_BASE_URL}/auth/refresh?refresh_token=${encodeURIComponent(refreshToken)}`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        retryTransportOnce: true,
        cache: 'no-store',
      });

      if (response.ok) {
        let data = null;
        try {
          data = await response.json();
        } catch {
          tokenBackoffUntilRef.current = Date.now() + 20000;
          return false;
        }
        
        // Update access token in localStorage
        localStorage.setItem('access_token', data.access_token);
        
        tokenLog('log', 'refresh_ok', '[TokenRefresh] ✓ Access token refreshed successfully', 60000);
        
        return true;
      } else {
        let errorData = {};
        try {
          errorData = await response.json();
        } catch {}
        errorDeduped('token:refresh_failed', '[TokenRefresh] ✗ Token refresh failed', {
          burstWindowMs: 60000,
          flushDelayMs: 1000,
        }, errorData.detail);
        
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
      errorDeduped('token:refresh_error', '[TokenRefresh] Error refreshing token', {
        burstWindowMs: 60000,
        flushDelayMs: 1000,
      }, error);
      return false;
    }
  };

  const validateBrokerToken = async () => {
    try {
      if (typeof document !== 'undefined' && document.hidden) {
        return;
      }
      if (Date.now() < Number(tokenBackoffUntilRef.current || 0)) {
        return;
      }

      const accessToken = localStorage.getItem('access_token');
      
      if (!accessToken) {
        return;
      }

      // Check broker token status
      const response = await config.authFetch(`${config.API_BASE_URL}/api/tokens/validate-all`, {
        headers: {
          'Authorization': `Bearer ${accessToken}`,
        },
        retryTransportOnce: true,
        cache: 'no-store',
      });

      if (response.ok) {
        let data = null;
        try {
          data = await response.json();
        } catch {
          tokenBackoffUntilRef.current = Date.now() + 20000;
          return;
        }
        const results = Array.isArray(data?.brokers) ? data.brokers : [];
        
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
      tokenBackoffUntilRef.current = Date.now() + 20000;
      errorDeduped('token:broker_validate_error', '[TokenRefresh] Error validating broker tokens', {
        burstWindowMs: 60000,
        flushDelayMs: 1000,
      }, error);
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
