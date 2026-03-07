import { describe, expect, it } from 'vitest';

import { extractLiveBalance } from './liveBalance';

describe('extractLiveBalance', () => {
  it('extracts top-level available_balance', () => {
    const payload = {
      status: 'success',
      available_balance: 15342.55,
      total_balance: 20000,
    };

    expect(extractLiveBalance(payload)).toBe(15342.55);
  });

  it('extracts nested live_balance from broker payloads', () => {
    const payload = {
      equity: {
        available: {
          live_balance: 7421.2,
        },
      },
    };

    expect(extractLiveBalance(payload)).toBe(7421.2);
  });

  it('treats zero available_balance as synced value', () => {
    const payload = {
      status: 'success',
      available_balance: 0,
      message: 'insufficient funds',
    };

    expect(extractLiveBalance(payload)).toBe(0);
  });

  it('returns null when no numeric balance fields exist', () => {
    const payload = {
      status: 'error',
      message: 'Broker unavailable',
    };

    expect(extractLiveBalance(payload)).toBeNull();
  });
});
