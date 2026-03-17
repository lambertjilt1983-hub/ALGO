export const ACTIVE_HISTORY_REFRESH_INTERVAL_MS = 1000;
export const DEFAULT_TABLE_VISIBILITY = Object.freeze({
  showActiveTradesTable: true,
  showTradeHistoryTable: true,
});

export const getTradeRowKey = (trade) => {
  if (!trade || typeof trade !== 'object') return 'unknown';
  const symbol = String(trade.symbol || '');
  const side = String(trade.side || trade.action || 'BUY');
  const entry = Number(trade.entry_price ?? trade.price ?? 0).toFixed(2);
  const ts = String(trade.entry_time || trade.timestamp || '');
  const id = String(trade.id ?? '');
  return `${symbol}|${side}|${entry}|${ts}|${id}`;
};

export const getHistoryRowKey = (trade) => {
  if (!trade || typeof trade !== 'object') return 'unknown';
  const symbol = String(trade.symbol || trade.index || '');
  const side = String(trade.side || trade.action || 'BUY');
  const entry = Number(trade.entry_price ?? trade.price ?? 0).toFixed(2);
  const exit = Number(trade.exit_price ?? 0).toFixed(2);
  const exitTime = String(trade.exit_time || trade.timestamp || '');
  const status = String(trade.status || 'CLOSED');
  return `${symbol}|${side}|${entry}|${exit}|${exitTime}|${status}`;
};

export const getHistoryDisplayKey = (trade, idx) => {
  if (!trade || typeof trade !== 'object') return `hist-${idx}`;
  const symbol = String(trade.symbol || trade.index || '');
  const side = String(trade.side || trade.action || 'BUY');
  const entry = Number(trade.entry_price ?? trade.price ?? 0).toFixed(2);
  const exitTime = String(trade.exit_time || trade.timestamp || '');
  const status = String(trade.status || 'CLOSED');
  return `${symbol}|${side}|${entry}|${exitTime}|${status}|${idx}`;
};

export const resolveStableActiveTrades = ({
  incomingTrades,
  prevTrades,
  hasLoaded,
  emptyPolls,
  canTrustEmpty = true,
  emptyPollsToClear = 2,
}) => {
  const incoming = Array.isArray(incomingTrades) ? incomingTrades : [];
  const prev = Array.isArray(prevTrades) ? prevTrades : [];

  if (incoming.length === 0) {
    if (!hasLoaded) {
      return { trades: [], hasLoaded: false, emptyPolls };
    }
    if (!canTrustEmpty) {
      return { trades: prev, hasLoaded: true, emptyPolls };
    }
    const nextEmpty = (Number(emptyPolls) || 0) + 1;
    if (nextEmpty >= emptyPollsToClear) {
      return { trades: [], hasLoaded: true, emptyPolls: nextEmpty };
    }
    return { trades: prev, hasLoaded: true, emptyPolls: nextEmpty };
  }

  const prevByKey = new Map(prev.map((t) => [getTradeRowKey(t), t]));
  const merged = incoming.map((t) => {
    const key = getTradeRowKey(t);
    const oldRow = prevByKey.get(key);
    return oldRow ? { ...oldRow, ...t } : t;
  });

  return { trades: merged, hasLoaded: true, emptyPolls: 0 };
};

export const resolveStableTradeHistory = ({
  incomingHistory,
  prevHistory,
  hasLoaded,
  emptyPolls,
}) => {
  const incoming = Array.isArray(incomingHistory) ? incomingHistory : [];
  const prev = Array.isArray(prevHistory) ? prevHistory : [];

  if (incoming.length === 0) {
    if (!hasLoaded) {
      return { trades: [], hasLoaded: false, emptyPolls };
    }
    return { trades: prev, hasLoaded: true, emptyPolls: (Number(emptyPolls) || 0) + 1 };
  }

  const prevByKey = new Map(prev.map((t) => [getHistoryRowKey(t), t]));
  const merged = incoming.map((t) => {
    const key = getHistoryRowKey(t);
    const oldRow = prevByKey.get(key);
    return oldRow ? { ...oldRow, ...t } : t;
  });

  return { trades: merged, hasLoaded: true, emptyPolls: 0 };
};
