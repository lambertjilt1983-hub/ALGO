export const ACTIVE_TRADE_PROBE_INTERVAL_MS = 5000;

export const shouldFetchCurrentModeActive = ({
  forceRefresh = false,
  hasOpenTradeForCurrentMode = false,
  autoTradingActive = false,
  nowMs = Date.now(),
  lastProbeAt = 0,
  probeIntervalMs = ACTIVE_TRADE_PROBE_INTERVAL_MS,
} = {}) => {
  if (forceRefresh) return true;
  if (hasOpenTradeForCurrentMode) return true;
  if (autoTradingActive) return true;
  return (Number(nowMs) - Number(lastProbeAt || 0)) >= Number(probeIntervalMs || ACTIVE_TRADE_PROBE_INTERVAL_MS);
};
