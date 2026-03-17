import { describe, expect, it } from 'vitest';

import {
  ACTIVE_HISTORY_REFRESH_INTERVAL_MS,
  DEFAULT_TABLE_VISIBILITY,
  getTradeRowKey,
  resolveStableActiveTrades,
  resolveStableTradeHistory,
} from './tradeTableState';

const t = (id, currentPrice = 100) => ({
  id,
  symbol: `SYM${id}`,
  side: 'BUY',
  entry_price: 100,
  current_price: currentPrice,
  quantity: 1,
  entry_time: '2026-03-07T10:00:00',
  status: 'OPEN',
});

describe('trade table defaults', () => {
  it('keeps both active and history tables visible by default', () => {
    expect(DEFAULT_TABLE_VISIBILITY.showActiveTradesTable).toBe(true);
    expect(DEFAULT_TABLE_VISIBILITY.showTradeHistoryTable).toBe(true);
  });

  it('uses 1-second refresh interval for trade updates', () => {
    expect(ACTIVE_HISTORY_REFRESH_INTERVAL_MS).toBe(1000);
  });
});

describe('resolveStableActiveTrades', () => {
  it('keeps previous rows on first trusted empty poll to avoid flicker', () => {
    const prev = [t(1, 101), t(2, 202)];
    const stable = resolveStableActiveTrades({
      incomingTrades: [],
      prevTrades: prev,
      hasLoaded: true,
      emptyPolls: 0,
      canTrustEmpty: true,
      emptyPollsToClear: 2,
    });

    expect(stable.trades).toEqual(prev);
    expect(stable.emptyPolls).toBe(1);
  });

  it('clears only after consecutive confirmed empty polls', () => {
    const prev = [t(1, 101)];
    const stable = resolveStableActiveTrades({
      incomingTrades: [],
      prevTrades: prev,
      hasLoaded: true,
      emptyPolls: 1,
      canTrustEmpty: true,
      emptyPollsToClear: 2,
    });

    expect(stable.trades).toEqual([]);
    expect(stable.emptyPolls).toBe(2);
  });

  it('updates prices for multiple trades in one cycle without dropping rows', () => {
    const prev = [t(1, 101), t(2, 201), t(3, 301)];
    const incoming = [t(1, 102), t(2, 203), t(3, 305)];

    const stable = resolveStableActiveTrades({
      incomingTrades: incoming,
      prevTrades: prev,
      hasLoaded: true,
      emptyPolls: 0,
      canTrustEmpty: true,
      emptyPollsToClear: 2,
    });

    expect(stable.trades).toHaveLength(3);
    expect(stable.trades.map((x) => x.current_price)).toEqual([102, 203, 305]);
    expect(stable.trades.map((x) => getTradeRowKey(x))).toEqual(incoming.map((x) => getTradeRowKey(x)));
  });

  it('keeps previous rows when empty result is not trustworthy', () => {
    const prev = [t(1, 101), t(2, 202)];
    const stable = resolveStableActiveTrades({
      incomingTrades: [],
      prevTrades: prev,
      hasLoaded: true,
      emptyPolls: 0,
      canTrustEmpty: false,
      emptyPollsToClear: 2,
    });

    expect(stable.trades).toEqual(prev);
  });
});

describe('resolveStableTradeHistory', () => {
  it('keeps previous history rows when incoming is empty to avoid flicker', () => {
    const prev = [{ id: 9, symbol: 'SYM9', side: 'BUY', entry_price: 100, exit_price: 102, exit_time: '2026-03-07T10:01:00', status: 'CLOSED' }];

    const stable = resolveStableTradeHistory({
      incomingHistory: [],
      prevHistory: prev,
      hasLoaded: true,
      emptyPolls: 0,
    });

    expect(stable.trades).toEqual(prev);
    expect(stable.emptyPolls).toBe(1);
  });
});
