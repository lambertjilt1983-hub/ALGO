/**
 * Token Management Utility
 * Handles automatic token refresh and validation
 * Provides hooks for maintaining broker authentication state
 */

import config from './config/api';

class TokenManager {
  constructor() {
    this.tokenCheckIntervals = {};
    this.refreshAttempts = {};
  }

  /**
   * Check if a broker token is still valid
   */
  async checkTokenStatus(brokerId) {
    try {
      const token = localStorage.getItem('access_token');
      const response = await fetch(`${config.API_BASE_URL}/api/tokens/status/${brokerId}`, {
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json'
        }
      });

      if (response.ok) {
        return await response.json();
      }
      return null;
    } catch (error) {
      console.error(`Failed to check token status for broker ${brokerId}:`, error);
      return null;
    }
  }

  /**
   * Attempt to refresh broker token
   */
  async attemptTokenRefresh(brokerId) {
    try {
      const token = localStorage.getItem('access_token');
      const response = await fetch(`${config.API_BASE_URL}/api/tokens/refresh/${brokerId}`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json'
        }
      });

      if (response.ok) {
        return await response.json();
      }
      return null;
    } catch (error) {
      console.error(`Failed to refresh token for broker ${brokerId}:`, error);
      return null;
    }
  }

  /**
   * Validate all tokens for the user
   */
  async validateAllTokens() {
    try {
      const token = localStorage.getItem('access_token');
      const response = await fetch(`${config.API_BASE_URL}/api/tokens/validate-all`, {
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json'
        }
      });

      if (response.ok) {
        return await response.json();
      }
      return null;
    } catch (error) {
      console.error('Failed to validate all tokens:', error);
      return null;
    }
  }

  /**
   * Start monitoring a broker token with automatic refresh
   */
  startMonitoring(brokerId, onTokenExpired, interval = 300000) {
    // Clear any existing interval
    this.stopMonitoring(brokerId);

    console.log(`Starting token monitoring for broker ${brokerId}, interval: ${interval}ms`);

    this.tokenCheckIntervals[brokerId] = setInterval(async () => {
      try {
        const status = await this.checkTokenStatus(brokerId);
        
        if (status && !status.is_valid) {
          console.warn(`Token expired for broker ${brokerId}`);
          if (onTokenExpired) {
            onTokenExpired(brokerId, status);
          }
        }
      } catch (error) {
        console.error(`Token check failed for broker ${brokerId}:`, error);
      }
    }, interval);
  }

  /**
   * Stop monitoring a broker token
   */
  stopMonitoring(brokerId) {
    if (this.tokenCheckIntervals[brokerId]) {
      clearInterval(this.tokenCheckIntervals[brokerId]);
      delete this.tokenCheckIntervals[brokerId];
      console.log(`Stopped token monitoring for broker ${brokerId}`);
    }
  }

  /**
   * Stop all monitoring
   */
  stopAllMonitoring() {
    Object.keys(this.tokenCheckIntervals).forEach(brokerId => {
      this.stopMonitoring(brokerId);
    });
  }

  /**
   * Handle token expiration with automatic re-auth attempt
   */
  async handleTokenExpired(brokerId, onNeedReauth) {
    console.log(`Handling token expiration for broker ${brokerId}`);
    
    this.refreshAttempts[brokerId] = (this.refreshAttempts[brokerId] || 0) + 1;
    const attempt = this.refreshAttempts[brokerId];
    
    // Try to refresh up to 3 times
    if (attempt <= 3) {
      console.log(`Attempting token refresh (attempt ${attempt}/3)...`);
      
      const result = await this.attemptTokenRefresh(brokerId);
      
      if (result && result.status === 'requires_reauth') {
        console.log(`Re-authentication required for broker ${brokerId}`);
        if (onNeedReauth) {
          onNeedReauth(brokerId, result);
        }
      }
    } else {
      console.error(`Max refresh attempts reached for broker ${brokerId}`);
      if (onNeedReauth) {
        onNeedReauth(brokerId, { 
          status: 'requires_reauth',
          message: 'Max retry attempts reached. Please re-authenticate manually.'
        });
      }
    }
  }

  /**
   * Reset retry counter for a broker
   */
  resetRetryCounter(brokerId) {
    delete this.refreshAttempts[brokerId];
  }
}

export default new TokenManager();
