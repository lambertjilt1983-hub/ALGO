import { describe, expect, it } from 'vitest';

import {
  ACTIVE_TRADE_PROBE_INTERVAL_MS,
  shouldFetchCurrentModeActive,
} from './activeTradeFetchPolicy';

describe('active trade fetch policy', () => {
  it('always fetches when force refresh is requested', () => {
    expect(shouldFetchCurrentModeActive({ forceRefresh: true })).toBe(true);
  });

  it('always fetches when there is already an open trade', () => {
    expect(shouldFetchCurrentModeActive({ hasOpenTradeForCurrentMode: true })).toBe(true);
  });

  it('always fetches while auto trading is active to avoid delayed row visibility', () => {
    expect(
      shouldFetchCurrentModeActive({
        autoTradingActive: true,
        nowMs: 50_000,
        lastProbeAt: 49_900,
      }),
    ).toBe(true);
  });

  it('uses probe interval when no force/open/active signal exists', () => {
    expect(
      shouldFetchCurrentModeActive({
        autoTradingActive: false,
        hasOpenTradeForCurrentMode: false,
        forceRefresh: false,
        nowMs: 30_000,
        lastProbeAt: 26_000,
      }),
    ).toBe(false);

    expect(
      shouldFetchCurrentModeActive({
        autoTradingActive: false,
        hasOpenTradeForCurrentMode: false,
        forceRefresh: false,
        nowMs: 31_000,
        lastProbeAt: 26_000,
      }),
    ).toBe(true);
  });

  it('exports 5-second default probe interval', () => {
    expect(ACTIVE_TRADE_PROBE_INTERVAL_MS).toBe(5000);
  });
});
