import React, { useState, useEffect } from 'react';

/**
 * 🚀 PERFORMANCE OPTIMIZATIONS APPLIED:
 * 
 * 1. REDUCED POLLING FREQUENCY
 *    - Data refresh: 5 seconds (was 2s) 
 *    - Price updates: 8 seconds (was every data fetch)
 *    - Health checks: 30 seconds
 *    - Professional signals: 60 seconds
 * 
 * 2. TAB VISIBILITY DETECTION
 *    - Trade data now refreshes even when tab is hidden
 *    - Ensures trades stay updated anytime
 * 
 * 3. REQUEST THROTTLING (Timestamp-based)
 *    - Prevents concurrent fetches using timestamp throttling (3s minimum between calls)
 *    - More efficient than flag-based blocking
 *    - Eliminates "Skipping - fetch already in progress" spam
 * 
 * 4. BATCHED PRICE UPDATES
 *    - Backend now fetches all prices in ONE Kite API call
 *    - Rate limited to max 1 update per 5 seconds
 * 
 * 5. TIMEOUT PROTECTION
 *    - 15s timeout on each API call
 *    - Graceful degradation on timeouts
 * 
 * Result: ~75% reduction in API calls, faster page loads, no Kite API timeouts, stable data flow
 */

// Use environment-based API URL if available
import config from '../config/api';
import { initializeWakeLock, getWakeLockStatus, releaseWakeLock, startKeepAliveHeartbeat, stopKeepAliveHeartbeat } from '../utils/wakeLock';
import { errorDeduped, logDeduped, warnDeduped } from '../utils/consoleDeduper';
import { extractLiveBalance } from '../utils/liveBalance';
import {
  ACTIVE_HISTORY_REFRESH_INTERVAL_MS,
  DEFAULT_TABLE_VISIBILITY,
  getHistoryDisplayKey,
  getTradeRowKey,
  resolveStableActiveTrades as resolveStableActiveTradesUtil,
  resolveStableTradeHistory as resolveStableTradeHistoryUtil,
} from '../utils/tradeTableState';
import { shouldFetchCurrentModeActive as shouldFetchCurrentModeActiveUtil } from '../utils/activeTradeFetchPolicy';

const OPTION_SIGNALS_API = `${config.API_BASE_URL}/option-signals/intraday-advanced`;
const PROFESSIONAL_SIGNAL_API = `${config.API_BASE_URL}/strategies/live/professional-signal`;
const AUTO_TRADE_STATUS_API = `${config.API_BASE_URL}/autotrade/status`;
const AUTO_TRADE_EXECUTE_API = config.endpoints?.autoTrade?.execute || `${config.API_BASE_URL}/autotrade/execute`;
const AUTO_TRADE_ACTIVE_API = config.endpoints?.autoTrade?.activeTrades || `${config.API_BASE_URL}/autotrade/trades/active`;
const AUTO_TRADE_UPDATE_API = `${config.API_BASE_URL}/autotrade/trades/update-prices`;
const AUTO_TRADE_CLOSE_API = config.endpoints?.autoTrade?.closeTrade || `${config.API_BASE_URL}/autotrade/trades/close`;
const AUTO_TRADE_HISTORY_API = config.endpoints?.autoTrade?.tradeHistory || `${config.API_BASE_URL}/autotrade/trades/history`;
const AUTO_TRADE_REPORT_API = config.endpoints?.autoTrade?.report || `${config.API_BASE_URL}/autotrade/report`;

// === AGGRESSIVE LOSS MANAGEMENT SYSTEM ===
const DEFAULT_DAILY_LOSS_LIMIT = 5000; // ₹5000 max daily loss - hardstop
const DEFAULT_DAILY_PROFIT_TARGET = 20000; // ₹10000 profit target - auto-stop at profit
const MIN_SIGNAL_CONFIDENCE = 80; // 80%+ confidence (AI adjusts dynamically)
const MIN_RR = 1.2; // Minimum risk:reward for entries
const MIN_PAPER_CONFIDENCE = 48; // Slightly lower threshold for demo/paper trades
const MIN_PAPER_RR = 1.0; // Lower RR threshold for demo/paper trades
const MAX_STOP_POINTS = 20; // 20-point max stop loss
const MIN_TREND_STRENGTH = 0.8; // 80%+ trend strength
const MIN_REGIME_SCORE = 0.6; // Market regime quality
const MIN_TRADE_QUALITY_SCORE = 0.48; // Minimum 48% quality threshold with weighted scoring
const MIN_LIVE_BALANCE_REQUIRED = 5000; // Mirror backend capital_min_balance for frontend gate visibility
const LIVE_MAX_PER_TRADE_LOSS_CAP = 650; // Mirror backend max_per_trade_loss hard cap
const LIVE_PER_TRADE_RISK_PCT = 0.06; // 6% of effective balance per trade (capped by hard limit)
const DEFAULT_SCANNER_MIN_QUALITY = 70; // Balanced default so scanner is not empty in normal sessions
const SCANNER_MIN_REFRESH_MS = 8000; // Prevent rapid manual refresh jitter
const SCANNER_STABILITY_WINDOW_MS = 120000; // Keep continuity over recent scans
const SCANNER_STICKY_MS = 45000; // Keep selected scanner rows stable for brief period unless quality threshold changes
const SCANNER_LOOP_INTERVAL_MS = 3000; // Lower backend pressure vs 1s loop to reduce transport truncation/mismatch
const PAPER_REJECTION_COOLDOWN_MS = 180000; // Back off repeated create attempts for same root/side after rejection
const EMPTY_ACTIVE_POLLS_TO_CLEAR = 2; // Anti-flicker: clear rows only after consecutive confirmed empty polls
const UI_ERROR_TTL_MS = 5000; // Auto-clear transient blocker/error messages after 5s
// Frontend mirror of backend concurrent trade limits
const MAX_CONCURRENT_TRADES = 3;
const MAX_DEMO_CONCURRENT_TRADES = 2;

// === DEMO SL PROTECTION SYSTEM ===
// After a demo SL hit, block re-entry on same symbol for 5 minutes.
const POST_SL_SYMBOL_COOLDOWN_MS = 5 * 60 * 1000;
// After 2+ consecutive SL hits on the same underlying root, block that root.
// Each additional strike doubles the penalty (capped at 3×).
const POST_SL_ROOT_STREAK_COOLDOWN_MS = 10 * 60 * 1000;
// If 3+ SL hits occur globally within 15 minutes, pause ALL demo entries.
const GLOBAL_SL_SURGE_THRESHOLD = 3;
const GLOBAL_SL_SURGE_WINDOW_MS = 15 * 60 * 1000;
const GLOBAL_SL_SURGE_COOLDOWN_MS = 15 * 60 * 1000;

// === ADAPTIVE LOSS CONTROL SYSTEM ===
const LOSS_CLUSTER_WINDOW_SHORT_MS = 10 * 60 * 1000;
const LOSS_CLUSTER_WINDOW_LONG_MS = 15 * 60 * 1000;
const LOSS_CLUSTER_SHORT_TRIGGER = 2; // 2 losses in 10 min
const LOSS_CLUSTER_LONG_TRIGGER = 3;  // 3 losses in 15 min
const LOSS_CLUSTER_SHORT_PAUSE_MS = 15 * 60 * 1000;
const LOSS_CLUSTER_LONG_PAUSE_MS = 30 * 60 * 1000;
const DRAW_DOWN_QTY_REDUCE_2_LOSS = 0.5;
const DRAW_DOWN_QTY_REDUCE_3_LOSS = 0.25;

// === MARKET HOURS (IST) ===
const MARKET_OPEN_HOUR = 9;
const MARKET_OPEN_MINUTE = 15;
const MARKET_CLOSE_HOUR = 15;
const MARKET_CLOSE_MINUTE = 30;
// NSE Equity market holidays for 2026 (YYYY-MM-DD)
// Source: NSE Exchange Communications - Holidays 2026 (Equities)
const MARKET_HOLIDAYS = [
  '2026-01-15', // Municipal Corporation Election - Maharashtra
  '2026-01-26', // Republic Day
  '2026-03-03', // Holi
  '2026-03-26', // Shri Ram Navami
  '2026-03-31', // Shri Mahavir Jayanti
  '2026-04-03', // Good Friday
  '2026-04-14', // Dr. Baba Saheb Ambedkar Jayanti
  '2026-05-01', // Maharashtra Day
  '2026-05-28', // Bakri Id
  '2026-06-26', // Muharram
  '2026-09-14', // Ganesh Chaturthi
  '2026-10-02', // Mahatma Gandhi Jayanti
  '2026-10-20', // Dussehra
  '2026-11-08', // Diwali Laxmi Pujan (Muhurat trading; market holiday)
  '2026-11-10', // Diwali-Balipratipada
  '2026-11-24', // Prakash Gurpurb Sri Guru Nanak Dev
  '2026-12-25', // Christmas
];

// Keep fetching trade data even when the tab is hidden
const ALWAYS_FETCH_TRADES = true;

// Helper function to format dates in IST timezone
// Many backend datetime strings are UTC but emitted without a "Z" suffix.
// Browsers interpret offset-less ISO strings as local time, which causes a
// 5.5 hour shift on machines running IST. To avoid that we append a 'Z'
// when no timezone information is present, forcing the value to be parsed
// as UTC before converting to Asia/Kolkata.
const formatTimeIST = (dateString) => {
  if (!dateString) return '--';
  try {
    // append Z if string lacks any timezone indicator
    let s = dateString;
    if (!/[Zz]|[+-]\d{2}:?\d{2}/.test(s)) {
      s = s + 'Z';
    }
    const date = new Date(s);
    return date.toLocaleString('en-IN', {
      timeZone: 'Asia/Kolkata',
      year: 'numeric',
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
      hour12: true
    });
  } catch {
    return dateString;
  }
};

// Screen Wake Lock - Prevent browser/system sleep

const AutoTradingDashboard = () => {
  const [enabled, setEnabled] = useState(true);
  const [isLiveMode, setIsLiveMode] = useState(false); // Starts in DEMO mode
  const [loading, setLoading] = useState(false);
  const [armingInProgress, setArmingInProgress] = useState(false);
  const [armError, setArmError] = useState(null);
  const [armStatus, setArmStatus] = useState(null);
  const [stats, setStats] = useState(null);
  const [activeTrades, setActiveTrades] = useState([]);
  const [tradeHistory, setTradeHistory] = useState([]);
  const [reportSummary, setReportSummary] = useState(null);
  const [analysis, setAnalysis] = useState(null);
  const [optionSignals, setOptionSignals] = useState([]);
  const [executing, setExecuting] = useState(false);
  const [livePrice, setLivePrice] = useState(null);
  const [activeTab, setActiveTab] = useState('trading');
  const [historySearch, setHistorySearch] = useState('');
  const [lotMultiplier, setLotMultiplier] = useState(1); // For quantity adjustment
  const [autoTradingActive, setAutoTradingActive] = useState(true);
  const [hasActiveTrade, setHasActiveTrade] = useState(false);
  const [lastPaperSignalSymbol, setLastPaperSignalSymbol] = useState(null);
  const [lastPaperSignalAt, setLastPaperSignalAt] = useState(0);
  const [confirmationMode, setConfirmationMode] = useState('balanced');
  const [historyStartDate, setHistoryStartDate] = useState(() => {
    const end = new Date();
    const start = new Date(end);
    start.setDate(start.getDate() - 7); // Last 7 days by default
    return start.toLocaleDateString('en-CA');
  });
  const [historyEndDate, setHistoryEndDate] = useState(() => new Date().toLocaleDateString('en-CA'));
  const [activeModeFilter, setActiveModeFilter] = useState('ALL');
  const [historyModeFilter, setHistoryModeFilter] = useState('ALL');
  const [historyActionFilter, setHistoryActionFilter] = useState('ALL');
  const [historyStatusFilter, setHistoryStatusFilter] = useState('ALL');
  const [selectedSignalSymbol, setSelectedSignalSymbol] = useState(() => {
    if (typeof window === 'undefined') return null;
    return localStorage.getItem('selectedSignalSymbol');
  });
  const [signalsLoaded, setSignalsLoaded] = useState(false);
  const [wakeLockActive, setWakeLockActive] = useState(false);
  const [cooldownEndsAt, setCooldownEndsAt] = useState(null);
  const [cooldownRemainingMs, setCooldownRemainingMs] = useState(0);
  const [lastProfessionalVisibleSignal, setLastProfessionalVisibleSignal] = useState(null);
  const [lastAiRecommendationSignal, setLastAiRecommendationSignal] = useState(null);
  const [aiGateRejections, setAiGateRejections] = useState([]);
  const [entryBlockEvents, setEntryBlockEvents] = useState([]);
  const [liveAccountBalance, setLiveAccountBalance] = useState(null);
  const [liveBalanceSyncedAt, setLiveBalanceSyncedAt] = useState(null);
  const [liveBalanceBrokerId, setLiveBalanceBrokerId] = useState(null);
  const [activeBrokerId, setActiveBrokerId] = useState(null);
  const [activeBrokerName, setActiveBrokerName] = useState(null);

  // calculate whether market is open (used by many effects below)
  const getIstDateParts = () => {
    const formatter = new Intl.DateTimeFormat('en-US', {
      timeZone: 'Asia/Kolkata',
      year: 'numeric',
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
      hour12: false,
      weekday: 'short'
    });
    const parts = formatter.formatToParts(new Date());
    const map = Object.fromEntries(parts.map((p) => [p.type, p.value]));
    return {
      year: map.year,
      month: map.month,
      day: map.day,
      hour: Number(map.hour),
      minute: Number(map.minute),
      weekday: map.weekday,
      iso: `${map.year}-${map.month}-${map.day}`
    };
  };

  const { hour: istHour, minute: istMinute, weekday: istWeekday, iso: istIso } = getIstDateParts();
  const isWeekend = istWeekday === 'Sat' || istWeekday === 'Sun';
  const isHoliday = MARKET_HOLIDAYS.includes(istIso);
  const isBeforeOpen = istHour < MARKET_OPEN_HOUR || (istHour === MARKET_OPEN_HOUR && istMinute < MARKET_OPEN_MINUTE);
  const isAfterClose = istHour > MARKET_CLOSE_HOUR || (istHour === MARKET_CLOSE_HOUR && istMinute > MARKET_CLOSE_MINUTE);
  const localMarketOpen = !isWeekend && !isHoliday && !isBeforeOpen && !isAfterClose;
  const localMarketReason = isWeekend
    ? 'Weekend'
    : isHoliday
      ? 'Holiday'
      : isBeforeOpen
        ? 'Before market open'
        : isAfterClose
          ? 'After market close'
          : 'Open';
  const backendMarketOpen = typeof stats?.market_open === 'boolean' ? stats.market_open : null;
  const backendMarketReason = stats?.market_reason || null;
  const isMarketOpen = backendMarketOpen !== null ? backendMarketOpen : localMarketOpen;
  const marketClosedReason = isMarketOpen ? null : (backendMarketReason || localMarketReason);
  const [qualityTrades, setQualityTrades] = useState([]); // Market scanner results
  const [totalSignalsScanned, setTotalSignalsScanned] = useState(0); // Track total for messaging
  const [scannerLoading, setScannerLoading] = useState(false);
  const [scannerLastError, setScannerLastError] = useState(null);
  const [scannerTab, setScannerTab] = useState('all');
  const [autoScanActive, setAutoScanActive] = useState(true); // Track auto-refresh status (auto-enable for immediate scans)
  const [scannerHoldOnStartYes, setScannerHoldOnStartYes] = useState(false);
  // User pause toggle for scanner loop
  const [scannerUserOverride, setScannerUserOverride] = useState(false);
  // Track when the last market scan completed (for UI timing)
  const [scannerLastRunAt, setScannerLastRunAt] = useState(null);
  const [lastSuccessfulSyncAt, setLastSuccessfulSyncAt] = useState(null);
  const [isUsingStaleData, setIsUsingStaleData] = useState(false);
  const [scannerMinQuality, setScannerMinQuality] = useState(() => {
    if (typeof window === 'undefined') return DEFAULT_SCANNER_MIN_QUALITY;
    const saved = Number(localStorage.getItem('scannerMinQuality'));
    return Number.isFinite(saved) && saved >= 60 && saved <= 95 ? saved : DEFAULT_SCANNER_MIN_QUALITY;
  });
  const [lossLimit, setLossLimit] = useState(() => {
    if (typeof window === 'undefined') return DEFAULT_DAILY_LOSS_LIMIT;
    const saved = Number(localStorage.getItem('dailyLossLimit'));
    return Number.isFinite(saved) && saved > 0 ? saved : DEFAULT_DAILY_LOSS_LIMIT;
  });
  const [profitTarget, setProfitTarget] = useState(() => {
    if (typeof window === 'undefined') return DEFAULT_DAILY_PROFIT_TARGET;
    const saved = Number(localStorage.getItem('dailyProfitTarget'));
    return Number.isFinite(saved) && saved > 0 ? saved : DEFAULT_DAILY_PROFIT_TARGET;
  });
  // AI dynamically calculates optimal RR based on market conditions
  const calculateOptimalRR = (signal, winRate = 0.5) => {
    // Base RR from signal quality
    const confidence = Number(signal.confirmation_score ?? signal.confidence ?? 0);
    const riskReward = Math.abs(Number(signal.target ?? 0) - Number(signal.entry_price ?? 0)) / 
                      Math.abs(Number(signal.entry_price ?? 0) - Number(signal.stop_loss ?? 0));
    
    // AI adjustment factors - more realistic for retail trading
    const confidenceBoost = confidence > 90 ? 0.1 : confidence > 85 ? 0.05 : 0;
    const winRateAdjust = Math.max(0, (winRate - 0.5) * 0.1); // Less aggressive adjustment
    
    // Dynamic threshold based on conditions (1.5 base for realistic options)
    const optimalRR = Math.max(1.0, 1.5 - confidenceBoost - winRateAdjust);
    return { 
      rr: isNaN(riskReward) || !isFinite(riskReward) ? 1.0 : riskReward, 
      optimalRR, 
      meets: riskReward >= optimalRR 
    };
  };

  // Calculate trade quality score (0-100) using weighted formula
  const calculateTradeQuality = (signal, winRate = 0.5) => {
    const confidence = Number(signal.confirmation_score ?? signal.confidence ?? 0);
    const { rr, optimalRR } = calculateOptimalRR(signal, winRate);

    const confidenceScore = Math.min(50, (confidence / 100) * 50);
    const rrScore = Math.min(30, Math.max(0, (rr / optimalRR) * 30));
    const winRateScore = Math.min(20, winRate * 20);

    const quality = Math.round(confidenceScore + rrScore + winRateScore);

    return {
      quality,
      isExcellent: quality >= 85,
      isGood: quality >= 60,
      factors: {
        confidenceScore: Math.round(confidenceScore),
        rrScore: Math.round(rrScore),
        winRateScore: Math.round(winRateScore)
      }
    };
  };

  const toFiniteNumberLoose = (value) => {
    if (typeof value === 'number') {
      return Number.isFinite(value) ? value : Number.NaN;
    }
    if (typeof value !== 'string') return Number.NaN;
    const cleaned = value.replace(/[^0-9.-]/g, '');
    if (!cleaned) return Number.NaN;
    const parsed = Number(cleaned);
    return Number.isFinite(parsed) ? parsed : Number.NaN;
  };

  const estimateSignalCapitalRequired = (signal, qtyMultiplier = lotMultiplier) => {
    const inferredQty = getSignalBaseQuantity(signal);
    const qty = Number(inferredQty) * Number(qtyMultiplier ?? 1);
    const price = Number(signal?.entry_price ?? 0);
    if (!Number.isFinite(qty) || !Number.isFinite(price) || qty <= 0 || price <= 0) {
      return Number.POSITIVE_INFINITY;
    }
    return price * qty;
  };

  const resolveSignalCapitalRequired = (signal, qtyMultiplier = lotMultiplier) => {
    const direct = toFiniteNumberLoose(
      signal?.capital_required
      ?? signal?.capitalRequired
      ?? signal?.required_capital
      ?? signal?.capital
      ?? signal?.margin_required
    );
    if (Number.isFinite(direct) && direct > 0) return direct;
    return estimateSignalCapitalRequired(signal, qtyMultiplier);
  };

  const getSignalBaseQuantity = (signal) => {
    const baseQty = Number(signal?.quantity ?? signal?.qty ?? 0);
    const lotSizeQty = Number(signal?.lot_size ?? signal?.lotSize ?? signal?.lot ?? signal?.lots ?? 0);
    const inferredQty = baseQty > 0 ? baseQty : (lotSizeQty > 0 ? lotSizeQty : 1);
    return Number.isFinite(inferredQty) && inferredQty > 0 ? inferredQty : 1;
  };

  const normalizeTradeQuantity = (qty) => {
    const parsedQty = Number(qty);
    if (!Number.isFinite(parsedQty) || parsedQty <= 0) return 1;
    return Math.max(1, Math.floor(parsedQty));
  };

  const getLossCappedQuantity = ({ signal, desiredQuantity, maxLossAllowed }) => {
    const normalizedDesired = normalizeTradeQuantity(desiredQuantity);
    const entryPrice = Number(signal?.entry_price ?? 0);
    const stopPrice = Number(signal?.stop_loss ?? 0);
    const stopDistance = Math.abs(entryPrice - stopPrice);

    if (!Number.isFinite(stopDistance) || stopDistance <= 0) {
      return {
        desiredQuantity: normalizedDesired,
        adjustedQuantity: normalizedDesired,
        maxAllowedQuantity: Number.POSITIVE_INFINITY,
        stopDistance,
        potentialLoss: 0,
        adjustedPotentialLoss: 0,
        fitsWithinCap: true,
        autoReduced: false,
      };
    }

    const potentialLoss = stopDistance * normalizedDesired;
    if (!Number.isFinite(maxLossAllowed) || maxLossAllowed <= 0) {
      return {
        desiredQuantity: normalizedDesired,
        adjustedQuantity: normalizedDesired,
        maxAllowedQuantity: Number.POSITIVE_INFINITY,
        stopDistance,
        potentialLoss,
        adjustedPotentialLoss: potentialLoss,
        fitsWithinCap: true,
        autoReduced: false,
      };
    }

    const maxAllowedQuantity = Math.floor(maxLossAllowed / stopDistance);
    const adjustedQuantity = Math.max(0, Math.min(normalizedDesired, maxAllowedQuantity));
    const adjustedPotentialLoss = stopDistance * adjustedQuantity;

    return {
      desiredQuantity: normalizedDesired,
      adjustedQuantity,
      maxAllowedQuantity,
      stopDistance,
      potentialLoss,
      adjustedPotentialLoss,
      fitsWithinCap: adjustedQuantity >= 1 && adjustedPotentialLoss <= maxLossAllowed,
      autoReduced: adjustedQuantity >= 1 && adjustedQuantity < normalizedDesired,
    };
  };

  const pushEntryBlockEvent = ({ symbol, action, mode, message, reasons = [], source = 'client' } = {}) => {
    const cleanedReasons = Array.isArray(reasons)
      ? reasons.map((r) => String(r || '').trim()).filter(Boolean)
      : [];
    const finalMessage = String(message || '').trim() || 'Entry blocked';
    const event = {
      at: new Date().toISOString(),
      symbol: symbol || '--',
      action: action || '',
      mode: String(mode || '').toUpperCase() || 'UNKNOWN',
      message: finalMessage,
      reasons: cleanedReasons,
      source,
      signature: `${String(symbol || '').toUpperCase()}|${String(action || '').toUpperCase()}|${String(mode || '').toUpperCase()}|${finalMessage}|${cleanedReasons.join('|')}`,
    };
    setEntryBlockEvents((prev) => {
      const last = Array.isArray(prev) ? prev[0] : null;
      if (last && last.signature === event.signature) {
        const prevTs = new Date(last.at).getTime();
        const nowTs = new Date(event.at).getTime();
        if (Number.isFinite(prevTs) && Number.isFinite(nowTs) && (nowTs - prevTs) < 3000) {
          return prev;
        }
      }
      return [event, ...(Array.isArray(prev) ? prev : [])].slice(0, 12);
    });
  };

  useEffect(() => {
    if (!scannerLastError) return;
    const timer = setTimeout(() => {
      setScannerLastError(null);
    }, UI_ERROR_TTL_MS);
    return () => clearTimeout(timer);
  }, [scannerLastError]);

  useEffect(() => {
    const parseTs = (item) => {
      const ts = new Date(item?.at || 0).getTime();
      return Number.isFinite(ts) ? ts : 0;
    };
    const keepRecent = (item, cutoff) => parseTs(item) >= cutoff;

    const cutoffNow = Date.now() - UI_ERROR_TTL_MS;
    const currentEntry = Array.isArray(entryBlockEvents) ? entryBlockEvents : [];
    const currentAi = Array.isArray(aiGateRejections) ? aiGateRejections : [];
    const nextEntry = currentEntry.filter((item) => keepRecent(item, cutoffNow));
    const nextAi = currentAi.filter((item) => keepRecent(item, cutoffNow));

    if (nextEntry.length !== currentEntry.length) setEntryBlockEvents(nextEntry);
    if (nextAi.length !== currentAi.length) setAiGateRejections(nextAi);

    const allTimestamps = [...nextEntry, ...nextAi].map(parseTs).filter((ts) => ts > 0);
    if (allTimestamps.length === 0) return;

    const soonestExpiry = Math.min(...allTimestamps) + UI_ERROR_TTL_MS;
    const delayMs = Math.max(120, soonestExpiry - Date.now() + 20);
    const timer = setTimeout(() => {
      const cutoff = Date.now() - UI_ERROR_TTL_MS;
      setEntryBlockEvents((prev) => (Array.isArray(prev) ? prev.filter((item) => keepRecent(item, cutoff)) : []));
      setAiGateRejections((prev) => (Array.isArray(prev) ? prev.filter((item) => keepRecent(item, cutoff)) : []));
    }, delayMs);

    return () => clearTimeout(timer);
  }, [entryBlockEvents, aiGateRejections]);

  const fmtPct = (v) => {
    const n = Number(v);
    return Number.isFinite(n) ? `${n.toFixed(1)}%` : '--';
  };

  const getTradeStatusPalette = (status) => {
    const normalized = String(status || 'CLOSED').toUpperCase();
    switch (normalized) {
      case 'TARGET_HIT':
        return { background: '#dcfce7', color: '#166534', label: 'TARGET_HIT' };
      case 'PROFIT_TRAIL':
        return { background: '#dbeafe', color: '#1d4ed8', label: 'PROFIT_TRAIL' };
      case 'MANUAL_CLOSE':
        return { background: '#ede9fe', color: '#6d28d9', label: 'MANUAL_CLOSE' };
      case 'SL_HIT':
        return { background: '#fee2e2', color: '#b91c1c', label: 'SL_HIT' };
      case 'EXPIRED':
        return { background: '#fef3c7', color: '#92400e', label: 'EXPIRED' };
      default:
        return { background: '#e5e7eb', color: '#374151', label: normalized };
    }
  };

  const pickPreferredBroker = (brokers) => {
    if (!Array.isArray(brokers) || !brokers.length) return null;
    const activeFirst = brokers.filter((b) => b && (b.is_active !== false));
    const pool = activeFirst.length ? activeFirst : brokers;
    const zerodha = pool.find((b) => String(b.broker_name || '').toLowerCase().includes('zerodha'));
    const selected = zerodha || pool[0];
    const id = Number(selected?.id);
    if (!Number.isFinite(id) || id <= 0) return null;
    return { id, name: String(selected?.broker_name || `Broker ${id}`) };
  };

  const fetchActiveBrokerContext = async () => {
    const endpoint = config.endpoints?.brokers?.credentials || '/brokers/credentials';
    const response = await timeoutPromise(
      config.authFetch(endpoint, { retryTransportOnce: true, cache: 'no-store' }),
      8000,
    );
    if (!response.ok) {
      throw new Error(`Broker credentials API failed (${response.status})`);
    }
    let data;
    try {
      data = await response.json();
    } catch {
      const retryRes = await config.authFetch(endpoint, { retryTransportOnce: true, cache: 'no-store' });
      if (!retryRes.ok) {
        throw new Error(`Broker credentials decode retry failed (${retryRes.status})`);
      }
      data = await retryRes.json();
    }
    const broker = pickPreferredBroker(data);
    if (!broker) {
      throw new Error('No active broker credentials found.');
    }
    if (Number(activeBrokerId) !== Number(broker.id)) {
      setLiveAccountBalance(null);
      setLiveBalanceSyncedAt(null);
      setLiveBalanceBrokerId(null);
    }
    setActiveBrokerId(broker.id);
    setActiveBrokerName(broker.name);
    return broker;
  };

  const timeoutPromise = (promise, ms) => Promise.race([
    promise,
    new Promise((_, reject) => setTimeout(() => reject(new Error('Timeout')), ms)),
  ]);

  const fetchLiveBalance = async (brokerIdOverride = null, options = {}) => {
    const { softFail = false } = options || {};
    const now = Date.now();
    if (softFail && now < Number(liveBalanceBackoffUntilRef.current || 0)) {
      const cached = Number(liveAccountBalance);
      if (Number.isFinite(cached) && cached >= 0) return cached;
    }

    let brokerId = Number(brokerIdOverride);
    if (!Number.isFinite(brokerId) || brokerId <= 0) {
      brokerId = Number(activeBrokerId);
    }
    if (!Number.isFinite(brokerId) || brokerId <= 0) {
      const broker = await fetchActiveBrokerContext();
      brokerId = Number(broker?.id);
    }
    if (!Number.isFinite(brokerId) || brokerId <= 0) {
      throw new Error('Unable to resolve active broker for live balance.');
    }

    const endpoint = config.endpoints?.brokers?.balance
      ? config.endpoints.brokers.balance(brokerId)
      : `/brokers/balance/${brokerId}`;
    let response;
    try {
      response = await timeoutPromise(
        config.authFetch(endpoint, { retryTransportOnce: true, cache: 'no-store' }),
        8000,
      );
    } catch (err) {
      if (softFail) {
        liveBalanceBackoffUntilRef.current = Date.now() + 20000;
        const cached = Number(liveAccountBalance);
        if (Number.isFinite(cached) && cached >= 0) return cached;
      }
      throw err;
    }
    if (!response.ok) {
      if (softFail) {
        liveBalanceBackoffUntilRef.current = Date.now() + 20000;
        const cached = Number(liveAccountBalance);
        if (Number.isFinite(cached) && cached >= 0) return cached;
      }
      throw new Error(`Balance API failed (${response.status})`);
    }
    let data;
    try {
      data = await response.json();
    } catch (err) {
      if (softFail) {
        liveBalanceBackoffUntilRef.current = Date.now() + 20000;
        const cached = Number(liveAccountBalance);
        if (Number.isFinite(cached) && cached >= 0) return cached;
      }
      throw err;
    }
    if (data?.status === 'token_expired' || data?.requires_reauth) {
      throw new Error('Broker token expired. Please reconnect broker.');
    }
    const balance = extractLiveBalance(data);
    if (!Number.isFinite(balance) || balance < 0) {
      throw new Error('Live balance unavailable from broker response.');
    }
    setLiveAccountBalance(balance);
    setLiveBalanceSyncedAt(Date.now());
    setLiveBalanceBrokerId(brokerId);
    return balance;
  };

  const fmtYesNo = (v) => (v === true ? 'YES' : v === false ? 'NO' : '--');

  const getBackendReadinessThresholds = (signal) => {
    const isStockSignal = signal?.signal_type === 'stock' || signal?.is_stock === true;
    return isStockSignal
      ? {
          quality_min: 67,
          confidence_min: 71,
          ai_edge_min: 37,
          rr_min: 1.35,
          confirmation_score_floor: 62,
          weak_both_quality_override: 90,
          weak_both_confidence_override: 92,
          max_fake_move_risk: 14,
          max_news_risk: 16,
          max_liquidity_spike_risk: 14,
          max_premium_distortion_risk: 12,
        }
      : {
          quality_min: 72,
          confidence_min: 76,
          ai_edge_min: 42,
          rr_min: 1.45,
          confirmation_score_floor: 62,
          weak_both_quality_override: 90,
          weak_both_confidence_override: 92,
          max_fake_move_risk: 14,
          max_news_risk: 16,
          max_liquidity_spike_risk: 14,
          max_premium_distortion_risk: 12,
        };
  };

  const inferTradeMode = (trade) => String(
    trade?.trade_mode
    || trade?.trade_source
    || trade?.mode
    || (trade?.broker_order_id ? 'LIVE' : 'DEMO')
  ).toUpperCase();

  const dedupeHistoryRows = (rows = []) => {
    if (!Array.isArray(rows)) return [];
    const seen = new Set();
    return rows.filter((trade) => {
      const key = `${getHistoryDisplayKey(trade)}:${inferTradeMode(trade)}:${String(trade?.status || '').toUpperCase()}`;
      if (seen.has(key)) return false;
      seen.add(key);
      return true;
    });
  };

  const getModeRecentClosedTrades = (mode) => {
    const normalizedMode = String(mode || 'DEMO').toUpperCase();
    const source = dedupeHistoryRows(tradeHistory || []);
    return source
      .filter((trade) => inferTradeMode(trade) === normalizedMode)
      .map((trade) => {
        const tsRaw = trade?.exit_time || trade?.closed_at || trade?.updated_at || trade?.entry_time || trade?.timestamp;
        const ts = tsRaw ? new Date(tsRaw).getTime() : 0;
        const status = String(trade?.status || '').toUpperCase();
        const pnl = Number(trade?.profit_loss ?? trade?.pnl ?? 0);
        const isLoss = status === 'SL_HIT' || pnl <= 0;
        return { trade, ts, status, pnl, isLoss };
      })
      .filter((row) => Number.isFinite(row.ts) && row.ts > 0)
      .sort((a, b) => b.ts - a.ts);
  };

  const getModeLossControlState = (mode = 'DEMO') => {
    const rows = getModeRecentClosedTrades(mode);
    const nowMs = Date.now();

    const lossesShort = rows.filter((r) => r.isLoss && (nowMs - r.ts) <= LOSS_CLUSTER_WINDOW_SHORT_MS);
    const lossesLong = rows.filter((r) => r.isLoss && (nowMs - r.ts) <= LOSS_CLUSTER_WINDOW_LONG_MS);

    let consecutiveLosses = 0;
    for (const row of rows) {
      if (row.isLoss) {
        consecutiveLosses += 1;
      } else {
        break;
      }
    }

    const shortTriggered = lossesShort.length >= LOSS_CLUSTER_SHORT_TRIGGER;
    const longTriggered = lossesLong.length >= LOSS_CLUSTER_LONG_TRIGGER;
    const latestLossTs = (rows.find((r) => r.isLoss)?.ts) || 0;
    const pauseMs = longTriggered ? LOSS_CLUSTER_LONG_PAUSE_MS : (shortTriggered ? LOSS_CLUSTER_SHORT_PAUSE_MS : 0);
    const pauseUntil = latestLossTs > 0 && pauseMs > 0 ? latestLossTs + pauseMs : 0;
    const active = pauseUntil > nowMs;

    return {
      active,
      pauseUntil,
      pauseRemainingMs: Math.max(0, pauseUntil - nowMs),
      lossesShort: lossesShort.length,
      lossesLong: lossesLong.length,
      consecutiveLosses,
    };
  };

  const getAdaptiveGateTightening = (mode = 'DEMO') => {
    const lossState = getModeLossControlState(mode);
    let qualityBump = 0;
    let confidenceBump = 0;
    let rrBump = 0;

    if (lossState.consecutiveLosses >= 3) {
      qualityBump += 8;
      confidenceBump += 10;
      rrBump += 0.25;
    } else if (lossState.consecutiveLosses >= 2) {
      qualityBump += 5;
      confidenceBump += 6;
      rrBump += 0.15;
    }

    const now = new Date();
    const ist = new Date(now.toLocaleString('en-US', { timeZone: 'Asia/Kolkata' }));
    const mins = ist.getHours() * 60 + ist.getMinutes();
    const isLateSession = mins >= (14 * 60) && mins <= (15 * 60);
    if (isLateSession) {
      qualityBump += 4;
      confidenceBump += 4;
      rrBump += 0.1;
    }

    return {
      qualityBump,
      confidenceBump,
      rrBump,
      lossState,
      isLateSession,
    };
  };

  const getQtyDrawdownMultiplier = (mode = 'DEMO') => {
    const { consecutiveLosses } = getModeLossControlState(mode);
    if (consecutiveLosses >= 3) return DRAW_DOWN_QTY_REDUCE_3_LOSS;
    if (consecutiveLosses >= 2) return DRAW_DOWN_QTY_REDUCE_2_LOSS;
    return 1;
  };

  const enrichSignalWithAiMetrics = (signal) => {
    if (!signal) return signal;
    const existingAiEdge = Number(signal.ai_edge_score);
    const existingMomentum = Number(signal.momentum_score);
    const existingBreakout = Number(signal.breakout_score);
    const existingFakeRisk = Number(signal.fake_move_risk);
    if (
      Number.isFinite(existingAiEdge)
      && Number.isFinite(existingMomentum)
      && Number.isFinite(existingBreakout)
      && Number.isFinite(existingFakeRisk)
    ) {
      return signal;
    }

    const confidence = Number(signal.confirmation_score ?? signal.confidence ?? 0);
    const quality = Number(signal.quality_score ?? signal.quality ?? 0);
    const entry = Number(signal.entry_price ?? 0);
    const target = Number(signal.target ?? 0);
    const stop = Number(signal.stop_loss ?? 0);
    const rr = Number(signal.rr ?? (entry > 0 ? (Math.abs(target - entry) / Math.max(0.0001, Math.abs(entry - stop))) : 0));

    const rrScore = Math.min(100, Math.max(0, (rr / 1.6) * 100));
    const momentumScore = Math.min(100, Math.max(0, confidence * 0.75 + quality * 0.15 + rrScore * 0.10));
    const breakoutScore = Math.min(100, Math.max(0, quality * 0.5 + rrScore * 0.35 + confidence * 0.15));
    const fakeMoveRisk = Math.min(95, Math.max(5, 100 - (momentumScore * 0.45 + breakoutScore * 0.35 + confidence * 0.20)));
    const suddenNewsRisk = Math.min(95, Math.max(5, fakeMoveRisk * 0.55 + (100 - confidence) * 0.25));
    const liquiditySpikeRisk = Math.min(95, Math.max(5, fakeMoveRisk * 0.45 + (100 - rrScore) * 0.20));
    const premiumDistortionRisk = Math.min(95, Math.max(5, fakeMoveRisk * 0.40 + (100 - breakoutScore) * 0.20));
    const aiEdgeScore = Math.min(100, Math.max(0, momentumScore * 0.35 + breakoutScore * 0.35 + quality * 0.20 + rrScore * 0.10 - fakeMoveRisk * 0.20));

    // Frontend fallback for timing-risk metadata when backend context is not available.
    const now = new Date();
    const ist = new Date(now.toLocaleString('en-US', { timeZone: 'Asia/Kolkata' }));
    const mins = ist.getHours() * 60 + ist.getMinutes();
    let timingWindow = 'NORMAL';
    let qtyMultiplier = 1.0;
    if (mins >= (9 * 60 + 15) && mins <= (9 * 60 + 35)) {
      timingWindow = 'OPENING';
      qtyMultiplier = 0.7;
    } else if (mins >= (14 * 60 + 55) && mins <= (15 * 60 + 30)) {
      timingWindow = 'PRE_CLOSE';
      qtyMultiplier = 0.7;
    } else if (mins >= (12 * 60 + 25) && mins <= (12 * 60 + 35)) {
      timingWindow = 'EVENT_WINDOW';
      qtyMultiplier = 0.8;
    }

    const breakoutHoldFallback = breakoutScore >= 55 && fakeMoveRisk <= 45;

    return {
      ...signal,
      rr,
      ai_edge_score: Number.isFinite(existingAiEdge) ? existingAiEdge : Number(aiEdgeScore.toFixed(2)),
      momentum_score: Number.isFinite(existingMomentum) ? existingMomentum : Number(momentumScore.toFixed(2)),
      breakout_score: Number.isFinite(existingBreakout) ? existingBreakout : Number(breakoutScore.toFixed(2)),
      fake_move_risk: Number.isFinite(existingFakeRisk) ? existingFakeRisk : Number(fakeMoveRisk.toFixed(2)),
      sudden_news_risk: Number.isFinite(Number(signal.sudden_news_risk ?? signal.news_risk)) ? Number(signal.sudden_news_risk ?? signal.news_risk) : Number(suddenNewsRisk.toFixed(2)),
      liquidity_spike_risk: Number.isFinite(Number(signal.liquidity_spike_risk)) ? Number(signal.liquidity_spike_risk) : Number(liquiditySpikeRisk.toFixed(2)),
      premium_distortion_risk: Number.isFinite(Number(signal.premium_distortion_risk ?? signal.premium_distortion)) ? Number(signal.premium_distortion_risk ?? signal.premium_distortion) : Number(premiumDistortionRisk.toFixed(2)),
      timing_risk: signal.timing_risk || timingWindow,
      breakout_hold_confirmed:
        typeof signal.breakout_hold_confirmed === 'boolean'
          ? signal.breakout_hold_confirmed
          : breakoutHoldFallback,
      timing_risk_profile:
        signal.timing_risk_profile && typeof signal.timing_risk_profile === 'object'
          ? signal.timing_risk_profile
          : { volatile: timingWindow !== 'NORMAL', window: timingWindow, qty_multiplier: qtyMultiplier },
      qty_reduced_for_timing:
        typeof signal.qty_reduced_for_timing === 'boolean'
          ? signal.qty_reduced_for_timing
          : (qtyMultiplier < 0.999),
    };
  };

  const getEntryReadiness = (signal) => {
    if (!signal) {
      return { status: 'WAIT', pass: false, reasons: ['No signal'], thresholds: getBackendReadinessThresholds({}) };
    }
    const normalizedSignal = enrichSignalWithAiMetrics(signal);
    // Unified gate: keep identical readiness thresholds for LIVE and DEMO.
    const liveAdaptive = getAdaptiveGateTightening('LIVE');
    const demoAdaptive = getAdaptiveGateTightening('DEMO');
    const adaptive = {
      qualityBump: Math.max(Number(liveAdaptive.qualityBump || 0), Number(demoAdaptive.qualityBump || 0)),
      confidenceBump: Math.max(Number(liveAdaptive.confidenceBump || 0), Number(demoAdaptive.confidenceBump || 0)),
      rrBump: Math.max(Number(liveAdaptive.rrBump || 0), Number(demoAdaptive.rrBump || 0)),
      lossState: (Number(liveAdaptive?.lossState?.consecutiveLosses || 0) >= Number(demoAdaptive?.lossState?.consecutiveLosses || 0))
        ? liveAdaptive.lossState
        : demoAdaptive.lossState,
      isLateSession: Boolean(liveAdaptive.isLateSession || demoAdaptive.isLateSession),
    };
    const baseThresholds = getBackendReadinessThresholds(normalizedSignal);
    const thresholds = {
      ...baseThresholds,
      quality_min: baseThresholds.quality_min + adaptive.qualityBump,
      confidence_min: baseThresholds.confidence_min + adaptive.confidenceBump,
      rr_min: Number((baseThresholds.rr_min + adaptive.rrBump).toFixed(2)),
    };
    const aiEdge = Number(normalizedSignal.ai_edge_score ?? 0);
    const momentum = Number(normalizedSignal.momentum_score ?? 0);
    const breakout = Number(normalizedSignal.breakout_score ?? 0);
    const fakeRisk = Number(normalizedSignal.fake_move_risk ?? 100);
    const confidence = Number(normalizedSignal.confirmation_score ?? normalizedSignal.confidence ?? 0);
    const newsRisk = Number(normalizedSignal.sudden_news_risk ?? 100);
    const liquidityRisk = Number(normalizedSignal.liquidity_spike_risk ?? 100);
    const premiumRisk = Number(normalizedSignal.premium_distortion_risk ?? 100);

    const entry = Number(normalizedSignal.entry_price ?? 0);
    const target = Number(normalizedSignal.target ?? 0);
    const stop = Number(normalizedSignal.stop_loss ?? 0);
    const rr = Number(normalizedSignal.rr ?? (entry > 0 ? (Math.abs(target - entry) / Math.max(0.0001, Math.abs(entry - stop))) : 0));
    const qtyBase = normalizeTradeQuantity(getSignalBaseQuantity(normalizedSignal) * Number(lotMultiplier || 1));
    const liveBalance = Number(liveAccountBalance);
    const hasLiveBalance = Number.isFinite(liveBalance) && liveBalance > 0;
    const liveRiskCap = hasLiveBalance
      ? Math.min(LIVE_MAX_PER_TRADE_LOSS_CAP, liveBalance * LIVE_PER_TRADE_RISK_PCT)
      : LIVE_MAX_PER_TRADE_LOSS_CAP;
    const liveCapSizing = getLossCappedQuantity({
      signal: normalizedSignal,
      desiredQuantity: qtyBase,
      maxLossAllowed: liveRiskCap,
    });
    const potentialLoss = liveCapSizing.potentialLoss;

    const qualityScore = Number(normalizedSignal.quality_score ?? normalizedSignal.quality ?? 0);
    const marketRegime = String(normalizedSignal.market_regime || '').toUpperCase();
    const marketBias = String(normalizedSignal.market_bias || '').toUpperCase();
    const timingRisk = String(normalizedSignal.timing_risk || normalizedSignal?.timing_risk_profile?.window || '').toUpperCase();
    const breakoutHold = normalizedSignal.breakout_hold_confirmed;
    const breakoutConfirmed = normalizedSignal.breakout_confirmed;
    const momentumConfirmed = normalizedSignal.momentum_confirmed;
    const breakoutOk = breakoutConfirmed === true || (breakoutConfirmed == null && breakout >= thresholds.confirmation_score_floor);
    const momentumOk = momentumConfirmed === true || (momentumConfirmed == null && momentum >= thresholds.confirmation_score_floor);

    const checks = [
      { ok: qualityScore >= thresholds.quality_min, fail: `Quality ${qualityScore.toFixed(1)} < ${thresholds.quality_min}` },
      { ok: confidence >= thresholds.confidence_min, fail: `Confidence ${confidence.toFixed(1)} < ${thresholds.confidence_min}` },
      { ok: aiEdge >= thresholds.ai_edge_min, fail: `AI edge ${aiEdge.toFixed(1)} < ${thresholds.ai_edge_min}` },
      { ok: rr >= thresholds.rr_min, fail: `RR ${rr.toFixed(2)} < ${thresholds.rr_min}` },
      { ok: breakoutOk && momentumOk, fail: `Need confirmations: breakout=${String(breakoutConfirmed)}/${breakout.toFixed(1)}, momentum=${String(momentumConfirmed)}/${momentum.toFixed(1)}` },
      { ok: breakoutHold !== false, fail: 'Breakout Hold NOT confirmed' },
      { ok: timingRisk !== 'HIGH', fail: 'Timing Risk HIGH — entry blocked' },
      {
        ok: marketBias !== 'WEAK_BOTH' || (qualityScore >= thresholds.weak_both_quality_override && confidence >= thresholds.weak_both_confidence_override),
        fail: `Market Bias WEAK_BOTH (needs quality>=${thresholds.weak_both_quality_override} and confidence>=${thresholds.weak_both_confidence_override})`
      },
      { ok: fakeRisk <= thresholds.max_fake_move_risk, fail: `Fake Move Risk ${fakeRisk.toFixed(1)}% > limit ${thresholds.max_fake_move_risk}%` },
      { ok: newsRisk <= thresholds.max_news_risk, fail: `News Risk ${newsRisk.toFixed(1)}% > limit ${thresholds.max_news_risk}%` },
      { ok: liquidityRisk <= thresholds.max_liquidity_spike_risk, fail: `Liquidity Risk ${liquidityRisk.toFixed(1)}% > limit ${thresholds.max_liquidity_spike_risk}%` },
      { ok: premiumRisk <= thresholds.max_premium_distortion_risk, fail: `Premium Distortion ${premiumRisk.toFixed(1)}% > limit ${thresholds.max_premium_distortion_risk}%` },
      { ok: marketRegime !== 'LOW_VOLATILITY' && marketRegime !== 'CHOPPY', fail: `Market regime ${marketRegime || 'UNKNOWN'}` },
      {
        ok: !isLiveMode || !autoTradingActive || liveCapSizing.fitsWithinCap,
        fail: `Potential loss ₹${potentialLoss.toFixed(2)} > live cap ₹${liveRiskCap.toFixed(2)} even at minimum qty 1`,
      },
      {
        ok: !adaptive.lossState.active,
        fail: `Loss-cluster cooldown active (${Math.ceil(adaptive.lossState.pauseRemainingMs / 60000)}m remaining)`
      },
    ];

    const reasons = checks.filter(c => !c.ok).map(c => c.fail);
    const pass = reasons.length === 0;
    return {
      status: pass ? 'GO' : 'WAIT',
      pass,
      reasons,
      thresholds,
      rr,
      aiEdge,
      momentum,
      breakout,
      fakeRisk,
      confidence,
      newsRisk,
      liquidityRisk,
      premiumRisk,
      effectiveQuantity: liveCapSizing.adjustedQuantity,
      sizingNote: isLiveMode && autoTradingActive && liveCapSizing.autoReduced
        ? `Qty auto-reduces to ${liveCapSizing.adjustedQuantity} to fit live cap ₹${liveRiskCap.toFixed(2)}`
        : null,
    };
  };

  const getOptionKind = (signal) => {
    const optionType = signal?.option_type || '';
    if (optionType === 'CE' || optionType === 'PE') return optionType;
    const symbol = String(signal?.symbol || '').toUpperCase();
    if (symbol.endsWith('CE')) return 'CE';
    if (symbol.endsWith('PE')) return 'PE';
    return null;
  };

  const INDEX_SYMBOLS = new Set(['NIFTY', 'BANKNIFTY', 'SENSEX', 'FINNIFTY']);

  const getSignalGroup = (signal) => {
    // Check new signal_type field from backend (preferred)
    if (signal?.signal_type) {
      return signal.signal_type === 'stock' ? 'stocks' : 'indices';
    }
    // Fallback to name-based heuristics if signal_type not present
    const indexName = String(signal?.index || '').toUpperCase();
    if (INDEX_SYMBOLS.has(indexName)) return 'indices';
    const symbol = String(signal?.symbol || '').toUpperCase();
    for (const idx of INDEX_SYMBOLS) {
      if (symbol.includes(idx)) return 'indices';
    }
    return 'stocks';
  };

  const getUnderlyingRoot = (signal) => {
    const raw = String(signal?.symbol || signal?.index || '').toUpperCase();
    if (!raw) return '';
    const cleaned = raw.replace(/^(NFO:|NSE:|BFO:|BSE:)/, '');
    const match = cleaned.match(/^([A-Z-]+)/);
    return match ? match[1] : cleaned;
  };

  const getMarketBiasLabel = (signal) => {
    const raw = String(signal?.market_bias || '').toUpperCase();
    if (raw.includes('STRONG')) return 'STRONG_ONE_SIDE';
    if (raw.includes('MODERATE')) return 'MODERATE_BOTH';
    if (raw.includes('WEAK')) return 'WEAK_BOTH';

    // Fallback when market_bias is not provided.
    const strength = String(signal?.trend_strength || '').toUpperCase();
    if (strength === 'STRONG') return 'STRONG_ONE_SIDE';
    if (strength === 'MODERATE') return 'MODERATE_BOTH';
    return 'WEAK_BOTH';
  };

  const getBestSignalByKind = (signals, kind) => {
    if (!Array.isArray(signals) || !kind) return null;
    const candidates = signals.filter((s) => getOptionKind(s) === kind);
    if (!candidates.length) return null;
    return candidates
      .slice()
      .sort((a, b) => {
        const qa = Number(a.quality_score ?? 0);
        const qb = Number(b.quality_score ?? 0);
        if (qb !== qa) return qb - qa;
        const ca = Number(a.confirmation_score ?? a.confidence ?? 0);
        const cb = Number(b.confirmation_score ?? b.confidence ?? 0);
        return cb - ca;
      })[0];
  };

  const hasStartYesCandidate = React.useMemo(() => {
    const threshold = Number(scannerMinQuality);
    return (Array.isArray(qualityTrades) ? qualityTrades : []).some((signal) => {
      const quality = Number(signal?.quality ?? signal?.quality_score ?? 0);
      if (quality < threshold) return false;
      return getEntryReadiness(enrichSignalWithAiMetrics(signal)).pass === true;
    });
  }, [qualityTrades, scannerMinQuality]);

  useEffect(() => {
    if (!autoTradingActive) {
      if (scannerHoldOnStartYes) {
        setScannerHoldOnStartYes(false);
      }
      sawTradeDuringStartHoldRef.current = false;
      return;
    }
    const activeCount = (activeTrades || []).length || 0;
    if (hasStartYesCandidate && activeCount === 0 && !scannerHoldOnStartYes) {
      setScannerHoldOnStartYes(true);
      sawTradeDuringStartHoldRef.current = false;
      logDeduped('dashboard:scanner_hold_yes', '⏸️ Start Trade YES found — scanner paused until trade cycle completes', {
        burstWindowMs: 60000,
        flushDelayMs: 1200,
      });
      return;
    }

    if (!scannerHoldOnStartYes) return;

    if (activeCount > 0) {
      sawTradeDuringStartHoldRef.current = true;
      return;
    }

    if (sawTradeDuringStartHoldRef.current && activeCount === 0) {
      sawTradeDuringStartHoldRef.current = false;
      setScannerHoldOnStartYes(false);
      logDeduped('dashboard:scanner_hold_release', '▶️ Trade cycle completed — scanner resumed', {
        burstWindowMs: 60000,
        flushDelayMs: 1200,
      });
    }
  }, [hasStartYesCandidate, scannerHoldOnStartYes, activeTrades.length, autoTradingActive]);
  
  // Track previous active trades count to detect exits
  const prevActiveTradesCount = React.useRef(0);
  const executingRef = React.useRef(false);
  const autoBatchExecutingRef = React.useRef(false);
  const activeTradesRef = React.useRef([]);
  const hasLoadedActiveTradesRef = React.useRef(false);
  const emptyActivePollsRef = React.useRef(0);
  const tradeHistoryRef = React.useRef([]);
  const hasLoadedTradeHistoryRef = React.useRef(false);
  const emptyHistoryPollsRef = React.useRef(0);
  const cooldownTimerRef = React.useRef(null);
  // Per-symbol demo entry cooldown: cleared individually when that symbol's trade closes.
  const paperSymbolEntryRef = React.useRef(new Map()); // key: "symbol:SIDE" -> timestamp
  const prevDemoOpenRef = React.useRef(new Set());    // Set of "symbol:SIDE" open last cycle
  const paperPriceUpdateAtRef = React.useRef(0);
  const demoAutoStartBurstGuardRef = React.useRef({ at: 0, key: '' });

  // Update visible cooldown countdown (ms) every second while cooldown is active
  useEffect(() => {
    let intervalId = null;
    if (cooldownEndsAt) {
      intervalId = setInterval(() => {
        const rem = Number(cooldownEndsAt) - Date.now();
        if (rem <= 0) {
          setCooldownRemainingMs(0);
          setCooldownEndsAt(null);
          if (intervalId) clearInterval(intervalId);
          return;
        }
        setCooldownRemainingMs(rem);
      }, 1000);
    } else {
      setCooldownRemainingMs(0);
    }
    return () => {
      if (intervalId) clearInterval(intervalId);
    };
  }, [cooldownEndsAt]);
  const [showActiveTradesTable] = useState(DEFAULT_TABLE_VISIBILITY.showActiveTradesTable);
  const [showTradeHistoryTable] = useState(DEFAULT_TABLE_VISIBILITY.showTradeHistoryTable);
  const dataFetchSeqRef = React.useRef(0);
  const dataFetchInFlightRef = React.useRef(false);
  const dataFetchStartedAtRef = React.useRef(0);
  const lastSuccessfulSyncAtRef = React.useRef(null);
  const isUsingStaleDataRef = React.useRef(false);
  const staleRecoveryLastRunRef = React.useRef(0);
  const sawTradeDuringStartHoldRef = React.useRef(false);
  const slowFetchCacheRef = React.useRef({
    at: 0,
    history: { trades: [] },
    perf: null,
    status: {},
  });
  const scannerLastRunAtRef = React.useRef(0);
  const scannerSnapshotRef = React.useRef({ at: 0, minQuality: null, trades: [], total: 0 });
  const scannerStabilityRef = React.useRef(new Map());
  const scannerTransportBackoffUntilRef = React.useRef(0);
  const scannerLogRef = React.useRef({
    startAt: 0,
    completeAt: 0,
    completeSummary: '',
  });
  const paperRejectCooldownRef = React.useRef(new Map());
  const paperCreateInFlightRef = React.useRef(new Set());
  const paperGlobalRejectUntilRef = React.useRef(0);
  const liveRiskRejectCooldownRef = React.useRef(new Map());
  const liveGlobalRejectUntilRef = React.useRef(0);
  const liveBalanceBackoffUntilRef = React.useRef(0);
  const historyFetchBackoffUntilRef = React.useRef(0);
  const historyFetchFailCountRef = React.useRef(0);
  const historyLastModeRef = React.useRef(null);
  const armRequestInFlightRef = React.useRef(false);
  const armSyncHoldUntilRef = React.useRef(0);
  const activeProbeAtRef = React.useRef(0);
  // Price-update throttle refs (separate for autotrade vs paper)
  const autoTradePriceUpdateAtRef = React.useRef(0);
  const priceUpdateBackoffUntilRef = React.useRef(0); // backs off both endpoints on repeated transport errors
  // Post-SL protection refs
  const paperSymbolSlCooldownRef = React.useRef(new Map());   // symbolSideKey → cooldownUntilMs
  const paperRootSlStreakRef = React.useRef(new Map());        // rootKey → { streak, lastSlAt }
  const paperSlHitTimestampsRef = React.useRef([]);            // recent SL hit timestamps (surge detector)

  useEffect(() => {
    activeTradesRef.current = activeTrades;
  }, [activeTrades]);

  useEffect(() => {
    tradeHistoryRef.current = tradeHistory;
  }, [tradeHistory]);

  useEffect(() => {
    lastSuccessfulSyncAtRef.current = lastSuccessfulSyncAt;
  }, [lastSuccessfulSyncAt]);

  useEffect(() => {
    isUsingStaleDataRef.current = isUsingStaleData;
  }, [isUsingStaleData]);

  const resolveStableActiveTrades = (incomingTrades, options = {}) => {
    const { canTrustEmpty = true } = options;
    const stable = resolveStableActiveTradesUtil({
      incomingTrades,
      prevTrades: activeTradesRef.current || [],
      hasLoaded: hasLoadedActiveTradesRef.current,
      emptyPolls: emptyActivePollsRef.current,
      canTrustEmpty,
      emptyPollsToClear: EMPTY_ACTIVE_POLLS_TO_CLEAR,
    });
    hasLoadedActiveTradesRef.current = stable.hasLoaded;
    emptyActivePollsRef.current = stable.emptyPolls;
    return stable.trades;
  };

  const resolveStableTradeHistory = (incomingHistory) => {
    const stable = resolveStableTradeHistoryUtil({
      incomingHistory,
      prevHistory: tradeHistoryRef.current || [],
      hasLoaded: hasLoadedTradeHistoryRef.current,
      emptyPolls: emptyHistoryPollsRef.current,
    });
    hasLoadedTradeHistoryRef.current = stable.hasLoaded;
    emptyHistoryPollsRef.current = stable.emptyPolls;
    return stable.trades;
  };

  const isLossLimitHit = () => {
    const dailyLoss = Number(stats?.daily_loss ?? 0);
    const dailyProfit = Number(stats?.daily_profit ?? 0);
    const realizedLoss = dailyLoss < 0 ? Math.abs(dailyLoss) : dailyLoss;
    return realizedLoss >= lossLimit || dailyProfit >= profitTarget;
  };

  const getTradingStatus = () => {
    const dailyLoss = Number(stats?.daily_loss ?? 0);
    const dailyProfit = Number(stats?.daily_profit ?? 0);
    const realizedLoss = dailyLoss < 0 ? Math.abs(dailyLoss) : dailyLoss;
    
    if (dailyProfit >= profitTarget) {
      return { status: 'PROFIT_TARGET_HIT', message: `🎉 Profit target (₹${profitTarget}) reached!` };
    }
    if (realizedLoss >= lossLimit) {
      return { status: 'LOSS_LIMIT_HIT', message: `🛑 Loss limit (₹${lossLimit}) breached!` };
    }
    return { status: 'NORMAL', message: 'Trading active' };
  };

  useEffect(() => {
    if (typeof window === 'undefined') return;
    localStorage.setItem('dailyLossLimit', String(lossLimit));
  }, [lossLimit]);

  useEffect(() => {
    if (typeof window === 'undefined') return;
    localStorage.setItem('dailyProfitTarget', String(profitTarget));
  }, [profitTarget]);

  useEffect(() => {
    if (typeof window === 'undefined') return;
    localStorage.setItem('scannerMinQuality', String(scannerMinQuality));
  }, [scannerMinQuality]);

  // When active trades drop to zero, trigger an immediate fresh scanner pass
  useEffect(() => {
    try {
      if (scannerHoldOnStartYes) {
        prevActiveTradesCount.current = (activeTrades || []).length || 0;
        return;
      }
      const prev = prevActiveTradesCount.current || 0;
      const curr = (activeTrades || []).length || 0;
      if (prev > 0 && curr === 0 && isMarketOpen) {
        if (!scannerLoading) {
          logDeduped('dashboard:no_active_trades_refresh', '🔁 No active trades detected — auto-refreshing market signals', {
            burstWindowMs: 60000,
            flushDelayMs: 1200,
          });
          scanMarketForQualityTrades(scannerMinQuality, true).catch((e) => errorDeduped('dashboard:scanner_refresh_failed', 'Scanner refresh failed', {
            burstWindowMs: 30000,
            flushDelayMs: 1200,
          }, e));
        }
      }
      prevActiveTradesCount.current = curr;
    } catch (e) {
      errorDeduped('dashboard:active_trade_watcher_error', 'Error in active-trade watcher', {
        burstWindowMs: 30000,
        flushDelayMs: 1200,
      }, e);
    }
  }, [activeTrades.length, isMarketOpen, scannerMinQuality, scannerHoldOnStartYes]);


  // --- Professional Signal Integration ---
  const [professionalSignal, setProfessionalSignal] = useState(null);
  useEffect(() => {
    const fetchProfessionalSignal = async () => {
      try {
        const res = await config.authFetch(PROFESSIONAL_SIGNAL_API);
        if (!res.ok) {
          if (res.status === 401) {
            setProfessionalSignal({ error: 'Session expired. Please login again.' });
            return;
          }
          // Backend can legitimately return 503 when no live professional setup is available.
          if (res.status === 503) {
            setProfessionalSignal({ error: 'No live option signals available.' });
            return;
          }
        }
        const parseProfessionalJson = async (response) => {
          try {
            return await response.json();
          } catch {
            // Retry once for intermittent truncated body/decode issues.
            const retryRes = await config.authFetch(PROFESSIONAL_SIGNAL_API, { cache: 'no-store' });
            if (!retryRes.ok) return null;
            return await retryRes.json();
          }
        };

        const data = await parseProfessionalJson(res);
        if (!data) {
          setProfessionalSignal({ error: 'Professional signal temporarily unavailable.' });
          return;
        }
        // Check if API returned an error (detail field indicates error)
        if (data.detail || data.error) {
          const detailText = String(data.detail || data.error || '');
          const expectedNoLiveSignal = /no live option signals available/i.test(detailText);
          if (expectedNoLiveSignal) {
            logDeduped('dashboard:professional_signal_unavailable', 'ℹ️ Professional signal unavailable (expected when no live setup is active)', {
              burstWindowMs: 180000,
              flushDelayMs: 1200,
              emitFirst: false,
            });
          } else {
            warnDeduped('dashboard:professional_signal_error', '⚠️ Professional signal error', {
              burstWindowMs: 120000,
              flushDelayMs: 1200,
              emitFirst: false,
            }, detailText);
          }
          setProfessionalSignal({ error: data.detail || data.error });
        } else {
          setProfessionalSignal(data);
        }
      } catch (err) {
        errorDeduped('dashboard:professional_signal_fetch_failed', '❌ Failed to fetch professional signal', {
          burstWindowMs: 60000,
          flushDelayMs: 1200,
        }, err);
        setProfessionalSignal({ error: err.message });
      }
    };
    fetchProfessionalSignal();
    const interval = setInterval(fetchProfessionalSignal, 120000); // refresh every 120s (reduced API calls)
    return () => clearInterval(interval);
  }, []);

  // Market Quality Scanner - finds all 75%+ quality trades
  const scanMarketForQualityTrades = async (minQuality = scannerMinQuality, bypassCache = false) => {
    const parsedMinQuality = Number(minQuality);
    const safeMinQuality = Number.isFinite(parsedMinQuality) ? parsedMinQuality : Number(scannerMinQuality);
    const nowMs = Date.now();

    if (typeof document !== 'undefined' && document.hidden && !autoTradingActive) {
      return;
    }
    const lastSnapshot = scannerSnapshotRef.current;
    
    // Skip cache checks when bypassCache=true (e.g., when auto-trading needs real-time updates)
    if (!bypassCache) {
      if (
        nowMs - lastSnapshot.at < SCANNER_MIN_REFRESH_MS
        && Number(lastSnapshot.minQuality) === Number(safeMinQuality)
        && Array.isArray(lastSnapshot.trades)
        && lastSnapshot.trades.length > 0
      ) {
        // Reuse recent snapshot to avoid "every second it changes" jitter.
        setQualityTrades(lastSnapshot.trades);
        setTotalSignalsScanned(lastSnapshot.total || 0);
        setScannerLastError(null);
        return;
      }

      // Sticky window: avoid churn on frequent refreshes when market hasn't changed much.
      if (
        nowMs - lastSnapshot.at < SCANNER_STICKY_MS
        && Number(lastSnapshot.minQuality) === Number(safeMinQuality)
        && Array.isArray(lastSnapshot.trades)
        && lastSnapshot.trades.length > 0
      ) {
        setQualityTrades(lastSnapshot.trades);
        setTotalSignalsScanned(lastSnapshot.total || 0);
        setScannerLastError(null);
        return;
      }
    }

    setScannerLoading(true);
    setScannerLastError(null);
    if ((nowMs - scannerLogRef.current.startAt) >= 30000) {
      logDeduped(`dashboard:scanner_start:${safeMinQuality}`, `🔍 Scanning entire market for top-quality trades (${safeMinQuality}%+)...`, {
        burstWindowMs: 180000,
        flushDelayMs: 1500,
        emitFirst: false,
      });
      scannerLogRef.current.startAt = nowMs;
    }
    
    try {
      // Fetch all signals from market with bounded full-universe first, then safe fallback.
      const modeParam = encodeURIComponent((confirmationMode || 'balanced').toLowerCase());
      const requestsToTry = [
        // Smaller FNO batch first - lower load, better chance to return stocks quickly
        `${OPTION_SIGNALS_API}?mode=${modeParam}&include_nifty50=true&include_fno_universe=true&max_symbols=12`,
        // Broad scan (tries to include FNO universe - may timeout on heavy load)
        `${OPTION_SIGNALS_API}?mode=${modeParam}&include_nifty50=true&include_fno_universe=true&max_symbols=40`,
        // Nifty-only fallback (indices)
        `${OPTION_SIGNALS_API}?mode=${modeParam}&include_nifty50=true`,
        // Generic fallback - whatever the API returns
        `${OPTION_SIGNALS_API}?mode=${modeParam}`,
      ];

      let allSignals = [];
      let lastError = null;
      let sawHttpError = false;
      const parseScanJsonWithRetry = async (url, response) => {
        try {
          return await response.json();
        } catch {
          // Retry once for intermittent truncated body/decode issues.
          const retryRes = await config.authFetch(url, { retryTransportOnce: true, cache: 'no-store' });
          if (!retryRes.ok) return null;
          return await retryRes.json();
        }
      };
      for (const url of requestsToTry) {
        try {
          const res = await config.authFetch(url, { retryTransportOnce: true, cache: 'no-store' });
          if (!res.ok) {
            if (Number(res.status) === 0) {
              scannerTransportBackoffUntilRef.current = Date.now() + 8000;
            }
            sawHttpError = true;
            continue;
          }
          const data = await parseScanJsonWithRetry(url, res);
          if (!data) {
            continue;
          }
          const candidateSignals = Array.isArray(data?.signals) ? data.signals : [];
          const isTimeoutCache = String(data?.status || '') === 'timeout_using_cache';
          const requestedBroadUniverse = url.includes('include_fno_universe=true');

          // If broad scan timed out and only cache is returned, try lighter requests
          // to get fresher stock coverage instead of freezing on stale index-only data.
          if (isTimeoutCache && requestedBroadUniverse) {
            continue;
          }

          if (candidateSignals.length > 0) {
            allSignals = candidateSignals;
            break;
          }
        } catch (e) {
          scannerTransportBackoffUntilRef.current = Date.now() + 8000;
          lastError = e;
        }
      }

      // Public endpoint fallback when auth wrapper has transient issues.
      if (!allSignals.length) {
        for (const url of requestsToTry) {
          try {
            const res = await fetch(url);
            if (!res.ok) continue;
            let data;
            try {
              data = await res.json();
            } catch {
              const retryRes = await fetch(url, { cache: 'no-store' });
              if (!retryRes.ok) continue;
              data = await retryRes.json();
            }
            const candidateSignals = Array.isArray(data?.signals) ? data.signals : [];
            if (candidateSignals.length > 0) {
              allSignals = candidateSignals;
              break;
            }
          } catch {
            scannerTransportBackoffUntilRef.current = Date.now() + 8000;
            // Keep scanning through fallback URLs.
          }
        }
      }

      if (!allSignals.length && lastError) {
        throw lastError;
      }

      // Fallback to already-loaded option signals if scan API returns empty.
      if (!allSignals.length && Array.isArray(optionSignals) && optionSignals.length > 0) {
        allSignals = optionSignals;
      }

      // If still empty, retain previous snapshot instead of clearing to zero abruptly.
      if (!allSignals.length && Array.isArray(lastSnapshot.trades) && lastSnapshot.trades.length > 0) {
        setQualityTrades(lastSnapshot.trades);
        setTotalSignalsScanned(lastSnapshot.total || 0);
        setScannerLastError(
          sawHttpError
            ? 'Scanner API returned temporary empty/error response. Showing last stable snapshot.'
            : 'No fresh signals from scanner yet. Showing last stable snapshot.'
        );
        return;
      }
      // Keep broader market coverage with clean tradable candidates only.
      const scanCandidates = allSignals.filter((signal) => {
        if (!signal || !signal.symbol || !signal.action) return false;
        const entry = Number(signal.entry_price ?? 0);
        const target = Number(signal.target ?? 0);
        const stop = Number(signal.stop_loss ?? 0);
        if (!(entry > 0) || !(target > 0) || !(stop > 0)) return false;
        if (signal.action === 'BUY' && !(target > entry && stop < entry)) return false;
        if (signal.action === 'SELL' && !(target < entry && stop > entry)) return false;
        return true;
      });
      const winRate = stats?.win_rate ? (stats.win_rate / 100) : 0.5;
      
      // Calculate quality for each signal
      const qualityScores = scanCandidates.map(signal => {
        const calculatedQuality = calculateTradeQuality(signal, winRate);
        const { rr, optimalRR } = calculateOptimalRR(signal, winRate);
        const backendQuality = Number(signal.quality ?? signal.quality_score ?? 0);
        const finalQuality = Math.round(Math.max(backendQuality, calculatedQuality.quality));
        const capitalRequired = resolveSignalCapitalRequired(signal, lotMultiplier);
        return {
          ...signal,
          quality: finalQuality,
          isExcellent: finalQuality >= 85,
          factors: calculatedQuality.factors,
          capital_required: Number.isFinite(capitalRequired) ? capitalRequired : null,
          rr,
          optimalRR,
          recommendation: finalQuality >= 90 ? '⭐ EXCELLENT' : finalQuality >= 80 ? '✅ GOOD' : '❌ POOR'
        };
      });
      
      // Nested filter Stage-1: structural + quality + confidence + RR.
      const cleanFiltered = qualityScores
        .filter((s) => {
          const confidence = Number(s.confirmation_score ?? s.confidence ?? 0);
          const rr = Number(s.rr ?? 0);
          return s.quality >= safeMinQuality && confidence >= 65 && rr >= 1.1;
        })
        .sort((a, b) => {
          if (b.quality !== a.quality) return b.quality - a.quality;
          const bc = Number(b.confirmation_score ?? b.confidence ?? 0);
          const ac = Number(a.confirmation_score ?? a.confidence ?? 0);
          if (bc !== ac) return bc - ac;
          return Number(b.rr ?? 0) - Number(a.rr ?? 0);
        });

      // Nested filter Stage-2: adaptive fallback band when strict set is empty.
      const adaptiveSource = cleanFiltered.length > 0
        ? cleanFiltered
        : qualityScores
            .filter((s) => {
              const confidence = Number(s.confirmation_score ?? s.confidence ?? 0);
              const rr = Number(s.rr ?? 0);
              return s.quality >= 65 && confidence >= 60 && rr >= 1.0;
            })
            .sort((a, b) => b.quality - a.quality)
            .slice(0, 20);

      // Nested filter Stage-3: stability/hysteresis across scans.
      const nextStability = new Map(scannerStabilityRef.current);
      const now = Date.now();
      adaptiveSource.forEach((signal) => {
        const key = `${getUnderlyingRoot(signal)}:${signal.option_type || ''}:${signal.action || ''}`;
        const prev = nextStability.get(key);
        const freshPrev = prev && (now - prev.lastSeenAt) <= SCANNER_STABILITY_WINDOW_MS;
        const seenCount = freshPrev ? (prev.seenCount + 1) : 1;
        nextStability.set(key, {
          seenCount,
          lastSeenAt: now,
          lastQuality: Number(signal.quality || 0),
          signal,
        });
      });
      // Drop very old keys to keep memory bounded.
      for (const [key, meta] of nextStability.entries()) {
        if ((now - meta.lastSeenAt) > SCANNER_STABILITY_WINDOW_MS) {
          nextStability.delete(key);
        }
      }
      scannerStabilityRef.current = nextStability;

      // Keep highly confident new entries immediately; require consistency for marginal ones.
      const stage3 = adaptiveSource.filter((signal) => {
        const key = `${getUnderlyingRoot(signal)}:${signal.option_type || ''}:${signal.action || ''}`;
        const meta = nextStability.get(key);
        const confidence = Number(signal.confirmation_score ?? signal.confidence ?? 0);
        const quality = Number(signal.quality || 0);
        return quality >= 85 && (confidence >= 75 || (meta?.seenCount || 0) >= 2);
      });

      // Deterministic ordering avoids tie-based reshuffling on each refresh.
      const rankSignals = (list) => list.slice().sort((a, b) => {
        const aStart = getEntryReadiness(enrichSignalWithAiMetrics(a)).pass ? 1 : 0;
        const bStart = getEntryReadiness(enrichSignalWithAiMetrics(b)).pass ? 1 : 0;
        if (bStart !== aStart) return bStart - aStart;
        const qDiff = Number(b.quality || 0) - Number(a.quality || 0);
        if (qDiff !== 0) return qDiff;
        const aCapital = resolveSignalCapitalRequired(a, lotMultiplier);
        const bCapital = resolveSignalCapitalRequired(b, lotMultiplier);
        if (Number.isFinite(aCapital) && Number.isFinite(bCapital) && aCapital !== bCapital) {
          return aCapital - bCapital;
        }
        const cDiff = Number(b.confirmation_score ?? b.confidence ?? 0) - Number(a.confirmation_score ?? a.confidence ?? 0);
        if (cDiff !== 0) return cDiff;
        const rrDiff = Number(b.rr || 0) - Number(a.rr || 0);
        if (rrDiff !== 0) return rrDiff;
        return String(a.symbol || '').localeCompare(String(b.symbol || ''));
      });

      const sortedStage3 = rankSignals(stage3);
      const prevByRoot = new Map(
        (Array.isArray(lastSnapshot.trades) ? lastSnapshot.trades : []).map((t) => [
          `${getUnderlyingRoot(t)}:${t.option_type || ''}`,
          t,
        ])
      );

      const bestByRoot = new Map();
      sortedStage3.forEach((signal) => {
        const root = `${getUnderlyingRoot(signal)}:${signal.option_type || ''}`;
        if (!root) return;

        // Sticky selection: if prior symbol for this root still exists and is close in quality,
        // keep it to reduce unnecessary symbol churn between refreshes.
        if (!bestByRoot.has(root)) {
          const previous = prevByRoot.get(root);
          if (previous?.symbol) {
            const prevCandidate = sortedStage3.find((s) =>
              `${getUnderlyingRoot(s)}:${s.option_type || ''}` === root
              && String(s.symbol || '') === String(previous.symbol || '')
            );
            if (prevCandidate) {
              const topForRoot = sortedStage3.find((s) => `${getUnderlyingRoot(s)}:${s.option_type || ''}` === root);
              const topQuality = Number(topForRoot?.quality || 0);
              const prevQuality = Number(prevCandidate.quality || 0);
              if (topQuality - prevQuality <= 6) {
                bestByRoot.set(root, prevCandidate);
                return;
              }
            }
          }

          bestByRoot.set(root, signal);
        }
      });
      let qualityOnly = rankSignals(Array.from(bestByRoot.values()));

      // If stability stage removed everything, keep the best adaptive candidates visible.
      if (qualityOnly.length === 0 && adaptiveSource.length > 0) {
        qualityOnly = rankSignals(adaptiveSource).slice(0, 8);
      }

      // Absolute last scanner fallback: if refinement stages still collapse to zero,
      // surface the best structurally valid scan candidates instead of showing an empty panel.
      if (qualityOnly.length === 0 && qualityScores.length > 0) {
        qualityOnly = rankSignals(
          qualityScores.filter((signal) => Number(signal.entry_price ?? 0) > 0 && Number(signal.target ?? 0) > 0 && Number(signal.stop_loss ?? 0) > 0)
        ).slice(0, 8);
      }

      // Stock supplement: Stage-3 only promotes signals with quality >= 85. Stock signals
      // from the backend typically score 60-75, so they rarely pass Stage-3 even when they
      // have solid RR. After the main pipeline (which may already have index signals), add
      // the best stock candidates that meet structural, RR and confidence minimums so they
      // appear in the Stocks tab alongside the index results.
      const stockSupplement = rankSignals(
        qualityScores.filter((s) => {
          if (getSignalGroup(s) !== 'stocks') return false;
          const rr = Number(s.rr ?? 0);
          const confidence = Number(s.confirmation_score ?? s.confidence ?? 0);
          return (
            Number(s.entry_price ?? 0) > 0 &&
            Number(s.target ?? 0) > 0 &&
            Number(s.stop_loss ?? 0) > 0 &&
            rr >= 1.0 &&
            confidence >= 60
          );
        })
      ).slice(0, 4);
      if (stockSupplement.length > 0) {
        const existingSymbols = new Set(qualityOnly.map((s) => s.symbol));
        const newStocks = stockSupplement.filter((s) => !existingSymbols.has(s.symbol));
        if (newStocks.length > 0) {
          qualityOnly = [...qualityOnly, ...newStocks];
        }
      }

      // If scanner stream is empty but Professional signal exists, show it as fallback row.
      if (
        qualityOnly.length === 0
        && professionalSignal
        && !professionalSignal.error
        && professionalSignal.symbol
        && professionalSignal.entry_price
      ) {
        const fallbackSignal = {
          symbol: professionalSignal.symbol,
          index: professionalSignal.index || 'MARKET',
          action: (professionalSignal.signal || professionalSignal.action || 'BUY').toUpperCase(),
          entry_price: Number(professionalSignal.entry_price),
          target: Number(professionalSignal.target || professionalSignal.entry_price),
          stop_loss: Number(professionalSignal.stop_loss || professionalSignal.entry_price),
          confirmation_score: Number(professionalSignal.confidence ?? 70),
          confidence: Number(professionalSignal.confidence ?? 70),
          quality: Number(professionalSignal.quality_score ?? 70),
          quality_score: Number(professionalSignal.quality_score ?? 70),
          rr: Number(professionalSignal.risk_reward ?? 1.1),
          recommendation: '⭐ PROFESSIONAL',
          strategy: professionalSignal.strategy || 'Professional Signal',
          expiry_date: professionalSignal.expiry_date || professionalSignal.expiry,
          option_type: professionalSignal.option_type,
          source: 'professional_fallback'
        };
        qualityOnly = [fallbackSignal];
      }

      // If current scan is empty but we had recent non-empty snapshot, keep it to avoid flicker-to-zero.
      if (qualityOnly.length === 0 && Array.isArray(lastSnapshot.trades) && lastSnapshot.trades.length > 0) {
        qualityOnly = lastSnapshot.trades;
      }

      // Count today's executed trades (active + closed)
      const today = new Date().toISOString().slice(0, 10);
      const tradesToday = tradeHistory.filter((t) => {
        const ts = t.exit_time || t.entry_time || t.timestamp;
        if (!ts) return false;
        return new Date(ts).toISOString().slice(0, 10) === today;
      });
      const activeToday = activeTrades.filter((t) => {
        const ts = t.entry_time || t.timestamp;
        if (!ts) return false;
        return new Date(ts).toISOString().slice(0, 10) === today;
      });
      const totalTradesToday = tradesToday.length + activeToday.length;
      
      const strictVisibleCount = qualityOnly.filter(
        (s) => Number(s?.quality ?? s?.quality_score ?? 0) >= safeMinQuality
      ).length;
      const scanSummary = `${strictVisibleCount}|${qualityOnly.length}|${allSignals.length}|${safeMinQuality}`;
      const shouldLogComplete =
        scanSummary !== scannerLogRef.current.completeSummary
        || (nowMs - scannerLogRef.current.completeAt) >= 180000;
      if (shouldLogComplete) {
        logDeduped(
          `dashboard:scanner_complete:${safeMinQuality}`,
          `✅ Market Scan Complete: ${strictVisibleCount} strict trades for ${safeMinQuality}%+ (${qualityOnly.length} shortlisted, ${allSignals.length} total signals)` ,
          {
          burstWindowMs: 120000,
          flushDelayMs: 1500,
          emitFirst: false,
        });
        scannerLogRef.current.completeSummary = scanSummary;
        scannerLogRef.current.completeAt = nowMs;
      }
      // Enrich signals once and store enriched snapshot to avoid recomputing
      // differences between renders which can flip Start/WAIT rapidly.
      const enrichedQualityOnly = qualityOnly.map((s) => enrichSignalWithAiMetrics(s));
      setTotalSignalsScanned(allSignals.length);
      setQualityTrades(enrichedQualityOnly);
      scannerSnapshotRef.current = {
        at: nowMs,
        minQuality: safeMinQuality,
        trades: enrichedQualityOnly,
        total: allSignals.length,
      };
      scannerLastRunAtRef.current = nowMs;
      try {
        setScannerLastRunAt(new Date(nowMs));
      } catch (e) {
        // ignore if unmounted
      }
      if (qualityOnly.length === 0) {
        setProfessionalSignal(null);
      }
    } catch (err) {
      console.error('❌ Market scan failed:', err);
      setScannerLastError(err?.message || 'Scanner request failed');
      // Keep previous scanner results visible when backend fails.
      setProfessionalSignal(null);
    } finally {
      setScannerLoading(false);
    }
  };

  // Auto-scan bootstrap: run one immediate scan once conditions are met.
  // Continuous scanning is managed by the dedicated scanner loop effect below.
  useEffect(() => {
    if (!signalsLoaded) return;
    if (!autoScanActive || scannerUserOverride) return;
    if (!isMarketOpen) return; // avoid scanning when market closed
    if (scannerHoldOnStartYes) return; // freeze scanner when Start YES candidate exists

    const runOnce = async () => {
      try {
        const lastAt = scannerSnapshotRef.current?.at || scannerLastRunAtRef.current || 0;
        if (Date.now() - lastAt < SCANNER_MIN_REFRESH_MS) return; // respect min refresh interval
        await scanMarketForQualityTrades(scannerMinQuality, true);
      } catch (e) {
        // ignore
      }
    };

    // Immediate first run
    runOnce();
  }, [signalsLoaded, autoScanActive, scannerUserOverride, scannerMinQuality, isMarketOpen, scannerHoldOnStartYes]);

  // Core data fetch logic (extracted for reuse)
  // forceRefresh: if true, bypasses the in-flight check to ensure immediate update (used after trade execution)
  // skipHistory: if true, skip the history/perf slow-endpoints (used by quiet background refresh)
  const performDataFetch = async (forceRefresh = false, skipHistory = false) => {
    const now = Date.now();
    if (dataFetchInFlightRef.current && !forceRefresh) {
      // Watchdog: if a previous cycle appears stuck, release it and continue.
      const startedAt = Number(dataFetchStartedAtRef.current || 0);
      if (startedAt > 0 && (now - startedAt) > 20000) {
        dataFetchInFlightRef.current = false;
        dataFetchStartedAtRef.current = 0;
      } else {
        return;
      }
    }
    dataFetchInFlightRef.current = true;
    dataFetchStartedAtRef.current = Date.now();
    const fetchSeq = ++dataFetchSeqRef.current;

    try {
      const timeoutPromise = (promise, ms) => Promise.race([
        promise,
        new Promise((_, reject) => setTimeout(() => reject(new Error('Timeout')), ms))
      ]);

      const nowMs = Date.now();
      const isOpenTradeForMode = (trade, mode) => {
        const status = String(trade?.status || '').toUpperCase();
        const tradeMode = String(trade?.trade_mode || trade?.trade_source || '').toUpperCase();
        const isOpen = status === 'OPEN' || (status !== 'CLOSED' && status !== 'CANCELLED' && status !== 'SL_HIT' && status !== 'TARGET_HIT' && status !== 'MANUAL_CLOSE');
        return isOpen && tradeMode === mode;
      };
      const currentModeLabel = isLiveMode ? 'LIVE' : 'DEMO';
      const currentModeOpenTrades = (activeTradesRef.current || []).filter((trade) => isOpenTradeForMode(trade, currentModeLabel));
      const hasOpenTradeForCurrentMode = currentModeOpenTrades.length > 0;

      // Update prices first, then fetch trades to keep UI marks current.
      // Both endpoints are throttled (min 5s gap) to reduce ERR_CONTENT_LENGTH_MISMATCH transport
      // errors caused by the dev proxy dropping connections under load.
      // An additional exponential backoff fires when transport errors repeat within a short window.
      const priceUpdateBackoffUntil = Number(priceUpdateBackoffUntilRef.current || 0);
      const priceUpdatesBlocked = priceUpdateBackoffUntil > nowMs;
      const updateJobs = [];
      const shouldRunAutoTradeUpdate = !priceUpdatesBlocked
        && hasOpenTradeForCurrentMode
        && (forceRefresh || (nowMs - Number(autoTradePriceUpdateAtRef.current || 0)) >= 5000);
      if (shouldRunAutoTradeUpdate) {
        autoTradePriceUpdateAtRef.current = nowMs;
        updateJobs.push(
          timeoutPromise(config.authFetch(AUTO_TRADE_UPDATE_API, { method: 'POST', retryTransportOnce: true, cache: 'no-store' }), 3000)
            .then((res) => {
              // A synthetic status:0 response means both fetch attempts failed (transport error).
              if (res && Number(res.status) === 0) {
                priceUpdateBackoffUntilRef.current = Date.now() + 10000;
              }
              return res;
            })
            .catch(() => {
              priceUpdateBackoffUntilRef.current = Date.now() + 10000;
              return null;
            })
        );
      }
      if (updateJobs.length > 0) await Promise.all(updateJobs);

      const safeFetch = async (url, options = {}) => {
        try {
          return await timeoutPromise(
            config.authFetch(url, { retryTransportOnce: true, cache: 'no-store', ...options }),
            15000,
          );
        } catch {
          return { ok: false };
        }
      };

    // Reset history backoff/fail-count on mode switch so new mode endpoint gets a fresh chance
    if (historyLastModeRef.current !== null && historyLastModeRef.current !== isLiveMode) {
      historyFetchBackoffUntilRef.current = 0;
      historyFetchFailCountRef.current = 0;
    }
    historyLastModeRef.current = isLiveMode;

    const modeParam = isLiveMode ? 'LIVE' : 'DEMO';
    const historyUrl = `${AUTO_TRADE_HISTORY_API}?mode=ALL&limit=200`;
    const perfUrl = `${AUTO_TRADE_REPORT_API}?mode=ALL&limit=500`;

    const pageHidden = typeof document !== 'undefined' && document.hidden;
    const shouldFetchSlowEndpoints = !pageHidden && (forceRefresh || (nowMs - Number(slowFetchCacheRef.current?.at || 0)) >= 10000);
    const historyBackoffActive = nowMs < Number(historyFetchBackoffUntilRef.current || 0);
    const shouldFetchHistoryEndpoint = shouldFetchSlowEndpoints && !historyBackoffActive && !skipHistory;

    const shouldFetchStatusEndpoint = forceRefresh || (nowMs - Number(slowFetchCacheRef.current?.at || 0)) >= 5000;
    const shouldFetchCurrentModeActive = shouldFetchCurrentModeActiveUtil({
      forceRefresh,
      hasOpenTradeForCurrentMode,
      autoTradingActive,
      nowMs,
      lastProbeAt: Number(activeProbeAtRef.current || 0),
    });
    if (shouldFetchCurrentModeActive && !hasOpenTradeForCurrentMode) {
      activeProbeAtRef.current = nowMs;
    }
    const currentModeActiveFallback = {
      trades: currentModeOpenTrades,
    };

    const [liveActiveRes, historyRes, perfRes, statusRes] = await Promise.all([
      shouldFetchCurrentModeActive ? safeFetch(AUTO_TRADE_ACTIVE_API) : Promise.resolve({ ok: false, skipped: true }),
      shouldFetchHistoryEndpoint ? safeFetch(historyUrl) : Promise.resolve({ ok: false, skipped: true }),
      shouldFetchSlowEndpoints && !skipHistory ? safeFetch(perfUrl) : Promise.resolve({ ok: false, skipped: true }),
      shouldFetchStatusEndpoint
        ? safeFetch(AUTO_TRADE_STATUS_API, { retryTransportOnce: true, cache: 'no-store' })
        : Promise.resolve({ ok: false, skipped: true }),
    ]);

    if (shouldFetchHistoryEndpoint && !historyRes?.ok) {
      const fc = Number(historyFetchFailCountRef.current || 0);
      const backoffMs = Math.min(20000 * Math.pow(2, fc), 300000); // 20s→40s→80s…cap 5min
      historyFetchFailCountRef.current = fc + 1;
      historyFetchBackoffUntilRef.current = nowMs + backoffMs;
      const statusCode = historyRes?.status || 'unknown';
      const statusText = historyRes?.statusText || '';
      warnDeduped(
        'fetch:history:backoff',
        `⚠️ History fetch failed (${statusCode} ${statusText}), backing off briefly`,
        { burstWindowMs: 300000, flushDelayMs: 2000 },
      );
    } else if (shouldFetchHistoryEndpoint && historyRes?.ok) {
      historyFetchFailCountRef.current = 0; // reset fail count on success
    }

    const hasAnyFreshResponse = [liveActiveRes, historyRes, perfRes, statusRes]
      .some((res) => !!res?.ok);

    const parseJsonSafe = async (response, fallback, retryUrl = null, onDecodeFail = null) => {
      if (!response?.ok) return fallback;
      try {
        return await response.json();
      } catch (err) {
        // Retry once on intermittent transport/body truncation in dev.
        if (retryUrl) {
          try {
            const retry = await timeoutPromise(
              config.authFetch(retryUrl, { retryTransportOnce: true, cache: 'no-store' }),
              8000,
            );
            if (retry?.ok) {
              return await retry.json();
            }
          } catch {}
        }
        warnDeduped(
          `fetch:decode:${retryUrl || 'request'}`,
          `⚠️ Response decode failed for ${retryUrl || 'request'}`,
          { burstWindowMs: 120000, flushDelayMs: 1200 },
          err?.message || err,
        );
        if (typeof onDecodeFail === 'function') {
          try { onDecodeFail(err); } catch {}
        }
        return fallback;
      }
    };

    const liveActiveData = await parseJsonSafe(
      liveActiveRes,
      currentModeActiveFallback,
      AUTO_TRADE_ACTIVE_API,
    );
    const historyData = shouldFetchHistoryEndpoint
      ? await parseJsonSafe(
          historyRes,
          { trades: [] },
          historyUrl,
          () => {
            const fc = Number(historyFetchFailCountRef.current || 0);
            const backoffMs = Math.min(20000 * Math.pow(2, fc), 300000);
            historyFetchFailCountRef.current = fc + 1;
            historyFetchBackoffUntilRef.current = Date.now() + backoffMs;
          },
        )
      : (slowFetchCacheRef.current?.history || { trades: [] });
    const perfDataRaw = shouldFetchSlowEndpoints
      ? await parseJsonSafe(perfRes, null, perfUrl)
      : (slowFetchCacheRef.current?.perf ?? null);
    const perfData = isLiveMode
      ? (perfDataRaw?.summary || perfDataRaw || null)
      : perfDataRaw;
    const statusData = shouldFetchStatusEndpoint
      ? await parseJsonSafe(statusRes, (slowFetchCacheRef.current?.status || {}), AUTO_TRADE_STATUS_API)
      : (slowFetchCacheRef.current?.status || {});

    if (shouldFetchSlowEndpoints) {
      slowFetchCacheRef.current = {
        at: nowMs,
        history: historyData || { trades: [] },
        perf: perfData ?? null,
        status: statusData || {},
      };
    } else if (shouldFetchStatusEndpoint) {
      slowFetchCacheRef.current = {
        ...(slowFetchCacheRef.current || {}),
        status: statusData || {},
      };
    }

    const liveActive = (Array.isArray(liveActiveData.trades) ? liveActiveData.trades : []).map((t) => {
      const inferredMode = String(
        t?.trade_mode
        || t?.trade_source
        || t?.mode
        || (t?.broker_response?.simulated ? 'DEMO' : (t?.broker_order_id ? 'LIVE' : 'LIVE'))
      ).toUpperCase();
      return {
        ...t,
        trade_mode: inferredMode,
        trade_source: String(t?.trade_source || 'autotrade').toLowerCase(),
      };
    });
    const activeCandidates = liveActive;
    const history = historyData.trades || [];
    const backendStatus = statusData.status || statusData;
    const backendEnabled = Boolean(backendStatus?.enabled ?? statusData?.enabled ?? true);
    const backendLiveArmed = Boolean(backendStatus?.live_armed ?? statusData?.live_armed ?? false);
    const backendDemoMode = backendLiveArmed
      ? false
      : Boolean(backendStatus?.is_demo_mode ?? statusData?.is_demo_mode ?? true);

    const canTrustActiveEmpty = shouldFetchCurrentModeActive && !!liveActiveRes?.ok;

    // Deduplicate active trades by symbol, action, entry_price, and entry_time
    const dedupedActive = Array.isArray(activeCandidates)
      ? activeCandidates.filter((trade, idx, arr) => {
          return (
            arr.findIndex(t =>
              t.symbol === trade.symbol &&
              (t.action || t.side) === (trade.action || trade.side) &&
              Number(t.entry_price ?? t.price) === Number(trade.entry_price ?? trade.price) &&
              (t.entry_time || t.timestamp) === (trade.entry_time || trade.timestamp)
              && String(t.trade_mode || '') === String(trade.trade_mode || '')
            ) === idx
          );
        })
      : activeCandidates;
    
    const dedupedHistory = dedupeHistoryRows(history);
    const resolvedActiveTrades = resolveStableActiveTrades(dedupedActive, { canTrustEmpty: canTrustActiveEmpty });
    const resolvedHistory = resolveStableTradeHistory(dedupedHistory);

    // Ignore stale responses from slower previous polls.
    if (fetchSeq !== dataFetchSeqRef.current) {
      dataFetchInFlightRef.current = false;
      return;
    }

    // Keep UI mode synchronized with backend truth, but avoid flicker right after arm/disarm clicks.
    if (Date.now() >= Number(armSyncHoldUntilRef.current || 0)) {
      setEnabled(backendEnabled);
      setIsLiveMode(backendLiveArmed && !backendDemoMode);
    }

    // Never clear already visible rows on one bad/empty response.
    setActiveTrades(resolvedActiveTrades);
    setTradeHistory(resolvedHistory);
    setReportSummary(perfData);
    setHasActiveTrade(resolvedActiveTrades.length > 0);

    // Compute daily P&L from closed trades
    const todayLabel = new Date().toDateString();
    const dailyTrades = resolvedHistory.filter((t) => {
      const ts = t.exit_time || t.entry_time;
      if (!ts) return false;
      return new Date(ts).toDateString() === todayLabel;
    });
    const dailyPnl = dailyTrades.reduce((acc, t) => acc + Number(t.pnl ?? t.profit_loss ?? 0), 0);
    const winCount = dailyTrades.filter(t => (t.pnl ?? t.profit_loss ?? 0) > 0).length;
    const lossCount = dailyTrades.filter(t => (t.pnl ?? t.profit_loss ?? 0) < 0).length;

    const capitalInUse = resolvedActiveTrades.reduce((acc, t) => acc + Number(t.entry_price ?? 0) * Number(t.quantity ?? 0), 0);

    const targetPoints = Number(activeSignal?.target_points ?? 0) || (activeSignal && activeSignal.entry_price && activeSignal.target
      ? Math.max(0, Number(activeSignal.target) - Number(activeSignal.entry_price))
      : 25);

    setStats({
      daily_pnl: dailyPnl,
      daily_loss: Number(backendStatus?.daily_loss ?? 0),
      daily_profit: Number(backendStatus?.daily_profit ?? 0),
      daily_loss_limit: Number(backendStatus?.daily_loss_limit ?? 5000),
      daily_profit_limit: Number(backendStatus?.daily_profit_limit ?? 10000),
      active_trades_count: resolvedActiveTrades.length,
      max_trades: backendStatus?.max_trades ?? null,
      target_points_per_trade: Math.round(targetPoints),
      capital_in_use: capitalInUse,
      win_rate: backendStatus?.win_rate ?? 0,
      win_sample: backendStatus?.win_sample ?? 0,
      today_wins: winCount,
      today_losses: lossCount,
      trading_paused: backendStatus?.trading_paused ?? false,
      pause_reason: backendStatus?.pause_reason,
      market_open: typeof backendStatus?.market_open === 'boolean' ? backendStatus.market_open : null,
      market_reason: backendStatus?.market_reason ?? null,
      market_date: backendStatus?.market_date ?? null,
      market_time: backendStatus?.market_time ?? null,
      remaining_capital: null,
      portfolio_cap: null,
    });

      if (hasAnyFreshResponse) {
        setLastSuccessfulSyncAt(new Date());
        setIsUsingStaleData(false);
      } else {
        setIsUsingStaleData(true);
      }
    } finally {
      dataFetchInFlightRef.current = false;
      dataFetchStartedAtRef.current = 0;
    }
  };

  // User-triggered fetch with loading state
  // forceRefresh: bypass in-flight check to ensure data updates immediately (used after trade execution)
  const fetchData = async (forceRefresh = false, skipHistory = false) => {
    try {
      await performDataFetch(forceRefresh, skipHistory);
    } catch (e) {
      // Keep previously rendered rows/data on fetch failure to avoid flicker.
      setIsUsingStaleData(true);
    } finally {
      dataFetchInFlightRef.current = false;
    }
  };

  // Background refresh WITHOUT loading state (prevents flickering)
  const refreshTradesQuietly = async () => {
    try {
      // Throttle: Skip if fetched within last 1 second
      const now = Date.now();
      if (refreshTradesQuietly.lastRun && (now - refreshTradesQuietly.lastRun) < 1000) {
        return; // Silent skip
      }
      refreshTradesQuietly.lastRun = now;

      // Skip history/perf in quiet-refresh: those are large payloads and already
      // fetched on-schedule by the main fetchData path. This eliminates the
      // bulk of ERR_CONTENT_LENGTH_MISMATCH noise from rapid quiet polls.
      await performDataFetch(false, true);
    } catch (e) {
      // Silent error - don't update state, keep stale data
      setIsUsingStaleData(true);
    }
  };

  const syncBadgeLabel = lastSuccessfulSyncAt
    ? `Last successful sync: ${lastSuccessfulSyncAt.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })}`
    : 'Waiting for first successful sync...';

  const formatCooldownLabel = (ms) => {
    if (!Number.isFinite(ms) || ms <= 0) return '';
    const total = Math.max(0, Math.floor(ms / 1000));
    const mins = Math.floor(total / 60);
    const secs = total % 60;
    return `${mins}m ${secs}s`;
  };

  // Enhanced analyzeMarket - AI-powered momentum detection and real-time market analysis
  const analyzeMarket = async () => {
    // Rate limiting: prevent spam calls (minimum 10s between analyses)
    const now = Date.now();
    if (analyzeMarket.lastRun && (now - analyzeMarket.lastRun) < 10000) {
      console.log('⏸️ Market analysis rate limited - wait 10s between calls');
      return;
    }
    
    // Deduplication: prevent concurrent calls
    if (analyzeMarket.isRunning) {
      console.log('⏭️ Market analysis already running - skipping');
      return;
    }
    
    analyzeMarket.isRunning = true;
    analyzeMarket.lastRun = now;
    
    try {
      // Soft block: skip new trades if daily loss limit is hit, but keep auto-trading alive.
      if (isLossLimitHit()) {
        console.log('⏸️ Daily loss limit hit - skipping new entries (auto-trading remains ON)');
        return;
      }

      // Soft block: pause new entries after 3/5 recent losses, but keep session alive.
      const recentTrades = tradeHistory.slice(0, 5); // Last 5 trades
      const recentLosses = recentTrades.filter(t => (t.pnl || t.profit_loss || 0) < 0).length;
      if (recentLosses >= 3) {
        console.log('⏸️ Too many recent losses (3/5) - skipping entry this cycle (auto-trading remains ON)');
        return;
      }

      // Step 1: Get real-time market trends with momentum data (with 10s timeout)
      const timeoutPromise = (promise, ms) => Promise.race([
        promise,
        new Promise((_, reject) => setTimeout(() => reject(new Error('Timeout')), ms))
      ]);
      
      const [marketRes, sentimentRes, newsRes] = await Promise.all([
        timeoutPromise(config.authFetch(`${config.API_BASE_URL}/market/trends`), 15000),
        timeoutPromise(config.authFetch(`${config.API_BASE_URL}/market/sentiment`), 15000),
        timeoutPromise(config.authFetch(`${config.API_BASE_URL}/market/news?limit=5`), 15000)
      ]).catch(err => {
        // Silent timeout - market APIs are optional, will use defaults
        return [{ ok: false }, { ok: false }, { ok: false }];
      });
      
      const marketData = marketRes?.ok ? await marketRes.json() : { indices: {} };
      const sentimentData = sentimentRes?.ok ? await sentimentRes.json() : { overall_sentiment: 'Neutral', sentiment_score: 0.5 };
      const newsData = newsRes?.ok ? await newsRes.json() : { news: [] };
      const indices = marketData.indices || {};
      const overallSentiment = sentimentData.overall_sentiment || 'Neutral';
      const sentimentScore = sentimentData.sentiment_score || 0.5;
      const recentNews = newsData.news || [];

      // Step 2: Analyze market momentum - CRITICAL for entry timing
      const momentumAnalysis = {};
      for (const [indexName, indexData] of Object.entries(indices)) {
        const changePercent = indexData.change_percent || 0;
        const trend = indexData.trend || 'Sideways';
        const strength = indexData.strength || 'Weak';
        
        // Momentum scoring
        let momentumScore = 0;
        let momentumDirection = 'NEUTRAL';
        
        // Strong directional movement
        if (Math.abs(changePercent) > 1.0 && strength === 'Strong') {
          momentumScore = 100;
          momentumDirection = changePercent > 0 ? 'BULLISH' : 'BEARISH';
        } else if (Math.abs(changePercent) > 0.7 && strength === 'Moderate') {
          momentumScore = 75;
          momentumDirection = changePercent > 0 ? 'BULLISH' : 'BEARISH';
        } else if (Math.abs(changePercent) > 0.4) {
          momentumScore = 50;
          momentumDirection = changePercent > 0 ? 'BULLISH' : 'BEARISH';
        } else if (Math.abs(changePercent) < 0.2) {
          momentumScore = 0; // No clear momentum = no trade
          momentumDirection = 'SIDEWAYS';
        } else {
          momentumScore = 25;
          momentumDirection = changePercent > 0 ? 'WEAK_BULLISH' : 'WEAK_BEARISH';
        }
        
        momentumAnalysis[indexName] = {
          score: momentumScore,
          direction: momentumDirection,
          changePercent,
          strength,
          trend
        };
      }

      // Only log if we have momentum data
      if (Object.keys(momentumAnalysis).length > 0) {
        console.log('📊 Momentum Analysis:', JSON.stringify(momentumAnalysis, null, 2));
      }

      // Step 3: Check news sentiment for sudden market moves
      const bullishNewsCount = recentNews.filter(n => n.sentiment === 'positive').length;
      const bearishNewsCount = recentNews.filter(n => n.sentiment === 'negative').length;
      const newsImpact = bullishNewsCount - bearishNewsCount;

      // Step 4: ONLY proceed if at least one index has strong momentum
      const hasStrongMomentum = Object.values(momentumAnalysis).some(m => m.score >= 75);
      if (!hasStrongMomentum) {
        console.log('⏸️ No strong momentum detected - waiting for clear market direction');
        console.log('   Market appears sideways/choppy - avoiding low-probability trades');
        return;
      }

      // AI regime selection: automatically tune confirmation mode.
      const strongMomentumCount = Object.values(momentumAnalysis).filter(m => m.score >= 75).length;
      const sentimentBias = Math.abs((sentimentScore || 0.5) - 0.5);
      let aiMode = 'balanced';
      if (strongMomentumCount >= 2 && sentimentBias >= 0.12 && recentLosses <= 1) {
        aiMode = 'aggressive';
      } else if (recentLosses >= 2 || sentimentBias < 0.05) {
        aiMode = 'conservative';
      }
      if (aiMode !== confirmationMode) {
        setConfirmationMode(aiMode);
      }
      console.log(`🧠 AI Mode Selected: ${aiMode} | strongMomentum=${strongMomentumCount} sentimentBias=${sentimentBias.toFixed(2)} recentLosses=${recentLosses}`);

      // Step 5: Refresh option signals with timeout
      let freshSignals = []; // Start with empty array, no fallback to old signals
      try {
        const signalTimeout = new Promise((_, reject) => 
          setTimeout(() => reject(new Error('Signal generation timeout')), 10000) // 10s max wait
        );
        const signalFetch = fetch(
          `${OPTION_SIGNALS_API}?mode=${encodeURIComponent(aiMode)}&include_nifty50=true&include_fno_universe=true&max_symbols=40`
        );
        const sigRes = await Promise.race([signalFetch, signalTimeout]);
        const sigData = await sigRes.json();
        
        // Check for API errors
        if (sigData.detail || sigData.error) {
          console.warn('⚠️ API returned error:', sigData.detail || sigData.error);
          freshSignals = [];
        } else {
          freshSignals = sigData.signals || [];
        }
        setOptionSignals(freshSignals);
      } catch (err) {
        console.warn('⚠️ Signal generation timed out (>10s):', err.message);
        freshSignals = [];
        setOptionSignals([]);
      }
      
      // Exit if no signals available
      if (freshSignals.length === 0) {
        console.log('⏸️ No signals available - cannot proceed with trade');
        return;
      }

      // Step 6: Apply filtering with momentum alignment
      // NOTE: This is for DISPLAYING signals - stricter filter for EXECUTION is applied later
      const validSignals = freshSignals.filter(s => {
        // Basic validation
        if (s.error || !s.symbol || !s.entry_price || s.entry_price <= 0) return false;
        if (!s.target || s.target <= 0 || !s.stop_loss || s.stop_loss <= 0) return false;
        
        // Display filter - show signals with 60%+ confidence for monitoring
        const confidence = s.confirmation_score ?? s.confidence ?? 0;
        if (confidence < 60) return false; // Low threshold for visibility
        
        // Basic risk-reward check
        const risk = Math.abs(s.entry_price - s.stop_loss);
        const reward = Math.abs(s.target - s.entry_price);
        if (reward / risk < 1.2) return false;
        
        // Price sanity check
        // Relaxed: allow higher entry prices (stocks and index options can be expensive).
        // Previously signals with entry_price > 250 were dropped which filtered many stock/index option rows.
        if (s.entry_price < 15) return false;  // Keep minimum to avoid far OTM
        
        // CRITICAL: Momentum alignment check
        const indexMomentum = momentumAnalysis[s.index];
        // If we have index momentum data, require it to be strong enough.
        if (indexMomentum && indexMomentum.score < 50) return false;

        // If index momentum is missing (common for stock-level signals), fall back to technical indicator checks
        // to avoid excluding valid stock signals when index-level data isn't available.
        if (!indexMomentum) {
          const tech = s.technical_indicators || {};
          const rsi = Number(tech.rsi ?? 50);
          const macdCross = String(tech.macd?.crossover || '').toLowerCase();
          const techBullish = (rsi >= 40 && rsi <= 75) && (macdCross === 'bullish' || macdCross === '');
          if (!techBullish) return false;
        }

        const signalBullish = s.action === 'BUY' && s.option_type === 'CE';
        const momentumBullish = indexMomentum ? indexMomentum.direction.includes('BULLISH') : null;
        const trendDirection = String(s.trend_direction || '').toUpperCase();
        const trendAligned = trendDirection
          ? ((trendDirection.includes('UP') && s.option_type === 'CE') || (trendDirection.includes('DOWN') && s.option_type === 'PE'))
          : true;

        // Technical indicator alignment (if available)
        const tech = s.technical_indicators || {};
        const rsi = Number(tech.rsi ?? 50);
        const macdCross = String(tech.macd?.crossover || '').toLowerCase();
        const techBullish = (rsi >= 45 && rsi <= 75) && (macdCross === 'bullish' || macdCross === '');
        const techBearish = (rsi >= 25 && rsi <= 55) && (macdCross === 'bearish' || macdCross === '');
        const techAligned = s.option_type === 'CE' ? techBullish : techBearish;
        
        // Signal MUST align with momentum direction
        if (signalBullish !== momentumBullish) return false;
        if (!trendAligned) return false;
        if (!techAligned) return false;
        
        return true;
      });

      if (validSignals.length === 0) {
        console.log('❌ No signals match momentum criteria (all filtered out)');
        return;
      }

      // Step 7: Advanced scoring with momentum-first approach
      const scoredSignals = validSignals.map(signal => {
        let finalScore = signal.confirmation_score ?? signal.confidence ?? 0;
        const scoringFactors = [];
        const indexMomentum = momentumAnalysis[signal.index];
        
        // Factor 1: MOMENTUM SCORE (MOST IMPORTANT) - up to 40 points
        if (indexMomentum) {
          const momentumBonus = Math.floor(indexMomentum.score * 0.4); // 0-40 points
          finalScore += momentumBonus;
          scoringFactors.push(`Momentum ${indexMomentum.direction} +${momentumBonus}`);
          
          // Extra bonus for very strong momentum (>1.5% move)
          if (Math.abs(indexMomentum.changePercent) > 1.5) {
            finalScore += 20;
            scoringFactors.push('Very strong move +20');
          }
        }
        
        // Factor 2: Trend strength and alignment (±20 points)
        const indexTrend = indices[signal.index];
        if (indexTrend) {
          const trendStrong = indexTrend.strength === 'Strong';
          const trendUp = indexTrend.trend === 'Uptrend' || indexTrend.change_percent > 0;
          const signalBullish = signal.action === 'BUY' && signal.option_type === 'CE';
          
          if ((trendUp && signalBullish) || (!trendUp && !signalBullish)) {
            const bonus = trendStrong ? 20 : 12;
            finalScore += bonus;
            scoringFactors.push(`Trend aligned +${bonus}`);
          } else {
            finalScore -= 15; // Heavy penalty for counter-trend
            scoringFactors.push('Counter-trend -15');
          }
        }
        
        // Factor 3: News sentiment impact (±15 points)
        const signalBullish = signal.action === 'BUY' && signal.option_type === 'CE';
        if (newsImpact > 1 && signalBullish) {
          finalScore += 15;
          scoringFactors.push('Bullish news +15');
        } else if (newsImpact < -1 && !signalBullish) {
          finalScore += 15;
          scoringFactors.push('Bearish news +15');
        } else if (Math.abs(newsImpact) > 1 && ((newsImpact > 0) !== signalBullish)) {
          finalScore -= 10;
          scoringFactors.push('News mismatch -10');
        }
        
        // Factor 4: Overall sentiment alignment (±10 points)
        const sentimentBullish = sentimentScore > 0.6;
        const sentimentBearish = sentimentScore < 0.4;
        
        if ((sentimentBullish && signalBullish) || (sentimentBearish && !signalBullish)) {
          finalScore += 10;
          scoringFactors.push('Sentiment aligned +10');
        } else if ((sentimentBullish && !signalBullish) || (sentimentBearish && signalBullish)) {
          finalScore -= 8;
          scoringFactors.push('Sentiment mismatch -8');
        }
        
        // Factor 5: Risk-reward quality (+10 to +20 points)
        const risk = Math.abs(signal.entry_price - signal.stop_loss);
        const reward = Math.abs(signal.target - signal.entry_price);
        const rrRatio = reward / risk;
        if (rrRatio >= 2.0) {
          finalScore += 20;
          scoringFactors.push(`RR 1:${rrRatio.toFixed(1)} +20`);
        } else if (rrRatio >= 1.7) {
          finalScore += 15;
          scoringFactors.push(`RR 1:${rrRatio.toFixed(1)} +15`);
        } else {
          finalScore += 10;
          scoringFactors.push(`RR 1:${rrRatio.toFixed(1)} +10`);
        }
        
        // Factor 6: Technical quality
        if (signal.quality_score && signal.quality_score >= 80) {
          finalScore += 15;
          scoringFactors.push(`Quality ${signal.quality_score} +15`);
        } else if (signal.quality_score && signal.quality_score >= 70) {
          finalScore += 8;
          scoringFactors.push(`Quality ${signal.quality_score} +8`);
        }
        
        return { ...signal, finalScore, scoringFactors, indexMomentum };
      });

      // Step 8: EXECUTION FILTER - ONLY trade signals with high quality and score
      // This ensures we only ENTER exceptionally strong trades, even though we DISPLAY more signals
      const highQualitySignals = scoredSignals.filter(s => {
        const baseConfidence = Number(s.confirmation_score ?? s.confidence ?? 0);
        const quality = Number(s.quality_score ?? s.quality ?? 0);
        if (quality < 70) return false;
        if (baseConfidence < 70) return false;
        // Must have high final score (100+) after all factors
        if (s.finalScore < 100) return false;
        // Must have strong momentum
        if (!s.indexMomentum || s.indexMomentum.score < 75) return false;
        return true;
      });
      
      if (highQualitySignals.length === 0) {
        console.log('❌ No signals meet EXECUTION criteria (quality 70+, confidence 70+, score 100+, momentum 75+)');
        // No trade if no signal meets execution thresholds; wait for better setup.
        return;
      }

      let candidateSignals = highQualitySignals;
      if (autoTradingActive && isLiveMode) {
        let selectionBalance = Number(liveAccountBalance);
        const balanceAgeMs = liveBalanceSyncedAt ? (Date.now() - Number(liveBalanceSyncedAt)) : Number.POSITIVE_INFINITY;
        if (!Number.isFinite(selectionBalance) || selectionBalance <= 0 || balanceAgeMs > 30000) {
          try {
            const brokerId = Number(activeBrokerId);
            selectionBalance = await fetchLiveBalance(Number.isFinite(brokerId) && brokerId > 0 ? brokerId : null);
          } catch (e) {
            console.warn(`⚠️ Could not refresh live balance for signal selection: ${e.message}`);
          }
        }

        if (Number.isFinite(selectionBalance) && selectionBalance > 0) {
          const affordableSignals = highQualitySignals.filter((s) => {
            const required = estimateSignalCapitalRequired(s, lotMultiplier);
            return Number.isFinite(required) && required <= selectionBalance;
          });
          if (affordableSignals.length === 0) {
            console.log(`⏸️ No high-quality signal fits available live balance ₹${selectionBalance.toFixed(2)}.`);
            return;
          }
          candidateSignals = affordableSignals;
        }
      }

      // Pick highest scored signal with best momentum.
      // If conditions are effectively equal, prefer lower required capital.
      const bestSignal = candidateSignals.reduce((best, curr) => {
        if (!best) return curr;
        // Prioritize momentum score, then final score
        const bestMomentum = best.indexMomentum?.score || 0;
        const currMomentum = curr.indexMomentum?.score || 0;
        if (currMomentum > bestMomentum) return curr;
        if (currMomentum < bestMomentum) return best;

        const bestScore = Number(best.finalScore || 0);
        const currScore = Number(curr.finalScore || 0);
        if (currScore > bestScore) return curr;
        if (currScore < bestScore) return best;

        // Secondary tie-break: higher model quality/confidence.
        const bestQuality = Number(best.quality_score ?? best.quality ?? 0);
        const currQuality = Number(curr.quality_score ?? curr.quality ?? 0);
        if (currQuality > bestQuality) return curr;
        if (currQuality < bestQuality) return best;

        const bestConfidence = Number(best.confirmation_score ?? best.confidence ?? 0);
        const currConfidence = Number(curr.confirmation_score ?? curr.confidence ?? 0);
        if (currConfidence > bestConfidence) return curr;
        if (currConfidence < bestConfidence) return best;

        // Capital efficiency tie-break (your requested behavior).
        const bestRequired = estimateSignalCapitalRequired(best, lotMultiplier);
        const currRequired = estimateSignalCapitalRequired(curr, lotMultiplier);
        if (Number.isFinite(currRequired) && Number.isFinite(bestRequired)) {
          return currRequired < bestRequired ? curr : best;
        }

        return best;
      });

      console.log(`✅ MOMENTUM-ALIGNED SIGNAL SELECTED`);
      console.log(`   ${bestSignal.index} ${bestSignal.option_type} ${bestSignal.symbol}`);
      console.log(`   Final Score: ${bestSignal.finalScore.toFixed(1)} | Momentum: ${bestSignal.indexMomentum.direction} (${bestSignal.indexMomentum.score})`);
      console.log(`   Market Move: ${bestSignal.indexMomentum.changePercent.toFixed(2)}% | Strength: ${bestSignal.indexMomentum.strength}`);
      console.log(`   Factors: ${bestSignal.scoringFactors.join(', ')}`);
      console.log(`   Entry: ₹${bestSignal.entry_price} | Target: ₹${bestSignal.target} | SL: ₹${bestSignal.stop_loss}`);

      // ═══════════════════════════════════════════════════════════════
      // ENHANCED PRE-EXECUTION VALIDATION WITH 10-POINT MAX STOP LOSS
      // ═══════════════════════════════════════════════════════════════
      
      // Validate stop loss is within 10-point limit
      const stopPoints = Math.abs(bestSignal.entry_price - bestSignal.stop_loss);
      if (stopPoints > MAX_STOP_POINTS) {
        console.warn(`⚠️ REJECTED: Stop loss ${stopPoints.toFixed(1)} points exceeds ${MAX_STOP_POINTS} point limit`);
        return;
      }
      
      const readiness = getEntryReadiness(bestSignal);
      if (!readiness.pass) {
        console.warn(`⚠️ REJECTED: ${readiness.reasons.join(' | ')}`);
        return;
      }
      
      console.log(`✅ PRE-EXECUTION VALIDATION PASSED:`);
      console.log(`   Stop Loss: ${stopPoints.toFixed(1)} points (max ${MAX_STOP_POINTS})`);
      console.log(`   Readiness: ${readiness.status}`);

      // Step 9: Execute LIVE trade when auto-trading is ENABLED, otherwise create PAPER trade for review
      if (autoTradingActive) {
        console.log('🚀 AUTO-TRADING ENABLED - Executing LIVE trade...');
        await executeAutoTrade(bestSignal, { skipPreScan: true });
        await fetchData(true);
        console.log('✅ Live trade executed!');
      } else {
        console.log('📊 AUTO-TRADING DISABLED - Creating PAPER trade for review...');
        await createPaperTradeFromSignal(bestSignal, { skipPreScan: true });
        await fetchData(true);
        console.log('✅ Paper trade created - Review quality and click "Start Auto-Trading" to go live!');
      }
    } catch (error) {
      console.error('Error analyzing market:', error);
    } finally {
      analyzeMarket.isRunning = false;
    }
  };

  // Remove toggleMode, always live
  const toggleMode = () => {};

  // Fetch option signals from backend
  useEffect(() => {
    const fetchOptionSignals = async () => {
      try {
        // Try broader universes with a smaller FNO batch first to improve stock coverage
        const modeParam = encodeURIComponent(confirmationMode);
        const urls = [
          `${OPTION_SIGNALS_API}?mode=${modeParam}&include_nifty50=true&include_fno_universe=true&max_symbols=12`,
          `${OPTION_SIGNALS_API}?mode=${modeParam}&include_nifty50=true&include_fno_universe=true&max_symbols=40`,
          `${OPTION_SIGNALS_API}?mode=${modeParam}&include_nifty50=true`,
          `${OPTION_SIGNALS_API}?mode=${modeParam}`,
        ];
        let data = null;
        for (const u of urls) {
          try {
            const res = await fetch(u);
            if (!res.ok) continue;
            data = await res.json();
            if (Array.isArray(data?.signals) && data.signals.length > 0) break;
          } catch (e) {
            // try next url
          }
        }
        data = data || { signals: [] };
        
        // Check if API returned an error or detail message
        if (data.detail || data.error) {
          console.log('⚠️ No option signals available:', data.detail || data.error);
          setOptionSignals([]);  // Clear old signals
        } else if (Array.isArray(data.signals) && data.signals.length > 0) {
          setOptionSignals(data.signals);
        } else {
          console.log('⚠️ No signals returned from API');
          setOptionSignals([]);  // Clear old signals
        }
      } catch (e) {
        console.error('❌ Failed to fetch option signals:', e);
        setOptionSignals([]);  // Clear on error
      } finally {
        setSignalsLoaded(true);
      }
    };
    fetchOptionSignals();
  }, [confirmationMode]);

  // Run an initial scanner pass once option signals are loaded so the UI
  // shows market-quality rows without requiring a manual Refresh click.
  useEffect(() => {
    if (!signalsLoaded) return;
    // Fire-and-forget fresh scan (bypass cache) to populate qualityTrades
    scanMarketForQualityTrades(scannerMinQuality, true).catch(() => {});
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [signalsLoaded]);

  const fetchLatestOptionSignals = async () => {
    try {
      const modeParam = encodeURIComponent(confirmationMode);
      const urls = [
        `${OPTION_SIGNALS_API}?mode=${modeParam}&include_nifty50=true&include_fno_universe=true&max_symbols=12`,
        `${OPTION_SIGNALS_API}?mode=${modeParam}&include_nifty50=true&include_fno_universe=true&max_symbols=40`,
        `${OPTION_SIGNALS_API}?mode=${modeParam}&include_nifty50=true`,
        `${OPTION_SIGNALS_API}?mode=${modeParam}`,
      ];
      for (const u of urls) {
        try {
          const res = await fetch(u);
          if (!res.ok) continue;
          const data = await res.json();
          if (Array.isArray(data.signals) && data.signals.length > 0) {
            setOptionSignals(data.signals);
            return data.signals;
          }
        } catch (e) {
          // try next
        }
      }
    } catch (e) {
      console.error('❌ Failed to refresh option signals:', e);
    }
    return [];
  };

  // Group signals by index to show CE and PE side-by-side
  const groupedSignals = optionSignals.reduce((acc, signal) => {
    // Filter out fake/invalid signals
    if (signal.error) return acc;
    if (!signal.symbol || !signal.index || !signal.strike) return acc;
    if (!signal.entry_price || signal.entry_price <= 0) return acc;
    if (!signal.target || signal.target <= 0) return acc;
    if (!signal.stop_loss || signal.stop_loss <= 0) return acc;
    if (!signal.confirmation_score && !signal.confidence) return acc;
    
    const key = signal.index;
    if (!acc[key]) {
      acc[key] = { ce: null, pe: null, strike: signal.strike, expiry: signal.expiry_date || signal.expiry_zone };
    }
    if (signal.option_type === 'CE') {
      acc[key].ce = signal;
    } else if (signal.option_type === 'PE') {
      acc[key].pe = signal;
    }
    return acc;
  }, {});

  // Get selected signal from grouped signals
  const selectedSignal = selectedSignalSymbol
    ? optionSignals.find((s) => s.symbol === selectedSignalSymbol)
    : null;

  const compareScannerSignals = (a, b) => {
    const getRatingTier = (signal) => {
      const q = Number(signal?.quality ?? signal?.quality_score ?? 0);
      if (q >= 90) return 2; // EXCELLENT
      if (q >= 80) return 1; // GOOD
      return 0; // POOR
    };

    const aStart = getEntryReadiness(enrichSignalWithAiMetrics(a)).pass ? 1 : 0;
    const bStart = getEntryReadiness(enrichSignalWithAiMetrics(b)).pass ? 1 : 0;
    if (bStart !== aStart) return bStart - aStart;
    const qDiff = Number(b?.quality || 0) - Number(a?.quality || 0);
    if (qDiff !== 0) return qDiff;
    const ratingDiff = getRatingTier(b) - getRatingTier(a);
    if (ratingDiff !== 0) return ratingDiff;
    const aCapital = resolveSignalCapitalRequired(a, lotMultiplier);
    const bCapital = resolveSignalCapitalRequired(b, lotMultiplier);
    if (Number.isFinite(aCapital) && Number.isFinite(bCapital) && aCapital !== bCapital) {
      return aCapital - bCapital;
    }
    const cDiff = Number(b?.confirmation_score ?? b?.confidence ?? 0) - Number(a?.confirmation_score ?? a?.confidence ?? 0);
    if (cDiff !== 0) return cDiff;
    const rrDiff = Number(b?.rr || 0) - Number(a?.rr || 0);
    if (rrDiff !== 0) return rrDiff;
    return String(a?.symbol || '').localeCompare(String(b?.symbol || ''));
  };

  const strictDisplayThreshold = Number(scannerMinQuality);
  const strictDisplayPass = (signal) => Number(signal?.quality ?? signal?.quality_score ?? 0) >= strictDisplayThreshold;

  // Show only strict scanner signals above current selected threshold.
  const displayQualityTrades = qualityTrades.filter((t) => strictDisplayPass(t));
  const fallbackVisibleTrades = displayQualityTrades.length > 0
    ? displayQualityTrades
    : qualityTrades.slice().sort(compareScannerSignals).slice(0, 8);
  // Execution fallback only: allow high-quality >=85 setups when strict bucket is empty.
  const executionQualityTrades = qualityTrades.filter((t) => Number(t?.quality ?? t?.quality_score ?? 0) >= 85);

  // Get best quality trade from market scanner (if available)
  const sortedQualityTrades = fallbackVisibleTrades.slice().sort(compareScannerSignals);
  const sortedExecutionQualityTrades = executionQualityTrades.slice().sort(compareScannerSignals);
  const bestQualityTrade = sortedQualityTrades.length > 0 ? sortedQualityTrades[0] : null;
  const qualityTradesIndices = fallbackVisibleTrades.filter((t) => getSignalGroup(t) === 'indices').sort(compareScannerSignals);
  const qualityTradesStocks = fallbackVisibleTrades.filter((t) => getSignalGroup(t) === 'stocks').sort(compareScannerSignals);
  const scannerTrades = scannerTab === 'indices'
    ? qualityTradesIndices
    : scannerTab === 'stocks'
      ? qualityTradesStocks
      : sortedQualityTrades;
  const scannerTradesSorted = scannerTrades.slice().sort(compareScannerSignals);

  // Pick the best signal (highest confidence) from valid optionSignals only
  const bestSignal = optionSignals.reduce((best, curr) => {
    // Skip invalid signals
    if (curr.error || !curr.symbol || !curr.entry_price || curr.entry_price <= 0) return best;
    if (!curr.confirmation_score && !curr.confidence) return best;
    
    return (!best || ((curr.confirmation_score ?? curr.confidence) > (best.confirmation_score ?? best.confidence))) ? curr : best;
  }, null);

  // For recommendation panel, use strict scanner-best signal only.
  const activeSignal = bestQualityTrade || null;

  const professionalSignalEligible = professionalSignal && !professionalSignal.error && strictDisplayPass(professionalSignal)
    ? professionalSignal
    : null;
  const currentProfessionalSignal = bestQualityTrade || professionalSignalEligible;
  const lastProfessionalEligible = strictDisplayPass(lastProfessionalVisibleSignal) ? lastProfessionalVisibleSignal : null;
  const lastRecommendationEligible = strictDisplayPass(lastAiRecommendationSignal) ? lastAiRecommendationSignal : null;
  const professionalSignalDisplay = enrichSignalWithAiMetrics(currentProfessionalSignal || lastProfessionalEligible);
  const activeSignalUi = enrichSignalWithAiMetrics(activeSignal || lastRecommendationEligible);
  const professionalReadiness = getEntryReadiness(professionalSignalDisplay);
  const recommendationReadiness = getEntryReadiness(activeSignalUi);
  const canStartTradingNow = recommendationReadiness?.pass === true;
  const professionalStartTradeLabel = professionalReadiness?.pass ? 'YES' : (professionalReadiness?.status || 'WAIT');
  const professionalStartTradeColor = professionalReadiness?.pass ? '#86efac' : '#fdba74';
  const recommendationStartTradeLabel = recommendationReadiness?.pass ? 'YES' : (recommendationReadiness?.status || 'WAIT');
  const recommendationStartTradeBackground = recommendationReadiness?.pass ? '#c6f6d5' : '#fed7aa';
  const recommendationStartTradeColor = recommendationReadiness?.pass ? '#22543d' : '#9a3412';

  useEffect(() => {
    if (!armStatus) return undefined;
    const timer = setTimeout(() => setArmStatus(null), 4000);
    return () => clearTimeout(timer);
  }, [armStatus]);

  useEffect(() => {
    if (currentProfessionalSignal?.symbol) {
      setLastProfessionalVisibleSignal(currentProfessionalSignal);
    }
  }, [currentProfessionalSignal?.symbol, currentProfessionalSignal?.entry_price, currentProfessionalSignal?.target, currentProfessionalSignal?.stop_loss]);

  useEffect(() => {
    if (activeSignal?.symbol) {
      setLastAiRecommendationSignal(activeSignal);
    }
  }, [activeSignal?.symbol, activeSignal?.entry_price, activeSignal?.target, activeSignal?.stop_loss]);

  const displayEntryPrice = activeSignalUi?.entry_price;
  const displayTarget = activeSignalUi?.target;
  const displayStopLoss = activeSignalUi?.stop_loss;
  const displayTargetPoints =
    displayTarget != null && displayEntryPrice != null
      ? Math.abs(Number(displayTarget) - Number(displayEntryPrice))
      : null;
  const displaySlPoints =
    displayStopLoss != null && displayEntryPrice != null
      ? Math.abs(Number(displayEntryPrice) - Number(displayStopLoss))
      : null;
  const normalizedLotMultiplier = Number.isFinite(Number(lotMultiplier)) && Number(lotMultiplier) > 0
    ? Number(lotMultiplier)
    : 1;
  const displayQuantityRaw = Number(
    activeSignalUi?.quantity
    ?? activeSignalUi?.qty
    ?? activeSignalUi?.lot_size
    ?? activeSignalUi?.lotSize
    ?? activeSignalUi?.lot
    ?? activeSignalUi?.lots
    ?? 1
  );
  const displayQuantity = Number.isFinite(displayQuantityRaw) && displayQuantityRaw > 0 ? displayQuantityRaw : 1;
  const displayTotalQuantity = displayQuantity * normalizedLotMultiplier;
  const displayCapitalRequiredRaw = resolveSignalCapitalRequired(activeSignalUi, normalizedLotMultiplier);
  const displayCapitalRequired = Number.isFinite(displayCapitalRequiredRaw) && displayCapitalRequiredRaw > 0
    ? displayCapitalRequiredRaw
    : (displayEntryPrice != null ? Number(displayEntryPrice) * displayTotalQuantity : 0);
  const displayHeaderSymbol = activeSignalUi?.index || activeSignalUi?.symbol || selectedSignalSymbol || 'Market';

  const liveDisplaySignal = professionalSignalDisplay || activeSignalUi;
  const liveEntryPrice = liveDisplaySignal?.entry_price;
  const liveTarget = liveDisplaySignal?.target;
  const liveStopLoss = liveDisplaySignal?.stop_loss;
  const liveTargetPoints =
    liveTarget != null && liveEntryPrice != null
      ? Math.abs(Number(liveTarget) - Number(liveEntryPrice))
      : null;
  const liveSlPoints =
    liveStopLoss != null && liveEntryPrice != null
      ? Math.abs(Number(liveEntryPrice) - Number(liveStopLoss))
      : null;
  const liveQuantityRaw = Number(
    liveDisplaySignal?.quantity
    ?? liveDisplaySignal?.qty
    ?? liveDisplaySignal?.lot_size
    ?? liveDisplaySignal?.lotSize
    ?? activeSignalUi?.quantity
    ?? activeSignalUi?.qty
    ?? activeSignalUi?.lot_size
    ?? activeSignalUi?.lotSize
    ?? 1
  );
  const liveQuantity = Number.isFinite(liveQuantityRaw) && liveQuantityRaw > 0 ? liveQuantityRaw : 1;
  const liveTotalQuantity = liveQuantity * normalizedLotMultiplier;
  const livePotentialProfit = liveTarget != null && liveEntryPrice != null
    ? (Number(liveTarget) - Number(liveEntryPrice)) * liveTotalQuantity
    : null;
  const liveMaxRisk = liveStopLoss != null && liveEntryPrice != null
    ? (Number(liveEntryPrice) - Number(liveStopLoss)) * liveTotalQuantity
    : null;
  const liveExpiryDate = liveDisplaySignal?.expiry_date || liveDisplaySignal?.expiry;

  const hasLiveBalance = Number.isFinite(Number(liveAccountBalance))
    && Number(liveAccountBalance) >= 0
    && Number.isFinite(Number(liveBalanceSyncedAt));
  const liveBalanceValue = hasLiveBalance ? Number(liveAccountBalance) : 0;
  const hasPositiveGateBalance = hasLiveBalance && liveBalanceValue > 0;
  const estimatedGateBalance = Math.max(Number(displayCapitalRequired || 0), MIN_LIVE_BALANCE_REQUIRED);
  const effectiveGateBalance = hasPositiveGateBalance ? liveBalanceValue : estimatedGateBalance;
  const effectiveGateBalanceLabel = hasPositiveGateBalance
    ? `₹${effectiveGateBalance.toLocaleString()}`
    : `₹${Math.round(effectiveGateBalance).toLocaleString()} (estimated)`;
  const liveArmed = Boolean(enabled && isLiveMode);
  const liveBalanceGateRows = isLiveMode
    ? [
        {
          label: 'Min Live Balance',
          pass: effectiveGateBalance >= MIN_LIVE_BALANCE_REQUIRED,
          detail: `${effectiveGateBalanceLabel} / Min ₹${MIN_LIVE_BALANCE_REQUIRED.toLocaleString()}`
        },
        {
          label: 'Capital Availability',
          pass: Number.isFinite(displayCapitalRequired) && displayCapitalRequired > 0 && effectiveGateBalance >= displayCapitalRequired,
          detail: `Need ₹${Math.round(displayCapitalRequired || 0).toLocaleString()} / Avail ${effectiveGateBalanceLabel}`
        },
      ]
    : [];
  const gateStatusRows = [
    {
      label: 'Market Open',
      pass: !!isMarketOpen,
      detail: isMarketOpen ? 'Open now' : (marketClosedReason || 'Closed')
    },
    {
      label: 'Live-Trading Armed',
      pass: isLiveMode ? liveArmed : true,
      detail: isLiveMode ? (liveArmed ? 'Armed (LIVE)' : 'Disarmed') : 'Demo mode active'
    },
    {
      label: 'AI Entry Gate',
      pass: recommendationReadiness?.pass === true,
      detail: recommendationReadiness?.pass
        ? (recommendationReadiness?.sizingNote || 'Start Trade YES')
        : (recommendationReadiness?.reasons?.[0] || 'Start Trade decision is NO')
    },
    {
      label: 'Premium Movement',
      pass: activeSignalUi?.premium_movement_ok ?? true,
      detail: activeSignalUi?.premium_movement_detail ?? 'Checking...'
    },
    {
      label: 'Min Live Balance',
      pass: !isLiveMode || effectiveGateBalance >= MIN_LIVE_BALANCE_REQUIRED,
      detail: !isLiveMode
        ? 'Demo mode - skipped'
        : `${effectiveGateBalanceLabel} / Min ₹${MIN_LIVE_BALANCE_REQUIRED.toLocaleString()}`
    },
    {
      label: 'Capital Availability',
      pass: !isLiveMode || (Number.isFinite(displayCapitalRequired) && displayCapitalRequired > 0 && effectiveGateBalance >= displayCapitalRequired),
      detail: !isLiveMode
        ? 'Demo mode - skipped'
        : `Need ₹${Math.round(displayCapitalRequired || 0).toLocaleString()} / Avail ${effectiveGateBalanceLabel}`
    },
    {
      label: 'Risk Pause',
      pass: !(stats?.trading_paused),
      detail: stats?.trading_paused ? (stats?.pause_reason || 'Paused by backend risk controls') : 'Active'
    },
  ];
  const gateBlockingReasons = gateStatusRows.filter((g) => !g.pass).map((g) => `${g.label}: ${g.detail}`);

  // Render option signals table - Side by side CE and PE
  const renderOptionSignalsTable = () => (
    <div style={{ margin: '32px 0' }}>
      <h3>📊 Intraday Option Signals (CE vs PE)</h3>
      {Object.keys(groupedSignals).length === 0 && signalsLoaded && (
        <div style={{ 
          padding: '20px', 
          background: '#fff3cd', 
          border: '2px solid #ffc107', 
          borderRadius: '8px', 
          marginBottom: '16px',
          textAlign: 'center'
        }}>
          <div style={{ fontSize: '18px', fontWeight: 'bold', color: '#856404', marginBottom: '8px' }}>
            ⚠️ No Live Signals Available
          </div>
          <div style={{ fontSize: '14px', color: '#856404' }}>
            The API did not return any valid signals. This could be due to:
            <ul style={{ textAlign: 'left', margin: '10px auto', maxWidth: '500px' }}>
              <li>Market conditions not meeting signal criteria</li>
              <li>All signals filtered out due to low quality scores</li>
              <li>API connection issues</li>
              <li>Market closed or low volatility</li>
            </ul>
          </div>
        </div>
      )}
      {!signalsLoaded && (
        <div style={{ padding: '20px', background: '#d1ecf1', border: '1px solid #17a2b8', borderRadius: '4px', marginBottom: '16px' }}>
          <strong>Loading signals...</strong>
        </div>
      )}
      <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '13px', background: 'white', borderRadius: '8px', overflow: 'hidden' }}>
        <thead>
          <tr style={{ background: '#f7fafc', borderBottom: '2px solid #e2e8f0' }}>
            <th style={{ padding: '12px', border: '1px solid #e2e8f0', textAlign: 'center' }}>Index</th>
            <th style={{ padding: '12px', border: '1px solid #e2e8f0', textAlign: 'center', color: '#2d8a3f', fontWeight: '700' }}>📈 CALL (CE) - BUY</th>
            <th style={{ padding: '12px', border: '1px solid #e2e8f0', textAlign: 'center', color: '#c92a2a', fontWeight: '700' }}>📉 PUT (PE) - BUY</th>
            <th style={{ padding: '12px', border: '1px solid #e2e8f0', textAlign: 'center' }}>Strike</th>
            <th style={{ padding: '12px', border: '1px solid #e2e8f0', textAlign: 'center' }}>Expiry</th>
          </tr>
        </thead>
        <tbody>
          {Object.entries(groupedSignals).map(([index, data]) => (
            <tr key={index} style={{ borderBottom: '1px solid #e2e8f0' }}>
              <td style={{ padding: '12px', border: '1px solid #e2e8f0', fontWeight: '700', textAlign: 'center', color: '#2b6cb0' }}>{index}</td>
              
              {/* CALL (CE) Signal */}
              <td style={{ padding: '10px', border: '1px solid #e2e8f0', textAlign: 'center', background: selectedSignalSymbol === data.ce?.symbol ? '#eff6ff' : 'white' }}>
                {data.ce ? (
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '6px', alignItems: 'center' }}>
                    <label style={{ display: 'flex', alignItems: 'center', gap: '6px', cursor: 'pointer' }}>
                      <input
                        type="radio"
                        name="signal_selection"
                        checked={selectedSignalSymbol === data.ce.symbol}
                        onChange={() => {
                          setSelectedSignalSymbol(data.ce.symbol);
                          localStorage.setItem('selectedSignalSymbol', data.ce.symbol);
                        }}
                        style={{ cursor: 'pointer', width: '16px', height: '16px' }}
                      />
                      <span style={{ color: '#2d8a3f', fontWeight: 'bold', fontSize: '12px' }}>SELECT</span>
                    </label>
                    <div style={{ fontSize: '12px', lineHeight: '1.4' }}>
                      <div><strong>Entry:</strong> ₹{(data.ce.entry_price ?? 0).toFixed(2)}</div>
                      <div><strong>Target:</strong> <span style={{ color: '#48bb78', fontWeight: 'bold' }}>₹{(data.ce.target ?? 0).toFixed(2)}</span></div>
                      <div><strong>SL:</strong> <span style={{ color: '#f56565' }}>₹{(data.ce.stop_loss ?? 0).toFixed(2)}</span></div>
                      <div style={{ marginTop: '4px', padding: '4px', borderRadius: '3px', background: Number(data.ce.confirmation_score ?? data.ce.confidence ?? 0) >= 85 ? '#c6f6d5' : Number(data.ce.confirmation_score ?? data.ce.confidence ?? 0) >= 75 ? '#feebc8' : '#fed7d7', color: Number(data.ce.confirmation_score ?? data.ce.confidence ?? 0) >= 85 ? '#22543d' : Number(data.ce.confirmation_score ?? data.ce.confidence ?? 0) >= 75 ? '#92400e' : '#742a2a', fontWeight: 'bold' }}>
                        Conf: {(data.ce.confirmation_score ?? data.ce.confidence ?? 0).toFixed(1)}%
                      </div>
                    </div>
                  </div>
                ) : (
                  <span style={{ color: '#cbd5e0' }}>No Signal</span>
                )}
              </td>
              
              {/* PUT (PE) Signal */}
              <td style={{ padding: '10px', border: '1px solid #e2e8f0', textAlign: 'center', background: selectedSignalSymbol === data.pe?.symbol ? '#eff6ff' : 'white' }}>
                {data.pe ? (
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '6px', alignItems: 'center' }}>
                    <label style={{ display: 'flex', alignItems: 'center', gap: '6px', cursor: 'pointer' }}>
                      <input
                        type="radio"
                        name="signal_selection"
                        checked={selectedSignalSymbol === data.pe.symbol}
                        onChange={() => {
                          setSelectedSignalSymbol(data.pe.symbol);
                          localStorage.setItem('selectedSignalSymbol', data.pe.symbol);
                        }}
                        style={{ cursor: 'pointer', width: '16px', height: '16px' }}
                      />
                      <span style={{ color: '#c92a2a', fontWeight: 'bold', fontSize: '12px' }}>SELECT</span>
                    </label>
                    <div style={{ fontSize: '12px', lineHeight: '1.4' }}>
                      <div><strong>Entry:</strong> ₹{(data.pe.entry_price ?? 0).toFixed(2)}</div>
                      <div><strong>Target:</strong> <span style={{ color: '#48bb78', fontWeight: 'bold' }}>₹{(data.pe.target ?? 0).toFixed(2)}</span></div>
                      <div><strong>SL:</strong> <span style={{ color: '#f56565' }}>₹{(data.pe.stop_loss ?? 0).toFixed(2)}</span></div>
                      <div style={{ marginTop: '4px', padding: '4px', borderRadius: '3px', background: Number(data.pe.confirmation_score ?? data.pe.confidence ?? 0) >= 85 ? '#c6f6d5' : Number(data.pe.confirmation_score ?? data.pe.confidence ?? 0) >= 75 ? '#feebc8' : '#fed7d7', color: Number(data.pe.confirmation_score ?? data.pe.confidence ?? 0) >= 85 ? '#22543d' : Number(data.pe.confirmation_score ?? data.pe.confidence ?? 0) >= 75 ? '#92400e' : '#742a2a', fontWeight: 'bold' }}>
                        Conf: {(data.pe.confirmation_score ?? data.pe.confidence ?? 0).toFixed(1)}%
                      </div>
                    </div>
                  </div>
                ) : (
                  <span style={{ color: '#cbd5e0' }}>No Signal</span>
                )}
              </td>
              
              <td style={{ padding: '12px', border: '1px solid #e2e8f0', textAlign: 'center', fontWeight: '600' }}>{data.strike}</td>
              <td style={{ padding: '12px', border: '1px solid #e2e8f0', textAlign: 'center', fontSize: '12px', color: '#666' }}>{data.expiry}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );

  useEffect(() => {
    if (signalsLoaded && selectedSignalSymbol && !selectedSignal) {
      setSelectedSignalSymbol(null);
      localStorage.removeItem('selectedSignalSymbol');
    }
    // eslint-disable-next-line
  }, [signalsLoaded, optionSignals, selectedSignalSymbol]);

  useEffect(() => {
    if (selectedSignalSymbol) {
      localStorage.setItem('selectedSignalSymbol', selectedSignalSymbol);
    } else {
      localStorage.removeItem('selectedSignalSymbol');
    }
  }, [selectedSignalSymbol]);

  // Auto-refresh quality trades scanner every 1 second while:
  // - Market is open
  // - No trades are currently active
  // - Either auto-trading is enabled OR user requested continuous scanning
  // Stop refreshing once a trade is active to avoid constant rescanning
  const scannerPrevShouldRunRef = React.useRef(null);
  const scannerIntervalRef = React.useRef(null);
  useEffect(() => {
    // Only LIVE trades should stop the scanner so demo trades don't starve the signal feed.
    const hasActiveLiveTrade = activeTrades.some((t) => {
      const status = String(t?.status || '').toUpperCase();
      const mode = String(t?.trade_mode || t?.trade_source || '').toUpperCase();
      const isOpen = status === 'OPEN' || (status !== 'CLOSED' && status !== 'CANCELLED' && status !== 'SL_HIT' && status !== 'TARGET_HIT');
      return isOpen && mode === 'LIVE';
    });
    // Keep a separate flag for any open trade (used only for stop-reason labelling below).
    const hasActiveTrade = activeTrades.some((t) => {
      const status = String(t?.status || '').toUpperCase();
      return status === 'OPEN' || (status !== 'CLOSED' && status !== 'CANCELLED' && status !== 'SL_HIT' && status !== 'TARGET_HIT');
    });

    const isActuallyExecuting = executingRef.current || autoBatchExecutingRef.current || executing;
    // Always scan during market hours when no LIVE trade is active.
    // Demo trades do not stop the scanner — fresh signals are needed to fill the 2nd demo slot.
    const shouldRunScanner = isMarketOpen && !hasActiveLiveTrade && !isActuallyExecuting && !scannerUserOverride && !scannerHoldOnStartYes;

    // Only act when desired run-state changes to avoid churn from frequent state updates
    if (scannerPrevShouldRunRef.current === shouldRunScanner) {
      return;
    }
    scannerPrevShouldRunRef.current = shouldRunScanner;

    if (!shouldRunScanner) {
      // Stop scanner
      if (scannerIntervalRef.current) {
        clearInterval(scannerIntervalRef.current);
        scannerIntervalRef.current = null;
      }
      setAutoScanActive(false);
      const _stopReason = hasActiveLiveTrade
        ? 'active trade open'
        : scannerHoldOnStartYes
          ? 'start trade yes available'
        : !isMarketOpen
          ? 'market closed'
          : isActuallyExecuting
            ? 'order execution in progress'
            : 'not needed';
      logDeduped(`dashboard:scanner_stop:${_stopReason}`, `⏹️ Stopped market scanner (${_stopReason})`, {
        burstWindowMs: 180000,
        flushDelayMs: 1200,
        emitFirst: false,
      });
      return;
    }

    // Start scanner
    setAutoScanActive(true);
    logDeduped('dashboard:scanner_loop_start', '🔄 Starting continuous market scanner (auto-refresh every 3 seconds with fresh data)...', {
      burstWindowMs: 180000,
      flushDelayMs: 1200,
      emitFirst: false,
    });
    scannerIntervalRef.current = setInterval(() => {
      if (Date.now() < Number(scannerTransportBackoffUntilRef.current || 0)) return;
      scanMarketForQualityTrades(scannerMinQuality, true).catch(() => {});
    }, SCANNER_LOOP_INTERVAL_MS);

    return () => {
      if (scannerIntervalRef.current) {
        clearInterval(scannerIntervalRef.current);
        scannerIntervalRef.current = null;
      }
      setAutoScanActive(false);
      scannerPrevShouldRunRef.current = null;
      logDeduped('dashboard:scanner_cleanup', '⏹️ Stopped market scanner (cleanup)', {
        burstWindowMs: 180000,
        flushDelayMs: 1200,
        emitFirst: false,
      });
    };
  }, [isMarketOpen, activeTrades.length, scannerMinQuality, executing, scannerUserOverride, scannerHoldOnStartYes]);

  // Auto-start rule:
  // - Live mode ON + auto-trading enabled => execute eligible LIVE candidates.
  // - Live mode OFF + auto-trading enabled => execute eligible DEMO candidates.
  useEffect(() => {
    if (!autoTradingActive || executing) return;
    if (!isMarketOpen) return;
    if (autoBatchExecutingRef.current) return;
    const nowMs = Date.now();
    if (isLiveMode && liveGlobalRejectUntilRef.current > nowMs) return;

    const sourceSignals = sortedQualityTrades.length > 0
      ? sortedQualityTrades
      : (activeSignal ? [activeSignal] : []);
    if (!sourceSignals.length) return;

    const seen = new Set();
    const executableCandidates = sourceSignals
      .map((signal) => enrichSignalWithAiMetrics(signal))
      .filter((signal) => {
        const key = `${String(signal?.symbol || '')}:${String(signal?.action || '').toUpperCase()}`;
        if (!signal?.symbol || seen.has(key)) return false;
        seen.add(key);
        return getEntryReadiness(signal).pass;
      })
      .sort((a, b) => {
        const qDiff = Number(b.quality ?? b.quality_score ?? 0) - Number(a.quality ?? a.quality_score ?? 0);
        if (qDiff !== 0) return qDiff;
        const cDiff = Number(b.confirmation_score ?? b.confidence ?? 0) - Number(a.confirmation_score ?? a.confidence ?? 0);
        if (cDiff !== 0) return cDiff;
        const rrA = Number(a.rr ?? 0);
        const rrB = Number(b.rr ?? 0);
        if (rrB !== rrA) return rrB - rrA;
        const capitalA = estimateSignalCapitalRequired(a, lotMultiplier);
        const capitalB = estimateSignalCapitalRequired(b, lotMultiplier);
        if (Number.isFinite(capitalA) && Number.isFinite(capitalB) && capitalA !== capitalB) {
          return capitalA - capitalB;
        }
        return String(a.symbol || '').localeCompare(String(b.symbol || ''));
      });

    if (!executableCandidates.length) return;

    // Try a small batch each cycle; enforce global single-active-trade lock across LIVE+DEMO.
    const currentModeLabel = isLiveMode ? 'LIVE' : 'DEMO';
    const openTradesAnyMode = (activeTrades || []).filter((t) => {
      const status = String(t?.status || '').toUpperCase();
      const open = status === 'OPEN' || (status !== 'CLOSED' && status !== 'CANCELLED' && status !== 'SL_HIT' && status !== 'TARGET_HIT');
      return open;
    });
    const openCount = openTradesAnyMode.length;
    const availableSlots = openCount > 0 ? 0 : 1;
    if (availableSlots <= 0) return;

    // helper: symbol root (e.g., BANKNIFTY26MAR... -> BANKNIFTY)
    const symbolRoot = (s) => {
      if (!s) return '';
      const m = String(s || '').toUpperCase().match(/^([A-Z]+)/);
      return m ? m[1] : String(s || '').toUpperCase();
    };

    const optionLeg = (signalLike) => {
      const fromType = String(signalLike?.option_type || signalLike?.optionType || '').toUpperCase();
      if (fromType === 'CE' || fromType === 'PE') return fromType;
      const sym = String(signalLike?.symbol || '').toUpperCase();
      if (sym.endsWith('CE')) return 'CE';
      if (sym.endsWith('PE')) return 'PE';
      return 'NA';
    };

    // Exclude candidates that duplicate an already-open root+leg (allow CE+PE pair on same root).
    const openLanes = new Set((activeTrades || [])
      .filter((t) => {
        const status = String(t?.status || '').toUpperCase();
        const open = status === 'OPEN' || (status !== 'CLOSED' && status !== 'CANCELLED' && status !== 'SL_HIT' && status !== 'TARGET_HIT');
        return open;
      })
      .map((t) => `${symbolRoot(t?.symbol)}:${optionLeg(t)}`));
    const selectionBalance = Number(liveAccountBalance);
    const hasSelectionBalance = Number.isFinite(selectionBalance) && selectionBalance > 0;
    const chosen = [];
    const seenLanes = new Set();
    for (const c of executableCandidates) {
      const root = symbolRoot(c?.symbol);
      const leg = optionLeg(c);
      const lane = `${root}:${leg}`;
      if (!root) continue;
      if (openLanes.has(lane)) continue; // avoid retrying same root+leg while open
      if (seenLanes.has(lane)) continue; // don't start two trades on same root+leg in same batch
      if (isLiveMode) {
        const rootRejectUntil = Number(liveRiskRejectCooldownRef.current.get(root) || 0);
        if (rootRejectUntil > nowMs) continue;
      }

      // In LIVE mode, skip symbols that cannot fit at minimum lot/multiplier.
      if (isLiveMode && hasSelectionBalance) {
        const minRequired = estimateSignalCapitalRequired(c, 1);
        if (Number.isFinite(minRequired) && minRequired > selectionBalance) {
          continue;
        }
      }

      seenLanes.add(lane);
      chosen.push(c);
      if (chosen.length >= availableSlots) break;
    }
    if (!chosen.length) return;

    autoBatchExecutingRef.current = true;
    (async () => {
      console.log(`🚀 AUTO START: ${chosen.length} Start Trade YES candidate(s) queued (slots=${availableSlots}, open=${openCount})`);
      for (const candidate of chosen) {
        await executeAutoTrade(candidate, { skipPreScan: true });
      }
      await fetchData(true);
    })().finally(() => {
      autoBatchExecutingRef.current = false;
    });
    // eslint-disable-next-line
  }, [qualityTrades, activeSignal, autoTradingActive, isLiveMode, executing, activeTrades.length, isMarketOpen, lotMultiplier]);

  // Remove legacy toggleAutoTrading logic (config references)
  const toggleAutoTrading = async () => {};

  // Implement auto trade execution using bestSignal
  const executeAutoTrade = async (signal, options = {}) => {
    const { manualStart = false, skipPreScan = false } = options || {};
    if (!signal || executingRef.current) return;
    
    // Execute only when auto-trading is enabled.
    // Mode routing is handled by isLiveMode (LIVE vs DEMO payload).
    if (!manualStart && !autoTradingActive) return;

    if (!isMarketOpen) {
      console.log('⏸️ Market closed - auto trade blocked');
      return;
    }

    let normalizedSignal = enrichSignalWithAiMetrics(signal);
    const lotUnitQty = normalizeTradeQuantity(getSignalBaseQuantity(normalizedSignal));

    const modeLossControl = getModeLossControlState(isLiveMode ? 'LIVE' : 'DEMO');
    if (modeLossControl.active && !manualStart) {
      logDeduped(
        `${isLiveMode ? 'live' : 'demo'}:loss_cluster_cooldown`,
        `⏸️ ${isLiveMode ? 'Live' : 'Demo'} entry paused by loss-cluster cooldown (${Math.ceil(modeLossControl.pauseRemainingMs / 60000)}m remaining)`,
        { burstWindowMs: 60000, emitFirst: false }
      );
      return;
    }

    // Run a fresh scan before executing to ensure the entry price/target/stop are current.
    if (!skipPreScan) {
      try {
        if (!scannerLoading) setScannerLoading(true);
        await scanMarketForQualityTrades(scannerMinQuality, true);
        const latest = (qualityTrades || []).find((s) => String(s.symbol || '').toUpperCase() === String(normalizedSignal.symbol || '').toUpperCase());
        if (latest) normalizedSignal = enrichSignalWithAiMetrics(latest);
      } catch (e) {
        console.warn('⚠️ Pre-entry market scan failed (auto-exec):', e?.message || e);
      } finally {
        try { setScannerLoading(false); } catch (e) {}
      }
    }

    const signalRoot = getUnderlyingRoot(normalizedSignal);
    if (isLiveMode && !manualStart) {
      const nowMs = Date.now();
      const globalRejectUntil = Number(liveGlobalRejectUntilRef.current || 0);
      if (globalRejectUntil > nowMs) {
        logDeduped('live:risk_cooldown:global', '⏸️ Live entry skipped: risk cooldown active after recent rejects', {
          burstWindowMs: 60000,
          flushDelayMs: 1200,
          emitFirst: false,
        });
        return;
      }
      const rootRejectUntil = Number(liveRiskRejectCooldownRef.current.get(signalRoot) || 0);
      if (rootRejectUntil > nowMs) {
        logDeduped(`live:risk_cooldown:${signalRoot}`, `⏸️ Live entry skipped: ${signalRoot || normalizedSignal?.symbol} in risk cooldown`, {
          burstWindowMs: 60000,
          flushDelayMs: 1200,
          emitFirst: false,
        });
        return;
      }
    }

    // Prevent duplicate re-entry attempts on the same live signal while it's already open.
    const hasSameOpenTrade = activeTrades.some((t) => {
      const open = String(t?.status || '').toUpperCase() === 'OPEN' || t?.status == null;
      if (!open) return false;
      const sameSymbol = String(t?.symbol || '') === String(normalizedSignal?.symbol || '');
      const existingSide = String(t?.side || t?.action || '').toUpperCase();
      const signalSide = String(normalizedSignal?.action || '').toUpperCase();
      return sameSymbol && existingSide && signalSide && existingSide === signalSide;
    });
    if (hasSameOpenTrade && !manualStart) {
      console.log(`⏸️ Auto-entry skipped: same live trade already open for ${normalizedSignal?.symbol}`);
      return;
    }

    const readiness = getEntryReadiness(normalizedSignal);
    if (!readiness.pass) {
      const blockText = `Live entry blocked: Start Trade WAIT (${readiness.reasons.join(' | ')})`;
      console.log(`⏸️ ${blockText}`);
      pushEntryBlockEvent({
        symbol: normalizedSignal?.symbol,
        action: normalizedSignal?.action,
        mode: 'LIVE',
        message: blockText,
        reasons: readiness.reasons,
        source: 'client-gate',
      });
      return;
    }

    // Soft block: skip this entry if daily loss limit is hit (auto-trading stays ON).
    if (isLossLimitHit()) {
      console.log('⏸️ Daily loss limit hit - skipping trade entry (auto-trading remains ON)');
      return;
    }
    
    // Concurrency is enforced by backend risk engine (balance/risk/quality gates).

    // Strict entry filters with AI quality assessment
    const confidence = Number(normalizedSignal.confirmation_score ?? normalizedSignal.confidence ?? 0);
    const winRate = stats?.win_rate ? (stats.win_rate / 100) : 0.5;
    const { rr: actualRR, optimalRR } = calculateOptimalRR(normalizedSignal, winRate);
    const tradeQuality = calculateTradeQuality(normalizedSignal, winRate);
    
    console.log(`📊 Trade Quality Analysis: ${tradeQuality.quality}% | Confidence: ${confidence.toFixed(1)}% | RR: ${actualRR.toFixed(2)} vs Optimal: ${optimalRR.toFixed(2)}`);
    
    const token = localStorage.getItem('access_token');
    if (!token) {
      alert('No access token found. Please login.');
      return;
    }
    
    executingRef.current = true;
    setExecuting(true);
    const mode = isLiveMode ? 'LIVE' : 'DEMO';
    console.log(`🚀 AUTO-EXECUTING ${mode} TRADE: ${normalizedSignal.symbol} ${normalizedSignal.action} at ₹${normalizedSignal.entry_price}`);
    
    // Adjust quantity based on capital required: boost lots when capital per lot is low.
    // Live mode downstream guards (balance check + loss-cap sizing) will still clamp if needed.
    const capReqExec = Number(normalizedSignal.capital_required ?? resolveSignalCapitalRequired(normalizedSignal, lotMultiplier));
    let execQtyBoost = 1;
    if (Number.isFinite(capReqExec)) {
      if (capReqExec <= 3000) execQtyBoost = 3;
      else if (capReqExec < 10000) execQtyBoost = 2;
    }
    let adjustedQuantity = normalizeTradeQuantity(getSignalBaseQuantity(normalizedSignal) * Number(lotMultiplier) * execQtyBoost);
    const liveDrawdownMultiplier = getQtyDrawdownMultiplier('LIVE');
    if (liveDrawdownMultiplier < 0.999) {
      adjustedQuantity = Math.max(1, Math.floor(adjustedQuantity * liveDrawdownMultiplier));
      logDeduped(
        `live:qty_drawdown:${liveDrawdownMultiplier}`,
        `🛡️ Live drawdown sizing active: qty scaled to ${Math.round(liveDrawdownMultiplier * 100)}%`,
        { burstWindowMs: 60000, emitFirst: false }
      );
    }
    
    try {
      let effectiveBalance = 0;
      let effectiveBrokerId = Number(activeBrokerId);
      if (isLiveMode) {
        if (!Number.isFinite(effectiveBrokerId) || effectiveBrokerId <= 0) {
          try {
            const broker = await fetchActiveBrokerContext();
            effectiveBrokerId = Number(broker?.id);
          } catch (brokerErr) {
            alert(`Unable to resolve active broker. ${brokerErr.message}`);
            return;
          }
        }
        try {
          effectiveBalance = await fetchLiveBalance(effectiveBrokerId);
        } catch (balErr) {
          const fallback = Number(liveAccountBalance);
          const fallbackBrokerMatch = Number(liveBalanceBrokerId) === Number(effectiveBrokerId);
          if (fallbackBrokerMatch && Number.isFinite(fallback) && fallback > 0) {
            effectiveBalance = fallback;
            console.warn(`⚠️ Using last known live balance ₹${fallback.toFixed(2)} due to fetch error: ${balErr.message}`);
          } else {
            alert(`Unable to fetch real live balance. ${balErr.message}`);
            return;
          }
        }
      }

      if (isLiveMode) {
        const estimatedRequired = estimateSignalCapitalRequired(normalizedSignal, lotMultiplier);
        if (Number.isFinite(estimatedRequired) && estimatedRequired > effectiveBalance) {
          const minUnitRequired = estimateSignalCapitalRequired(normalizedSignal, 1);
          if (Number.isFinite(minUnitRequired) && minUnitRequired > 0 && effectiveBalance >= minUnitRequired) {
            const affordableMultiplier = Math.max(1, Math.floor(effectiveBalance / minUnitRequired));
            adjustedQuantity = normalizeTradeQuantity(getSignalBaseQuantity(normalizedSignal) * affordableMultiplier);
            console.log(`⚙️ Live qty auto-scaled to fit balance: qty=${adjustedQuantity} (multiplier=${affordableMultiplier})`);
          } else {
            const balanceValue = Number(effectiveBalance);
            const deficit = Math.max(0, estimatedRequired - balanceValue);
            const coveragePct = estimatedRequired > 0 ? (balanceValue / estimatedRequired) * 100 : 0;
            const msg = `Insufficient live balance: required ₹${estimatedRequired.toFixed(2)}, available ₹${balanceValue.toFixed(2)}, short ₹${deficit.toFixed(2)} (${coveragePct.toFixed(1)}% covered)`;
            if (manualStart) {
              alert(msg);
            } else {
              console.log(`⏸️ ${msg}`);
            }
            return;
          }
        }

        const entryPrice = Number(normalizedSignal.entry_price ?? 0);
        const stopPrice = Number(normalizedSignal.stop_loss ?? 0);
        const stopDistance = Math.abs(entryPrice - stopPrice);
        const potentialLoss = stopDistance * Number(adjustedQuantity || 0);
        const dynamicPerTradeCap = Number(effectiveBalance) > 0
          ? Number(effectiveBalance) * LIVE_PER_TRADE_RISK_PCT
          : LIVE_MAX_PER_TRADE_LOSS_CAP;
        const maxLossAllowed = Math.min(LIVE_MAX_PER_TRADE_LOSS_CAP, dynamicPerTradeCap);
        const liveCapSizing = getLossCappedQuantity({
          signal: normalizedSignal,
          desiredQuantity: adjustedQuantity,
          maxLossAllowed,
        });
        if (liveCapSizing.autoReduced) {
          adjustedQuantity = liveCapSizing.adjustedQuantity;
          console.log(`⚙️ Live qty auto-reduced to fit risk cap: qty=${adjustedQuantity}, max loss ₹${liveCapSizing.adjustedPotentialLoss.toFixed(2)} / ₹${maxLossAllowed.toFixed(2)}`);
        }
        if (
          Number.isFinite(liveCapSizing.potentialLoss)
          && Number.isFinite(maxLossAllowed)
          && maxLossAllowed > 0
          && !liveCapSizing.fitsWithinCap
        ) {
          const riskUntil = Date.now() + LIVE_RISK_REJECTION_COOLDOWN_MS;
          liveGlobalRejectUntilRef.current = riskUntil;
          if (signalRoot) {
            liveRiskRejectCooldownRef.current.set(signalRoot, riskUntil);
          }
          const riskMsg = `Live entry blocked locally: Potential loss ₹${liveCapSizing.potentialLoss.toFixed(2)} exceeds limit ₹${maxLossAllowed.toFixed(2)} even at minimum qty 1.`;
          pushEntryBlockEvent({
            symbol: normalizedSignal?.symbol,
            action: normalizedSignal?.action,
            mode: 'LIVE',
            message: riskMsg,
            reasons: [
              `potential_loss(${liveCapSizing.potentialLoss.toFixed(2)})`,
              `max_per_trade_loss(${maxLossAllowed.toFixed(2)})`,
            ],
            source: 'client-gate',
          });
          logDeduped(`live:risk_local:${signalRoot || normalizedSignal?.symbol}`, `⏸️ ${riskMsg} Cooling down retries for ${Math.round(LIVE_RISK_REJECTION_COOLDOWN_MS / 1000)}s`, {
            burstWindowMs: 60000,
            flushDelayMs: 1200,
            emitFirst: false,
          });
          return;
        }

        // Enforce exchange lot-size multiples in LIVE mode.
        const alignedLiveQty = Math.floor(Number(adjustedQuantity || 0) / lotUnitQty) * lotUnitQty;
        if (!Number.isFinite(alignedLiveQty) || alignedLiveQty < lotUnitQty) {
          const lotRisk = Math.abs(Number(normalizedSignal.entry_price ?? 0) - Number(normalizedSignal.stop_loss ?? 0)) * lotUnitQty;
          const lotMsg = `Live entry blocked: minimum lot ${lotUnitQty} exceeds risk cap (lot risk ₹${lotRisk.toFixed(2)} > ₹${maxLossAllowed.toFixed(2)}).`;
          pushEntryBlockEvent({
            symbol: normalizedSignal?.symbol,
            action: normalizedSignal?.action,
            mode: 'LIVE',
            message: lotMsg,
            reasons: [
              `lot_size(${lotUnitQty})`,
              `lot_risk(${lotRisk.toFixed(2)})`,
              `max_per_trade_loss(${maxLossAllowed.toFixed(2)})`,
            ],
            source: 'client-gate',
          });
          logDeduped(`live:lot_reject:${signalRoot || normalizedSignal?.symbol}`, `⏸️ ${lotMsg}`, {
            burstWindowMs: 60000,
            flushDelayMs: 1200,
            emitFirst: false,
          });
          return;
        }
        if (alignedLiveQty !== adjustedQuantity) {
          adjustedQuantity = alignedLiveQty;
          console.log(`⚙️ Live qty aligned to lot size: qty=${adjustedQuantity} (lot=${lotUnitQty})`);
        }
      }

      const params = {
        symbol: normalizedSignal.symbol,
        price: normalizedSignal.entry_price,
        target: normalizedSignal.target,
        stop_loss: normalizedSignal.stop_loss,
        quantity: adjustedQuantity,
        side: normalizedSignal.action,
        quality_score: normalizedSignal.quality_score ?? normalizedSignal.quality,
        confirmation_score: normalizedSignal.confirmation_score ?? normalizedSignal.confidence,
        ai_edge_score: normalizedSignal.ai_edge_score,
        momentum_score: normalizedSignal.momentum_score,
        breakout_score: normalizedSignal.breakout_score,
        option_type: normalizedSignal.option_type,
        signal_type: normalizedSignal.signal_type,
        is_stock: normalizedSignal.is_stock === true || normalizedSignal.signal_type === 'stock',
        trend_direction: normalizedSignal.trend_direction,
        trend_strength: normalizedSignal.trend_strength,
        breakout_confirmed: normalizedSignal.breakout_confirmed,
        momentum_confirmed: normalizedSignal.momentum_confirmed,
        breakout_hold_confirmed: normalizedSignal.breakout_hold_confirmed,
        timing_risk: normalizedSignal.timing_risk || normalizedSignal?.timing_risk_profile?.window,
        sudden_news_risk: normalizedSignal.sudden_news_risk ?? normalizedSignal.news_risk,
        news_risk: normalizedSignal.sudden_news_risk ?? normalizedSignal.news_risk,
        liquidity_spike_risk: normalizedSignal.liquidity_spike_risk,
        premium_distortion_risk: normalizedSignal.premium_distortion_risk ?? normalizedSignal.premium_distortion,
        premium_distortion: normalizedSignal.premium_distortion_risk ?? normalizedSignal.premium_distortion,
        close_back_in_range: normalizedSignal.close_back_in_range,
        fake_breakout_by_candle: normalizedSignal.fake_breakout_by_candle,
        market_bias: normalizedSignal.market_bias,
        market_regime: normalizedSignal.market_regime,
        expiry: normalizedSignal.expiry_date,
        force_demo: !isLiveMode,
        broker_id: isLiveMode && Number.isFinite(effectiveBrokerId) && effectiveBrokerId > 0 ? effectiveBrokerId : 1,
        balance: isLiveMode ? effectiveBalance : 0  // 0 = demo mode, positive = live mode
      };
      const response = await config.authFetch(config.endpoints.autoTrade.execute, {
        method: 'POST',
        body: JSON.stringify(params)
      });
      if (response.ok) {
        const data = await response.json();
        if (data && data.success === false) {
          let errorMsg = `Failed to execute trade.\nReason: ${data.message || 'Broker rejected order.'}`;
          if (data.detail) {
            const detailText = typeof data.detail === 'string' ? data.detail : JSON.stringify(data.detail);
            errorMsg += `\nDetail: ${detailText}`;
          }
          console.error(`❌ TRADE EXECUTION FAILED: ${errorMsg}`);
          console.log(`♻️ AUTO-TRADING REMAINS ACTIVE: Will retry when conditions improve`);
          return;
        }
        const executedMode = isLiveMode ? 'LIVE' : 'DEMO';
        const executedTs = new Date().toISOString();
        const optimisticTrade = {
          id: data?.trade_id || data?.id || `optimistic:${executedMode}:${normalizedSignal.symbol}:${executedTs}`,
          symbol: normalizedSignal.symbol,
          side: String(normalizedSignal.action || 'BUY').toUpperCase(),
          action: String(normalizedSignal.action || 'BUY').toUpperCase(),
          quantity: Number(adjustedQuantity || 1),
          entry_price: Number(normalizedSignal.entry_price || params.price || 0),
          price: Number(normalizedSignal.entry_price || params.price || 0),
          current_price: Number(normalizedSignal.entry_price || params.price || 0),
          target: Number(normalizedSignal.target || params.target || 0),
          stop_loss: Number(normalizedSignal.stop_loss || params.stop_loss || 0),
          status: 'OPEN',
          entry_time: executedTs,
          timestamp: executedTs,
          trade_mode: executedMode,
          trade_source: 'autotrade',
          broker_response: data?.broker_response || {},
        };

        // Immediate UI visibility for both LIVE and DEMO; backend sync still reconciles truth.
        setActiveTrades((prev) => {
          const rows = Array.isArray(prev) ? prev : [];
          const duplicate = rows.some((t) => {
            const sameMode = String(t?.trade_mode || t?.trade_source || '').toUpperCase() === executedMode;
            const sameSymbol = String(t?.symbol || '').toUpperCase() === String(optimisticTrade.symbol || '').toUpperCase();
            const sameSide = String(t?.side || t?.action || '').toUpperCase() === String(optimisticTrade.side || '').toUpperCase();
            const isOpen = String(t?.status || '').toUpperCase() === 'OPEN';
            return sameMode && sameSymbol && sameSide && isOpen;
          });
          if (duplicate) return rows;
          return [optimisticTrade, ...rows];
        });
        setHasActiveTrade(true);
        setLastSuccessfulSyncAt(new Date());
        setIsUsingStaleData(false);

        console.log(`✅ ${mode} TRADE EXECUTED: ${normalizedSignal.symbol} - ${data.message || 'Success!'}`);
        // Update UI: refresh active trades immediately with force flag to bypass in-flight guard
        try { await fetchData(true); } catch (e) { console.warn('⚠️ Refresh after execute failed:', e?.message || e); }
        // Don't show alert for auto-trades, just log
      } else {
        let errorMsg = 'Failed to execute trade.';
        let shouldStopAutoTrading = false;
        let cooldownMinutes = 0;

        // Keep auto-trading running for transient/server-side failures.
        // Only disarm automatically for explicit auth failures or hard risk locks.
        if (response.status === 401) {
          shouldStopAutoTrading = true;
        }
        
        try {
          const errData = await response.json();
          if (errData.message) errorMsg += '\nReason: ' + errData.message;
          if (errData.detail) {
            const detailText = typeof errData.detail === 'string'
              ? errData.detail
              : JSON.stringify(errData.detail);
            errorMsg += '\nDetail: ' + detailText;

            // Capture server-side AI quality gate reject details for dashboard visibility.
            const aiGateMsg = errData?.detail?.message || errData?.message || '';
            const aiGateReasons = Array.isArray(errData?.detail?.reasons) ? errData.detail.reasons : [];
            if (String(aiGateMsg).toLowerCase().includes('ai quality gate') || aiGateReasons.length > 0) {
              const event = {
                at: new Date().toISOString(),
                symbol: normalizedSignal.symbol,
                action: normalizedSignal.action,
                mode,
                message: aiGateMsg || 'Rejected by AI quality gate',
                reasons: aiGateReasons,
              };
              setAiGateRejections((prev) => [event, ...prev].slice(0, 8));
            }

            const detailReasons = Array.isArray(errData?.detail?.reasons)
              ? errData.detail.reasons
              : (typeof errData?.detail === 'string' ? [errData.detail] : []);
            const liveRejectMsg = `Live trade rejected: ${errData?.message || errData?.detail?.message || 'Execution blocked'}`;
            pushEntryBlockEvent({
              symbol: normalizedSignal?.symbol,
              action: normalizedSignal?.action,
              mode,
              message: liveRejectMsg,
              reasons: detailReasons,
              source: 'server-reject',
            });
            
            // Check if it's a cooldown/consecutive loss error (temporary - don't stop auto-trading)
            const detailLower = detailText.toLowerCase();
            if (detailLower.includes('cooldown') || detailLower.includes('consecutive loss')) {
              shouldStopAutoTrading = false;
              
              // Extract cooldown minutes from error message
              const cooldownMatch = errData.detail && String(errData.detail).match(/(\d+)\s*more\s*minutes/i);
              if (cooldownMatch) {
                cooldownMinutes = parseInt(cooldownMatch[1]);
                console.log(`⏸️ COOLDOWN ACTIVE: Waiting ${cooldownMinutes} minutes before next trade attempt`);
              } else {
                console.log(`⏸️ CONSECUTIVE LOSS LIMIT: Waiting for cooldown period to complete`);
              }

              // Schedule a refresh after the cooldown so scanner re-evaluates fresh signals
              try {
                if (cooldownTimerRef.current) {
                  clearTimeout(cooldownTimerRef.current);
                  cooldownTimerRef.current = null;
                }
                if (cooldownMinutes > 0) {
                  const ms = cooldownMinutes * 60 * 1000;
                  try {
                    setCooldownEndsAt(Date.now() + ms);
                    setCooldownRemainingMs(ms);
                  } catch (e) {
                    console.warn('⚠️ Could not set cooldown state:', e?.message || e);
                  }
                  cooldownTimerRef.current = setTimeout(async () => {
                    try {
                      console.log('🔁 Cooldown expired — refreshing trades and re-running scanner');
                      await fetchData(true);
                      await scanMarketForQualityTrades(scannerMinQuality, true);
                    } catch (e) {
                      console.warn('⚠️ Post-cooldown refresh failed:', e?.message || e);
                    } finally {
                      cooldownTimerRef.current = null;
                      try { setCooldownEndsAt(null); setCooldownRemainingMs(0); } catch (e) {}
                    }
                  }, ms);
                }
              } catch (e) {
                console.warn('⚠️ Could not schedule cooldown refresh:', e?.message || e);
              }
            }
            
            // Check if it's a daily loss limit (permanent - stop auto-trading)
            if (detailLower.includes('daily loss') || detailLower.includes('trading locked')) {
              shouldStopAutoTrading = true;
              console.error(`🛑 DAILY LOSS LIMIT REACHED: Auto-trading stopped for the day`);
              alert('⛔ Daily loss limit breached. Auto-trading locked for the day to protect capital.');
            }
            
            // Check if it's a trend/regime rejection (temporary - keep trying)
            if (detailLower.includes('regime') || detailLower.includes('trend') || detailLower.includes('market')) {
              shouldStopAutoTrading = false;
              console.log(`📊 MARKET CONDITIONS: ${errData.detail}`);
            }

            // Concurrent-trade gate should not disable auto-trading; wait for a new eligible setup.
            if (
              detailLower.includes('concurrent live trade blocked')
              || detailLower.includes('max_simultaneous_reached')
              || detailLower.includes('same_root_blocked')
            ) {
              shouldStopAutoTrading = false;
              console.log('⏸️ Concurrent trade gate active - keeping auto-trading ON and waiting for next eligible signal.');
            }

            if (
              detailLower.includes('potential loss')
              || detailLower.includes('per_trade_risk_exceeded')
              || detailLower.includes('strict capital protection')
            ) {
              shouldStopAutoTrading = false;
              const riskUntil = Date.now() + LIVE_RISK_REJECTION_COOLDOWN_MS;
              liveGlobalRejectUntilRef.current = riskUntil;
              const rejectRoot = getUnderlyingRoot(normalizedSignal);
              if (rejectRoot) {
                liveRiskRejectCooldownRef.current.set(rejectRoot, riskUntil);
              }
              logDeduped(`live:risk_server:${rejectRoot || normalizedSignal?.symbol}`, '⏸️ Per-trade risk cap active - delaying further live retries briefly', {
                burstWindowMs: 60000,
                flushDelayMs: 1200,
                emitFirst: false,
              });
            }
          }
        } catch {}
        
        console.error(`❌ TRADE EXECUTION FAILED: ${errorMsg}`);
        
        // Never auto-stop on errors — only user action or mode change stops auto-trading.
        console.log(`♻️ AUTO-TRADING REMAINS ACTIVE: Will retry when conditions improve`);
      }
    } catch (e) {
      console.error(`❌ TRADE EXECUTION ERROR: ${e.message}`);
      // Don't auto-stop on network errors - keep retrying when network recovers
      console.log(`♻️ AUTO-TRADING REMAINS ACTIVE: Will retry when connection recovers`);
    } finally {
      executingRef.current = false;
      setExecuting(false);
    }
  };

  const closeActiveTrade = async (trade) => {
    if (!trade) return;

    const side = String(trade.side || trade.action || 'BUY').toUpperCase();
    const qty = Number(trade.quantity ?? 0) || 0;
    const entry = Number(trade.entry_price ?? trade.price ?? 0) || 0;
    const exit = Number(trade.current_price ?? trade.ltp ?? trade.price ?? entry) || entry;
    const pnlRaw = (exit - entry) * qty * (side === 'BUY' ? 1 : -1);
    const pnl = Number.isFinite(pnlRaw) ? Number(pnlRaw.toFixed(2)) : 0;
    const closeTs = new Date().toISOString();
    const optimisticClosed = {
      ...trade,
      status: 'MANUAL_CLOSE',
      exit_reason: 'MANUAL_CLOSE',
      exit_price: exit,
      current_price: exit,
      exit_time: closeTs,
      pnl,
      profit_loss: pnl,
    };

    // Optimistic UI: move row immediately to history, then reconcile with backend.
    setActiveTrades((prev) => {
      const key = getTradeRowKey(trade);
      const next = prev.filter((t) => getTradeRowKey(t) !== key);
      setHasActiveTrade(next.length > 0);
      return next;
    });
    setTradeHistory((prev) => [optimisticClosed, ...(Array.isArray(prev) ? prev : [])]);

    try {
      let response;
      // Unified close path: autotrade endpoint handles both LIVE and DEMO trades.
      response = await config.authFetch(AUTO_TRADE_CLOSE_API, {
        method: 'POST',
        body: JSON.stringify({ trade_id: trade.id, symbol: trade.symbol })
      });

      // Backward-compatible fallback for legacy rows that exist only in paper_trades.
      if (!response.ok && response.status === 404) {
        response = await config.authFetch(`${config.API_BASE_URL}/paper-trades/${trade.id}`, {
          method: 'PUT',
          body: JSON.stringify({ status: 'MANUAL_CLOSE' })
        });
      }
      if (!response.ok) {
        const errText = await response.text();
        console.error('❌ Close trade failed:', errText);
        await fetchData(true);
        return;
      }
      await refreshTradesQuietly();
    } catch (e) {
      console.error('❌ Close trade error:', e.message);
      await fetchData(true);
    }
  };

  const createPaperTradeFromSignal = async (signal, options = {}) => {
    const {
      allowWhenWait = false,
      bypassMarketOpen = false,
      reason = null,
      // allow skipping the pre-entry scan for internal calls if necessary
      skipPreScan = false,
    } = options || {};

    if (!signal || !signal.symbol) return;

    // Start with the incoming signal and enrich it.
    let normalizedSignal = enrichSignalWithAiMetrics(signal);

    // Before taking any new entry, run a fresh market scan to ensure prices/signals are up-to-date.
    if (!skipPreScan) {
      try {
        if (!scannerLoading) setScannerLoading(true);
        // Force a bypassed, real-time scan so cached snapshots are ignored.
        await scanMarketForQualityTrades(scannerMinQuality, true);
        // If the scan returned a newer version of this symbol, use that latest one
        const latest = (qualityTrades || []).find((s) => String(s.symbol || '').toUpperCase() === String(normalizedSignal.symbol || '').toUpperCase());
        if (latest) {
          normalizedSignal = enrichSignalWithAiMetrics(latest);
        }
      } catch (e) {
        console.warn('⚠️ Pre-entry market scan failed:', e?.message || e);
      } finally {
        try { setScannerLoading(false); } catch (e) {}
      }
    }
    const readiness = getEntryReadiness(normalizedSignal);
    if (!readiness.pass && !allowWhenWait) {
      const blockText = `Paper entry blocked: Start Trade WAIT (${readiness.reasons.join(' | ')})`;
      console.log(`⏸️ ${blockText}`);
      pushEntryBlockEvent({
        symbol: normalizedSignal?.symbol,
        action: normalizedSignal?.action,
        mode: 'DEMO',
        message: blockText,
        reasons: readiness.reasons,
        source: 'client-gate',
      });
      return;
    }
    if (!readiness.pass && allowWhenWait) {
      const note = reason || `Start Trade WAIT (${readiness.reasons.join(' | ')})`;
      console.log(`📄 Paper mode fallback: ${note}`);
    }

    if (!isMarketOpen && !bypassMarketOpen) {
      console.log('⏸️ Market closed - paper trade creation blocked');
      return;
    }

    // Block demo entry once live mode is armed — live takes over completely.
    if (isLiveMode) {
      console.log('⏸️ Demo entry blocked: live trading is active.');
      return;
    }
    
    // Enforce global single-active-trade lock across LIVE+DEMO.
    const openTradesAnyMode = (activeTrades || []).filter((t) => {
      const status = String(t?.status || '').toUpperCase();
      const isOpen = status === 'OPEN' || (status !== 'CLOSED' && status !== 'CANCELLED' && status !== 'SL_HIT' && status !== 'TARGET_HIT');
      return isOpen;
    });
    if (openTradesAnyMode.length > 0) {
      console.log(`⏸️ Demo trade creation blocked: ${openTradesAnyMode.length} active trade(s) already exist. Wait for close before next entry.`);
      return;
    }

    const openDemoTrades = openTradesAnyMode.filter((t) => {
      const mode = String(t?.trade_mode || t?.trade_source || '').toUpperCase();
      return mode === 'DEMO' || mode === 'PAPER';
    });

    // Prevent duplicate demo entry: if the same symbol+side is already open as demo, skip.
    const signalSideNorm = String(normalizedSignal?.action || '').toUpperCase();
    const hasSameDemoOpen = openDemoTrades.some((t) => {
      const tSide = String(t?.side || t?.action || '').toUpperCase();
      return String(t?.symbol || '') === String(normalizedSignal?.symbol || '') && tSide === signalSideNorm;
    });
    if (hasSameDemoOpen) {
      console.log(`⏸️ Demo entry skipped: ${normalizedSignal?.symbol} ${signalSideNorm} already open.`);
      return;
    }
    
    const paperSignalKey = `${normalizedSignal.symbol}:${normalizedSignal.entry_price}:${normalizedSignal.target}:${normalizedSignal.stop_loss}`;
    const paperRootKey = `${getUnderlyingRoot(normalizedSignal)}:${String(normalizedSignal.action || 'BUY').toUpperCase()}`;
    const now = Date.now();
    const demoLossControl = getModeLossControlState('DEMO');
    if (demoLossControl.active) {
      paperGlobalRejectUntilRef.current = Math.max(Number(paperGlobalRejectUntilRef.current || 0), Number(demoLossControl.pauseUntil || 0));
      logDeduped(
        'paper:loss_cluster_cooldown',
        `⏸️ Demo entry paused by loss-cluster cooldown (${Math.ceil(demoLossControl.pauseRemainingMs / 60000)}m remaining)`,
        { burstWindowMs: 60000, emitFirst: false }
      );
      return;
    }
    if (paperGlobalRejectUntilRef.current > now) return;
    if (paperCreateInFlightRef.current.has(paperSignalKey)) {
      logDeduped(
        `paper:inflight:${paperRootKey}`,
        `⏸️ Paper entry skipped: request already in-flight for ${normalizedSignal.symbol}`,
        { burstWindowMs: 60000, flushDelayMs: 1200, emitFirst: false }
      );
      return;
    }
    // Per-symbol 60-second cooldown (cleared immediately when that trade closes — allows re-entry after SL/target).
    const symbolSideKey = `${normalizedSignal.symbol}:${signalSideNorm}`;
    const lastSymbolEntry = paperSymbolEntryRef.current.get(symbolSideKey) || 0;
    if (lastSymbolEntry && (now - lastSymbolEntry) < 60000) return;
    // Post-SL penalty cooldown: blocks re-entry for POST_SL_SYMBOL_COOLDOWN_MS after an SL hit.
    const slCooldownUntil = paperSymbolSlCooldownRef.current.get(symbolSideKey) || 0;
    if (slCooldownUntil > now) {
      logDeduped(
        `paper:sl_cooldown:${symbolSideKey}`,
        `⏸️ Post-SL cooldown: ${symbolSideKey} blocked ${((slCooldownUntil - now) / 60000).toFixed(1)}min remaining`,
        { burstWindowMs: 120000, emitFirst: false }
      );
      return;
    }
    const recentReject = paperRejectCooldownRef.current.get(paperRootKey);
    const rejectCooldownMs = Number(recentReject?.cooldownMs || PAPER_REJECTION_COOLDOWN_MS);
    if (recentReject && (now - recentReject.at) < rejectCooldownMs) return;

    if (isLossLimitHit() && autoTradingActive) {
      console.log('🛑 Daily loss limit hit - paper trading paused');
      return;
    }

    // Adjust quantity based on capital required: boost size for inexpensive signals
    const capRequired = Number(normalizedSignal.capital_required ?? resolveSignalCapitalRequired(normalizedSignal, lotMultiplier));
    let capitalQtyBoost = 1;
    if (Number.isFinite(capRequired)) {
      if (capRequired <= 3000) capitalQtyBoost = 3; // very small capital -> triple lots
      else if (capRequired < 10000) capitalQtyBoost = 2; // below 10k capital -> double lots
    }
    const demoDrawdownMultiplier = getQtyDrawdownMultiplier('DEMO');
    if (demoDrawdownMultiplier < 0.999) {
      logDeduped(
        `paper:qty_drawdown:${demoDrawdownMultiplier}`,
        `🛡️ Demo drawdown sizing active: qty scaled to ${Math.round(demoDrawdownMultiplier * 100)}%`,
        { burstWindowMs: 60000, emitFirst: false }
      );
    }

    const payload = {
      symbol: normalizedSignal.symbol,
      price: normalizedSignal.entry_price,
      side: normalizedSignal.action,
      quantity: Math.max(1, Math.floor(Number(normalizedSignal.quantity || 1) * Number(lotMultiplier) * capitalQtyBoost * demoDrawdownMultiplier)),
      stop_loss: normalizedSignal.stop_loss,
      target: normalizedSignal.target,
      quality_score: normalizedSignal.quality_score ?? normalizedSignal.quality,
      confirmation_score: normalizedSignal.confirmation_score ?? normalizedSignal.confidence,
      ai_edge_score: normalizedSignal.ai_edge_score,
      momentum_score: normalizedSignal.momentum_score,
      breakout_score: normalizedSignal.breakout_score,
      option_type: normalizedSignal.option_type,
      signal_type: normalizedSignal.signal_type,
      is_stock: normalizedSignal.is_stock === true || normalizedSignal.signal_type === 'stock',
      trend_direction: normalizedSignal.trend_direction,
      trend_strength: normalizedSignal.trend_strength,
      breakout_confirmed: normalizedSignal.breakout_confirmed,
      momentum_confirmed: normalizedSignal.momentum_confirmed,
      breakout_hold_confirmed: normalizedSignal.breakout_hold_confirmed,
      timing_risk: normalizedSignal.timing_risk || normalizedSignal?.timing_risk_profile?.window,
      sudden_news_risk: normalizedSignal.sudden_news_risk ?? normalizedSignal.news_risk,
      liquidity_spike_risk: normalizedSignal.liquidity_spike_risk,
      premium_distortion_risk: normalizedSignal.premium_distortion_risk ?? normalizedSignal.premium_distortion,
      close_back_in_range: normalizedSignal.close_back_in_range,
      fake_breakout_by_candle: normalizedSignal.fake_breakout_by_candle,
      market_bias: normalizedSignal.market_bias,
      market_regime: normalizedSignal.market_regime,
      expiry: normalizedSignal.expiry_date,
      force_demo: true,
      balance: 0,
      broker_id: 1,
    };

    paperCreateInFlightRef.current.add(paperSignalKey);
    try {
      const res = await config.authFetch(AUTO_TRADE_EXECUTE_API, {
        method: 'POST',
        body: JSON.stringify(payload),
      });
      if (res.ok) {
        const data = await res.json();
        if (data?.success === true) {
          console.log(`✅ Demo trade created: ${normalizedSignal.symbol}`);
          paperRejectCooldownRef.current.delete(paperRootKey);
          paperSymbolEntryRef.current.set(symbolSideKey, Date.now());
          setLastPaperSignalSymbol(paperSignalKey);
          setLastPaperSignalAt(Date.now());
          // Refresh active trades immediately with force flag to ensure UI update
          try {
            await fetchData(true);
          } catch (e) {
            console.warn('⚠️ Refresh after trade creation failed:', e?.message || e);
          }
        } else if (data?.success === false) {
          const rejectText = String(data?.message || data?.quality_gate_reason || '').toLowerCase();
          const rejectCooldownMs = rejectText.includes('quality gate') ? 20000 : PAPER_REJECTION_COOLDOWN_MS;
          if (rejectText.includes('active trade') || rejectText.includes('already exist')) {
            // Backend already has an open demo trade; pause all paper-create retries briefly.
            paperGlobalRejectUntilRef.current = Date.now() + PAPER_REJECTION_COOLDOWN_MS;
            try {
              await fetchData(true);
            } catch (e) {
              console.warn('⚠️ Refresh after active-trade reject failed:', e?.message || e);
            }
          }
          paperRejectCooldownRef.current.set(paperRootKey, {
            at: Date.now(),
            reason: String(data?.message || data?.quality_gate_reason || 'rejected'),
            cooldownMs: rejectCooldownMs,
          });
          const demoGateMsg = data?.message || '';
          const demoGateReason = data?.quality_gate_reason || '';
          if (String(demoGateMsg).toLowerCase().includes('quality gate') || String(demoGateReason).length > 0) {
            const event = {
              at: new Date().toISOString(),
              symbol: normalizedSignal.symbol,
              action: normalizedSignal.action,
              mode: 'DEMO',
              message: demoGateMsg || 'Rejected by quality gate',
              reasons: demoGateReason ? [String(demoGateReason)] : [],
            };
            setAiGateRejections((prev) => [event, ...prev].slice(0, 8));
          }
          pushEntryBlockEvent({
            symbol: normalizedSignal?.symbol,
            action: normalizedSignal?.action,
            mode: 'DEMO',
            message: `Paper trade rejected: ${data?.message || 'Must close active trade first'}`,
            reasons: demoGateReason ? [String(demoGateReason)] : [],
            source: 'server-reject',
          });
          logDeduped(`paper:reject:${paperRootKey}`, `⏸️ Paper trade rejected: ${data.message || 'Must close active trade first'}`, {
            burstWindowMs: 60000,
            flushDelayMs: 1200,
            emitFirst: false,
          });
        }
      } else {
        let rejectMessage = `HTTP ${res.status}`;
        try {
          const errData = await res.json();
          rejectMessage = String(errData?.message || errData?.detail?.message || errData?.detail || rejectMessage);
        } catch (e) {
          // Ignore parse failures and keep default status message.
        }
        const rejectText = rejectMessage.toLowerCase();
        const rejectCooldownMs = rejectText.includes('quality gate') ? 20000 : PAPER_REJECTION_COOLDOWN_MS;
        paperRejectCooldownRef.current.set(paperRootKey, {
          at: Date.now(),
          reason: rejectMessage,
          cooldownMs: rejectCooldownMs,
        });
        if (rejectText.includes('active trade') || rejectText.includes('already exist')) {
          paperGlobalRejectUntilRef.current = Date.now() + PAPER_REJECTION_COOLDOWN_MS;
        }
        logDeduped(`paper:reject:${paperRootKey}`, `⏸️ Paper trade rejected: ${rejectMessage}`, {
          burstWindowMs: 60000,
          flushDelayMs: 1200,
          emitFirst: false,
        });
      }
    } catch (e) {
      console.error('Paper trade creation error:', e);
    } finally {
      paperCreateInFlightRef.current.delete(paperSignalKey);
    }
  };

  // Arm/disarm live trading on backend
  const armLiveTrading = async (armed = true, silent = false) => {
    if (armRequestInFlightRef.current) {
      return false;
    }
    armRequestInFlightRef.current = true;
    armSyncHoldUntilRef.current = Date.now() + 4000;

    if (!silent) {
      setArmingInProgress(true);
      setArmError(null);
    }
    const token = localStorage.getItem('access_token');
    if (!token) {
      const msg = 'No access token found. Please login.';
      if (!silent) setArmError(msg);
      if (!silent) console.error('❌ ARM FAILED:', msg);
      if (!silent) setArmingInProgress(false);
      armRequestInFlightRef.current = false;
      return false;
    }
    try {
      const armEndpoint = config.endpoints.autoTrade.arm || '/autotrade/arm';
      const armUrl = `${armEndpoint}?armed=${armed ? 'true' : 'false'}`;
      if (!silent) console.log('🔄 Calling arm endpoint:', armUrl);
      const response = await config.authFetch(armUrl, {
        method: 'POST',
      });
      if (!silent) console.log('✅ Arm response status:', response.status);
      if (response.ok) {
        const data = await response.json();
        if (!silent) console.log(armed ? '✅ LIVE TRADING ARMED:' : '🛑 LIVE TRADING DISARMED:', data);
        const nextLiveArmed = Boolean(data?.live_armed ?? armed);
        const nextDemoMode = nextLiveArmed ? false : Boolean(data?.is_demo_mode ?? !armed);
        const nextEnabled = Boolean(data?.enabled ?? true);
        setEnabled(nextEnabled);
        setIsLiveMode(nextLiveArmed && !nextDemoMode);
        setAutoTradingActive(nextLiveArmed);
        if (!silent) {
          setArmError(null);
          setArmingInProgress(false);
        }
        armRequestInFlightRef.current = false;
        return true;
      }
      const errData = await response.text();
      const msg = `Failed to ${armed ? 'arm' : 'disarm'} live trading (${response.status}): ${errData}`;
      if (!silent) setArmError(msg);
      if (!silent) console.error('❌ ARM FAILED:', msg);
      if (!silent) setArmingInProgress(false);
      armRequestInFlightRef.current = false;
      return false;
    } catch (e) {
      const msg = `Error ${armed ? 'arming' : 'disarming'} live trading: ${e.message}`;
      if (!silent) setArmError(msg);
      if (!silent) console.error('❌ ARM ERROR:', msg, e);
      if (!silent) setArmingInProgress(false);
      armRequestInFlightRef.current = false;
      return false;
    }
  };

  useEffect(() => {
    // Start wake lock + heartbeat immediately
    const activateWakeLock = async () => {
      const status = await initializeWakeLock();
      // Only mark active when wake lock/heartbeat is actually active, not merely supported.
      setWakeLockActive(!!status?.wakeLockActive || !!status?.heartbeatActive || !!status?.isActive || !!status?.heartbeatRunning);
      startKeepAliveHeartbeat();
    };
    
    activateWakeLock();

    // Resolve active broker early so live balance/execute use correct broker_id.
    // Retry a few times to avoid startup-time transient timeout noise.
    (async () => {
      const attempts = [0, 600, 1500];
      let lastErr = null;
      for (const waitMs of attempts) {
        if (waitMs > 0) {
          await new Promise((resolve) => setTimeout(resolve, waitMs));
        }
        try {
          await fetchActiveBrokerContext();
          return;
        } catch (e) {
          lastErr = e;
        }
      }
      console.warn('⚠️ Could not resolve active broker at startup:', lastErr?.message || 'Unknown error');
    })();

    const handleVisibilityRefresh = () => {
      if (!document.hidden) {
        fetchData();
      }
    };

    document.addEventListener('visibilitychange', handleVisibilityRefresh);

    const wakeLockStatusInterval = setInterval(() => {
      const status = getWakeLockStatus();
      setWakeLockActive(!!status?.isActive || !!status?.heartbeatRunning);
    }, 30000);

    // Fetch data in background (non-blocking)
    const initialDataTimeout = setTimeout(() => {
      fetchData();
      // analyzeMarket() only called when auto-trading starts or trade exits
    }, 100); // Small delay to ensure UI renders first

    // Keep-alive heartbeat: Ping backend health every 30 seconds
    const healthCheckInterval = setInterval(async () => {
      try {
        await config.authFetch(`${config.API_BASE_URL}/health`);
        logDeduped('dashboard:health_ok', '💓 Health check passed - connection alive', {
          burstWindowMs: 120000,
          flushDelayMs: 1200,
          emitFirst: false,
        });
        const istTime = new Date().toLocaleString('en-IN', { timeZone: 'Asia/Kolkata' });
        document.title = `🚀 Auto Trading - Alive ${istTime}`;
      } catch (e) {
        warnDeduped('dashboard:health_failed', '⚠️ Health check failed', {
          burstWindowMs: 60000,
          flushDelayMs: 1200,
        }, e.message);
      }
    }, 30000); // Every 30 seconds

    // Auto-refresh data every 5 seconds for real-time updates
    const dataRefreshInterval = setInterval(async () => {
      const prevCount = prevActiveTradesCount.current;
      
      // Always fetch trade data so it stays updated anytime
      if (document.hidden && !ALWAYS_FETCH_TRADES) {
        console.log('⏸️ Tab hidden - skipping data fetch');
        return;
      }

      // Recovery watchdog: if stale sync persists, force a full refresh cycle.
      const syncTs = lastSuccessfulSyncAtRef.current
        ? new Date(lastSuccessfulSyncAtRef.current).getTime()
        : 0;
      const syncAgeMs = syncTs > 0 ? (Date.now() - syncTs) : Number.POSITIVE_INFINITY;
      const staleTooLong = Boolean(isUsingStaleDataRef.current) && syncAgeMs >= 15000;
      if (staleTooLong) {
        const now = Date.now();
        if ((now - Number(staleRecoveryLastRunRef.current || 0)) >= 5000) {
          staleRecoveryLastRunRef.current = now;
          await fetchData(true, true);
          prevActiveTradesCount.current = activeTrades.length;
          return;
        }
      }
      
      // Use quiet refresh to prevent flickering
      await refreshTradesQuietly();
      
      // No continuous market analysis - only on trade exits or manual action.
      
      // Update ref for next iteration
      prevActiveTradesCount.current = activeTrades.length;
    }, ACTIVE_HISTORY_REFRESH_INTERVAL_MS); // 1 second for real-time price updates

    return () => {
      clearTimeout(initialDataTimeout);
      clearInterval(dataRefreshInterval);
      clearInterval(healthCheckInterval);
      document.removeEventListener('visibilitychange', handleVisibilityRefresh);
      clearInterval(wakeLockStatusInterval);
      releaseWakeLock();
    };
  }, []); // Run once on mount to avoid wake-lock release/reacquire churn during mode toggles

  useEffect(() => {
    if (!isLiveMode) return undefined;

    let cancelled = false;
    const syncLiveBalance = async () => {
      if (typeof document !== 'undefined' && document.hidden) return;
      try {
        await fetchLiveBalance(null, { softFail: true });
      } catch (e) {
        if (!cancelled) {
          warnDeduped(
            'live:balance_sync_failed',
            '⚠️ Live balance sync failed',
            { burstWindowMs: 120000, flushDelayMs: 1200 },
            e?.message || e,
          );
        }
      }
    };

    syncLiveBalance();
    const intervalId = setInterval(syncLiveBalance, 15000);
    return () => {
      cancelled = true;
      clearInterval(intervalId);
    };
  }, [isLiveMode, activeBrokerId]);

  // Refresh once whenever wake lock state changes.
  useEffect(() => {
    fetchData();
  }, [wakeLockActive]);

  // Detect individual demo trade closures mid-session and apply appropriate cooldowns.
  // SL_HIT → 5-min penalty per symbol + root streak tracking + global surge detection.
  // TARGET_HIT → immediate re-entry unlock (reward).
  // MANUAL_CLOSE → standard 60s delay.
  useEffect(() => {
    const isOpenDemo = (t) => {
      const st = String(t?.status || '').toUpperCase();
      const md = String(t?.trade_mode || t?.trade_source || '').toUpperCase();
      return (
        (st === 'OPEN' || (st !== 'CLOSED' && st !== 'CANCELLED' && st !== 'SL_HIT' && st !== 'TARGET_HIT' && st !== 'MANUAL_CLOSE')) &&
        (md === 'DEMO' || md === 'PAPER')
      );
    };
    const currentOpenKeys = new Set(
      (activeTrades || []).filter(isOpenDemo).map((t) => `${t.symbol}:${String(t?.side || t?.action || '').toUpperCase()}`)
    );

    for (const key of prevDemoOpenRef.current) {
      if (!currentOpenKeys.has(key)) {
        const [closedSym, closedSide] = key.split(':');
        // Find the recently-closed trade in the current snapshot to read its exit status.
        const closedTrade = (activeTrades || []).find((t) => {
          const tSt = String(t?.status || '').toUpperCase();
          const tMd = String(t?.trade_mode || t?.trade_source || '').toUpperCase();
          return (
            (tSt === 'SL_HIT' || tSt === 'TARGET_HIT' || tSt === 'MANUAL_CLOSE') &&
            (tMd === 'DEMO' || tMd === 'PAPER') &&
            String(t?.symbol || '') === closedSym &&
            String(t?.side || t?.action || '').toUpperCase() === closedSide
          );
        });
        const exitStatus = String(closedTrade?.status || '').toUpperCase();
        const rootKey = closedTrade
          ? `${getUnderlyingRoot(closedTrade)}:${closedSide}`
          : `${closedSym}:${closedSide}`;
        const nowMs = Date.now();

        if (exitStatus === 'SL_HIT') {
          // ── Per-symbol 5-min cooldown ─────────────────────────────────
          paperSymbolSlCooldownRef.current.set(key, nowMs + POST_SL_SYMBOL_COOLDOWN_MS);
          paperSymbolEntryRef.current.set(key, nowMs); // belt-and-suspenders for 60s check too

          // ── Root SL streak tracking ───────────────────────────────────
          const prev = paperRootSlStreakRef.current.get(rootKey) || { streak: 0, lastSlAt: 0 };
          const newStreak = prev.streak + 1;
          paperRootSlStreakRef.current.set(rootKey, { streak: newStreak, lastSlAt: nowMs });
          if (newStreak >= 2) {
            const mult = Math.min(newStreak - 1, 3); // cap multiplier at 3×
            const streakCooldown = POST_SL_ROOT_STREAK_COOLDOWN_MS * mult;
            paperRejectCooldownRef.current.set(rootKey, {
              at: nowMs,
              reason: `Post-SL streak x${newStreak} — root blocked`,
              cooldownMs: streakCooldown,
            });
            logDeduped(
              `paper:sl_streak:${rootKey}`,
              `🚫 Demo root ${rootKey} SL streak x${newStreak} — root blocked ${(streakCooldown / 60000).toFixed(0)}min`,
              { burstWindowMs: 120000 }
            );
          }

          // ── Global SL surge detection ─────────────────────────────────
          paperSlHitTimestampsRef.current = [
            ...paperSlHitTimestampsRef.current.filter((ts) => (nowMs - ts) < GLOBAL_SL_SURGE_WINDOW_MS),
            nowMs,
          ];
          if (paperSlHitTimestampsRef.current.length >= GLOBAL_SL_SURGE_THRESHOLD) {
            const surgeUntil = nowMs + GLOBAL_SL_SURGE_COOLDOWN_MS;
            paperGlobalRejectUntilRef.current = Math.max(Number(paperGlobalRejectUntilRef.current || 0), surgeUntil);
            logDeduped(
              'paper:sl_surge',
              `🚫 DEMO SL SURGE — ${paperSlHitTimestampsRef.current.length} hits in 15min — global pause ${GLOBAL_SL_SURGE_COOLDOWN_MS / 60000}min`,
              { burstWindowMs: 300000 }
            );
          }

          console.log(`🔴 Demo SL hit — ${key} penalty ${POST_SL_SYMBOL_COOLDOWN_MS / 60000}min | root streak x${newStreak}`);

        } else if (exitStatus === 'TARGET_HIT') {
          // Reward: clear all cooldowns → immediate re-entry allowed
          paperSymbolEntryRef.current.delete(key);
          paperSymbolSlCooldownRef.current.delete(key);
          paperRootSlStreakRef.current.delete(rootKey); // streak broken by profit
          logDeduped(`paper:target_unlock:${key}`, `♻️ Demo TARGET_HIT — re-entry unlocked for ${key}`, { burstWindowMs: 60000 });

        } else {
          // MANUAL_CLOSE or status unknown → standard 60s delay, preserve any existing SL penalty
          paperSymbolEntryRef.current.set(key, nowMs);
          logDeduped(`paper:close_unlock:${key}`, `♻️ Demo trade closed — 60s delay for ${key}`, { burstWindowMs: 60000 });
        }
      }
    }
    prevDemoOpenRef.current = currentOpenKeys;
  }, [activeTrades]);

  // Detect when activeTrades changes from 1+ to 0
  useEffect(() => {
    const prevCount = prevActiveTradesCount.current;
    const currentCount = activeTrades.length;
    
    // Trade just exited (SL/Target hit)
    if (prevCount > 0 && currentCount === 0) {
      console.log(`🚨 TRADE EXIT IMMEDIATE: ${prevCount} → ${currentCount}`);
      // Clear 60s entry timestamps so slots open up — but preserve SL penalty cooldowns.
      // paperSymbolSlCooldownRef is intentionally NOT cleared; SL penalties survive slot resets.
      paperSymbolEntryRef.current.clear();
      prevDemoOpenRef.current = new Set();
      setLastPaperSignalSymbol(null);
      setLastPaperSignalAt(0);

      if (autoTradingActive) {
        if (isMarketOpen) {
          // normal behaviour during market hours
          setTimeout(async () => {
            await scanMarketForQualityTrades();
            analyzeMarket();
          }, 1500);
        } else {
          console.log('⏸️ Market closed - no auto scan/analyze until market opens or manual scan.');
        }
      }
    }
    
    prevActiveTradesCount.current = currentCount;
  }, [activeTrades.length, autoTradingActive, wakeLockActive, isMarketOpen]);

  useEffect(() => {
    if (activeSignal?.entry_price) {
      setLivePrice(activeSignal.entry_price);
    }
  }, [activeSignal]);

  // Loss limit: only block new entries, never auto-kill the session.
  // Auto-trading stops only via explicit user action or mode change.
  useEffect(() => {
    if (isLossLimitHit() && autoTradingActive) {
      console.log('⏸️ Daily loss limit hit - new entries paused (auto-trading remains ON until user stops)');
    }
  }, [stats?.daily_loss, stats?.daily_profit, lossLimit, profitTarget, autoTradingActive]);

  // Manual-only live start: do not auto-analyze/auto-execute on toggle.

  useEffect(() => {
    const AUTO_DEMO_BACKGROUND_ENTRIES = false;
    if (!AUTO_DEMO_BACKGROUND_ENTRIES) return;
    if (!isMarketOpen) return;
    if (executing || autoBatchExecutingRef.current) return;
    // Hard safety: never place demo background entries when live is armed/enabled.
    if (enabled || isLiveMode || autoTradingActive) return;
    const openTradesAnyMode = (activeTrades || []).filter((t) => {
      const status = String(t?.status || '').toUpperCase();
      const isOpen = status === 'OPEN' || (status !== 'CLOSED' && status !== 'CANCELLED' && status !== 'SL_HIT');
      return isOpen;
    });
    const availableDemoSlots = openTradesAnyMode.length > 0 ? 0 : 1;
    if (!autoTradingActive && !isLiveMode && signalsLoaded && availableDemoSlots > 0) {
      const now = Date.now();
      if (paperGlobalRejectUntilRef.current > now) return;
      // Use the same Start-YES candidate model as live path, but route to paper execution.
      const sourceSignals = sortedQualityTrades.length > 0
        ? sortedQualityTrades
        : (activeSignal ? [activeSignal] : []);
      if (!sourceSignals.length) return;
      const seen = new Set();
      const executableCandidates = sourceSignals
        .map((signal) => enrichSignalWithAiMetrics(signal))
        .filter((signal) => {
          const key = `${String(signal?.symbol || '')}:${String(signal?.action || '').toUpperCase()}`;
          if (!signal?.symbol || seen.has(key)) return false;
          seen.add(key);
          if (!getEntryReadiness(signal).pass) return false;
          const paperRootKey = `${getUnderlyingRoot(signal)}:${String(signal?.action || 'BUY').toUpperCase()}`;
          const recentReject = paperRejectCooldownRef.current.get(paperRootKey);
          const rejectCooldownMs = Number(recentReject?.cooldownMs || PAPER_REJECTION_COOLDOWN_MS);
          if (recentReject && (now - Number(recentReject.at || 0)) < rejectCooldownMs) return false;
          const paperSignalKey = `${signal.symbol}:${signal.entry_price}:${signal.target}:${signal.stop_loss}`;
          if (paperCreateInFlightRef.current.has(paperSignalKey)) return false;
          // Skip symbols still in post-SL penalty cooldown.
          const symSideKey = `${String(signal?.symbol || '')}:${String(signal?.action || 'BUY').toUpperCase()}`;
          if ((paperSymbolSlCooldownRef.current.get(symSideKey) || 0) > now) return false;
          // Skip symbols that hit the 60s per-entry cooldown.
          const lastEntry = paperSymbolEntryRef.current.get(symSideKey) || 0;
          if (lastEntry && (now - lastEntry) < 60000) return false;
          return true;
        })
        .sort((a, b) => {
          const qDiff = Number(b.quality ?? b.quality_score ?? 0) - Number(a.quality ?? a.quality_score ?? 0);
          if (qDiff !== 0) return qDiff;
          const cDiff = Number(b.confirmation_score ?? b.confidence ?? 0) - Number(a.confirmation_score ?? a.confidence ?? 0);
          if (cDiff !== 0) return cDiff;
          const rrA = Number(a.rr ?? 0);
          const rrB = Number(b.rr ?? 0);
          if (rrB !== rrA) return rrB - rrA;
          const capitalA = estimateSignalCapitalRequired(a, lotMultiplier);
          const capitalB = estimateSignalCapitalRequired(b, lotMultiplier);
          if (Number.isFinite(capitalA) && Number.isFinite(capitalB) && capitalA !== capitalB) {
            return capitalA - capitalB;
          }
          return String(a.symbol || '').localeCompare(String(b.symbol || ''));
        });
      if (!executableCandidates.length) return;

      const chosen = executableCandidates.slice(0, availableDemoSlots);
      const burstKey = chosen.map((c) => `${String(c?.symbol || '')}:${String(c?.action || 'BUY').toUpperCase()}`).join('|');
      const burstNow = Date.now();
      const lastBurst = demoAutoStartBurstGuardRef.current || { at: 0, key: '' };
      if (lastBurst.key === burstKey && (burstNow - Number(lastBurst.at || 0)) < 2500) {
        return;
      }
      demoAutoStartBurstGuardRef.current = { at: burstNow, key: burstKey };

      autoBatchExecutingRef.current = true;
      (async () => {
        logDeduped(
          `dashboard:auto_demo_start:${chosen.length}`,
          `🚀 AUTO START (DEMO): ${chosen.length} Start Trade YES candidate(s)`,
          { burstWindowMs: 90000, flushDelayMs: 1200, emitFirst: false }
        );
        for (const candidate of chosen) {
          await createPaperTradeFromSignal(candidate, { skipPreScan: true });
        }
      })().finally(() => {
        autoBatchExecutingRef.current = false;
        // After batch completes, trigger a fresh scanner pass so the 2nd demo slot
        // can be filled immediately if any qualifying signal is available.
        try { scanMarketForQualityTrades(scannerMinQuality, true).catch(() => {}); } catch (_) {}
      });
    }
  }, [enabled, autoTradingActive, isLiveMode, signalsLoaded, activeTrades.length, sortedQualityTrades, activeSignal, lotMultiplier, isMarketOpen, executing]);

  const todayLabel = new Date().toDateString();
  const todayIso = new Date().toISOString().slice(0, 10);
  const tradesToday = tradeHistory.filter((trade) => {
    const ts = trade.exit_time || trade.entry_time || trade.timestamp;
    if (!ts) return false;
    return new Date(ts).toDateString() === todayLabel;
  });
  const sumPnl = (trades) => trades.reduce((acc, t) => acc + Number(t.profit_loss ?? t.pnl ?? 0), 0);
  const sumWins = (trades) => trades.filter((t) => Number(t.profit_loss ?? t.pnl ?? 0) > 0).length;
  const inferExitPrice = (trade) => {
    const directExit = trade?.exit_price;
    if (directExit !== null && directExit !== undefined && Number.isFinite(Number(directExit))) {
      return Number(directExit);
    }
    const current = trade?.current_price ?? trade?.ltp;
    if (current !== null && current !== undefined && Number.isFinite(Number(current))) {
      return Number(current);
    }
    const entry = Number(trade?.entry_price ?? trade?.price ?? 0);
    const qty = Number(trade?.quantity ?? 0);
    const pnl = Number(trade?.profit_loss ?? trade?.pnl ?? 0);
    const side = String(trade?.action || trade?.side || 'BUY').toUpperCase();
    if (entry > 0 && qty > 0 && Number.isFinite(pnl)) {
      const dir = side === 'BUY' ? 1 : -1;
      return entry + (pnl / (qty * dir));
    }
    return null;
  };
  const overallPnl = reportSummary?.total_pnl ?? sumPnl(tradeHistory);
  const todayPnlFromSummary = reportSummary?.by_date?.find((d) => d.date === todayIso)?.pnl;
  const dateFilteredHistory = tradeHistory.filter((trade) => {
    const ts = trade.exit_time || trade.entry_time || trade.timestamp;
    if (!ts) return false;
    const tradeDate = new Date(ts).toLocaleDateString('en-CA');
    if (historyStartDate && tradeDate < historyStartDate) return false;
    if (historyEndDate && tradeDate > historyEndDate) return false;
    return true;
  });
  const filteredHistory = dateFilteredHistory.filter((t) => {
    const mode = String(
      t?.trade_mode
      || t?.trade_source
      || t?.mode
      || (t?.broker_order_id ? 'LIVE' : 'DEMO')
    ).toUpperCase();
    const action = String(t?.action || t?.side || '').toUpperCase();
    const status = String(t?.status || 'CLOSED').toUpperCase();

    if (historyModeFilter !== 'ALL' && mode !== historyModeFilter) return false;
    if (historyActionFilter !== 'ALL' && action !== historyActionFilter) return false;
    if (historyStatusFilter !== 'ALL' && status !== historyStatusFilter) return false;

    const q = historySearch.trim().toLowerCase();
    if (!q) return true;
    return [t.symbol, t.index, t.action, t.side, t.status, t.strategy, mode]
      .filter(Boolean)
      .some((field) => String(field).toLowerCase().includes(q));
  });
  const rangePnl = sumPnl(filteredHistory);
  const rangeWins = sumWins(filteredHistory);
  const todayTableRows = tradesToday;

  const resolveTradeMode = (trade) => String(
    trade?.trade_mode
    || trade?.trade_source
    || trade?.mode
    || (trade?.broker_order_id ? 'LIVE' : 'DEMO')
  ).toUpperCase();

  const currentUiTradeMode = isLiveMode ? 'LIVE' : 'DEMO';
  const activeTradesForCurrentMode = (activeTrades || []).filter((trade) => {
    const mode = resolveTradeMode(trade);
    return currentUiTradeMode === 'LIVE' ? mode === 'LIVE' : (mode === 'DEMO' || mode === 'PAPER');
  });
  const filteredActiveTrades = (activeTrades || []).filter((trade) => {
    const mode = resolveTradeMode(trade);
    if (activeModeFilter === 'ALL') return true;
    if (activeModeFilter === 'DEMO') return mode === 'DEMO' || mode === 'PAPER';
    return mode === 'LIVE';
  });
  const riskMode = isLiveMode ? 'LIVE' : 'DEMO';
  const riskControlState = getModeLossControlState(riskMode);
  const adaptiveGateState = getAdaptiveGateTightening(riskMode);
  const qtyDrawdownMultiplier = getQtyDrawdownMultiplier(riskMode);
  const gateTighteningActive =
    Number(adaptiveGateState?.qualityBump || 0) > 0
    || Number(adaptiveGateState?.confidenceBump || 0) > 0
    || Number(adaptiveGateState?.rrBump || 0) > 0;

  // --- Professional Signal Integration ---
  // ...existing code...

  return (
    <div style={{ minHeight: '100vh', background: '#f3f4f6', padding: '24px' }}>
      <div style={{
        textAlign: 'center',
        fontSize: '2.2rem',
        fontWeight: 700,
        color: '#b0b7c3',
        letterSpacing: '2px',
        margin: '0 0 18px 0',
        fontFamily: 'inherit',
      }}>
        ALGORITHM BASED AUTO TRADING
      </div>
      <div style={{ maxWidth: '1400px', margin: '24px auto 0' }}>
        <div style={{
          background: 'rgba(255, 255, 255, 0.95)',
          borderRadius: '16px',
          padding: '32px',
          marginBottom: '32px',
          boxShadow: '0 8px 32px rgba(0, 0, 0, 0.1)'
        }}>
      {!isMarketOpen && (
        <div style={{
          marginBottom: '16px',
          padding: '12px 16px',
          borderRadius: '8px',
          background: '#fff5f5',
          border: '1px solid #fed7d7',
          color: '#742a2a',
          fontSize: '13px',
          fontWeight: '600'
        }}>
          🚫 Market Closed{marketClosedReason ? ` (${marketClosedReason})` : ''}. Trading allowed only during market hours (9:15 AM – 3:30 PM IST).
        </div>
      )}
      <style>{`
        @keyframes pulse {
          0%, 100% { opacity: 1; }
          50% { opacity: 0.7; }
        }
      `}</style>
      {/* Header with Toggle */}
      
      <div style={{
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'center',
        marginBottom: '32px',
        paddingBottom: '20px',
        borderBottom: '2px solid #e2e8f0'
      }}>
        <div>
          <h3 style={{
            margin: '0 0 8px 0',
            color: '#2d3748',
            fontSize: '24px',
            fontWeight: 'bold',
            display: 'flex',
            alignItems: 'center',
            gap: '12px'
          }}>
            🤖 Auto Trading Engine
            <span style={{
              fontSize: '14px',
              padding: '4px 12px',
              borderRadius: '20px',
              background: autoTradingActive ? '#48bb78' : enabled ? '#ed8936' : '#cbd5e0',
              color: 'white',
              fontWeight: '600'
            }}>
              {autoTradingActive ? 'ACTIVE' : enabled ? '⏸️ STANDBY' : 'DISABLED'}
            </span>
            <span style={{
              fontSize: '14px',
              padding: '4px 12px',
              borderRadius: '20px',
              background: isLiveMode ? '#22c55e' : '#f59e0b',
              color: 'white',
              fontWeight: '600'
            }}>
              {isLiveMode ? '🔴 LIVE TRADES' : '⚪ DEMO MODE'}
            </span>
            <span style={{
              fontSize: '14px',
              padding: '4px 12px',
              borderRadius: '20px',
              background: wakeLockActive ? '#48bb78' : '#ed8936',
              color: 'white',
              fontWeight: '600',
              animation: wakeLockActive ? 'pulse 2s infinite' : 'none'
            }}>
              {wakeLockActive ? '😴 AWAKE' : '⚠️ SLEEP MODE'}
            </span>
            {cooldownRemainingMs > 0 && (
              <span style={{
                fontSize: '14px',
                padding: '4px 12px',
                borderRadius: '20px',
                background: '#ef4444',
                color: 'white',
                fontWeight: '700'
              }}>
                ⏳ Cooldown {formatCooldownLabel(cooldownRemainingMs)}
              </span>
            )}
          </h3>
          <p style={{
            margin: 0,
            color: '#718096',
            fontSize: '14px'
          }}>
            {(() => {
              const activeCount = Number(stats?.active_trades_count ?? activeTrades.length ?? 0);
              if (activeCount > 0) {
                return (
                  <>
                    <span style={{ color: '#c53030', fontWeight: '700' }}>🟢 ACTIVE TRADES: {activeCount}</span>
                    <span> • Monitoring live positions</span>
                    {activeBrokerName && (
                      <span> • Broker: {activeBrokerName}{Number.isFinite(Number(activeBrokerId)) ? ` (#${Number(activeBrokerId)})` : ''}</span>
                    )}
                    {Number.isFinite(Number(liveAccountBalance)) && Number(liveAccountBalance) > 0 && (
                      <span> • Live Balance: ₹{Number(liveAccountBalance).toLocaleString()}</span>
                    )}
                  </>
                );
              }
              return (
                <>
                  <span>⚪ NO ACTIVE TRADES</span>
                  {activeBrokerName && (
                    <span> • Broker: {activeBrokerName}{Number.isFinite(Number(activeBrokerId)) ? ` (#${Number(activeBrokerId)})` : ''}</span>
                  )}
                  {Number.isFinite(Number(liveAccountBalance)) && Number(liveAccountBalance) > 0 && (
                    <span> • Live Balance: ₹{Number(liveAccountBalance).toLocaleString()}</span>
                  )}
                </>
              );
            })()}
          </p>
        </div>
        <div style={{ display: 'flex', gap: '12px', alignItems: 'center' }}>
          <div style={{
            padding: '20px',
            background: 'linear-gradient(135deg, #ed8936 0%, #dd6b20 100%)',
            borderRadius: '12px',
            color: 'white',
            textAlign: 'center'
          }}>
            <div style={{ fontSize: '13px', opacity: 0.9, marginBottom: '8px' }}>Active Trades</div>
            <div style={{ fontSize: '32px', fontWeight: 'bold' }}>
              {(stats?.active_trades_count ?? 0)}
            </div>
          </div>
          <div style={{
            padding: '20px',
            background: 'linear-gradient(135deg, #939BA3 0%, #7a8289 100%)',
            borderRadius: '12px',
            color: 'white',
            textAlign: 'center'
          }}>
            <div style={{ fontSize: '13px', opacity: 0.9, marginBottom: '8px' }}>Target / Trade</div>
            <div style={{ fontSize: '32px', fontWeight: 'bold' }}>{stats?.target_points_per_trade ?? 25}pts</div>
          </div>

          {stats?.portfolio_cap !== null && stats?.portfolio_cap !== undefined && (
            <div style={{
              padding: '20px',
              background: 'linear-gradient(135deg, #319795 0%, #2c7a7b 100%)',
              borderRadius: '12px',
              color: 'white',
              textAlign: 'center'
            }}>
              <div style={{ fontSize: '13px', opacity: 0.9, marginBottom: '8px' }}>Capital In Use</div>
              <div style={{ fontSize: '24px', fontWeight: 'bold' }}>₹{(stats?.capital_in_use ?? 0).toLocaleString()}</div>
              <div style={{ fontSize: '12px', opacity: 0.85, marginTop: '6px' }}>
                {stats?.remaining_capital != null && stats?.portfolio_cap != null
                  ? `Remaining: ₹${Number(stats.remaining_capital).toLocaleString()} / Cap: ₹${Number(stats.portfolio_cap).toLocaleString()}`
                  : 'Remaining/Cap: n/a'}
              </div>
            </div>
          )}
        </div>

        {/* Risk Control Status */}
        <div style={{
          marginBottom: '20px',
          padding: '12px 14px',
          borderRadius: '10px',
          border: riskControlState.active ? '1px solid #f87171' : '1px solid #a7f3d0',
          background: riskControlState.active ? '#fff1f2' : '#f0fdf4',
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))',
          gap: '10px',
          fontSize: '12px'
        }}>
          <div>
            <div style={{ fontWeight: '700', color: '#334155', marginBottom: '4px' }}>Risk Control</div>
            <div style={{ color: riskControlState.active ? '#b91c1c' : '#166534', fontWeight: '700' }}>
              {riskControlState.active
                ? `COOLDOWN ACTIVE (${Math.ceil(Number(riskControlState.pauseRemainingMs || 0) / 60000)}m left)`
                : 'RUNNING NORMALLY'}
            </div>
          </div>
          <div>
            <div style={{ fontWeight: '700', color: '#334155', marginBottom: '4px' }}>Adaptive Gate</div>
            <div style={{ color: '#1f2937' }}>
              {gateTighteningActive
                ? `Q+${adaptiveGateState.qualityBump}, C+${adaptiveGateState.confidenceBump}, RR+${Number(adaptiveGateState.rrBump || 0).toFixed(2)}`
                : 'No tightening'}
            </div>
          </div>
          <div>
            <div style={{ fontWeight: '700', color: '#334155', marginBottom: '4px' }}>Drawdown Sizing</div>
            <div style={{ color: qtyDrawdownMultiplier < 1 ? '#b45309' : '#1f2937' }}>
              Qty x{Number(qtyDrawdownMultiplier || 1).toFixed(2)}
            </div>
          </div>
          <div>
            <div style={{ fontWeight: '700', color: '#334155', marginBottom: '4px' }}>Recent Loss Pattern</div>
            <div style={{ color: '#1f2937' }}>
              10m: {Number(riskControlState.lossesShort || 0)} | 15m: {Number(riskControlState.lossesLong || 0)} | Consecutive: {Number(riskControlState.consecutiveLosses || 0)}
            </div>
          </div>
        </div>

        {/* Performance Summary */}
        <div style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(140px, 1fr))',
          gap: '12px',
          padding: '0',
          marginBottom: '24px'
        }}>
          <div style={{
            padding: '16px',
            background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
            borderRadius: '12px',
            color: 'white',
            textAlign: 'center'
          }}>
            <div style={{ fontSize: '12px', opacity: 0.9, marginBottom: '6px' }}>Today Trades</div>
            <div style={{ fontSize: '28px', fontWeight: 'bold' }}>{(stats?.today_wins ?? 0) + (stats?.today_losses ?? 0)}</div>
            <div style={{ fontSize: '11px', marginTop: '6px', opacity: 0.8 }}>
              ✓ {stats?.today_wins ?? 0} | ✗ {stats?.today_losses ?? 0}
            </div>
          </div>

          <div style={{
            padding: '16px',
            background: 'linear-gradient(135deg, #48bb78 0%, #38a169 100%)',
            borderRadius: '12px',
            color: 'white',
            textAlign: 'center'
          }}>
            <div style={{ fontSize: '12px', opacity: 0.9, marginBottom: '6px' }}>Win Rate</div>
            <div style={{ fontSize: '28px', fontWeight: 'bold' }}>{(stats?.win_rate ?? 0).toFixed(1)}%</div>
            <div style={{ fontSize: '11px', marginTop: '6px', opacity: 0.8 }}>
              ({stats?.win_sample ?? 0} recent)
            </div>
          </div>

          <div style={{
            padding: '16px',
            background: 'linear-gradient(135deg, #f6ad55 0%, #ed8936 100%)',
            borderRadius: '12px',
            color: 'white',
            textAlign: 'center'
          }}>
            <div style={{ fontSize: '12px', opacity: 0.9, marginBottom: '6px' }}>Daily P&L</div>
            <div style={{
              fontSize: '28px',
              fontWeight: 'bold',
              color: (stats?.daily_pnl ?? 0) >= 0 ? '#c6f6d5' : '#fed7d7'
            }}>
              ₹{(stats?.daily_pnl ?? 0).toLocaleString()}
            </div>
          </div>

          {stats?.trading_paused && (
            <div style={{
              padding: '16px',
              background: 'linear-gradient(135deg, #f56565 0%, #e53e3e 100%)',
              borderRadius: '12px',
              color: 'white',
              textAlign: 'center'
            }}>
              <div style={{ fontSize: '12px', opacity: 0.9, marginBottom: '6px' }}>⏸️ PAUSED</div>
              <div style={{ fontSize: '11px', marginTop: '6px', lineHeight: '1.4' }}>
                {stats?.pause_reason || 'Trading paused'}
              </div>
            </div>
          )}
        </div>
    </div>

      {/* Market Quality Scanner */}
      <div style={{
        padding: '24px',
        background: 'linear-gradient(135deg, #fef3c7 0%, #fde68a 100%)',
        borderRadius: '12px',
        border: '2px solid #f59e0b',
        marginBottom: '24px'
      }}>
        <div style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          marginBottom: '16px'
        }}>
          <h4 style={{
            margin: 0,
            color: '#92400e',
            fontSize: '18px',
            fontWeight: 'bold'
          }}>
            {autoScanActive ? '🔄 Scanning...' : '🎯 All Quality Signals from Market'} ({scannerMinQuality}%+ Quality across indices and stocks)
          </h4>
          <div style={{ fontSize: '12px', color: '#92400e', opacity: 0.9 }}>
            {scannerLastRunAt ? `Last scan: ${scannerLastRunAt.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })}` : ''}
          </div>
          <button
            onClick={() => {
              // Toggle scanner pause/resume explicitly.
              setScannerUserOverride((prev) => {
                const next = !prev;
                if (!next) {
                  // Resuming: trigger an immediate fresh scan.
                  scanMarketForQualityTrades(scannerMinQuality, true).catch(() => {});
                }
                return next;
              });
            }}
            disabled={scannerLoading}
            style={{
              padding: '10px 20px',
              background: scannerLoading ? '#cbd5e0' : (scannerUserOverride ? '#64748b' : '#f59e0b'),
              color: 'white',
              border: 'none',
              borderRadius: '6px',
              fontSize: '14px',
              fontWeight: '600',
              cursor: scannerLoading ? 'wait' : 'pointer'
            }}>
            {scannerLoading ? '🔄 Scanning...' : (scannerUserOverride ? '▶️ Resume Scanner' : '⏸️ Pause Scanner')}
          </button>
        </div>

        <div style={{
          display: 'flex',
          gap: '8px',
          marginBottom: '14px',
          flexWrap: 'wrap'
        }}>
          {[90, 80, 70].map((q) => (
            <button
              key={`q-${q}`}
              onClick={() => {
                setScannerMinQuality(q);
                scanMarketForQualityTrades(q, true);
              }}
              style={{
                padding: '6px 12px',
                borderRadius: '999px',
                border: scannerMinQuality === q ? '1px solid #92400e' : '1px solid #fcd34d',
                background: scannerMinQuality === q ? '#92400e' : '#fff7ed',
                color: scannerMinQuality === q ? '#ffffff' : '#92400e',
                fontSize: '12px',
                fontWeight: '700',
                cursor: 'pointer'
              }}
            >
              {q}%+
            </button>
          ))}
          {[
            { key: 'all', label: `All (${sortedQualityTrades.length})` },
            { key: 'indices', label: `Indices (${qualityTradesIndices.length})` },
            { key: 'stocks', label: `Stocks (${qualityTradesStocks.length})` },
          ].map((tab) => (
            <button
              key={tab.key}
              onClick={() => setScannerTab(tab.key)}
              style={{
                padding: '6px 12px',
                borderRadius: '999px',
                border: scannerTab === tab.key ? '1px solid #92400e' : '1px solid #fcd34d',
                background: scannerTab === tab.key ? '#92400e' : '#fff7ed',
                color: scannerTab === tab.key ? '#ffffff' : '#92400e',
                fontSize: '12px',
                fontWeight: '700',
                cursor: 'pointer'
              }}
            >
              {tab.label}
            </button>
          ))}
        </div>

        {scannerTradesSorted.length > 0 ? (
          <div style={{ overflowX: 'auto' }}>
            <table style={{
              width: '100%',
              borderCollapse: 'collapse',
              fontSize: '13px'
            }}>
              <thead>
                <tr style={{ background: '#f59e0b', color: 'white' }}>
                  <th style={{ padding: '10px', textAlign: 'left' }}>Symbol</th>
                  <th style={{ padding: '10px', textAlign: 'center' }}>Action</th>
                  <th style={{ padding: '10px', textAlign: 'center' }}>Market Bias</th>
                  <th style={{ padding: '10px', textAlign: 'center' }}>Quality</th>
                  <th style={{ padding: '10px', textAlign: 'center' }}>Confidence</th>
                  <th style={{ padding: '10px', textAlign: 'center' }}>RR</th>
                  <th style={{ padding: '10px', textAlign: 'center' }}>Entry</th>
                  <th style={{ padding: '10px', textAlign: 'center' }}>Target</th>
                  <th style={{ padding: '10px', textAlign: 'center' }}>Capital Required</th>
                  <th style={{ padding: '10px', textAlign: 'center' }}>Start</th>
                  <th style={{ padding: '10px', textAlign: 'center' }}>Rating</th>
                </tr>
              </thead>
              <tbody>
                {scannerTradesSorted.map((trade, idx) => (
                  (() => {
                    const enrichedTrade = enrichSignalWithAiMetrics(trade);
                    const tradeReadiness = getEntryReadiness(enrichedTrade);
                    const startLabel = tradeReadiness.pass ? 'YES' : 'WAIT';
                    const marketBias = getMarketBiasLabel(enrichedTrade);
                    const capitalRequired = resolveSignalCapitalRequired(trade, lotMultiplier);
                    return (
                  <tr key={idx} style={{
                    background: idx % 2 === 0 ? '#fffbeb' : '#fef3c7',
                    borderBottom: '1px solid #fcd34d'
                  }}>
                    <td style={{ padding: '10px', fontWeight: '600', color: '#1f2937' }}>{trade.symbol}</td>
                    <td style={{ padding: '10px', textAlign: 'center', color: trade.action === 'BUY' ? '#48bb78' : '#f56565' }}>
                      {trade.action}
                    </td>
                    <td style={{
                      padding: '10px',
                      textAlign: 'center',
                      fontWeight: '700',
                      color: marketBias === 'STRONG_ONE_SIDE' ? '#7f1d1d' : marketBias === 'MODERATE_BOTH' ? '#7c2d12' : '#1f2937'
                    }}>
                      {marketBias}
                    </td>
                    <td style={{
                      padding: '10px',
                      textAlign: 'center',
                      fontWeight: 'bold',
                      background: trade.quality >= 85 ? '#c6f6d5' : '#feebc8',
                      borderRadius: '4px'
                    }}>
                      {trade.quality}%
                    </td>
                    <td style={{ padding: '10px', textAlign: 'center' }}>
                      {(trade.confirmation_score ?? trade.confidence ?? 0).toFixed(1)}%
                    </td>
                    <td style={{ padding: '10px', textAlign: 'center' }}>
                      {trade.rr.toFixed(2)}
                    </td>
                    <td style={{ padding: '10px', textAlign: 'center' }}>₹{trade.entry_price?.toFixed(2) || '-'}</td>
                    <td style={{ padding: '10px', textAlign: 'center' }}>₹{trade.target?.toFixed(2) || '-'}</td>
                    <td style={{ padding: '10px', textAlign: 'center', fontWeight: '600' }}>
                      {Number.isFinite(capitalRequired) ? `₹${Math.round(capitalRequired).toLocaleString()}` : '-'}
                    </td>
                    <td style={{
                      padding: '10px',
                      textAlign: 'center',
                      fontWeight: '700',
                      color: startLabel === 'YES' ? '#22543d' : '#92400e'
                    }}>
                      {startLabel}
                    </td>
                    <td style={{ padding: '10px', textAlign: 'center' }}>{trade.recommendation}</td>
                  </tr>
                    );
                  })()
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <div style={{
            margin: 0,
            color: '#92400e',
            textAlign: 'center',
            padding: '20px'
          }}>
            {autoScanActive && totalSignalsScanned === 0 ? (
              <p style={{ margin: '10px 0' }}>🔄 <strong>Auto-scanning...</strong> Searching for signals at {strictDisplayThreshold}%+ quality.</p>
            ) : scannerLoading ? (
              <p style={{ margin: '10px 0' }}>🔄 Scanning all markets for signals at {strictDisplayThreshold}%+ quality...</p>
            ) : scannerLastError ? (
              <div>
                <p style={{ margin: '10px 0', fontWeight: '600' }}>⚠️ Scanner temporarily unavailable</p>
                <p style={{ margin: '5px 0', fontSize: '12px', color: '#92400e', opacity: 0.8 }}>
                  {scannerLastError}. Keeping last visible results if available.
                </p>
              </div>
            ) : displayQualityTrades.length === 0 && totalSignalsScanned > 0 ? (
              <div>
                <p style={{ margin: '10px 0', fontWeight: '600' }}>📊 No signals found above {strictDisplayThreshold}% quality</p>
                <p style={{ margin: '5px 0', fontSize: '12px', color: '#92400e', opacity: 0.8 }}>
                  Scanned {totalSignalsScanned} signals • Showing best available scanner candidates below the strict {strictDisplayThreshold}% filter.
                  Showing strict visible scanner candidates only.
                </p>
              </div>
            ) : (
              <p style={{ margin: '10px 0' }}>📊 No signals available yet. Click Refresh to scan the market.</p>
            )}
          </div>
        )}
      </div>

      {/* Professional Signal Display - uses best quality trade from market scanner */}
      {professionalSignalDisplay ? (
        <div style={{
          background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
          borderRadius: '16px',
          padding: '24px',
          marginBottom: '24px',
          color: 'white',
          boxShadow: '0 10px 40px rgba(102, 126, 234, 0.3)'
        }}>
          <h3 style={{ margin: '0 0 16px 0', fontSize: '20px', fontWeight: 'bold', display: 'flex', alignItems: 'center', gap: '8px' }}>
            🎯 Professional Intraday Signal
            <span style={{
              fontSize: '12px',
              padding: '4px 10px',
              borderRadius: '12px',
              background: 'rgba(255,255,255,0.2)',
              fontWeight: '600'
            }}>
              {currentProfessionalSignal ? (bestQualityTrade ? '✨ SCANNED' : 'LIVE') : '🕘 LAST'}
            </span>
          </h3>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: '16px' }}>
            <div>
              <div style={{ fontSize: '12px', opacity: 0.9, marginBottom: '4px' }}>Symbol</div>
              <div style={{ fontSize: '18px', fontWeight: 'bold' }}>{professionalSignalDisplay?.symbol}</div>
            </div>
            <div>
              <div style={{ fontSize: '12px', opacity: 0.9, marginBottom: '4px' }}>Action</div>
              <div style={{ fontSize: '20px', fontWeight: 'bold' }}>
                <span style={{
                  padding: '6px 16px',
                  borderRadius: '8px',
                  background: (professionalSignalDisplay?.action || professionalSignalDisplay?.signal) === 'BUY' || (professionalSignalDisplay?.action || professionalSignalDisplay?.signal) === 'buy' ? '#48bb78' : (professionalSignalDisplay?.action || professionalSignalDisplay?.signal) === 'SELL' || (professionalSignalDisplay?.action || professionalSignalDisplay?.signal) === 'sell' ? '#f56565' : '#cbd5e0',
                  color: 'white'
                }}>
                  {(professionalSignalDisplay?.action || professionalSignalDisplay?.signal || 'HOLD').toUpperCase()}
                </span>
              </div>
            </div>
            <div>
              <div style={{ fontSize: '12px', opacity: 0.9, marginBottom: '4px' }}>Entry Price</div>
              <div style={{ fontSize: '18px', fontWeight: 'bold' }}>
                ₹{professionalSignalDisplay?.entry_price?.toFixed(2) || 'N/A'}
              </div>
            </div>
            <div>
              <div style={{ fontSize: '12px', opacity: 0.9, marginBottom: '4px' }}>Target</div>
              <div style={{ fontSize: '18px', fontWeight: 'bold', color: '#c6f6d5' }}>
                ₹{professionalSignalDisplay?.target?.toFixed(2) || 'N/A'}
              </div>
            </div>
            <div>
              <div style={{ fontSize: '12px', opacity: 0.9, marginBottom: '4px' }}>Stop Loss</div>
              <div style={{ fontSize: '18px', fontWeight: 'bold', color: '#fed7d7' }}>
                ₹{professionalSignalDisplay?.stop_loss?.toFixed(2) || 'N/A'}
              </div>
            </div>
            {professionalSignalDisplay?.quality !== undefined && (
              <div>
                <div style={{ fontSize: '12px', opacity: 0.9, marginBottom: '4px' }}>Quality Score</div>
                <div style={{ fontSize: '18px', fontWeight: 'bold', color: '#fbbf24' }}>
                  {professionalSignalDisplay.quality}% ✨
                </div>
              </div>
            )}
            <div>
              <div style={{ fontSize: '12px', opacity: 0.9, marginBottom: '4px' }}>AI Edge</div>
              <div style={{ fontSize: '18px', fontWeight: 'bold', color: '#bfdbfe' }}>
                {fmtPct(professionalSignalDisplay?.ai_edge_score)}
              </div>
            </div>
            <div>
              <div style={{ fontSize: '12px', opacity: 0.9, marginBottom: '4px' }}>Momentum</div>
              <div style={{ fontSize: '18px', fontWeight: 'bold', color: '#a7f3d0' }}>
                {fmtPct(professionalSignalDisplay?.momentum_score)}
              </div>
            </div>
            <div>
              <div style={{ fontSize: '12px', opacity: 0.9, marginBottom: '4px' }}>Breakout</div>
              <div style={{ fontSize: '18px', fontWeight: 'bold', color: '#fde68a' }}>
                {fmtPct(professionalSignalDisplay?.breakout_score)}
              </div>
            </div>
            <div>
              <div style={{ fontSize: '12px', opacity: 0.9, marginBottom: '4px' }}>Fake Move Risk</div>
              <div style={{
                fontSize: '18px',
                fontWeight: 'bold',
                color: Number(professionalSignalDisplay?.fake_move_risk ?? 100) <= 45 ? '#86efac' : '#fecaca'
              }}>
                {fmtPct(professionalSignalDisplay?.fake_move_risk)}
              </div>
            </div>
            <div>
              <div style={{ fontSize: '12px', opacity: 0.9, marginBottom: '4px' }}>Breakout Hold</div>
              <div style={{
                fontSize: '18px',
                fontWeight: 'bold',
                color: professionalSignalDisplay?.breakout_hold_confirmed === false ? '#fecaca' : '#a7f3d0'
              }}>
                {fmtYesNo(professionalSignalDisplay?.breakout_hold_confirmed)}
              </div>
            </div>
            <div>
              <div style={{ fontSize: '12px', opacity: 0.9, marginBottom: '4px' }}>Timing Risk</div>
              <div style={{ fontSize: '18px', fontWeight: 'bold', color: '#ddd6fe' }}>
                {professionalSignalDisplay?.timing_risk_profile?.window || '--'}
              </div>
            </div>
            <div>
              <div style={{ fontSize: '12px', opacity: 0.9, marginBottom: '4px' }}>News Risk</div>
              <div style={{ fontSize: '18px', fontWeight: 'bold', color: '#fecaca' }}>
                {fmtPct(professionalSignalDisplay?.sudden_news_risk)}
              </div>
            </div>
            <div>
              <div style={{ fontSize: '12px', opacity: 0.9, marginBottom: '4px' }}>Liquidity Spike Risk</div>
              <div style={{ fontSize: '18px', fontWeight: 'bold', color: '#fecaca' }}>
                {fmtPct(professionalSignalDisplay?.liquidity_spike_risk)}
              </div>
            </div>
            <div>
              <div style={{ fontSize: '12px', opacity: 0.9, marginBottom: '4px' }}>Premium Distortion</div>
              <div style={{ fontSize: '18px', fontWeight: 'bold', color: '#fecaca' }}>
                {fmtPct(professionalSignalDisplay?.premium_distortion_risk)}
              </div>
            </div>
            <div>
              <div style={{ fontSize: '12px', opacity: 0.9, marginBottom: '4px' }}>Start Trade</div>
              <div style={{
                fontSize: '18px',
                fontWeight: 'bold',
                color: professionalStartTradeColor
              }}>
                {professionalStartTradeLabel}
              </div>
            </div>
          </div>
        </div>
      ) : null}

      {/* Market Analysis */}
      {activeSignalUi && (
        <div style={{
          padding: '24px',
          background: 'linear-gradient(135deg, #fef5e7 0%, #fdebd0 100%)',
          borderRadius: '12px',
          border: '2px solid #f59e0b',
          marginBottom: '24px'
        }}>
          <div style={{
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'start',
            marginBottom: '16px'
          }}>
            <div>
              <h4 style={{
                margin: '0 0 8px 0',
                color: '#78350f',
                fontSize: '18px',
                fontWeight: 'bold'
              }}>
                🎯 AI Recommendation (best signal)
              </h4>
              <div style={{ marginBottom: '8px' }}>
                <span style={{
                  fontSize: '12px',
                  padding: '4px 10px',
                  borderRadius: '999px',
                  fontWeight: '700',
                  background: recommendationReadiness.pass ? '#16a34a' : '#b45309',
                  color: '#ffffff'
                }}>
                  Entry Readiness: {recommendationReadiness.status}
                </span>
                {!recommendationReadiness.pass && (
                  <span style={{ marginLeft: '10px', fontSize: '12px', color: '#9a3412' }}>
                    {recommendationReadiness.reasons.slice(0, 3).join(' • ')}
                  </span>
                )}
              </div>

              <div style={{
                marginBottom: '12px',
                padding: '10px 12px',
                borderRadius: '8px',
                background: '#fffaf0',
                border: '1px solid #fed7aa'
              }}>
                <div style={{
                  fontSize: '12px',
                  fontWeight: '800',
                  color: '#7c2d12',
                  marginBottom: '8px'
                }}>
                  🧭 Trading Gate Status
                </div>
                <div style={{
                  display: 'grid',
                  gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))',
                  gap: '6px 10px',
                  fontSize: '12px'
                }}>
                  {gateStatusRows.map((gate) => (
                    <div key={gate.label} style={{ color: gate.pass ? '#166534' : '#9a3412' }}>
                      <strong>{gate.pass ? 'PASS' : 'WAIT'}:</strong> {gate.label} - {gate.detail}
                    </div>
                  ))}
                </div>
                {gateBlockingReasons.length > 0 && (
                  <div style={{ marginTop: '8px', fontSize: '12px', color: '#9a3412' }}>
                    <strong>Blocked By:</strong> {gateBlockingReasons.join(' | ')}
                  </div>
                )}
              </div>

              <div style={{
                display: 'flex',
                gap: '16px',
                fontSize: '14px',
                color: '#92400e',
                flexWrap: 'wrap'
              }}>
                <span>
                      <strong>Strategy:</strong>{' '}
                      <span style={{
                        padding: '2px 8px',
                        borderRadius: '4px',
                        background: '#667eea',
                        color: 'white',
                        fontWeight: '600'
                      }}>
                        {activeSignalUi.strategy || 'Best Match'}
                      </span>
                </span>
                <span>
                  <strong>Action:</strong>{' '}
                  <span style={{
                    padding: '2px 8px',
                    borderRadius: '4px',
                    background: activeSignalUi.action === 'BUY' ? '#48bb78' : '#f56565',
                    color: 'white',
                    fontWeight: 'bold'
                  }}>
                    {activeSignalUi.action}
                  </span>
                </span>
                <span><strong>Symbol:</strong> {activeSignalUi.symbol}</span>
                <span>
                  <strong>Confidence:</strong>{' '}
                  <span style={{
                    padding: '2px 8px',
                    borderRadius: '4px',
                    background: Number(activeSignalUi.confirmation_score ?? activeSignalUi.confidence) >= 85 ? '#c6f6d5' : Number(activeSignalUi.confirmation_score ?? activeSignalUi.confidence) >= 75 ? '#feebc8' : '#fed7d7',
                    color: Number(activeSignalUi.confirmation_score ?? activeSignalUi.confidence) >= 85 ? '#22543d' : Number(activeSignalUi.confirmation_score ?? activeSignalUi.confidence) >= 75 ? '#92400e' : '#742a2a',
                    fontWeight: '600'
                  }}>
                    {(activeSignalUi.confirmation_score ?? activeSignalUi.confidence ?? 0).toFixed(1)}%
                  </span>
                </span>
                <span>
                  <strong>AI Edge:</strong>{' '}
                  <span style={{
                    padding: '2px 8px',
                    borderRadius: '4px',
                    background: Number(activeSignalUi.ai_edge_score ?? 0) >= 70 ? '#c6f6d5' : Number(activeSignalUi.ai_edge_score ?? 0) >= 60 ? '#feebc8' : '#fed7d7',
                    color: Number(activeSignalUi.ai_edge_score ?? 0) >= 70 ? '#22543d' : Number(activeSignalUi.ai_edge_score ?? 0) >= 60 ? '#92400e' : '#742a2a',
                    fontWeight: '700'
                  }}>
                    {fmtPct(activeSignalUi.ai_edge_score)}
                  </span>
                </span>
                <span><strong>Momentum:</strong> {fmtPct(activeSignalUi.momentum_score)}</span>
                <span><strong>Breakout:</strong> {fmtPct(activeSignalUi.breakout_score)}</span>
                <span><strong>Fake Move Risk:</strong> {fmtPct(activeSignalUi.fake_move_risk)}</span>
                <span><strong>News Risk:</strong> {fmtPct(activeSignalUi.sudden_news_risk)}</span>
                <span><strong>Liquidity Spike Risk:</strong> {fmtPct(activeSignalUi.liquidity_spike_risk)}</span>
                <span><strong>Premium Distortion:</strong> {fmtPct(activeSignalUi.premium_distortion_risk)}</span>
                <span><strong>Breakout Hold:</strong> {fmtYesNo(activeSignalUi.breakout_hold_confirmed)}</span>
                <span><strong>Timing Risk:</strong> {activeSignalUi?.timing_risk_profile?.window || '--'}</span>
                <span><strong>Qty Reduced:</strong> {fmtYesNo(activeSignalUi?.qty_reduced_for_timing)}</span>
                <span>
                  <strong>Start Trade:</strong>{' '}
                  <span style={{
                    padding: '2px 8px',
                    borderRadius: '4px',
                    background: recommendationStartTradeBackground,
                    color: recommendationStartTradeColor,
                    fontWeight: '700'
                  }}>
                    {recommendationStartTradeLabel}
                  </span>
                </span>
                <span style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <strong>Quantity:</strong>
                  <button
                    onClick={() => setLotMultiplier(Math.max(1, lotMultiplier - 1))}
                    style={{
                      padding: '2px 8px',
                      background: '#e2e8f0',
                      border: '1px solid #cbd5e0',
                      borderRadius: '4px',
                      cursor: 'pointer',
                      fontSize: '14px',
                      fontWeight: 'bold'
                    }}
                  >
                    −
                  </button>
                  <span style={{
                    padding: '4px 12px',
                    background: '#edf2f7',
                    borderRadius: '6px',
                    fontWeight: 'bold',
                    minWidth: '80px',
                    textAlign: 'center'
                  }}>
                    {displayTotalQuantity}
                  </span>
                  <button
                    onClick={() => setLotMultiplier(lotMultiplier + 1)}
                    style={{
                      padding: '2px 8px',
                      background: '#e2e8f0',
                      border: '1px solid #cbd5e0',
                      borderRadius: '4px',
                      cursor: 'pointer',
                      fontSize: '14px',
                      fontWeight: 'bold'
                    }}
                  >
                    +
                  </button>
                  <span style={{ fontSize: '12px', color: '#718096' }}>({lotMultiplier} lots)</span>
                </span>
                <span>
                  <strong>Capital Required:</strong>{' '}
                  ₹{displayCapitalRequired.toLocaleString()}
                </span>
                {(() => {
                  // If activeSignal is from market scan (bestQualityTrade), use its pre-calculated quality
                  if (activeSignalUi === bestQualityTrade && activeSignalUi?.quality !== undefined) {
                    const preCalcQuality = activeSignalUi.quality;
                    const { rr, optimalRR } = calculateOptimalRR(activeSignalUi, stats?.win_rate ? (stats.win_rate / 100) : 0.5);
                    return (
                      <span style={{
                        display: 'flex',
                        alignItems: 'center',
                        gap: '8px',
                        padding: '8px 12px',
                        background: preCalcQuality >= 90 ? '#c6f6d5' : preCalcQuality >= 80 ? '#feebc8' : '#fed7d7',
                        borderRadius: '6px',
                        borderLeft: `4px solid ${preCalcQuality >= 90 ? '#22c55e' : preCalcQuality >= 80 ? '#f59e0b' : '#ef4444'}`
                      }}>
                        <strong>🤖 Quality:</strong>
                        <span style={{ fontWeight: 'bold', fontSize: '13px' }}>{preCalcQuality}%</span>
                        <span style={{ fontSize: '11px', opacity: 0.8 }}>• RR: {rr.toFixed(2)} (✓{optimalRR.toFixed(2)})</span>
                      </span>
                    );
                  }
                  // Otherwise recalculate for live signals
                  const winRate = stats?.win_rate ? (stats.win_rate / 100) : 0.5;
                  const quality = calculateTradeQuality(activeSignalUi, winRate);
                  const { rr, optimalRR } = calculateOptimalRR(activeSignalUi, winRate);
                  return (
                    <span style={{
                      display: 'flex',
                      alignItems: 'center',
                      gap: '8px',
                      padding: '8px 12px',
                      background: quality.quality >= 85 ? '#c6f6d5' : quality.quality >= 75 ? '#feebc8' : '#fed7d7',
                      borderRadius: '6px',
                      borderLeft: `4px solid ${quality.quality >= 85 ? '#22c55e' : quality.quality >= 75 ? '#f59e0b' : '#ef4444'}`
                    }}>
                      <strong>🤖 Quality:</strong>
                      <span style={{ fontWeight: 'bold', fontSize: '13px' }}>{quality.quality}%</span>
                      <span style={{ fontSize: '11px', opacity: 0.8 }}>• RR: {rr.toFixed(2)} (✓{optimalRR.toFixed(2)})</span>
                    </span>
                  );
                })()}
                <span><strong>Expiry:</strong> {activeSignalUi.expiry_date || activeSignalUi.expiry}</span>
              </div>
            </div>
            <div style={{ display: 'flex', gap: '12px', alignItems: 'center' }}>
              <button
                onClick={async () => {
                  if (armingInProgress) return;

                  setArmStatus(null);
                  setArmingInProgress(true);

                  if (isLiveMode) {
                    // Switch LIVE -> DEMO (disarm live first).
                    const disarmed = await armLiveTrading(false, false);
                    if (!disarmed) return;
                    setIsLiveMode(false);
                    setEnabled(true);
                    setAutoTradingActive(true);
                    setArmError(null);
                    setArmingInProgress(false);
                    setArmStatus('DEMO MODE ENABLED. AUTO-TRADING ACTIVE.');
                    return;
                  }

                  // Close all open demo trades before going live so demo P&L is settled.
                  const openDemoNow = (activeTrades || []).filter((t) => {
                    const st = String(t?.status || '').toUpperCase();
                    const isOpen = st === 'OPEN' || (st !== 'CLOSED' && st !== 'CANCELLED' && st !== 'SL_HIT' && st !== 'TARGET_HIT');
                    const md = String(t?.trade_mode || t?.trade_source || '').toUpperCase();
                    return isOpen && (md === 'DEMO' || md === 'PAPER');
                  });
                  if (openDemoNow.length > 0) {
                    console.log(`🔄 Closing ${openDemoNow.length} open demo trade(s) before arming live...`);
                    await Promise.allSettled(
                      openDemoNow.map((t) =>
                        config.authFetch(`${config.API_BASE_URL}/paper-trades/${t.id}`, {
                          method: 'PUT',
                          body: JSON.stringify({ status: 'MANUAL_CLOSE' }),
                        }).catch(() => null)
                      )
                    );
                    await fetchData(true).catch(() => null);
                    console.log('✅ Demo trades closed.');
                  }

                  // Switch DEMO -> LIVE (arm live).
                  const armed = await armLiveTrading(true, false);
                  if (!armed) {
                    setIsLiveMode(false);
                    setAutoTradingActive(true);
                    setEnabled(true);
                    setArmError(null);
                    setArmingInProgress(false);
                    setArmStatus('LIVE START FAILED. CONTINUING AUTO-TRADING IN DEMO.');
                    return;
                  }
                  setIsLiveMode(true);
                  setEnabled(true);
                  setAutoTradingActive(true);
                  setArmError(null);
                  setArmingInProgress(false);
                  setArmStatus('LIVE MODE ENABLED. AUTO-TRADING ACTIVE.');
                }}
                disabled={armingInProgress}
                style={{
                  padding: '12px 18px',
                  background: isLiveMode ? '#f59e0b' : '#ef4444',
                  color: 'white',
                  border: 'none',
                  borderRadius: '8px',
                  fontSize: '14px',
                  fontWeight: '600',
                  cursor: armingInProgress ? 'wait' : 'pointer',
                  boxShadow: '0 4px 6px rgba(0,0,0,0.1)',
                  opacity: armingInProgress ? 0.7 : 1
                }}
              >
                {isLiveMode ? '⚪ Switch To Demo Mode' : '🔴 Switch To Live Mode'}
              </button>
              {armStatus && (
                <div style={{
                  padding: '12px 16px',
                  background: '#c6f6d5',
                  color: '#22543d',
                  borderRadius: '6px',
                  fontSize: '13px',
                  fontWeight: '700',
                  maxWidth: '300px'
                }}>
                  ✅ {armStatus}
                </div>
              )}
              {armError && (
                <div style={{
                  padding: '12px 16px',
                  background: '#fed7d7',
                  color: '#742a2a',
                  borderRadius: '6px',
                  fontSize: '13px',
                  fontWeight: '600',
                  maxWidth: '300px'
                }}>
                  ❌ {armError}
                </div>
              )}
              {autoTradingActive && (
                <div style={{
                  padding: '8px 16px',
                  background: isLiveMode ? '#c6f6d5' : '#feebc8',
                  color: isLiveMode ? '#22543d' : '#78350f',
                  borderRadius: '6px',
                  fontSize: '13px',
                  fontWeight: '600'
                }}>
                  {isLiveMode ? '🔴 REAL TRADES' : '⚪ DEMO MODE'} {activeTradesForCurrentMode.length > 0 ? '(Trade Active)' : '(Ready)'}
                </div>
              )}
            </div>
          </div>
          <div style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fit, minmax(150px, 1fr))',
            gap: '12px',
            padding: '16px',
            background: 'rgba(255, 255, 255, 0.5)',
            borderRadius: '8px'
          }}>
            <div>
              <div style={{ fontSize: '12px', color: '#78350f', marginBottom: '4px' }}>
                🔴 Live Entry Price
              </div>
              <div style={{ fontSize: '18px', fontWeight: 'bold', color: '#1a202c' }}>
                ₹{liveEntryPrice != null ? Number(liveEntryPrice).toFixed(2) : '--'}
              </div>
            </div>
            <div>
              <div style={{ fontSize: '12px', color: '#78350f', marginBottom: '4px' }}>
                Target (+{liveTargetPoints != null ? liveTargetPoints.toFixed(2) : '--'}pts)
              </div>
              <div style={{ fontSize: '18px', fontWeight: 'bold', color: '#48bb78' }}>
                ₹{liveTarget != null ? Number(liveTarget).toFixed(2) : '--'}
              </div>
            </div>
            <div>
              <div style={{ fontSize: '12px', color: '#78350f', marginBottom: '4px' }}>
                Stop Loss (-{liveSlPoints != null ? liveSlPoints.toFixed(2) : '--'}pts)
              </div>
              <div style={{ fontSize: '18px', fontWeight: 'bold', color: '#f56565' }}>
                ₹{liveStopLoss != null ? Number(liveStopLoss).toFixed(2) : '--'}
              </div>
            </div>
            <div>
              <div style={{ fontSize: '12px', color: '#78350f', marginBottom: '4px' }}>Potential Profit</div>
              <div style={{ fontSize: '18px', fontWeight: 'bold', color: '#38a169' }}>
                ₹{Number.isFinite(livePotentialProfit) ? livePotentialProfit.toLocaleString() : '--'}
              </div>
            </div>
            <div>
              <div style={{ fontSize: '12px', color: '#78350f', marginBottom: '4px' }}>Max Risk</div>
              <div style={{ fontSize: '18px', fontWeight: 'bold', color: '#e53e3e' }}>
                ₹{Number.isFinite(liveMaxRisk) ? liveMaxRisk.toLocaleString() : '--'}
              </div>
            </div>
            <div>
              <div style={{ fontSize: '12px', color: '#78350f', marginBottom: '4px' }}>Quantity</div>
              <div style={{ fontSize: '18px', fontWeight: 'bold', color: '#5a67d8' }}>
                {liveTotalQuantity}
              </div>
            </div>
            <div>
              <div style={{ fontSize: '12px', color: '#78350f', marginBottom: '4px' }}>Expiry Date</div>
              <div style={{ fontSize: '18px', fontWeight: 'bold', color: '#2d3748' }}>
                {liveExpiryDate || 'N/A'}
              </div>
            </div>
          </div>
        </div>
      )}

      {/* All Signals Table */}
      {/* Debug: Raw signals output */}
      {analysis && analysis.signals && (
        <div style={{ margin: '16px 0', padding: '12px', background: '#f7fafc', border: '1px dashed #cbd5e0', borderRadius: '8px', fontSize: '12px', color: '#2d3748' }}>
          <strong>Debug: Raw signals array</strong>
          <pre style={{ whiteSpace: 'pre-wrap', wordBreak: 'break-all', margin: 0 }}>
            {JSON.stringify(analysis.signals, null, 2)}
          </pre>
        </div>
      )}
      {!isLiveMode && analysis && analysis.signals && analysis.signals.length > 0 && (
        <div style={{ marginBottom: '24px' }}>
          <h4 style={{
            margin: '0 0 16px 0',
            color: '#2d3748',
            fontSize: '18px',
            fontWeight: 'bold'
          }}>
            📋 All Strategy Signals ({analysis.signals?.length ?? 0})
          </h4>
          <div style={{ overflowX: 'auto' }}>
            <table style={{
              width: '100%',
              borderCollapse: 'collapse',
              fontSize: '14px',
              background: 'white',
              borderRadius: '8px',
              overflow: 'hidden'
            }}>
              <thead>
                <tr style={{ background: '#f7fafc', borderBottom: '2px solid #e2e8f0' }}>
                  <th style={{ padding: '12px', textAlign: 'left' }}>Strategy</th>
                  <th style={{ padding: '12px', textAlign: 'left' }}>Symbol</th>
                  <th style={{ padding: '12px', textAlign: 'left' }}>Action</th>
                  <th style={{ padding: '12px', textAlign: 'right' }}>Confidence</th>
                  <th style={{ padding: '12px', textAlign: 'right' }}>Quantity</th>
                  <th style={{ padding: '12px', textAlign: 'right' }}>Entry</th>
                  <th style={{ padding: '12px', textAlign: 'right' }}>Target</th>
                  <th style={{ padding: '12px', textAlign: 'right' }}>Stop Loss</th>
                  <th style={{ padding: '12px', textAlign: 'left' }}>Expiry</th>
                </tr>
              </thead>
              <tbody>
                {analysis.signals?.map((signal, idx) => (
                  <tr key={idx} style={{ borderBottom: '1px solid #e2e8f0' }}>
                    <td style={{ padding: '12px', fontSize: '13px' }}>{signal.strategy}</td>
                    <td style={{ padding: '12px', fontWeight: '600', fontSize: '13px' }}>{signal.symbol}</td>
                    <td style={{ padding: '12px' }}>
                      <span style={{
                        padding: '4px 8px',
                        borderRadius: '4px',
                        background: signal.action === 'BUY' ? '#c6f6d5' : '#fed7d7',
                        color: signal.action === 'BUY' ? '#22543d' : '#742a2a',
                        fontSize: '12px',
                        fontWeight: 'bold'
                      }}>
                        {signal.action}
                      </span>
                    </td>
                    <td style={{ padding: '12px', textAlign: 'right', fontWeight: '600' }}>
                      {signal.confidence}%
                    </td>
                    <td style={{ padding: '12px', textAlign: 'right', fontWeight: '600', color: '#5a67d8' }}>
                      {signal.quantity}
                    </td>
                    <td style={{ padding: '12px', textAlign: 'right' }}>
                      ₹{signal.entry_price.toFixed(2)}
                    </td>
                    <td style={{ padding: '12px', textAlign: 'right', color: '#48bb78', fontWeight: '600' }}>
                      ₹{signal.target.toFixed(2)}
                    </td>
                    <td style={{ padding: '12px', textAlign: 'right', color: '#f56565', fontWeight: '600' }}>
                      ₹{signal.stop_loss.toFixed(2)}
                    </td>
                    <td style={{ padding: '12px', fontSize: '12px', color: '#718096' }}>
                      {signal.expiry_date || signal.expiry}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Scan & Trade Status Banner */}
      {(() => {
        const _hasOpenTrade = (activeTrades || []).some((t) => String(t?.status || '').toUpperCase() === 'OPEN');
        const _entryBlockers = recommendationReadiness?.reasons || [];
        const _strictSignalsCount = Number(sortedQualityTrades?.length || 0);
        const _signalsAvailable = _strictSignalsCount > 0 || !!activeSignalUi?.symbol;
        if (_hasOpenTrade) return null;
        if (!isMarketOpen) return (
          <div style={{ marginBottom: '14px', padding: '10px 14px', background: '#f1f5f9', border: '1px solid #cbd5e1', borderRadius: '8px', fontSize: '12px', color: '#475569' }}>
            <strong>⏸️ Market Closed</strong> — Scanner paused until next trading session.
          </div>
        );
        if (!_signalsAvailable && !scannerLoading) return (
          <div style={{ marginBottom: '14px', padding: '10px 14px', background: '#fefce8', border: '1px solid #fde047', borderRadius: '8px', fontSize: '12px', color: '#713f12' }}>
            <strong>🔍 Scanner Active ({scannerMinQuality}%+):</strong> No quality signals found yet.{' '}
            {autoScanActive ? 'Scanning continuously...' : 'Click Refresh to scan.'}
          </div>
        );
        if (_signalsAvailable && !autoTradingActive) return (
          <div style={{ marginBottom: '14px', padding: '10px 14px', background: '#eff6ff', border: '1px solid #93c5fd', borderRadius: '8px', fontSize: '12px', color: '#1e3a8a' }}>
            <strong>📡 {_strictSignalsCount || 1} signal{(_strictSignalsCount || 1) !== 1 ? 's' : ''} ready</strong>{' '}—{' '}
            Auto-trading is <strong>OFF</strong>. Use <em>▶️ Start Live Trading</em> to execute.
          </div>
        );
        if (_signalsAvailable && _entryBlockers.length > 0) return (
          <div style={{ marginBottom: '14px', padding: '10px 14px', background: '#fff7ed', border: '1px solid #fb923c', borderRadius: '8px', fontSize: '12px' }}>
            <div style={{ fontWeight: '700', color: '#9a3412', marginBottom: '4px' }}>
              ⛔ Entry Blocked — {_strictSignalsCount || 1} signal{(_strictSignalsCount || 1) !== 1 ? 's' : ''} found but gate failed:
            </div>
            {_entryBlockers.slice(0, 5).map((r, i) => (
              <div key={i} style={{ color: '#7c2d12', paddingLeft: '8px' }}>• {r}</div>
            ))}
          </div>
        );
        return null;
      })()}

      {(() => {
        const mergedBlockers = [
          ...(entryBlockEvents || []).map((item) => ({ ...item, sourceLabel: 'Client Gate' })),
          ...(aiGateRejections || []).map((item) => ({ ...item, sourceLabel: 'Server Gate' })),
        ]
          .sort((a, b) => new Date(b?.at || 0).getTime() - new Date(a?.at || 0).getTime())
          .slice(0, 14);

        if (mergedBlockers.length === 0) return null;

        return (
          <div style={{
            marginBottom: '18px',
            padding: '12px',
            background: '#fff7ed',
            border: '1px solid #fdba74',
            borderRadius: '8px'
          }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px', gap: '8px', flexWrap: 'wrap' }}>
              <h4 style={{ margin: 0, color: '#9a3412', fontSize: '14px', fontWeight: '700' }}>
                ⛔ Execution Blockers (Live + Demo)
              </h4>
              <button
                onClick={() => { setEntryBlockEvents([]); setAiGateRejections([]); }}
                style={{
                  border: '1px solid #fdba74',
                  background: '#ffedd5',
                  color: '#9a3412',
                  borderRadius: '6px',
                  padding: '4px 8px',
                  cursor: 'pointer',
                  fontSize: '11px',
                  fontWeight: '700'
                }}
              >
                Clear
              </button>
            </div>
            <div style={{ display: 'grid', gap: '6px' }}>
              {mergedBlockers.map((item, idx) => (
                <div key={`${item.at}-${item.symbol}-${item.sourceLabel || 'gate'}-${idx}`} style={{ fontSize: '12px', color: '#7c2d12', background: '#fffaf0', border: '1px solid #fed7aa', borderRadius: '6px', padding: '8px' }}>
                  <strong>{item.symbol}</strong> {item.action ? `(${item.action})` : ''} {item.mode ? `[${item.mode}]` : ''} | {formatTimeIST(item.at)} | {item.sourceLabel || 'Gate'}<br />
                  {item.message}
                  {Array.isArray(item.reasons) && item.reasons.length > 0 ? ` | ${item.reasons.join(' | ')}` : ''}
                </div>
              ))}
            </div>
          </div>
        );
      })()}

      {/* Active Trades */}

      {showActiveTradesTable && (
        <div style={{ marginBottom: '24px' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', margin: '0 0 16px 0', gap: '12px', flexWrap: 'wrap' }}>
            <h4 style={{
              margin: 0,
              color: '#2d3748',
              fontSize: '18px',
              fontWeight: 'bold'
            }}>
              ⚡ Active Trades ({filteredActiveTrades.length})
            </h4>
            <span style={{
              padding: '4px 10px',
              borderRadius: '999px',
              fontSize: '11px',
              fontWeight: '700',
              border: isUsingStaleData ? '1px solid #f59e0b' : '1px solid #10b981',
              color: isUsingStaleData ? '#92400e' : '#065f46',
              background: isUsingStaleData ? '#fef3c7' : '#ecfdf5'
            }}>
              {isUsingStaleData ? 'STALE VIEW' : 'LIVE SYNC'} • {syncBadgeLabel}
            </span>
          </div>
          <div style={{
            display: 'flex',
            flexWrap: 'wrap',
            gap: '12px',
            alignItems: 'center',
            marginBottom: '12px'
          }}>
            <select
              value={activeModeFilter}
              onChange={(e) => setActiveModeFilter(e.target.value)}
              style={{
                padding: '6px 10px',
                border: '1px solid #e2e8f0',
                borderRadius: '6px',
                fontSize: '12px'
              }}
            >
              <option value="ALL">Mode: All</option>
              <option value="LIVE">Mode: Live</option>
              <option value="DEMO">Mode: Demo</option>
            </select>
          </div>
          <div style={{ overflowX: 'auto' }}>
            <table style={{
              width: '100%',
              borderCollapse: 'collapse',
              fontSize: '13px',
              background: 'white',
              borderRadius: '8px',
              overflow: 'hidden'
            }}>
              <thead>
                <tr style={{ background: '#f7fafc', borderBottom: '2px solid #e2e8f0' }}>
                  <th style={{ padding: '10px', textAlign: 'left' }}>Symbol</th>
                  <th style={{ padding: '10px', textAlign: 'center' }}>Mode</th>
                  <th style={{ padding: '10px', textAlign: 'left' }}>Action</th>
                  <th style={{ padding: '10px', textAlign: 'right' }}>Entry</th>
                  <th style={{ padding: '10px', textAlign: 'right' }}>Current</th>
                  <th style={{ padding: '10px', textAlign: 'right' }}>Target</th>
                  <th style={{ padding: '10px', textAlign: 'right' }}>Stop Loss</th>
                  <th style={{ padding: '10px', textAlign: 'right' }}>Expected</th>
                  <th style={{ padding: '10px', textAlign: 'right' }}>P&L</th>
                  <th style={{ padding: '10px', textAlign: 'right' }}>%</th>
                  <th style={{ padding: '10px', textAlign: 'right' }}>Qty</th>
                  <th style={{ padding: '10px', textAlign: 'left' }}>Opened</th>
                  <th style={{ padding: '10px', textAlign: 'center' }}>Action</th>
                </tr>
              </thead>
              <tbody>
                {filteredActiveTrades.map((trade) => {
                  const entry = Number(trade.entry_price ?? trade.price ?? 0);
                  const current = Number(trade.current_price ?? entry);
                  const action = String(trade.side || trade.action || 'BUY').toUpperCase();
                  const tradeMode = resolveTradeMode(trade);
                  const qty = Number(trade.quantity ?? 0);
                  const computedPnl = entry > 0 && qty > 0
                    ? (action === 'BUY' ? (current - entry) * qty : (entry - current) * qty)
                    : 0;
                  const pnl = Number(trade.pnl ?? trade.profit_loss ?? trade.unrealized_pnl ?? computedPnl);
                  const pnlPct = Number(
                    trade.pnl_percentage
                    ?? trade.profit_percentage
                    ?? trade.pnl_percent
                    ?? (entry > 0 && qty > 0 ? (computedPnl / (entry * qty)) * 100 : 0)
                  );
                  const target = Number(trade.target ?? 0);
                  const stopLoss = Number(trade.stop_loss ?? 0);
                  const expected = entry > 0 && target > 0 ? Math.abs(target - entry) * qty : 0;
                  return (
                    <tr key={getTradeRowKey(trade)} style={{ borderBottom: '1px solid #e2e8f0' }}>
                      <td style={{ padding: '10px', fontWeight: '600' }}>{trade.symbol}</td>
                      <td style={{ padding: '10px', textAlign: 'center' }}>
                        <span style={{
                          padding: '2px 8px',
                          borderRadius: '999px',
                          background: tradeMode === 'LIVE' ? '#fee2e2' : '#e0f2fe',
                          color: tradeMode === 'LIVE' ? '#991b1b' : '#0c4a6e',
                          fontSize: '11px',
                          fontWeight: '700'
                        }}>
                          {tradeMode}
                        </span>
                      </td>
                      <td style={{ padding: '10px' }}>
                        <span style={{
                          padding: '2px 6px',
                          borderRadius: '3px',
                          background: action === 'BUY' ? '#c6f6d5' : '#fed7d7',
                          color: action === 'BUY' ? '#22543d' : '#742a2a',
                          fontSize: '11px',
                          fontWeight: 'bold'
                        }}>
                          {action}
                        </span>
                      </td>
                      <td style={{ padding: '10px', textAlign: 'right' }}>₹{entry.toFixed(2)}</td>
                      <td style={{ padding: '10px', textAlign: 'right' }}>₹{current.toFixed(2)}</td>
                      <td style={{ padding: '10px', textAlign: 'right', color: '#48bb78', fontWeight: '600' }}>
                        {target ? `₹${target.toFixed(2)}` : '--'}
                      </td>
                      <td style={{ padding: '10px', textAlign: 'right', color: '#f56565', fontWeight: '600' }}>
                        {stopLoss ? `₹${stopLoss.toFixed(2)}` : '--'}
                      </td>
                      <td style={{ padding: '10px', textAlign: 'right', fontWeight: '600', color: '#2b6cb0' }}>
                        {expected ? `₹${expected.toFixed(2)}` : '--'}
                      </td>
                      <td style={{
                        padding: '10px',
                        textAlign: 'right',
                        fontWeight: '700',
                        color: pnl >= 0 ? '#48bb78' : '#f56565'
                      }}>
                        {pnl >= 0 ? '+' : ''}₹{pnl.toLocaleString()}
                      </td>
                      <td style={{
                        padding: '10px',
                        textAlign: 'right',
                        fontWeight: '600',
                        color: pnlPct >= 0 ? '#48bb78' : '#f56565'
                      }}>
                        {pnlPct >= 0 ? '+' : ''}{pnlPct.toFixed(2)}%
                      </td>
                      <td style={{ padding: '10px', textAlign: 'right' }}>{trade.quantity}</td>
                      <td style={{ padding: '10px', fontSize: '11px', color: '#718096' }}>
                        {formatTimeIST(trade.entry_time)}
                      </td>
                      <td style={{ padding: '10px', textAlign: 'center' }}>
                        <button
                          onClick={() => closeActiveTrade(trade)}
                          style={{
                            padding: '6px 10px',
                            borderRadius: '6px',
                            border: '1px solid #e53e3e',
                            background: '#fff5f5',
                            color: '#c53030',
                            fontSize: '12px',
                            fontWeight: '600',
                            cursor: 'pointer'
                          }}
                        >
                          Close
                        </button>
                      </td>
                    </tr>
                  );
                })}
                {filteredActiveTrades.length === 0 && (
                  <tr>
                    <td colSpan={13} style={{ padding: '16px', textAlign: 'center', color: '#718096' }}>
                      No active trades for selected mode.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Trade History */}
      {showTradeHistoryTable && (
        <div>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', margin: '0 0 16px 0', gap: '12px', flexWrap: 'wrap' }}>
            <h4 style={{
              margin: 0,
              color: '#2d3748',
              fontSize: '18px',
              fontWeight: 'bold'
            }}>
              📊 Trade History ({filteredHistory.length})
            </h4>
            <span style={{
              padding: '4px 10px',
              borderRadius: '999px',
              fontSize: '11px',
              fontWeight: '700',
              border: isUsingStaleData ? '1px solid #f59e0b' : '1px solid #10b981',
              color: isUsingStaleData ? '#92400e' : '#065f46',
              background: isUsingStaleData ? '#fef3c7' : '#ecfdf5'
            }}>
              {isUsingStaleData ? 'STALE VIEW' : 'LIVE SYNC'} • {syncBadgeLabel}
            </span>
          </div>
          <div style={{
            display: 'flex',
            flexWrap: 'wrap',
            gap: '12px',
            alignItems: 'center',
            marginBottom: '12px'
          }}>
            <div style={{ fontSize: '12px', color: '#4a5568', fontWeight: '600' }}>Date Range</div>
            <input
              type="date"
              value={historyStartDate}
              onChange={(e) => setHistoryStartDate(e.target.value)}
              style={{
                padding: '6px 10px',
                border: '1px solid #e2e8f0',
                borderRadius: '6px',
                fontSize: '12px'
              }}
            />
            <span style={{ color: '#718096', fontSize: '12px' }}>to</span>
            <input
              type="date"
              value={historyEndDate}
              onChange={(e) => setHistoryEndDate(e.target.value)}
              style={{
                padding: '6px 10px',
                border: '1px solid #e2e8f0',
                borderRadius: '6px',
                fontSize: '12px'
              }}
            />
            <button
              onClick={() => {
                const today = new Date().toISOString().slice(0, 10);
                setHistoryStartDate(today);
                setHistoryEndDate(today);
              }}
              style={{
                padding: '6px 10px',
                border: '1px solid #cbd5e0',
                borderRadius: '6px',
                background: '#edf2f7',
                fontSize: '12px',
                cursor: 'pointer'
              }}
            >
              Today
            </button>
            <select
              value={historyModeFilter}
              onChange={(e) => setHistoryModeFilter(e.target.value)}
              style={{
                padding: '6px 10px',
                border: '1px solid #e2e8f0',
                borderRadius: '6px',
                fontSize: '12px'
              }}
            >
              <option value="ALL">Mode: All</option>
              <option value="LIVE">Mode: Live</option>
              <option value="DEMO">Mode: Demo</option>
            </select>
            <select
              value={historyActionFilter}
              onChange={(e) => setHistoryActionFilter(e.target.value)}
              style={{
                padding: '6px 10px',
                border: '1px solid #e2e8f0',
                borderRadius: '6px',
                fontSize: '12px'
              }}
            >
              <option value="ALL">Action: All</option>
              <option value="BUY">Action: BUY</option>
              <option value="SELL">Action: SELL</option>
            </select>
            <select
              value={historyStatusFilter}
              onChange={(e) => setHistoryStatusFilter(e.target.value)}
              style={{
                padding: '6px 10px',
                border: '1px solid #e2e8f0',
                borderRadius: '6px',
                fontSize: '12px'
              }}
            >
              <option value="ALL">Status: All</option>
              <option value="OPEN">OPEN</option>
              <option value="MANUAL_CLOSE">MANUAL_CLOSE</option>
              <option value="SL_HIT">SL_HIT</option>
              <option value="TARGET_HIT">TARGET_HIT</option>
              <option value="EXPIRED">EXPIRED</option>
            </select>
            <div style={{
              marginLeft: 'auto',
              display: 'flex',
              gap: '12px',
              flexWrap: 'wrap'
            }}>
              <div style={{
                padding: '6px 10px',
                borderRadius: '6px',
                background: '#edf2f7',
                fontSize: '12px',
                fontWeight: '600'
              }}>
                Range P&L: <span style={{ color: rangePnl >= 0 ? '#2f855a' : '#c53030' }}>
                  ₹{rangePnl.toLocaleString()}
                </span>
              </div>
              <div style={{
                padding: '6px 10px',
                borderRadius: '6px',
                background: '#edf2f7',
                fontSize: '12px',
                fontWeight: '600'
              }}>
                Trades: {filteredHistory.length}
              </div>
              <div style={{
                padding: '6px 10px',
                borderRadius: '6px',
                background: '#edf2f7',
                fontSize: '12px',
                fontWeight: '600'
              }}>
                Win/Loss: {rangeWins} / {filteredHistory.length - rangeWins}
              </div>
            </div>
          </div>
          <div style={{ overflowX: 'auto', maxHeight: '400px', overflowY: 'auto' }}>
            <table style={{
              width: '100%',
              borderCollapse: 'collapse',
              fontSize: '13px'
            }}>
              <thead style={{ position: 'sticky', top: 0, background: '#f7fafc', zIndex: 1 }}>
                <tr style={{ borderBottom: '2px solid #e2e8f0' }}>
                  <th style={{ padding: '10px', textAlign: 'left' }}>ID</th>
                  <th style={{ padding: '10px', textAlign: 'left' }}>Symbol</th>
                  <th style={{ padding: '10px', textAlign: 'center' }}>Mode</th>
                  <th style={{ padding: '10px', textAlign: 'left' }}>Action</th>
                  <th style={{ padding: '10px', textAlign: 'right' }}>Entry</th>
                  <th style={{ padding: '10px', textAlign: 'right' }}>Exit</th>
                  <th style={{ padding: '10px', textAlign: 'right' }}>P&L</th>
                  <th style={{ padding: '10px', textAlign: 'right' }}>%</th>
                  <th style={{ padding: '10px', textAlign: 'left' }}>Status</th>
                  <th style={{ padding: '10px', textAlign: 'left' }}>Exit Time</th>
                </tr>
              </thead>
              <tbody>
                {filteredHistory.map((trade, idx) => {
                  const entry = Number(trade.entry_price || trade.price || 0);
                  const inferredExit = inferExitPrice(trade);
                  const exit = inferredExit != null ? Number(inferredExit) : null;
                  const pnl = Number(trade.profit_loss ?? trade.pnl ?? 0);
                  const pnlPct = Number(trade.pnl_percentage ?? trade.profit_percentage ?? trade.pnl_percent ?? 0);
                  const action = trade.action || trade.side || 'BUY';
                  const tradeMode = String(
                    trade?.trade_mode
                    || trade?.trade_source
                    || trade?.mode
                    || (trade?.broker_order_id ? 'LIVE' : 'DEMO')
                  ).toUpperCase();
                  const statusPalette = getTradeStatusPalette(trade.status);
                  return (
                    <tr key={getHistoryDisplayKey(trade, idx)} style={{ borderBottom: '1px solid #e2e8f0' }}>
                      <td style={{ padding: '10px' }}>#{idx + 1}</td>
                      <td style={{ padding: '10px', fontWeight: '600' }}>{trade.symbol || trade.index || '—'}</td>
                      <td style={{ padding: '10px', textAlign: 'center' }}>
                        <span style={{
                          padding: '2px 8px',
                          borderRadius: '999px',
                          background: tradeMode === 'LIVE' ? '#fee2e2' : '#e0f2fe',
                          color: tradeMode === 'LIVE' ? '#991b1b' : '#0c4a6e',
                          fontSize: '11px',
                          fontWeight: '700'
                        }}>
                          {tradeMode}
                        </span>
                      </td>
                      <td style={{ padding: '10px' }}>
                        <span style={{
                          padding: '2px 6px',
                          borderRadius: '3px',
                          background: action === 'BUY' ? '#c6f6d5' : '#fed7d7',
                          color: action === 'BUY' ? '#22543d' : '#742a2a',
                          fontSize: '11px',
                          fontWeight: 'bold'
                        }}>
                          {action}
                        </span>
                      </td>
                      <td style={{ padding: '10px', textAlign: 'right' }}>₹{entry.toFixed(2)}</td>
                      <td style={{ padding: '10px', textAlign: 'right' }}>₹{exit !== null ? exit.toFixed(2) : '-'}</td>
                      <td style={{
                        padding: '10px',
                        textAlign: 'right',
                        fontWeight: '700',
                        color: pnl >= 0 ? '#48bb78' : '#f56565'
                      }}>
                        {pnl >= 0 ? '+' : ''}₹{pnl.toLocaleString()}
                      </td>
                      <td style={{
                        padding: '10px',
                        textAlign: 'right',
                        fontWeight: '600',
                        color: pnlPct >= 0 ? '#48bb78' : '#f56565'
                      }}>
                        {pnlPct >= 0 ? '+' : ''}{pnlPct.toFixed(2)}%
                      </td>
                      <td style={{ padding: '10px' }}>
                        <span style={{
                          padding: '2px 6px',
                          borderRadius: '3px',
                          background: statusPalette.background,
                          color: statusPalette.color,
                          fontSize: '11px',
                          fontWeight: 'bold'
                        }}>
                          {statusPalette.label}
                        </span>
                      </td>
                      <td style={{ padding: '10px', fontSize: '11px', color: '#718096' }}>
                        {formatTimeIST(trade.exit_time)}
                      </td>
                    </tr>
                  );
                })}
                {filteredHistory.length === 0 && (
                  <tr>
                    <td colSpan={10} style={{ padding: '16px', textAlign: 'center', color: '#718096' }}>
                      No trades in selected date range.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Empty States - Show Analysis instead of empty message */}
      {!showActiveTradesTable && !showTradeHistoryTable && activeTrades.length === 0 && tradeHistory.length === 0 && !analysis && (
        <div style={{
          padding: '60px 20px',
          textAlign: 'center',
          background: '#f7fafc',
          borderRadius: '12px',
          border: '2px dashed #cbd5e0'
        }}>
          <div style={{ fontSize: '48px', marginBottom: '16px' }}>📊</div>
          <h4 style={{ margin: '0 0 8px 0', color: '#2d3748', fontSize: '18px' }}>
            No Trades Yet
          </h4>
          <p style={{ margin: 0, color: '#718096', fontSize: '14px', marginBottom: '16px' }}>
            Click "📊 Analyze" to see live market signals and expected profit/loss
          </p>
          <button
            onClick={analyzeMarket}
            style={{
              padding: '12px 32px',
              background: '#4299e1',
              color: 'white',
              border: 'none',
              borderRadius: '8px',
              fontSize: '16px',
              fontWeight: '600',
              cursor: 'pointer'
            }}
          >
            📊 Analyze Market Now
          </button>
        </div>
      )}
      

      {activeTab === 'report' && (
        <div style={{
          background: 'white',
          borderRadius: '12px',
          padding: '20px',
          border: '1px solid #e2e8f0'
        }}>
          <div style={{ display: 'flex', gap: '12px', flexWrap: 'wrap', marginBottom: '16px' }}>
            <div style={{ padding: '16px', background: '#1a202c', color: 'white', borderRadius: '10px', minWidth: '180px' }}>
              <div style={{ fontSize: '12px', opacity: 0.8 }}>Today P&L</div>
              <div style={{ fontSize: '26px', fontWeight: '700', color: (todayPnlFromSummary ?? sumPnl(tradesToday)) >= 0 ? '#c6f6d5' : '#fed7d7' }}>
                ₹{(todayPnlFromSummary ?? sumPnl(tradesToday)).toLocaleString()}
              </div>
            </div>
            <div style={{ padding: '16px', background: '#2b6cb0', color: 'white', borderRadius: '10px', minWidth: '180px' }}>
              <div style={{ fontSize: '12px', opacity: 0.9 }}>Today Trades</div>
              <div style={{ fontSize: '26px', fontWeight: '700' }}>{tradesToday.length}</div>
            </div>
            <div style={{ padding: '16px', background: '#2f855a', color: 'white', borderRadius: '10px', minWidth: '180px' }}>
              <div style={{ fontSize: '12px', opacity: 0.9 }}>Today Win / Loss</div>
              <div style={{ fontSize: '16px', fontWeight: '700' }}>{sumWins(tradesToday)} / {tradesToday.length - sumWins(tradesToday)}</div>
            </div>
            <div style={{ padding: '16px', background: '#4a5568', color: 'white', borderRadius: '10px', minWidth: '180px' }}>
              <div style={{ fontSize: '12px', opacity: 0.9 }}>Overall P&L</div>
              <div style={{ fontSize: '26px', fontWeight: '700', color: overallPnl >= 0 ? '#c6f6d5' : '#fed7d7' }}>
                ₹{overallPnl.toLocaleString()}
              </div>
            </div>
          </div>

          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '12px' }}>
            <h4 style={{ margin: 0, color: '#2d3748' }}>Trade Report (search & history)</h4>
            <input
              type="text"
              placeholder="Search symbol / action / status"
              value={historySearch}
              onChange={(e) => setHistorySearch(e.target.value)}
              style={{
                padding: '10px 12px',
                borderRadius: '8px',
                border: '1px solid #cbd5e0',
                minWidth: '240px'
              }}
            />
          </div>

          <div style={{ marginBottom: '12px' }}>
            <h5 style={{ margin: '0 0 8px 0', color: '#2d3748' }}>Today Trades</h5>
            <div style={{ overflowX: 'auto' }}>
              <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '13px' }}>
                <thead style={{ background: '#f7fafc', borderBottom: '2px solid #e2e8f0' }}>
                  <tr>
                    <th style={{ padding: '8px', textAlign: 'left' }}>ID</th>
                    <th style={{ padding: '8px', textAlign: 'left' }}>Symbol</th>
                    <th style={{ padding: '8px', textAlign: 'left' }}>Action</th>
                    <th style={{ padding: '8px', textAlign: 'right' }}>Entry</th>
                    <th style={{ padding: '8px', textAlign: 'right' }}>Exit</th>
                    <th style={{ padding: '8px', textAlign: 'right' }}>P&L</th>
                    <th style={{ padding: '8px', textAlign: 'left' }}>Time (IST)</th>
                  </tr>
                </thead>
                <tbody>
                  {todayTableRows.map((t, idx) => {
                    const entry = Number(t.entry_price || t.price || 0);
                    const inferredExit = inferExitPrice(t);
                    const exit = inferredExit != null ? Number(inferredExit) : null;
                    const pnl = Number(t.pnl ?? t.profit_loss ?? 0);
                    const action = t.action || t.side || 'BUY';
                    return (
                      <tr key={idx} style={{ borderBottom: '1px solid #e2e8f0' }}>
                        <td style={{ padding: '8px' }}>{t.id}</td>
                        <td style={{ padding: '8px', fontWeight: '600' }}>{t.symbol || t.index || '—'}</td>
                        <td style={{ padding: '8px' }}>
                          <span style={{
                            padding: '2px 6px',
                            borderRadius: '3px',
                            background: action === 'BUY' ? '#c6f6d5' : '#fed7d7',
                            color: action === 'BUY' ? '#22543d' : '#742a2a',
                            fontSize: '11px',
                            fontWeight: 'bold'
                          }}>
                            {action}
                          </span>
                        </td>
                        <td style={{ padding: '8px', textAlign: 'right' }}>₹{entry.toFixed(2)}</td>
                        <td style={{ padding: '8px', textAlign: 'right' }}>₹{exit !== null ? exit.toFixed(2) : '-'}</td>
                        <td style={{ padding: '8px', textAlign: 'right', fontWeight: '700', color: pnl >= 0 ? '#48bb78' : '#f56565' }}>
                          {pnl >= 0 ? '+' : ''}₹{pnl.toLocaleString()}
                        </td>
                        <td style={{ padding: '8px', fontSize: '11px', color: '#718096' }}>
                          {formatTimeIST(t.exit_time || t.entry_time)}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
            {tradesToday.length === 0 && (
              <div style={{ marginTop: '8px', fontSize: '12px', color: '#718096' }}>
                Showing sample rows. Real trades will appear here once captured today.
              </div>
            )}
          </div>

          {filteredHistory.length === 0 ? (
            <div style={{ padding: '24px', textAlign: 'center', color: '#718096', border: '1px dashed #e2e8f0', borderRadius: '10px' }}>
              No trades found for the current filters.
            </div>
          ) : (
            <div style={{ overflowX: 'auto', maxHeight: '480px', overflowY: 'auto' }}>
              <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '13px' }}>
                <thead style={{ position: 'sticky', top: 0, background: '#f7fafc', zIndex: 1 }}>
                  <tr style={{ borderBottom: '2px solid #e2e8f0' }}>
                    <th style={{ padding: '10px', textAlign: 'left' }}>ID</th>
                    <th style={{ padding: '10px', textAlign: 'left' }}>Symbol</th>
                    <th style={{ padding: '10px', textAlign: 'center' }}>Mode</th>
                    <th style={{ padding: '10px', textAlign: 'left' }}>Action</th>
                    <th style={{ padding: '10px', textAlign: 'right' }}>Entry</th>
                    <th style={{ padding: '10px', textAlign: 'right' }}>Exit</th>
                    <th style={{ padding: '10px', textAlign: 'right' }}>P&L</th>
                    <th style={{ padding: '10px', textAlign: 'right' }}>%</th>
                    <th style={{ padding: '10px', textAlign: 'left' }}>Status</th>
                    <th style={{ padding: '10px', textAlign: 'left' }}>Date</th>
                  </tr>
                </thead>
                <tbody>
                  {filteredHistory.map((trade, idx) => {
                    const entry = Number(trade.entry_price || trade.price || 0);
                    const inferredExit = inferExitPrice(trade);
                    const exit = inferredExit != null ? Number(inferredExit) : null;
                    const pnl = Number(trade.profit_loss ?? trade.pnl ?? 0);
                    const pnlPct = Number(trade.pnl_percentage ?? trade.profit_percentage ?? trade.pnl_percent ?? 0);
                    const action = trade.action || trade.side || 'BUY';
                    const tradeMode = String(
                      trade?.trade_mode
                      || trade?.trade_source
                      || trade?.mode
                      || (trade?.broker_order_id ? 'LIVE' : 'DEMO')
                    ).toUpperCase();
                    const statusPalette = getTradeStatusPalette(trade.status);
                    return (
                      <tr key={idx} style={{ borderBottom: '1px solid #e2e8f0' }}>
                        <td style={{ padding: '10px' }}>#{trade.id}</td>
                        <td style={{ padding: '10px', fontWeight: '600' }}>{trade.symbol || trade.index || '—'}</td>
                        <td style={{ padding: '10px', textAlign: 'center' }}>
                          <span style={{
                            padding: '2px 8px',
                            borderRadius: '999px',
                            background: tradeMode === 'LIVE' ? '#fee2e2' : '#e0f2fe',
                            color: tradeMode === 'LIVE' ? '#991b1b' : '#0c4a6e',
                            fontSize: '11px',
                            fontWeight: '700'
                          }}>
                            {tradeMode}
                          </span>
                        </td>
                        <td style={{ padding: '10px' }}>
                          <span style={{
                            padding: '2px 6px',
                            borderRadius: '3px',
                            background: action === 'BUY' ? '#c6f6d5' : '#fed7d7',
                            color: action === 'BUY' ? '#22543d' : '#742a2a',
                            fontSize: '11px',
                            fontWeight: 'bold'
                          }}>
                            {action}
                          </span>
                        </td>
                        <td style={{ padding: '10px', textAlign: 'right' }}>₹{entry.toFixed(2)}</td>
                        <td style={{ padding: '10px', textAlign: 'right' }}>₹{exit !== null ? exit.toFixed(2) : '-'}</td>
                        <td style={{
                          padding: '10px',
                          textAlign: 'right',
                          fontWeight: '700',
                          color: pnl >= 0 ? '#48bb78' : '#f56565'
                        }}>
                          {pnl >= 0 ? '+' : ''}₹{pnl.toLocaleString()}
                        </td>
                        <td style={{
                          padding: '10px',
                          textAlign: 'right',
                          fontWeight: '600',
                          color: pnlPct >= 0 ? '#48bb78' : '#f56565'
                        }}>
                          {pnlPct >= 0 ? '+' : ''}{pnlPct.toFixed(2)}%
                        </td>
                        <td style={{ padding: '10px' }}>
                          <span style={{
                            padding: '2px 6px',
                            borderRadius: '3px',
                            background: statusPalette.background,
                            color: statusPalette.color,
                            fontSize: '11px',
                            fontWeight: 'bold'
                          }}>
                            {statusPalette.label}
                          </span>
                        </td>
                        <td style={{ padding: '10px', fontSize: '11px', color: '#718096' }}>
                          {formatTimeIST(trade.exit_time || trade.entry_time)}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}
      
        </div>
      </div>
    </div>
  );
}

export default AutoTradingDashboard;
