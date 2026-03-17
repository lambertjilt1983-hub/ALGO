/**
 * Browser Wake Lock Utility
 * Prevents browser/system from going to sleep during auto-trading
 * Uses multiple strategies for maximum compatibility
 */

import { dedupedConsole, errorDeduped, warnDeduped } from './consoleDeduper';

let wakeLock = null;
let keepAliveInterval = null;
let isIntentionalWakeRelease = false;

const wakeLog = (level, key, message, minIntervalMs = 0) => {
  dedupedConsole(level, `wake:${key}`, message, {
    burstWindowMs: Math.max(15000, minIntervalMs || 0),
    flushDelayMs: 1000,
    emitFirst: false,
  });
};

/**
 * Request Screen Wake Lock using modern API
 * Prevents screen from turning off
 */
export const requestWakeLock = async () => {
  try {
    if (typeof document !== 'undefined' && document.hidden) {
      wakeLog('log', 'wake_skip_hidden', '⚠️ Wake Lock request skipped: page is not visible', 15000);
      return false;
    }
    if ('wakeLock' in navigator) {
      wakeLock = await navigator.wakeLock.request('screen');
      wakeLog('log', 'wake_activated', '✅ Screen Wake Lock activated', 15000);
      
      // Listen for release events (e.g., tab loses focus)
      wakeLock.addEventListener('release', () => {
        if (!isIntentionalWakeRelease) {
          wakeLog('log', 'wake_released_event', '⚠️ Wake Lock released', 5000);
        }
        wakeLock = null;
      });
      
      return true;
    } else {
      wakeLog('log', 'wake_api_unsupported', '⚠️ Wake Lock API not supported in this browser', 60000);
      return false;
    }
  } catch (err) {
    errorDeduped('wake:request_failed', '❌ Wake Lock request failed', {
      burstWindowMs: 60000,
      flushDelayMs: 1000,
    }, err);
    return false;
  }
};

/**
 * Release the wake lock
 */
export const releaseWakeLock = async () => {
  if (wakeLock) {
    try {
      isIntentionalWakeRelease = true;
      await wakeLock.release();
      wakeLock = null;
      wakeLog('log', 'wake_released_manual', '✅ Wake Lock released', 15000);
    } catch (err) {
      errorDeduped('wake:release_failed', 'Error releasing wake lock', {
        burstWindowMs: 60000,
        flushDelayMs: 1000,
      }, err);
    } finally {
      // Reset after release event has had a chance to fire.
      setTimeout(() => {
        isIntentionalWakeRelease = false;
      }, 0);
    }
  }
};

/**
 * Fallback: Keep browser active via periodic DOM updates
 * Works on all browsers, prevents sleep on older systems
 */
export const startKeepAliveHeartbeat = () => {
  if (keepAliveInterval) return;
  
  keepAliveInterval = setInterval(() => {
    // Trigger a minimal DOM update to keep browser awake
    const now = new Date().toLocaleTimeString();
    
    // Update document title to show last heartbeat time
    if (document.title.includes('Auto Trading')) {
      document.title = `🚀 Auto Trading - Alive ${now}`;
    }
    
    // Optional network activity (avoid hardcoded endpoints)
  }, 30000); // Every 30 seconds
  
  wakeLog('log', 'heartbeat_started', '✅ Keep-alive heartbeat started (30s interval)', 15000);
};

/**
 * Stop the keep-alive heartbeat
 */
export const stopKeepAliveHeartbeat = () => {
  if (keepAliveInterval) {
    clearInterval(keepAliveInterval);
    keepAliveInterval = null;
    wakeLog('log', 'heartbeat_stopped', '✅ Keep-alive heartbeat stopped', 15000);
  }
};

/**
 * Initialize all wake lock mechanisms
 */
export const initializeWakeLock = async () => {
  wakeLog('log', 'wake_init', '🔧 Initializing browser wake lock mechanisms...', 15000);
  
  // Try modern API first (only if page visible)
  const hasModernAPI = !document.hidden ? await requestWakeLock() : false;
  
  // Always start heartbeat as fallback
  startKeepAliveHeartbeat();
  
  // Handle page visibility changes
  document.addEventListener('visibilitychange', async () => {
    if (document.hidden) {
      wakeLog('log', 'page_hidden', '⚠️ Page hidden - browser may sleep', 15000);
      startKeepAliveHeartbeat(); // Increase fallback activity
    } else {
      wakeLog('log', 'page_visible', '✅ Page visible - checking wake lock status', 15000);
      // Try to re-request if it was lost
      if (!wakeLock && 'wakeLock' in navigator) {
        const relocked = await requestWakeLock();
        if (!relocked) {
          warnDeduped('wake:restore_failed', '⚠️ Failed to restore wake lock', {
            burstWindowMs: 30000,
            flushDelayMs: 1000,
          });
        }
      }
    }
  });
  
  // Handle page unload
  window.addEventListener('beforeunload', () => {
    releaseWakeLock();
    stopKeepAliveHeartbeat();
  });
  
  return {
    wakeLockActive: !!wakeLock,
    hasModernAPI,
    heartbeatActive: !!keepAliveInterval
  };
};

/**
 * Check current wake lock status
 */
export const getWakeLockStatus = () => {
  return {
    isActive: !!wakeLock,
    hasModernAPI: 'wakeLock' in navigator,
    heartbeatRunning: !!keepAliveInterval
  };
};
