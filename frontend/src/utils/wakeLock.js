/**
 * Browser Wake Lock Utility
 * Prevents browser/system from going to sleep during auto-trading
 * Uses multiple strategies for maximum compatibility
 */

let wakeLock = null;
let keepAliveInterval = null;

/**
 * Request Screen Wake Lock using modern API
 * Prevents screen from turning off
 */
export const requestWakeLock = async () => {
  try {
    if (typeof document !== 'undefined' && document.hidden) {
      console.warn('⚠️ Wake Lock request skipped: page is not visible');
      return false;
    }
    if ('wakeLock' in navigator) {
      wakeLock = await navigator.wakeLock.request('screen');
      console.log('✅ Screen Wake Lock activated');
      
      // Listen for release events (e.g., tab loses focus)
      wakeLock.addEventListener('release', () => {
        console.log('⚠️ Wake Lock released');
        wakeLock = null;
      });
      
      return true;
    } else {
      console.warn('⚠️ Wake Lock API not supported in this browser');
      return false;
    }
  } catch (err) {
    console.error('❌ Wake Lock request failed:', err);
    return false;
  }
};

/**
 * Release the wake lock
 */
export const releaseWakeLock = async () => {
  if (wakeLock) {
    try {
      await wakeLock.release();
      wakeLock = null;
      console.log('✅ Wake Lock released');
    } catch (err) {
      console.error('Error releasing wake lock:', err);
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
  
  console.log('✅ Keep-alive heartbeat started (30s interval)');
};

/**
 * Stop the keep-alive heartbeat
 */
export const stopKeepAliveHeartbeat = () => {
  if (keepAliveInterval) {
    clearInterval(keepAliveInterval);
    keepAliveInterval = null;
    console.log('✅ Keep-alive heartbeat stopped');
  }
};

/**
 * Initialize all wake lock mechanisms
 */
export const initializeWakeLock = async () => {
  console.log('🔧 Initializing browser wake lock mechanisms...');
  
  // Try modern API first (only if page visible)
  const hasModernAPI = !document.hidden ? await requestWakeLock() : false;
  
  // Always start heartbeat as fallback
  startKeepAliveHeartbeat();
  
  // Handle page visibility changes
  document.addEventListener('visibilitychange', async () => {
    if (document.hidden) {
      console.log('⚠️ Page hidden - browser may sleep');
      startKeepAliveHeartbeat(); // Increase fallback activity
    } else {
      console.log('✅ Page visible - checking wake lock status');
      // Try to re-request if it was lost
      if (!wakeLock && 'wakeLock' in navigator) {
        const relocked = await requestWakeLock();
        if (!relocked) {
          console.warn('⚠️ Failed to restore wake lock');
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
